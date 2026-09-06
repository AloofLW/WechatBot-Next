"""Experimental adapter boundary for a current Windows WeChat client.

The candidate backend (``wechatauto-replica``) is imported only inside
``initialize``.  Importing this module is safe on macOS and does not install,
load, or exercise Windows automation dependencies.
"""

from __future__ import annotations

import importlib
import os
import uuid
from datetime import datetime
from typing import Any, Callable, FrozenSet

from .base import AdapterCapability, CapabilityNotSupportedError, ChatKind, InboundMessage, MessageHandler, MessageType


class ModernWeChatDependencyError(RuntimeError):
    """Raised when the selected experimental backend is unavailable."""


class ModernWeChatPlatformError(RuntimeError):
    """Raised when an attempt is made to initialize the Windows-only PoC elsewhere."""


ImportModule = Callable[[str], Any]
PlatformName = Callable[[], str]


class ModernWeChatAdapter:
    """Minimal, non-default PoC backed by ``wechatauto-replica``.

    It deliberately covers only initialization, nickname lookup, text listener
    registration, normalized text callback delivery, and text sending.  Media,
    file sends, special actions, and group queries stay out of this PoC until
    they have a Windows behavior baseline.
    """

    _BACKEND = 'wechatauto'

    def __init__(
        self,
        importer: ImportModule | None = None,
        platform_name: PlatformName | None = None,
        listener_interval: float = 1.0,
    ) -> None:
        self._importer = importer or importlib.import_module
        self._platform_name = platform_name or (lambda: os.name)
        self._listener_interval = listener_interval
        self._module: Any | None = None
        self._database: Any | None = None
        self._listener: Any | None = None
        self._listener_started = False
        self._message_handler: MessageHandler | None = None
        self.callback_errors: list[Exception] = []
        self.initialization_count = 0

    @property
    def provider(self) -> str | None:
        return self._BACKEND if self._module is not None else None

    @property
    def is_started(self) -> bool:
        return self._message_handler is not None

    @property
    def nickname(self) -> str:
        database = self._require_database()
        info = database.get_self_info()
        if not isinstance(info, dict):
            return ''
        return str(info.get('nick_name') or info.get('nickname') or info.get('username') or '')

    @property
    def capabilities(self) -> FrozenSet[AdapterCapability]:
        if self._module is None:
            return frozenset()
        capabilities = {AdapterCapability.RECEIVE}
        if callable(getattr(self._module, 'Listener', None)):
            capabilities.add(AdapterCapability.LISTEN)
        if callable(getattr(self._module, 'quick_send', None)):
            capabilities.add(AdapterCapability.SEND_TEXT)
        return frozenset(capabilities)

    def initialize(self) -> None:
        """Load the experimental backend and create exactly one database client."""
        if self._database is not None:
            return
        if self._platform_name() != 'nt':
            raise ModernWeChatPlatformError(
                'ModernWeChatAdapter is Windows-only. Run its real-client PoC on Windows, not macOS.'
            )
        try:
            module = self._importer(self._BACKEND)
            database_class = getattr(module, 'WeChatDB')
        except (ImportError, AttributeError) as error:
            raise ModernWeChatDependencyError(
                'ModernWeChatAdapter requires the Windows-only wechatauto-replica backend '
                '(import name: wechatauto). Install and validate it only on Windows.'
            ) from error
        self._module = module
        self._database = database_class()
        self.initialization_count += 1

    def start(self, on_message: MessageHandler) -> None:
        self.initialize()
        self._message_handler = on_message

    def stop(self) -> None:
        listener = self._listener
        self._listener = None
        self._listener_started = False
        self._message_handler = None
        if listener is not None:
            stop = getattr(listener, 'stop', None)
            if callable(stop):
                stop()

    def listen(self, conversation_id: str) -> None:
        """Listen to one backend session identifier using normalized callbacks."""
        if self._message_handler is None:
            raise RuntimeError('Call start(on_message) before listen().')
        self.initialize()
        listener = self._listener
        if listener is None:
            listener_class = getattr(self._module, 'Listener', None)
            if not callable(listener_class):
                raise CapabilityNotSupportedError(
                    'Modern adapter does not support listen: backend has no Listener.'
                )
            listener = listener_class(self._require_database(), interval=self._listener_interval)
            self._listener = listener
        add_listener = getattr(listener, 'add_listener', None)
        if not callable(add_listener):
            raise CapabilityNotSupportedError(
                'Modern adapter does not support listen: Listener has no add_listener().'
            )
        add_listener(conversation_id, lambda raw, _: self._on_raw_message(raw, conversation_id))
        start = getattr(listener, 'start', None)
        if not callable(start):
            raise CapabilityNotSupportedError(
                'Modern adapter does not support listen: Listener has no start().'
            )
        if not self._listener_started:
            start()
            self._listener_started = True

    def send_text(self, conversation_id: str, text: str) -> bool:
        self.initialize()
        sender = getattr(self._module, 'quick_send', None)
        if not callable(sender):
            raise CapabilityNotSupportedError(
                'Modern adapter does not support send_text: backend has no quick_send().'
            )
        result = sender(text, conversation_id, verify=True)
        return result is not False

    def normalize_message(self, raw_message: Any, fallback_conversation_id: str = '') -> InboundMessage:
        """Convert a backend dict/object without exposing backend types to business code."""
        raw = self._message_mapping(raw_message)
        conversation_id = str(
            raw.get('conversation_id') or raw.get('chat_name') or raw.get('username') or fallback_conversation_id
        )
        sender_id = str(raw.get('sender_id') or raw.get('sender') or conversation_id)
        raw_type = str(raw.get('type') or raw.get('message_type') or 'text').lower()
        raw_chat_kind = str(raw.get('chat_type') or raw.get('kind') or '').lower()
        kind = ChatKind.GROUP if raw_chat_kind == 'group' or conversation_id.endswith('@chatroom') else ChatKind.PRIVATE
        opaque_source = raw.get('local_id') or raw.get('message_id') or raw.get('msg_id') or uuid.uuid4().hex
        timestamp = raw.get('create_time') or raw.get('timestamp')
        return InboundMessage(
            message_id=f'modern:{conversation_id}:{opaque_source}',
            conversation_id=conversation_id,
            sender_id=sender_id,
            content=str(raw.get('content') or raw.get('text') or ''),
            kind=kind,
            message_type=self._message_type(raw_type),
            is_self=bool(raw.get('is_self')) or str(raw.get('attr') or '') == 'self',
            is_friend_message=not bool(raw.get('is_stranger')),
            quote_content=self._optional_text(raw.get('quote_content')),
            url=self._optional_text(raw.get('url')),
            timestamp=datetime.fromtimestamp(timestamp) if isinstance(timestamp, (int, float)) else None,
            metadata={},
        )

    def _on_raw_message(self, raw_message: Any, fallback_conversation_id: str) -> None:
        if self._message_handler is None:
            return
        try:
            self._message_handler(self.normalize_message(raw_message, fallback_conversation_id))
        except Exception as error:
            # Backend worker threads must survive a malformed message or callback failure.
            self.callback_errors.append(error)

    def _require_database(self) -> Any:
        if self._database is None:
            raise ModernWeChatDependencyError(
                'ModernWeChatAdapter is not initialized. Call initialize() or start() on Windows first.'
            )
        return self._database

    @staticmethod
    def _message_mapping(raw_message: Any) -> dict[str, Any]:
        if isinstance(raw_message, dict):
            return raw_message
        return {
            name: getattr(raw_message, name)
            for name in ('conversation_id', 'chat_name', 'username', 'sender_id', 'sender', 'type', 'message_type',
                         'chat_type', 'kind', 'local_id', 'message_id', 'msg_id', 'create_time', 'timestamp',
                         'content', 'text', 'is_self', 'attr', 'is_stranger', 'quote_content', 'url')
            if hasattr(raw_message, name)
        }

    @staticmethod
    def _message_type(raw_type: str) -> MessageType:
        return {
            'text': MessageType.TEXT,
            'image': MessageType.IMAGE,
            'emoji': MessageType.EMOJI,
            'emotion': MessageType.EMOJI,
            'file': MessageType.FILE,
            'link': MessageType.LINK,
            'quote': MessageType.QUOTE,
            'voice': MessageType.VOICE,
            'merge': MessageType.MERGED,
            'merged': MessageType.MERGED,
            'system': MessageType.SYSTEM,
        }.get(raw_type, MessageType.UNKNOWN)

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        return str(value) if value is not None else None
