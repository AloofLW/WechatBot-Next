# Configuration security transition

## Current arrangement

`config.py` remains the runtime configuration file so the existing application and WebUI continue to work unchanged. It is now intentionally ignored by Git. `config.example.py` is the complete, credential-free, tracked template.

Existing installations keep their current `config.py`; no automatic migration or configuration rewrite occurs in this baseline. New clones must copy `config.example.py` to `config.py` before starting the WebUI or bot, then set API keys and the WebUI password only in that local file.

## Rules

- Never stage `config.py`, `.env*`, `config.local.py`, or private backups.
- API keys and `LOGIN_PASSWORD` must remain blank in `config.example.py`.
- The WebUI continues to read and update `config.py`; do not point it at the example file.
- Before every commit, run the sensitive-information scan documented in `docs/DEVELOPMENT_AUDIT_2026-09-06.md` and inspect `git status`.
- A future structured configuration migration must read legacy `config.py` first and preserve all existing setting names or provide an explicit migration.

## First-time setup

On macOS or Windows, copy the example file using the platform's normal file-copy operation, edit the resulting local `config.py`, and keep it outside commits. On Windows, continue using the existing `Run.bat` flow after this local configuration file exists.
