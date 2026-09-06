# Dependency baseline

## Source of truth today

`requirements.txt` remains the production dependency declaration. It is intentionally unchanged in this baseline: no dependency was upgraded or downgraded without Windows verification. `requirements-dev.txt` adds the macOS/client-free test dependency only.

## Import reconciliation

The main runtime imports Flask, Flask-CORS, Flask-WTF, Flask-Limiter, Waitress, OpenAI, Requests, BeautifulSoup, lxml, Pillow, psutil, filelock, pyautogui, and Windows support through pywin32/comtypes. `sqlalchemy` and `pyperclip` are declared but have no import in the audited main Python source; keep them until a Windows dependency audit confirms they are unnecessary.

The runtime dynamically imports `wxautox_wechatbot`, `wxautox`, or `wxauto`, but none is declared in `requirements.txt`. They are Windows-only automation dependencies and must be version-pinned only after testing a specific Windows Python + WeChat client + adapter combination. Do not install, resolve, or lock them from macOS.

## OpenAI wheel conflict

`requirements.txt` requires `openai==1.84.0`, while `libs/` contains `openai-1.61.1-py3-none-any.whl`. The declared requirement is authoritative for normal online installation; the bundled wheelhouse is not a reproducible offline install set. Do not use the old wheel as a fallback for 1.84.0.

Before a Windows release, create a clean, pinned Windows wheelhouse from the selected requirements and validate it with the supported Python version. This must include a separately recorded automation-library version and its tested capability matrix. Until then, the `libs/` directory is legacy cache content, not a lockfile.

## Commands

For macOS development tests, install `requirements-dev.txt` in an isolated environment. Do not install or import the real WeChat automation packages on macOS. Windows CI may install the non-client test/build dependency set; real UI tests remain an explicit Windows-machine or VM acceptance step.
