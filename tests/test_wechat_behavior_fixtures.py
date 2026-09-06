"""Client-free fixtures for behavior the current bot expects from adapters.

These tests deliberately exercise normalized messages and adapter actions, not
``bot.py`` imports: the latter requires a local runtime configuration and AI
providers.  Trigger expectations below mirror the current group branch in
``bot.message_listener`` without invoking it.
"""

from pathlib import Path

import pytest

from wechatbot.adapters.wechat import (
    AdapterCapability,
    CapabilityNotSupportedError,
    ChatKind,
    FakeWeChatAdapter,
    ForwardedMessage,
    InboundMessage,
    MessageType,
)


def current_group_trigger(
    content: str,
    robot_name: str = '机器人',
    keywords: tuple[str, ...] = (),
    accept_all: bool = False,
    keyword_ignores_probability: bool = True,
    response_roll: int = 1,
    response_probability: int = 100,
) -> tuple[bool, str]:
    """Fixture of bot.py's group branch with deterministic probability input."""
    processed_content = content
    at_triggered = False
    for marker in (f'@{robot_name}\u2005', f'@{robot_name} '):
        if marker in processed_content:
            at_triggered = True
            processed_content = processed_content.replace(marker, '', 1).strip()
            break
    if not at_triggered and processed_content.strip() == f'@{robot_name}':
        at_triggered = True
        processed_content = ''
    keyword_triggered = any(keyword in processed_content for keyword in keywords)
    if not (accept_all or at_triggered or keyword_triggered):
        return False, processed_content
    if keyword_triggered and keyword_ignores_probability:
        return True, processed_content
    return response_roll <= response_probability, processed_content


def safe_special_action(action) -> str:
    try:
        action()
    except CapabilityNotSupportedError:
        return 'UNSUPPORTED'
    return 'PASS'


def test_private_message_order_self_filter_and_unknown_are_preserved() -> None:
    received: list[InboundMessage] = []
    adapter = FakeWeChatAdapter()
    adapter.start(received.append)
    messages = [
        InboundMessage('friend', 'friend', 'first', message_id='one'),
        InboundMessage('friend', 'friend', 'second', message_id='two'),
        InboundMessage('friend', 'bot', 'sent', message_id='three', is_self=True),
        InboundMessage(
            'friend', 'friend', 'future payload', message_id='four', message_type=MessageType.UNKNOWN
        ),
    ]
    for message in messages:
        adapter.emit(message)

    processable = [item for item in received if not item.is_self]
    assert [item.content for item in received] == ['first', 'second', 'sent', 'future payload']
    assert [item.content for item in processable] == ['first', 'second', 'future payload']
    assert processable[-1].message_type is MessageType.UNKNOWN


def test_group_session_sender_at_trigger_and_non_trigger_are_distinct() -> None:
    received: list[InboundMessage] = []
    adapter = FakeWeChatAdapter()
    adapter.start(received.append)
    group_message = InboundMessage(
        conversation_id='test-group',
        sender_id='member-a',
        content='@机器人\u2005 hello',
        message_id='group-one',
        kind=ChatKind.GROUP,
    )
    adapter.emit(group_message)

    triggered, stripped = current_group_trigger(group_message.content)
    keyword_triggered, keyword_content = current_group_trigger('please help', keywords=('help',))
    not_triggered, untouched = current_group_trigger('ordinary group message')

    assert adapter.is_group_chat('test-group') is True
    assert adapter.is_group_chat('not-seen') is None  # Current bot falls back to private handling.
    assert received[0].conversation_id == 'test-group'
    assert received[0].sender_id == 'member-a'
    assert triggered is True and stripped == 'hello'
    assert keyword_triggered is True and keyword_content == 'please help'
    assert not_triggered is False and untouched == 'ordinary group message'


def test_media_fixture_supports_images_emoji_and_continuous_media() -> None:
    adapter = FakeWeChatAdapter()
    adapter.start(lambda _: None)
    image = InboundMessage(
        'friend', 'friend', '', message_id='image-one', message_type=MessageType.IMAGE,
        attachment_path=Path('image-one.png'),
    )
    emoji = InboundMessage(
        'friend', 'friend', '', message_id='emoji-one', message_type=MessageType.EMOJI,
        attachment_path=Path('emoji-one.png'),
    )
    image_two = InboundMessage(
        'friend', 'friend', '', message_id='image-two', message_type=MessageType.IMAGE,
        attachment_path=Path('image-two.png'),
    )
    for message in (image, emoji, image_two):
        adapter.emit(message)

    assert adapter.download_media('image-one') == Path('image-one.png')
    assert adapter.capture_media('emoji-one') == Path('emoji-one.png')
    assert adapter.download_media('image-two') == Path('image-two.png')
    with pytest.raises(CapabilityNotSupportedError, match='does not have media'):
        adapter.download_media('missing')


def test_media_without_attachment_and_explicit_unsupported_capability_are_safe() -> None:
    adapter = FakeWeChatAdapter()
    adapter.start(lambda _: None)
    adapter.emit(InboundMessage('friend', 'friend', '', message_id='empty-image', message_type=MessageType.IMAGE))

    with pytest.raises(CapabilityNotSupportedError, match='does not have media'):
        adapter.download_media('empty-image')
    assert safe_special_action(lambda: adapter.voice_call('friend')) == 'UNSUPPORTED'


def test_quote_link_and_forwarded_message_fixtures_have_safe_unknown_fallback() -> None:
    quote = InboundMessage(
        'friend', 'friend', 'reply', message_id='quote', message_type=MessageType.QUOTE,
        quote_content='original',
    )
    link = InboundMessage(
        'friend', 'friend', 'card', message_id='link', message_type=MessageType.LINK,
        url='https://example.test/card',
    )
    merged = InboundMessage(
        'friend', 'friend', '', message_id='merged', message_type=MessageType.MERGED,
        forwarded_messages=(
            ForwardedMessage(sender_id='member', content='known', timestamp='10:00'),
            ForwardedMessage(sender_id='', content='unknown-child'),
        ),
        forwarded_fallback=None,
    )
    fallback = InboundMessage(
        'friend', 'friend', '', message_id='merged-fallback', message_type=MessageType.MERGED,
        forwarded_fallback='unavailable',
    )

    assert quote.quote_content == 'original'
    assert link.url == 'https://example.test/card'
    assert [item.content for item in merged.forwarded_messages] == ['known', 'unknown-child']
    assert fallback.forwarded_fallback == 'unavailable'


def test_special_actions_and_lifecycle_are_explicit_and_client_free() -> None:
    capabilities = frozenset({
        AdapterCapability.RECEIVE,
        AdapterCapability.TAP_INBOUND,
        AdapterCapability.RECALL_OUTBOUND,
        AdapterCapability.VOICE_CALL,
    })
    adapter = FakeWeChatAdapter(capabilities)
    adapter.start(lambda _: None)
    assert adapter.is_started is True

    adapter.tap_last_inbound('opaque-inbound')
    adapter.recall_last_outbound('opaque-outbound')
    adapter.voice_call('friend')
    assert [action.capability for action in adapter.actions] == [
        AdapterCapability.TAP_INBOUND,
        AdapterCapability.RECALL_OUTBOUND,
        AdapterCapability.VOICE_CALL,
    ]
    adapter.stop()
    assert adapter.is_started is False
    with pytest.raises(RuntimeError, match='not been started'):
        adapter.emit(InboundMessage('friend', 'friend', 'after stop'))
