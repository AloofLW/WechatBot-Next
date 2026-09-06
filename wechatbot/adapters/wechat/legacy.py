"""Legacy wxauto-family adapter.

The wxauto/wxautox imports are deliberately delayed until ``initialize``.
Importing this module is safe on macOS and in client-free test environments.
"""

from __future__ import annotations

import importlib
import os
import uuid
from pathlib import Path
from typing import Any, Callable, FrozenSet

from .base import (
    AdapterCapability,
    CapabilityNotSupportedError,
    ChatKind,
    InboundMessage,
    MessageHandler,
)


class LegacyWeChatDependencyError(RuntimeError):
    """Raised only when a legacy adapter is initialized without its library."""


ImportModule = Callable[[str], Any]


class LegacyWeChatAdapter:
    """Adapter for the existing wxautox_wechatbot -> wxautox -> wxauto fallback."""

    _PROVIDERS = ('wxautox_wechatbot', 'wxautox', 'wxauto')

    def __init__(self, importer: ImportModule | None = None) -> None:
        self._importer = importer or importlib.import_module
        self._client: Any | None = None
        self._provider: str | None = None
        self._message_handler: MessageHandler | None = None
        self._inbound_handles: dict[str, Any] = {}
        self._outbound_handles: dict[str, Any] = {}

    @property
    def provider(self) -> str | None:
        return self._provider

    @property
    def raw_client(self) -> Any:
        """Temporary escape hatch for not-yet-migrated legacy bot.py paths."""
        return self._require_client()

    @property
    def nickname(self) -> str:
        return str(getattr(self._require_client(), 'nickname', ''))

    @property
    def capabilities(self) -> FrozenSet[AdapterCapability]:
        if self._client is None:
            return frozenset()
        capabilities = {AdapterCapability.RECEIVE}
        method_capabilities = {
            'AddListenChat': AdapterCapability.LISTEN,
            'Show': AdapterCapability.SHOW,
            'KeepRunning': AdapterCapability.KEEP_RUNNING,
            'SendMsg': AdapterCapability.SEND_TEXT,
            'SendFiles': AdapterCapability.SEND_FILE,
            'VoiceCall': AdapterCapability.VOICE_CALL,
        }
        for method, capability in method_capabilities.items():
            if callable(getattr(self._client, method, None)):
                capabilities.add(capability)
        return frozenset(capabilities)

    def initialize(self) -> None:
        """Load the selected library and create exactly one client instance."""
        if self._client is not None:
            return
        wechat_class = self._load_wechat_class()
        self._client = wechat_class()

    def show(self) -> None:
        self._call_client_method('Show', AdapterCapability.SHOW)

    def start(self, on_message: MessageHandler) -> None:
        self.initialize()
        self._message_handler = on_message

    def stop(self) -> None:
        self._message_handler = None

    def listen(self, nickname: str) -> Any:
        """Register a normalized-message listener for new application code."""
        if self._message_handler is None:
            raise RuntimeError('Call start(on_message) before listen().')
        return self._call_client_method(
            'AddListenChat', AdapterCapability.LISTEN, nickname=nickname, callback=self._on_raw_message
        )

    def add_legacy_listener(self, nickname: str, callback: Callable[[Any, Any], None]) -> Any:
        """Transitional raw callback bridge for unchanged bot.py message handling."""
        return self._call_client_method(
            'AddListenChat', AdapterCapability.LISTEN, nickname=nickname, callback=callback
        )

    def listening_conversations(self) -> set[str]:
        client = self._require_client()
        listeners = getattr(client, 'listen', None)
        if not isinstance(listeners, dict):
            return set()
        return set(listeners.keys())

    def keep_running(self) -> Any:
        return self._call_client_method('KeepRunning', AdapterCapability.KEEP_RUNNING)

    def send_text(self, conversation_id: str, text: str) -> bool:
        return bool(
            self._call_client_method(
                'SendMsg', AdapterCapability.SEND_TEXT, msg=text, who=conversation_id
            )
        )

    def send_file(self, conversation_id: str, file_path: Path | str) -> bool:
        return bool(
            self._call_client_method(
                'SendFiles', AdapterCapability.SEND_FILE, filepath=str(file_path), who=conversation_id
            )
        )

    def voice_call(self, conversation_id: str) -> Any:
        return self._call_client_method('VoiceCall', AdapterCapability.VOICE_CALL, conversation_id)

    def normalize_message(self, raw_message: Any, raw_chat: Any) -> InboundMessage:
        """Translate raw wx objects without exposing their types to callers."""
        conversation_id = str(getattr(raw_chat, 'who', ''))
        chat_info = self._chat_info(raw_chat)
        kind = ChatKind.GROUP if chat_info.get('chat_type') == 'group' else ChatKind.PRIVATE
        content = getattr(raw_message, 'content', None) or getattr(raw_message, 'text', '') or ''
        handle = uuid.uuid4().hex
        self._inbound_handles[conversation_id] = raw_message
        metadata = {'opaque_handle': handle, 'attr': str(getattr(raw_message, 'attr', ''))}
        if getattr(raw_message, 'type', '') == 'link':
            url = self._safe_message_value(raw_message, 'get_url')
            if url:
                metadata['url'] = str(url)
        quote_content = getattr(raw_message, 'quote_content', None)
        if quote_content:
            metadata['quote_content'] = str(quote_content)
        return InboundMessage(
            conversation_id=conversation_id,
            sender_id=str(getattr(raw_message, 'sender', conversation_id)),
            content=str(content),
            kind=kind,
            message_type=str(getattr(raw_message, 'type', 'text')),
            is_self=getattr(raw_message, 'attr', '') == 'self',
            metadata=metadata,
        )

    def download_media(self, conversation_id: str) -> Path:
        message = self._last_inbound(conversation_id)
        return Path(self._call_message_method(message, 'download', AdapterCapability.RECEIVE))

    def capture_media(self, conversation_id: str) -> Path:
        message = self._last_inbound(conversation_id)
        return Path(self._call_message_method(message, 'capture', AdapterCapability.RECEIVE))

    def extract_url(self, conversation_id: str) -> str | None:
        return self._safe_message_value(self._last_inbound(conversation_id), 'get_url')

    def quote_content(self, conversation_id: str) -> str | None:
        value = getattr(self._last_inbound(conversation_id), 'quote_content', None)
        return str(value) if value is not None else None

    def remember_outbound_handle(self, conversation_id: str, raw_message: Any) -> None:
        """Adapter-internal bridge for later migration of self-message callbacks."""
        self._outbound_handles[conversation_id] = raw_message

    def tap_last_inbound(self, conversation_id: str) -> None:
        self._call_message_method(
            self._last_inbound(conversation_id), 'tickle', AdapterCapability.TAP_INBOUND
        )

    def tap_last_outbound(self, conversation_id: str) -> None:
        self._call_message_method(
            self._last_outbound(conversation_id), 'tickle', AdapterCapability.TAP_OUTBOUND
        )

    def recall_last_outbound(self, conversation_id: str) -> None:
        self._call_message_method(
            self._last_outbound(conversation_id),
            'select_option',
            AdapterCapability.RECALL_OUTBOUND,
            '撤回',
        )
        self._outbound_handles.pop(conversation_id, None)

    def _load_wechat_class(self) -> type[Any]:
        failures = []
        for provider in self._PROVIDERS:
            try:
                module = self._importer(provider)
                wechat_class = getattr(module, 'WeChat')
                if provider == 'wxautox_wechatbot':
                    self._configure_wxautox_wechatbot(provider)
                self._provider = provider
                return wechat_class
            except (ImportError, AttributeError) as error:
                failures.append(f'{provider}: {error}')
        attempted = ', '.join(self._PROVIDERS)
        detail = '; '.join(failures)
        raise LegacyWeChatDependencyError(
            f'No supported Windows WeChat automation library is available. Tried: {attempted}. {detail}'
        )

    def _configure_wxautox_wechatbot(self, provider: str) -> None:
        param_module = self._importer(f'{provider}.param')
        wx_param = getattr(param_module, 'WxParam')
        wx_param.ENABLE_FILE_LOGGER = False
        wx_param.FORCE_MESSAGE_XBIAS = True
        os.environ['PROJECT_NAME'] = 'iwyxdxl/WeChatBot_WXAUTO_SE'

    def _on_raw_message(self, raw_message: Any, raw_chat: Any) -> None:
        if self._message_handler is not None:
            self._message_handler(self.normalize_message(raw_message, raw_chat))

    def _require_client(self) -> Any:
        if self._client is None:
            raise LegacyWeChatDependencyError(
                'LegacyWeChatAdapter is not initialized. Call initialize() or start() on Windows first.'
            )
        return self._client

    def _call_client_method(self, method: str, capability: AdapterCapability, *args: Any, **kwargs: Any) -> Any:
        client = self._require_client()
        candidate = getattr(client, method, None)
        if not callable(candidate):
            raise CapabilityNotSupportedError(
                f'Legacy adapter does not support {capability.value}: client has no {method}().'
            )
        return candidate(*args, **kwargs)

    def _call_message_method(
        self, message: Any, method: str, capability: AdapterCapability, *args: Any
    ) -> Any:
        candidate = getattr(message, method, None)
        if not callable(candidate):
            raise CapabilityNotSupportedError(
                f'Legacy adapter does not support {capability.value}: message has no {method}().'
            )
        return candidate(*args)

    def _last_inbound(self, conversation_id: str) -> Any:
        if conversation_id not in self._inbound_handles:
            raise CapabilityNotSupportedError(
                f'Legacy adapter does not support tap_inbound: no inbound message for {conversation_id}.'
            )
        return self._inbound_handles[conversation_id]

    def _last_outbound(self, conversation_id: str) -> Any:
        if conversation_id not in self._outbound_handles:
            raise CapabilityNotSupportedError(
                f'Legacy adapter does not support recall_outbound: no outbound message for {conversation_id}.'
            )
        return self._outbound_handles[conversation_id]

    @staticmethod
    def _safe_message_value(message: Any, method: str) -> str | None:
        candidate = getattr(message, method, None)
        if not callable(candidate):
            return None
        try:
            value = candidate()
        except Exception:
            return None
        return str(value) if value is not None else None

    @staticmethod
    def _chat_info(raw_chat: Any) -> dict[str, Any]:
        candidate = getattr(raw_chat, 'ChatInfo', None)
        if not callable(candidate):
            return {}
        try:
            value = candidate()
        except Exception:
            return {}
        return value if isinstance(value, dict) else {}
