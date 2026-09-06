"""Ensure the Windows hand-off tool stays harmless on macOS."""

import subprocess
import sys
from pathlib import Path


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
