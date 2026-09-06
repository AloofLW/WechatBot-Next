import importlib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from wechatbot.adapters.wechat import (
    AdapterCapability,
    ChatKind,
    MessageType,
    ModernWeChatAdapter,
    ModernWeChatDependencyError,
    ModernWeChatPlatformError,
)


class FakeDatabase:
    instances = 0

    def __init__(self) -> None:
        type(self).instances += 1

    def get_self_info(self):
        return {'nick_name': 'modern-bot'}


class FakeListener:
    latest = None

    def __init__(self, database, interval):
        type(self).latest = self
        self.database = database
        self.interval = interval
        self.callbacks = {}
        self.start_calls = 0
        self.stop_calls = 0

    def add_listener(self, conversation_id, callback):
        self.callbacks[conversation_id] = callback

    def start(self):
        self.start_calls += 1

    def stop(self):
        self.stop_calls += 1


def backend(sent=None):
    sent = [] if sent is None else sent

    def quick_send(text, who, verify):
        sent.append((text, who, verify))
        return True

    return SimpleNamespace(WeChatDB=FakeDatabase, Listener=FakeListener, quick_send=quick_send)


def importer_for(modules):
    def importer(name):
        if name in modules:
            return modules[name]
        raise ImportError(f'{name} unavailable')

    return importer


def test_importing_modern_does_not_load_candidate_backend() -> None:
    importlib.import_module('wechatbot.adapters.wechat.modern')

    assert 'wechatauto' not in sys.modules


def test_windows_modern_poc_is_safe_to_execute_on_macos() -> None:
    result = subprocess.run(
        [sys.executable, str(Path('tools/windows_modern_wechat_poc.py'))],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert '[NOT_TESTED] Modern adapter PoC only initializes a client on Windows.' in result.stdout


def test_macos_initialization_fails_before_any_windows_backend_import() -> None:
    called = []
    adapter = ModernWeChatAdapter(importer=lambda name: called.append(name), platform_name=lambda: 'posix')

    with pytest.raises(ModernWeChatPlatformError, match='Windows-only'):
        adapter.initialize()

    assert called == []


def test_missing_backend_is_a_clear_windows_time_error() -> None:
    adapter = ModernWeChatAdapter(importer=importer_for({}), platform_name=lambda: 'nt')

    with pytest.raises(ModernWeChatDependencyError, match='wechatauto-replica'):
        adapter.initialize()


def test_initialize_nickname_and_capabilities_are_backend_owned() -> None:
    FakeDatabase.instances = 0
    adapter = ModernWeChatAdapter(
        importer=importer_for({'wechatauto': backend()}), platform_name=lambda: 'nt'
    )

    adapter.initialize()
    adapter.initialize()

    assert FakeDatabase.instances == 1
    assert adapter.initialization_count == 1
    assert adapter.nickname == 'modern-bot'
    assert adapter.capabilities == frozenset({
        AdapterCapability.RECEIVE,
        AdapterCapability.LISTEN,
        AdapterCapability.SEND_TEXT,
    })


def test_normalize_current_backend_messages_preserves_session_sender_group_and_unknown() -> None:
    adapter = ModernWeChatAdapter()
    group_message = adapter.normalize_message(
        {
            'username': 'room@chatroom',
            'sender_id': 'member-id',
            'content': 'hello',
            'type': 'text',
            'local_id': 42,
            'attr': 'self',
        }
    )
    unknown = adapter.normalize_message({'content': 'new payload', 'type': 'future'}, 'friend-id')

    assert group_message.conversation_id == 'room@chatroom'
    assert group_message.sender_id == 'member-id'
    assert group_message.kind is ChatKind.GROUP
    assert group_message.message_type is MessageType.TEXT
    assert group_message.is_self is True
    assert group_message.message_id == 'modern:room@chatroom:42'
    assert unknown.conversation_id == 'friend-id'
    assert unknown.message_type is MessageType.UNKNOWN


def test_listener_callback_is_normalized_isolated_and_starts_once() -> None:
    module = backend()
    adapter = ModernWeChatAdapter(importer=importer_for({'wechatauto': module}), platform_name=lambda: 'nt')
    received = []
    adapter.start(received.append)
    adapter.listen('friend-id')
    adapter.listen('group@chatroom')

    callback = FakeListener.latest.callbacks['friend-id']
    callback({'content': 'first', 'type': 'text', 'sender_id': 'friend-id'}, FakeListener.latest)
    adapter.start(lambda _: (_ for _ in ()).throw(ValueError('bad callback')))
    callback({'content': 'bad', 'type': 'text'}, FakeListener.latest)

    assert [message.content for message in received] == ['first']
    assert FakeListener.latest.start_calls == 1
    assert [str(error) for error in adapter.callback_errors] == ['bad callback']
    assert adapter.is_started is True
    adapter.stop()
    assert FakeListener.latest.stop_calls == 1
    assert adapter.is_started is False


def test_send_text_maps_to_quick_send() -> None:
    sent = []
    adapter = ModernWeChatAdapter(
        importer=importer_for({'wechatauto': backend(sent)}), platform_name=lambda: 'nt'
    )

    assert adapter.send_text('friend-id', 'hello') is True
    assert sent == [('hello', 'friend-id', True)]
