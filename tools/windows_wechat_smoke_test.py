"""Interactive Windows-only acceptance check for the legacy WeChat adapter.

This tool never imports a wxauto-family package directly.  On macOS it can be
imported or syntax-checked safely; executing it there reports NOT_TESTED and
does not initialize the adapter.
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

# Permit direct ``python tools/windows_wechat_smoke_test.py`` execution without
# requiring installation as a package. This only adjusts the local project path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wechatbot.adapters.wechat import (
    AdapterCapability,
    CapabilityNotSupportedError,
    InboundMessage,
    MessageType,
)
from wechatbot.adapters.wechat.legacy import LegacyWeChatAdapter, LegacyWeChatDependencyError


class ResultStatus(str, Enum):
    PASS = 'PASS'
    FAIL = 'FAIL'
    UNSUPPORTED = 'UNSUPPORTED'
    NOT_TESTED = 'NOT_TESTED'


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: ResultStatus
    detail: str = ''


class SmokeTest:
    """Collects privacy-preserving result labels for a manual local run."""

    def __init__(self) -> None:
        self.results: list[CheckResult] = []
        self.messages: list[InboundMessage] = []
        self.adapter = LegacyWeChatAdapter()

    def record(self, name: str, status: ResultStatus, detail: str = '') -> None:
        self.results.append(CheckResult(name, status, detail))
        suffix = f' — {detail}' if detail else ''
        print(f'[{status.value}] {name}{suffix}')

    def check(self, name: str, action: Callable[[], object]) -> object | None:
        try:
            value = action()
        except CapabilityNotSupportedError as error:
            self.record(name, ResultStatus.UNSUPPORTED, str(error))
            return None
        except (LegacyWeChatDependencyError, OSError, RuntimeError) as error:
            self.record(name, ResultStatus.FAIL, str(error))
            return None
        except Exception as error:  # Manual acceptance must keep checking later rows.
            self.record(name, ResultStatus.FAIL, f'{type(error).__name__}: {error}')
            return None
        if value is False:
            self.record(name, ResultStatus.FAIL, 'Adapter returned False.')
            return value
        self.record(name, ResultStatus.PASS)
        return value

    def not_tested(self, name: str, detail: str = '') -> None:
        self.record(name, ResultStatus.NOT_TESTED, detail)

    def on_message(self, message: InboundMessage) -> None:
        self.messages.append(message)
        # Do not log chat names, sender IDs, text, file paths, or message handles.
        print(f'[RECEIVED] {message.kind.value}/{message.message_type.value}')

    def first_message(self, message_type: MessageType) -> InboundMessage | None:
        return next((item for item in reversed(self.messages) if item.message_type is message_type), None)

    def report(self) -> None:
        print('\n=== Legacy WeChat Adapter smoke-test summary ===')
        for result in self.results:
            suffix = f' — {result.detail}' if result.detail else ''
            print(f'{result.status.value:12} {result.name}{suffix}')


def installed_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return 'not installed or distribution metadata unavailable'


def wait_for_manual_step(prompt: str) -> bool:
    answer = input(f'{prompt}\nPress Enter when complete, or type skip: ').strip().lower()
    return answer != 'skip'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contact', help='Local test contact selected by the operator; never saved.')
    parser.add_argument('--group', help='Local test group selected by the operator; never saved.')
    parser.add_argument('--file', type=Path, help='A local disposable file for the optional send-file check.')
    parser.add_argument('--wechat-version', help='Optional manually observed client version; printed only.')
    parser.add_argument('--send', action='store_true', help='Enable manual send-text/send-file checks.')
    parser.add_argument('--voice', action='store_true', help='Enable the manual voice-call capability check.')
    parser.add_argument('--special', action='store_true', help='Enable manual tickle/recall checks.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if os.name != 'nt':
        print('[NOT_TESTED] Legacy adapter smoke test only initializes a client on Windows.')
        return 0

    test = SmokeTest()
    test.record('environment.windows', ResultStatus.PASS, platform.platform())
    test.record('environment.python', ResultStatus.PASS, platform.python_version())
    test.record(
        'environment.wechat_client',
        ResultStatus.NOT_TESTED if not args.wechat_version else ResultStatus.PASS,
        args.wechat_version or 'Record the version manually with --wechat-version.',
    )

    test.check('adapter.initialize', test.adapter.initialize)
    if test.adapter.provider is None:
        test.not_tested('adapter.provider', 'Initialization did not select a provider.')
        test.report()
        return 1
    test.record('adapter.provider', ResultStatus.PASS, test.adapter.provider)
    test.record(
        'adapter.provider_version', ResultStatus.PASS, installed_version(test.adapter.provider)
    )
    test.check('adapter.nickname', lambda: test.adapter.nickname)
    test.check('adapter.show', test.adapter.show)
    test.check('adapter.reinitialize_single_client', lambda: (test.adapter.initialize(), test.adapter.initialization_count == 1)[1])

    test.check('listener.start', lambda: test.adapter.start(test.on_message))
    if args.contact:
        test.check('listener.private.register', lambda: test.adapter.listen(args.contact))
        for message_type, instruction in (
            (MessageType.TEXT, 'Send one disposable text from the selected test contact.'),
            (MessageType.IMAGE, 'Send one disposable image from the selected test contact.'),
            (MessageType.EMOJI, 'Send one emoji/sticker from the selected test contact.'),
            (MessageType.QUOTE, 'Send one quoted message from the selected test contact.'),
            (MessageType.LINK, 'Send one link/card from the selected test contact.'),
        ):
            if wait_for_manual_step(instruction):
                seen = test.first_message(message_type)
                test.record(
                    f'listener.private.{message_type.value}',
                    ResultStatus.PASS if seen else ResultStatus.FAIL,
                    '' if seen else 'No matching normalized callback was received.',
                )
            else:
                test.not_tested(f'listener.private.{message_type.value}', 'Skipped by operator.')
    else:
        test.not_tested('listener.private', 'Pass --contact to run manual receive checks.')

    if args.group:
        test.check('listener.group.register', lambda: test.adapter.listen(args.group))
        if wait_for_manual_step('Send one disposable text in the selected test group.'):
            seen = next((item for item in reversed(test.messages) if item.conversation_id == args.group), None)
            test.record('listener.group.callback', ResultStatus.PASS if seen else ResultStatus.FAIL)
            test.check('group.query', lambda: test.adapter.is_group_chat(args.group) is True)
        else:
            test.not_tested('listener.group.callback', 'Skipped by operator.')
    else:
        test.not_tested('listener.group', 'Pass --group to run manual group checks.')

    image = test.first_message(MessageType.IMAGE)
    emoji = test.first_message(MessageType.EMOJI)
    if image:
        test.check('media.download', lambda: test.adapter.download_media(image.message_id))
    else:
        test.not_tested('media.download', 'Receive an image first.')
    if emoji:
        test.check('media.emoji_capture', lambda: test.adapter.capture_media(emoji.message_id))
    else:
        test.not_tested('media.emoji_capture', 'Receive an emoji/sticker first.')

    if args.send and args.contact:
        if wait_for_manual_step('Confirm that it is safe to send a disposable text to the selected test contact.'):
            test.check('send.text', lambda: test.adapter.send_text(args.contact, 'Legacy adapter smoke test'))
        else:
            test.not_tested('send.text', 'Skipped by operator.')
        if args.file and args.file.is_file() and wait_for_manual_step('Confirm that it is safe to send the selected disposable file.'):
            test.check('send.file', lambda: test.adapter.send_file(args.contact, args.file))
        else:
            test.not_tested('send.file', 'Use --file with an existing disposable file, then confirm.')
    else:
        test.not_tested('send', 'Requires both --send and --contact.')

    last_inbound = test.messages[-1] if test.messages else None
    if args.special and last_inbound and wait_for_manual_step('Confirm a tickle on the latest received test message is safe.'):
        test.check('special.tickle_inbound', lambda: test.adapter.tap_last_inbound(last_inbound.message_id))
    else:
        test.not_tested('special.tickle_inbound', 'Requires --special and a received test message.')
    if args.special and args.contact and args.voice and wait_for_manual_step('Confirm a voice-call reminder to the test contact is safe.'):
        test.check('special.voice_call', lambda: test.adapter.voice_call(args.contact))
    else:
        test.not_tested('special.voice_call', 'Requires --special --voice --contact and confirmation.')
    self_message = next(
        (item for item in reversed(test.messages) if item.is_self and item.message_type is MessageType.TEXT),
        None,
    )
    if args.special and args.contact and self_message is None:
        if wait_for_manual_step('Confirm a disposable text may be sent so its self callback can be recalled.'):
            test.check(
                'special.recall_outbound.send_disposable',
                lambda: test.adapter.send_text(args.contact, 'Legacy adapter recall smoke test'),
            )
            wait_for_manual_step('Wait for the self-sent callback, then continue.')
            self_message = next(
                (item for item in reversed(test.messages) if item.is_self and item.message_type is MessageType.TEXT),
                None,
            )
    if args.special and self_message and wait_for_manual_step('Confirm a tickle on the self-sent disposable test message is safe.'):
        test.check('special.tickle_outbound', lambda: test.adapter.tap_last_outbound(self_message.message_id))
    else:
        test.not_tested('special.tickle_outbound', 'Requires --special and a self-sent text callback.')
    if args.special and self_message and wait_for_manual_step('Confirm recall of the latest self-sent disposable test message is safe.'):
        test.check('special.recall_outbound', lambda: test.adapter.recall_last_outbound(self_message.message_id))
    else:
        test.not_tested(
            'special.recall_outbound',
            'Requires --special and a self-sent text callback with an opaque handle.',
        )

    test.adapter.stop()
    test.record('adapter.stop', ResultStatus.PASS if not test.adapter.is_started else ResultStatus.FAIL)
    test.report()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
