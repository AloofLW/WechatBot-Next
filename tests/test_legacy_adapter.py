import importlib
import sys
from types import SimpleNamespace

import pytest

from wechatbot.adapters.wechat import (
    AdapterCapability,
    CapabilityNotSupportedError,
    ChatKind,
    LegacyWeChatAdapter,
    LegacyWeChatDependencyError,
)


class RawClient:
    def __init__(self) -> None:
        self.nickname = 'bot-name'
        self.listen = {}
        self.sent = []
        self.shown = 0
        self.keep_running_calls = 0

    def Show(self) -> None:
        self.shown += 1

    def AddListenChat(self, nickname, callback):
        self.listen[nickname] = callback
        return nickname

    def KeepRunning(self) -> None:
        self.keep_running_calls += 1

    def SendMsg(self, msg, who):
        self.sent.append(('text', msg, who))
        return True

    def SendFiles(self, filepath, who):
        self.sent.append(('file', filepath, who))
        return True


class CountingClient(RawClient):
    instances = 0

    def __init__(self) -> None:
        type(self).instances += 1
        super().__init__()


def importer_for(modules):
    def importer(name):
        if name in modules:
            return modules[name]
        raise ImportError(f'{name} unavailable')

    return importer


def test_importing_legacy_does_not_load_windows_automation_modules() -> None:
    importlib.import_module('wechatbot.adapters.wechat.legacy')

    assert {'wxauto', 'wxautox', 'wxautox_wechatbot'}.isdisjoint(sys.modules)


def test_missing_legacy_dependencies_fail_only_when_initialized() -> None:
    adapter = LegacyWeChatAdapter(importer=importer_for({}))

    assert adapter.provider is None
    with pytest.raises(LegacyWeChatDependencyError, match='Tried: wxautox_wechatbot, wxautox, wxauto'):
        adapter.initialize()


def test_dynamic_import_prefers_wxautox_wechatbot_and_configures_params(monkeypatch) -> None:
    wx_param = SimpleNamespace(ENABLE_FILE_LOGGER=True, FORCE_MESSAGE_XBIAS=False)
    modules = {
        'wxautox_wechatbot': SimpleNamespace(WeChat=RawClient),
        'wxautox_wechatbot.param': SimpleNamespace(WxParam=wx_param),
        'wxautox': SimpleNamespace(WeChat=lambda: (_ for _ in ()).throw(AssertionError())),
    }
    monkeypatch.delenv('PROJECT_NAME', raising=False)
    adapter = LegacyWeChatAdapter(importer=importer_for(modules))

    adapter.initialize()

    assert adapter.provider == 'wxautox_wechatbot'
    assert wx_param.ENABLE_FILE_LOGGER is False
    assert wx_param.FORCE_MESSAGE_XBIAS is True


def test_dynamic_import_falls_back_in_declared_order() -> None:
    adapter = LegacyWeChatAdapter(
        importer=importer_for({'wxautox': SimpleNamespace(WeChat=RawClient)})
    )

    adapter.initialize()

    assert adapter.provider == 'wxautox'


def test_dynamic_import_reaches_wxauto_after_enhanced_providers_are_missing() -> None:
    adapter = LegacyWeChatAdapter(
        importer=importer_for({'wxauto': SimpleNamespace(WeChat=RawClient)})
    )

    adapter.initialize()

    assert adapter.provider == 'wxauto'


def test_initialize_creates_one_client_instance_and_listener_bridge_maps() -> None:
    CountingClient.instances = 0
    adapter = LegacyWeChatAdapter(
        importer=importer_for({'wxauto': SimpleNamespace(WeChat=CountingClient)})
    )
    callback_calls = []

    adapter.initialize()
    adapter.initialize()
    result = adapter.add_legacy_listener('friend', lambda message, chat: callback_calls.append((message, chat)))

    assert CountingClient.instances == 1
    assert result == 'friend'
    assert 'friend' in adapter.listening_conversations()
    assert callback_calls == []


def test_send_operations_map_to_legacy_client_methods() -> None:
    adapter = LegacyWeChatAdapter(
        importer=importer_for({'wxauto': SimpleNamespace(WeChat=RawClient)})
    )
    adapter.initialize()

    assert adapter.send_text('friend', 'hello') is True
    assert adapter.send_file('friend', 'emoji.gif') is True

    assert adapter.raw_client.sent == [
        ('text', 'hello', 'friend'),
        ('file', 'emoji.gif', 'friend'),
    ]


def test_raw_message_is_normalized_without_exposing_raw_object() -> None:
    raw_message = SimpleNamespace(
        content='quoted message',
        sender='member',
        type='quote',
        attr='friend',
        quote_content='original text',
    )
    raw_chat = SimpleNamespace(who='group', ChatInfo=lambda: {'chat_type': 'group'})
    adapter = LegacyWeChatAdapter()

    message = adapter.normalize_message(raw_message, raw_chat)

    assert message.conversation_id == 'group'
    assert message.sender_id == 'member'
    assert message.kind is ChatKind.GROUP
    assert message.metadata['quote_content'] == 'original text'
    assert 'raw_message' not in message.metadata


def test_unsupported_capability_is_explicit() -> None:
    adapter = LegacyWeChatAdapter(
        importer=importer_for({'wxauto': SimpleNamespace(WeChat=RawClient)})
    )
    adapter.initialize()

    with pytest.raises(CapabilityNotSupportedError, match='voice_call'):
        adapter.voice_call('friend')

    assert AdapterCapability.VOICE_CALL not in adapter.capabilities
