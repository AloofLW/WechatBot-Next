"""Check declared dependencies against source imports without importing the app."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMPORT_TO_REQUIREMENT = {
    'bs4': 'beautifulsoup4',
    'filelock': 'filelock',
    'flask': 'flask',
    'flask_cors': 'flask-cors',
    'flask_limiter': 'flask-limiter',
    'flask_wtf': 'flask-wtf',
    'lxml': 'lxml',
    'openai': 'openai',
    'psutil': 'psutil',
    'pyautogui': 'pyautogui',
    'requests': 'requests',
    'waitress': 'waitress',
    'werkzeug': 'werkzeug',
}
WINDOWS_AUTOMATION_IMPORTS = {'wxauto', 'wxautox', 'wxautox_wechatbot'}


def requirement_names() -> set[str]:
    names = set()
    for line in (ROOT / 'requirements.txt').read_text(encoding='utf-8').splitlines():
        line = line.split('#', 1)[0].strip()
        if line:
            names.add(re.split(r'[<>=!~\[]', line, maxsplit=1)[0].lower())
    return names


def imported_top_levels() -> set[str]:
    modules = set()
    for path in ROOT.rglob('*.py'):
        if any(part in {'.git', '__pycache__', 'tests', 'tools'} for part in path.parts):
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split('.', 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split('.', 1)[0])
    return modules


def main() -> int:
    requirements = requirement_names()
    imports = imported_top_levels()
    missing = sorted(
        requirement
        for module, requirement in IMPORT_TO_REQUIREMENT.items()
        if module in imports and requirement not in requirements
    )
    if missing:
        print(f'FAIL: requirements missing imported packages: {", ".join(missing)}')
        return 1

    detected_windows = sorted(imports & WINDOWS_AUTOMATION_IMPORTS)
    print('PASS: declared requirements cover audited cross-platform imports.')
    print(
        'INFO: Windows-only dynamic automation imports are intentionally separate: '
        + (', '.join(detected_windows) or 'none detected')
    )

    bundled_openai = sorted((ROOT / 'libs').glob('openai-*.whl'))
    if bundled_openai and 'openai==1.84.0' in (ROOT / 'requirements.txt').read_text(encoding='utf-8'):
        print(
            'WARNING: legacy bundled OpenAI wheel differs from requirements.txt; '
            'see docs/DEPENDENCY_BASELINE.md.'
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
