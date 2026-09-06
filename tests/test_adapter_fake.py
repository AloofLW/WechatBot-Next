from pathlib import Path

import pytest

from wechatbot.adapters.wechat import (
    AdapterCapability,
    CapabilityNotSupportedError,
    ChatKind,
    FakeWeChatAdapter,
    InboundMessage,
)


def test_fake_adapter_delivers_normalized_group_message() -> None:
    received = []
    adapter = FakeWeChatAdapter()
    adapter.start(received.append)

    message = InboundMessage(
        conversation_id='group-1',
        sender_id='member-1',
        content='hello',
        kind=ChatKind.GROUP,
    )
    adapter.emit(message)

    assert received == [message]


def test_fake_adapter_records_supported_outbound_actions() -> None:
    adapter = FakeWeChatAdapter()

    adapter.send_text('friend-1', 'reply')
    adapter.send_file('friend-1', Path('emoji.gif'))

    assert [action.capability for action in adapter.actions] == [
        AdapterCapability.SEND_TEXT,
        AdapterCapability.SEND_FILE,
    ]
    assert adapter.actions[0].content == 'reply'
    assert adapter.actions[1].file_path == Path('emoji.gif')


def test_fake_adapter_rejects_unsupported_capability_explicitly() -> None:
    adapter = FakeWeChatAdapter()

    with pytest.raises(CapabilityNotSupportedError, match='voice_call'):
        adapter.voice_call('friend-1')


def test_fake_adapter_provides_group_and_media_data_without_platform_dependencies() -> None:
    adapter = FakeWeChatAdapter()
    message = InboundMessage(
        message_id='image-1',
        conversation_id='group-1',
        sender_id='member-1',
        content='',
        kind=ChatKind.GROUP,
        attachment_path=Path('received.png'),
    )
    adapter.start(lambda _: None)
    adapter.emit(message)

    assert adapter.is_group_chat('group-1') is True
    assert adapter.download_media('image-1') == Path('received.png')
    assert adapter.capture_media('image-1') == Path('received.png')


def test_fake_adapter_can_model_supported_special_capability() -> None:
    adapter = FakeWeChatAdapter(
        frozenset({AdapterCapability.RECALL_OUTBOUND})
    )

    adapter.recall_last_outbound('friend-1')

    assert adapter.actions[0].capability is AdapterCapability.RECALL_OUTBOUND
