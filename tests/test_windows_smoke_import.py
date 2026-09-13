"""Verify platform-specific behavior of the Windows legacy smoke-test tool."""

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

from wechatbot.adapters.wechat.legacy import LegacyWeChatDependencyError


def test_windows_smoke_script_import_does_not_load_automation_packages() -> None:
    importlib.import_module('tools.windows_wechat_smoke_test')

    assert not {
        'wxauto',
        'wxautox',
        'wxautox_wechatbot',
    }.intersection(sys.modules)


@pytest.mark.skipif(
    sys.platform != 'darwin',
    reason='Validates the macOS-only safe-execution contract of the Windows smoke test.',
)
def test_windows_smoke_script_import_and_macos_execution_do_not_load_automation_packages() -> None:
    script = Path('tools/windows_wechat_smoke_test.py')
    result = subprocess.run(
        [sys.executable, str(script)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert '[NOT_TESTED] Legacy adapter smoke test only initializes a client on Windows.' in result.stdout


def test_windows_smoke_script_reports_missing_backend_without_starting_wechat(monkeypatch, capsys) -> None:
    smoke_module = importlib.import_module('tools.windows_wechat_smoke_test')

    class MissingBackendAdapter:
        provider = None

        def initialize(self) -> None:
            raise LegacyWeChatDependencyError(
                'No supported Windows WeChat automation library is installed.'
            )

    monkeypatch.setattr(smoke_module, 'LegacyWeChatAdapter', MissingBackendAdapter)
    monkeypatch.setattr(smoke_module.os, 'name', 'nt')
    monkeypatch.setattr(smoke_module.platform, 'platform', lambda: 'simulated-windows')
    monkeypatch.setattr(smoke_module.platform, 'python_version', lambda: 'simulated-python')
    monkeypatch.setattr(smoke_module.sys, 'argv', ['windows_wechat_smoke_test.py'])

    assert smoke_module.main() == 1
    output = capsys.readouterr().out
    assert '[FAIL] adapter.initialize' in output
    assert 'No supported Windows WeChat automation library is installed.' in output
