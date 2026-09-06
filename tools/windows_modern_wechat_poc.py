"""Opt-in Windows PoC for the experimental ModernWeChatAdapter.

On macOS this file is safe to import, syntax-check, or execute: it reports
NOT_TESTED before the adapter can import a Windows-only backend.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import os
import platform
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wechatbot.adapters.wechat import (
    CapabilityNotSupportedError,
    InboundMessage,
    ModernWeChatAdapter,
    ModernWeChatDependencyError,
    ModernWeChatPlatformError,
    MessageType,
)


class Status(str, Enum):
    PASS = 'PASS'
    FAIL = 'FAIL'
    UNSUPPORTED = 'UNSUPPORTED'
    NOT_TESTED = 'NOT_TESTED'


@dataclass(frozen=True)
class Result:
    name: str
    status: Status
    detail: str = ''


class ModernPoc:
    def __init__(self) -> None:
        self.adapter = ModernWeChatAdapter()
        self.messages: list[InboundMessage] = []
        self.results: list[Result] = []

    def record(self, name: str, status: Status, detail: str = '') -> None:
        self.results.append(Result(name, status, detail))
        suffix = f' — {detail}' if detail else ''
        print(f'[{status.value}] {name}{suffix}')

    def check(self, name: str, action: Callable[[], object]) -> object | None:
        try:
            value = action()
        except CapabilityNotSupportedError as error:
            self.record(name, Status.UNSUPPORTED, str(error))
            return None
        except (ModernWeChatDependencyError, ModernWeChatPlatformError, OSError, RuntimeError) as error:
            self.record(name, Status.FAIL, str(error))
            return None
        except Exception as error:
            self.record(name, Status.FAIL, f'{type(error).__name__}: {error}')
            return None
        if value is False:
            self.record(name, Status.FAIL, 'Adapter returned False.')
            return value
        self.record(name, Status.PASS)
        return value

    def on_message(self, message: InboundMessage) -> None:
        self.messages.append(message)
        # Avoid printing personal message text, names, IDs, or local paths.
        print(f'[RECEIVED] {message.kind.value}/{message.message_type.value}')

    def summary(self) -> None:
        print('\n=== Modern adapter PoC summary ===')
        for result in self.results:
            suffix = f' — {result.detail}' if result.detail else ''
            print(f'{result.status.value:12} {result.name}{suffix}')


def installed_backend_version() -> str:
    try:
        return importlib.metadata.version('wechatauto-replica')
    except importlib.metadata.PackageNotFoundError:
        return 'distribution metadata unavailable'


def confirmed(prompt: str) -> bool:
    return input(f'{prompt}\nPress Enter to continue, or type skip: ').strip().lower() != 'skip'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contact', help='Operator-selected disposable test contact; never persisted.')
    parser.add_argument('--send', action='store_true', help='Enable the confirmed text-send step.')
    parser.add_argument('--wechat-version', help='Manually observed WeChat version; never persisted.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if os.name != 'nt':
        print('[NOT_TESTED] Modern adapter PoC only initializes a client on Windows.')
        return 0

    poc = ModernPoc()
    poc.record('environment.windows', Status.PASS, platform.platform())
    poc.record('environment.python', Status.PASS, platform.python_version())
    poc.record('backend.version', Status.PASS, installed_backend_version())
    poc.record(
        'environment.wechat_client',
        Status.PASS if args.wechat_version else Status.NOT_TESTED,
        args.wechat_version or 'Record manually with --wechat-version.',
    )
    poc.check('adapter.initialize', poc.adapter.initialize)
    if poc.adapter.provider is None:
        poc.summary()
        return 1
    poc.record('adapter.provider', Status.PASS, poc.adapter.provider)
    poc.check('adapter.nickname', lambda: poc.adapter.nickname)
    poc.check('adapter.start', lambda: poc.adapter.start(poc.on_message))

    if args.contact:
        poc.check('listener.text.register', lambda: poc.adapter.listen(args.contact))
        if confirmed('Send one disposable text from the selected test contact.'):
            received = any(message.message_type is MessageType.TEXT for message in poc.messages)
            poc.record(
                'listener.text.receive',
                Status.PASS if received else Status.FAIL,
                '' if received else 'No normalized text callback was received.',
            )
        else:
            poc.record('listener.text.receive', Status.NOT_TESTED, 'Skipped by operator.')
        if args.send and confirmed('Confirm a disposable text may be sent to the selected test contact.'):
            poc.check('send.text', lambda: poc.adapter.send_text(args.contact, 'Modern adapter PoC test'))
        else:
            poc.record('send.text', Status.NOT_TESTED, 'Requires --send and explicit confirmation.')
    else:
        poc.record('listener.text', Status.NOT_TESTED, 'Pass --contact to enable receive/send checks.')
        poc.record('send.text', Status.NOT_TESTED, 'Pass --contact --send to enable this check.')

    poc.adapter.stop()
    poc.record('adapter.stop', Status.PASS if not poc.adapter.is_started else Status.FAIL)
    poc.summary()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
