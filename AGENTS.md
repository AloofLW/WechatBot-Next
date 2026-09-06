# WeChatBot development conventions

## Scope and preservation

- Read the relevant code paths, configuration, and user-visible behaviour before changing a file.
- Keep changes narrowly scoped to the assigned task. Do not perform unrelated large refactors or formatting sweeps.
- Do not remove, disable, or silently change an existing feature unless the task explicitly requires it. Preserve behaviour with tests or documented compatibility decisions.

## Architecture direction

- Treat `bot.py` as a legacy composition root, not a destination for new feature logic. Put new responsibilities in focused modules and keep `bot.py` delegating to them.
- Decouple WeChat automation incrementally through a `WeChatAdapter` interface. Application logic must consume domain messages and adapter capabilities, not `wxauto`/`wxautox` objects.
- Keep adapter-specific types, imports, callbacks, UI automation details, and version workarounds inside adapter implementations.
- When changing configuration structure or names, provide a documented migration path, preserve old configuration where practical, and test both old and new forms before removing compatibility.

## Platform contract

- Windows is the production target. Real WeChat, the production `WeChatAdapter`, all message/media/special capabilities, packaging, and release acceptance are validated on Windows.
- macOS is a development-only environment for editing, Git, pytest, fake-adapter tests, and platform-neutral AI, memory, scheduling, and WebUI work. Do not attempt to run or simulate a real wxauto/wxautox WeChat client on macOS.
- Keep all Windows-only imports (`wxauto`, `wxautox`, `wxautox_wechatbot`, Win32 APIs, COM/UI automation) in Windows adapter or infrastructure modules. Use delayed imports and/or an explicit platform check at the adapter boundary.
- Platform-neutral modules must never import Windows-only modules transitively. `pytest` on macOS must run without a Windows WeChat package or client installed.
- The fake adapter must run fully on macOS and cover inbound messages, outbound actions, group/private cases, media metadata, and unsupported-capability responses. Never weaken or remove Windows behaviour merely to make macOS tests pass.
- Preserve a capability matrix per production adapter. Verify private/group receive/send, images/files, voice, recall, and tap separately; do not infer a capability from another adapter or client version.

## Windows acceptance and CI

- Before a release, run the documented Windows acceptance flow: Python-version confirmation; dependency installation; current WeChat start; adapter initialization; private receive/send; group receive/send; image/file flow; every supported special capability; stable-run observation; and EXE/ZIP packaging.
- Reserve Windows GitHub Actions for dependency installation, Python syntax checks, tests that do not require a live WeChat client, PyInstaller build, and artifact upload. Real WeChat UI automation remains an opt-in Windows physical-machine or VM acceptance test.

## Data and security

- Never commit API keys, access tokens, passwords, cookies, chat contexts, memory files, reminders containing user data, logs, downloaded media, or private forum data.
- Do not log full prompts, user messages, model responses, or credentials unless the task explicitly requires a secure diagnostic path.
- Treat every URL, imported backup, uploaded file, and externally supplied model response as untrusted input.

## Verification and handoff

- Run the checks and tests appropriate to the changed surface before finishing. Add or update tests when behaviour changes.
- For WeChat work, use a fake adapter for automated tests; real-client smoke tests must be explicit, opt-in, and must not send a real message by default.
- In every final report list: modified files, checks/tests and their results, and known issues or unverified paths.
