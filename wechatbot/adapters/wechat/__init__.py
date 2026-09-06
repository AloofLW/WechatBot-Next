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
from .legacy import LegacyWeChatAdapter, LegacyWeChatDependencyError

__all__ = [
    'AdapterCapability',
    'CapabilityNotSupportedError',
    'ChatKind',
    'FakeWeChatAdapter',
    'InboundMessage',
    'LegacyWeChatAdapter',
    'LegacyWeChatDependencyError',
    'OutboundAction',
    'WeChatAdapter',
]
