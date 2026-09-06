"""Deterministic in-memory adapter for macOS and client-free tests."""

from __future__ import annotations

from pathlib import Path
from typing import FrozenSet

from .base import (
    AdapterCapability,
    CapabilityNotSupportedError,
    ChatKind,
    InboundMessage,
    MessageHandler,
    OutboundAction,
)


class FakeWeChatAdapter:
    """A complete test double whose supported capabilities are explicit."""

    def __init__(
        self,
        capabilities: FrozenSet[AdapterCapability] | None = None,
    ) -> None:
        self._capabilities = capabilities or frozenset(
            {
                AdapterCapability.RECEIVE,
                AdapterCapability.SEND_TEXT,
                AdapterCapability.SEND_FILE,
            }
        )
        self._handler: MessageHandler | None = None
        self.actions: list[OutboundAction] = []
        self._messages: dict[str, InboundMessage] = {}
        self._chat_kinds: dict[str, ChatKind] = {}

    @property
    def capabilities(self) -> FrozenSet[AdapterCapability]:
        return self._capabilities

    def start(self, on_message: MessageHandler) -> None:
        self._require(AdapterCapability.RECEIVE)
        self._handler = on_message

    def stop(self) -> None:
        self._handler = None

    def emit(self, message: InboundMessage) -> None:
        if self._handler is None:
            raise RuntimeError('FakeWeChatAdapter has not been started.')
        if message.message_id:
            self._messages[message.message_id] = message
        self._chat_kinds[message.conversation_id] = message.kind
        self._handler(message)

    def send_text(self, conversation_id: str, text: str) -> bool:
        self._require(AdapterCapability.SEND_TEXT)
        self.actions.append(
            OutboundAction(conversation_id, AdapterCapability.SEND_TEXT, content=text)
        )
        return True

    def send_file(self, conversation_id: str, file_path: Path) -> bool:
        self._require(AdapterCapability.SEND_FILE)
        self.actions.append(
            OutboundAction(conversation_id, AdapterCapability.SEND_FILE, file_path=file_path)
        )
        return True

    def is_group_chat(self, conversation_id: str) -> bool | None:
        kind = self._chat_kinds.get(conversation_id)
        if kind is None:
            return None
        return kind is ChatKind.GROUP

    def download_media(self, message_id: str) -> Path:
        return self._attachment_for(message_id)

    def capture_media(self, message_id: str) -> Path:
        return self._attachment_for(message_id)

    def voice_call(self, conversation_id: str) -> None:
        self._record_capability_action(AdapterCapability.VOICE_CALL, conversation_id)

    def tap_last_inbound(self, conversation_id: str) -> None:
        self._record_capability_action(AdapterCapability.TAP_INBOUND, conversation_id)

    def tap_last_outbound(self, conversation_id: str) -> None:
        self._record_capability_action(AdapterCapability.TAP_OUTBOUND, conversation_id)

    def recall_last_outbound(self, conversation_id: str) -> None:
        self._record_capability_action(AdapterCapability.RECALL_OUTBOUND, conversation_id)

    def _record_capability_action(
        self, capability: AdapterCapability, conversation_id: str
    ) -> None:
        self._require(capability)
        self.actions.append(OutboundAction(conversation_id, capability))

    def _require(self, capability: AdapterCapability) -> None:
        if capability not in self._capabilities:
            raise CapabilityNotSupportedError(
                f'FakeWeChatAdapter does not support {capability.value}.'
            )

    def _attachment_for(self, message_id: str) -> Path:
        message = self._messages.get(message_id)
        if message is None or message.attachment_path is None:
            raise CapabilityNotSupportedError(
                f'FakeWeChatAdapter does not have media for message {message_id}.'
            )
        return message.attachment_path
