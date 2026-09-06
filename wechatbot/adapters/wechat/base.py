"""Platform-neutral contract for WeChat-facing implementations.

This module deliberately has no Windows or wxauto/wxautox imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, FrozenSet, Protocol


class ChatKind(str, Enum):
    PRIVATE = 'private'
    GROUP = 'group'


class AdapterCapability(str, Enum):
    RECEIVE = 'receive'
    SEND_TEXT = 'send_text'
    SEND_FILE = 'send_file'
    VOICE_CALL = 'voice_call'
    TAP_INBOUND = 'tap_inbound'
    TAP_OUTBOUND = 'tap_outbound'
    RECALL_OUTBOUND = 'recall_outbound'


class CapabilityNotSupportedError(RuntimeError):
    """Raised when an adapter cannot perform an explicitly requested action."""


@dataclass(frozen=True)
class InboundMessage:
    conversation_id: str
    sender_id: str
    content: str
    kind: ChatKind = ChatKind.PRIVATE
    message_type: str = 'text'
    attachment_path: Path | None = None
    is_self: bool = False
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class OutboundAction:
    conversation_id: str
    capability: AdapterCapability
    content: str | None = None
    file_path: Path | None = None


MessageHandler = Callable[[InboundMessage], None]


class WeChatAdapter(Protocol):
    """Small capability-oriented contract for legacy and future adapters."""

    @property
    def capabilities(self) -> FrozenSet[AdapterCapability]:
        """Capabilities verified for this adapter/client combination."""

    def start(self, on_message: MessageHandler) -> None:
        """Start receiving messages and deliver normalized project messages."""

    def stop(self) -> None:
        """Stop receiving messages and release adapter resources."""

    def send_text(self, conversation_id: str, text: str) -> None:
        """Send a text message."""

    def send_file(self, conversation_id: str, file_path: Path) -> None:
        """Send a local file."""

    def voice_call(self, conversation_id: str) -> None:
        """Trigger a voice-call reminder when the adapter supports it."""

    def tap_last_inbound(self, conversation_id: str) -> None:
        """Tap the latest inbound message when supported."""

    def tap_last_outbound(self, conversation_id: str) -> None:
        """Tap the latest outbound message when supported."""

    def recall_last_outbound(self, conversation_id: str) -> None:
        """Recall the latest outbound message when supported."""
