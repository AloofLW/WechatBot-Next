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
    MessageType,
)


class RawClient:
    latest = None

    def __init__(self) -> None:
        RawClient.latest = self
        self.nickname = 'bot-name'
        self.listen = {}
        self.sent = []
        self.shown = 0
        self.keep_running_calls = 0
        self.voice_calls = []
        self.windows = []

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

    def VoiceCall(self, who):
        self.voice_calls.append(who)

    def GetAllSubWindow(self):
        return self.windows


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


def test_initialize_creates_one_client_instance_and_normalized_listener_registers() -> None:
    CountingClient.instances = 0
    adapter = LegacyWeChatAdapter(
        importer=importer_for({'wxauto': SimpleNamespace(WeChat=CountingClient)})
    )
    callback_calls = []

    adapter.initialize()
    adapter.initialize()
    adapter.start(callback_calls.append)
    result = adapter.listen('friend')

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

    assert RawClient.latest.sent == [
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
    assert message.quote_content == 'original text'
    assert message.message_type is MessageType.QUOTE
    assert message.message_id
    assert 'raw_message' not in message.metadata


def test_unsupported_capability_is_explicit() -> None:
    adapter = LegacyWeChatAdapter(
        importer=importer_for({'wxauto': SimpleNamespace(WeChat=RawClient)})
    )
    adapter.initialize()

    with pytest.raises(CapabilityNotSupportedError, match='tap_inbound'):
        adapter.tap_last_inbound('missing-handle')


def test_callback_normalizes_text_group_and_unknown_messages() -> None:
    adapter = LegacyWeChatAdapter(
        importer=importer_for({'wxauto': SimpleNamespace(WeChat=RawClient)})
    )
    received = []
    adapter.start(received.append)
    adapter.listen('group')
    callback = RawClient.latest.listen['group']
    group_chat = SimpleNamespace(who='group', ChatInfo=lambda: {'chat_type': 'group'})

    callback(SimpleNamespace(content='hello', sender='member', type='text', attr='friend'), group_chat)
    callback(SimpleNamespace(content='future', sender='member', type='future_type', attr='friend'), group_chat)

    assert [message.message_type for message in received] == [MessageType.TEXT, MessageType.UNKNOWN]
    assert all(message.kind is ChatKind.GROUP for message in received)


def test_link_url_and_message_handle_media_operations_are_adapter_owned() -> None:
    link_message = SimpleNamespace(
        content='card',
        sender='friend',
        type='link',
        attr='friend',
        get_url=lambda: 'https://example.test/card',
    )
    adapter = LegacyWeChatAdapter()
    message = adapter.normalize_message(link_message, SimpleNamespace(who='friend', ChatInfo=lambda: {}))
    image_message = adapter.normalize_message(
        SimpleNamespace(
            content='', sender='friend', type='image', attr='friend', download=lambda: 'received.png'
        ),
        SimpleNamespace(who='friend', ChatInfo=lambda: {}),
    )
    emoji_message = adapter.normalize_message(
        SimpleNamespace(
            content='', sender='friend', type='emotion', attr='friend', capture=lambda: 'emoji.png'
        ),
        SimpleNamespace(who='friend', ChatInfo=lambda: {}),
    )

    assert message.url == 'https://example.test/card'
    assert adapter.extract_url(message.message_id) == 'https://example.test/card'
    assert image_message.message_type is MessageType.IMAGE
    assert emoji_message.message_type is MessageType.EMOJI
    assert str(adapter.download_media(image_message.message_id)) == 'received.png'
    assert str(adapter.capture_media(emoji_message.message_id)) == 'emoji.png'


def test_merged_messages_are_normalized_with_a_safe_fallback() -> None:
    adapter = LegacyWeChatAdapter()
    chat = SimpleNamespace(who='friend', ChatInfo=lambda: {})
    merged = adapter.normalize_message(
        SimpleNamespace(
            content='',
            sender='friend',
            type='merge',
            attr='friend',
            get_messages=lambda: [['member', 'hello', '10:00']],
        ),
        chat,
    )
    fallback = adapter.normalize_message(
        SimpleNamespace(
            content='', sender='friend', type='merge', attr='friend', get_messages=lambda: 'unavailable'
        ),
        chat,
    )

    assert merged.forwarded_messages[0].sender_id == 'member'
    assert merged.forwarded_messages[0].timestamp == '10:00'
    assert fallback.forwarded_fallback == 'unavailable'


def test_tap_recall_voice_and_group_lookup_use_adapter_capabilities() -> None:
    class RawActionMessage:
        def __init__(self):
            self.actions = []

        def tickle(self):
            self.actions.append('tickle')

        def select_option(self, value):
            self.actions.append(value)

    adapter = LegacyWeChatAdapter(
        importer=importer_for({'wxauto': SimpleNamespace(WeChat=RawClient)})
    )
    adapter.initialize()
    raw_message = RawActionMessage()
    message = adapter.normalize_message(
        raw_message, SimpleNamespace(who='friend', ChatInfo=lambda: {})
    )

    adapter.tap_last_inbound(message.message_id)
    adapter.tap_last_outbound(message.message_id)
    adapter.recall_last_outbound(message.message_id)
    adapter.voice_call('friend')
    RawClient.latest.windows = [
        SimpleNamespace(who='group', ChatInfo=lambda: {'chat_type': 'group'}),
        SimpleNamespace(who='friend', ChatInfo=lambda: {'chat_type': 'private'}),
    ]

    assert raw_message.actions == ['tickle', 'tickle', '撤回']
    assert RawClient.latest.voice_calls == ['friend']
    assert adapter.is_group_chat('group') is True
    assert adapter.is_group_chat('friend') is False
    assert adapter.is_group_chat('missing') is None
    assert AdapterCapability.VOICE_CALL in adapter.capabilities
