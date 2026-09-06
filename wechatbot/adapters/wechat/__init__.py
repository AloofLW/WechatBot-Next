"""Project-owned WeChat adapter contracts and test implementations.

Production wxauto/wxautox implementations are intentionally not imported here.
"""

from .base import (
    AdapterCapability,
    CapabilityNotSupportedError,
    ChatKind,
    InboundMessage,
    OutboundAction,
    WeChatAdapter,
)
from .fake import FakeWeChatAdapter

__all__ = [
    'AdapterCapability',
    'CapabilityNotSupportedError',
    'ChatKind',
    'FakeWeChatAdapter',
    'InboundMessage',
    'OutboundAction',
    'WeChatAdapter',
]
