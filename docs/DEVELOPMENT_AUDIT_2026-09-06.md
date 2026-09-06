# Development-preparation audit — 2026-09-06

## Scope and evidence

This is a source audit of the current working directory. It does not change business logic or migrate WeChat support. The directory does not contain `.git`, so repository history, tracked-file status, and `git diff --check` cannot be assessed here.

## Platform contract: macOS development, Windows production

Windows is the final target platform. It alone is responsible for running the real WeChat client and production adapter, receiving/sending private and group messages, media and special capabilities, release packaging, and final acceptance. macOS is only for source editing, Git, pytest, the fake adapter, and platform-neutral AI, memory, scheduling, and WebUI tests.

Future platform-neutral modules must not import `wxauto`, `wxautox`, `wxautox_wechatbot`, Win32 APIs, COM, or UI automation either directly or transitively. These imports belong in a Windows adapter/infrastructure boundary and must be delayed until that adapter is explicitly selected on Windows. A macOS `pytest` run must work with neither WeChat nor Windows-only packages installed. Do not run or simulate a real wxauto/wxautox client on macOS.

The fake adapter is a required macOS test implementation. It must deterministically exercise inbound private/group messages, outbound text/file actions, attachment metadata, capability failures, and application-level processing. It is not permission to remove or reduce production Windows capabilities.

### Windows acceptance flow

1. Confirm the supported Python version and install the pinned production dependencies.
2. Start the current supported/latest-target WeChat client and initialize the selected production adapter.
3. Verify private-message receive and send, then group receive and send.
4. Verify image/file handling and each special feature individually against the adapter capability matrix: voice, recall, and tap where supported.
5. Run a stable-operation observation test, then build and validate both EXE and ZIP release outputs.

### CI reservation

Add a Windows GitHub Actions workflow when the test/build baseline is introduced. It must install dependencies, run Python syntax checks, run only pytest cases not requiring a live WeChat client, execute the PyInstaller build, and upload artifacts. Real WeChat UI automation is an explicit physical-Windows-machine or VM acceptance task, not a GitHub Actions requirement.

## Current architecture

```text
Run.bat
  -> updater.py -> config_editor.py (Flask/Waitress WebUI)
                    | start_bot subprocess
                    v
                  bot.py
                    |-- config.py (Python source configuration, dynamically reread in places)
                    |-- wxautox_wechatbot -> wxautox -> wxauto (dynamic import fallback)
                    |-- OpenAI-compatible clients (main / assistant / online)
                    |-- prompts/*.md, chat_contexts.json, Memory_Temp/, CoreMemory/
                    |-- reminder/timer, proactive-message, restart, heartbeat threads
                    `-- local HTTP log/heartbeat calls to config_editor.py
```

`bot.py` is both the composition root and the application: it receives platform callbacks, detects group policy, parses media and commands, queues work, calls models, persists memory, schedules reminders, sends messages, and owns lifecycle threads. `config_editor.py` is both the WebUI and a process/config/data-management service.

### Startup and feature flow

1. `Run.bat` rejects WeChat major version 4 or above, installs unpinned dependencies plus the automation libraries, invokes `updater.py`, then runs `config_editor.py`.
2. The WebUI parses and rewrites `config.py`; it starts `bot.py` in a subprocess and receives log batches/heartbeats over localhost.
3. Importing `bot.py` already imports and instantiates `WeChat`, reads `wx.nickname`, constructs OpenAI clients, and configures logging. `main()` instantiates `WeChat` again, shows it, registers listeners, then starts daemon threads.
4. The listener turns raw WeChat message objects into queued input; inactivity processing calls the main model (and optionally the online model), then sends typed actions.

### AI, prompt, memory, scheduling, and media

- Main, assistant, online, and forum calls use `openai.OpenAI` with configurable OpenAI-compatible base URLs in `bot.py` and `config_editor.py`.
- Prompts are Markdown files selected by `LISTEN_LIST`; `get_user_prompt()` merges prompt-based and JSON core memories.
- Context is persisted in `chat_contexts.json`; temporary transcripts are stored in `Memory_Temp/`; core memory uses `CoreMemory/` or prompt edits.
- Timers use `threading.Timer` for short reminders and `recurring_reminders.json` plus a polling thread for recurring/long reminders. Proactive messages are per-user countdowns persisted in `user_timers.json`.
- URL extraction uses `requests`, BeautifulSoup, and lxml; online search is delegated to a configured model rather than a direct search SDK.
- Image and animated-emotion messages are downloaded/captured through the automation message object, recognized by the configured Moonshot-compatible client, then temporary wxautox files are removed. Voice relies on the client object's `to_text()`; outbound voice is a WeChat voice-call operation, not audio synthesis.

## WeChat automation coupling inventory

| Location | Current dependency / object contract | Impact |
| --- | --- | --- |
| `bot.py:35-45` | Dynamic imports: `wxautox_wechatbot.WeChat`, then `wxautox.WeChat`, then `wxauto.WeChat`; provider-specific `WxParam` is configured only for the first. | No declared adapter contract or compatibility tests; fallbacks must expose the same undocumented surface. |
| `bot.py:530-536`, `4528-4532` | `WeChat()` is constructed at module import and again in `main()`; uses `.nickname` and `.Show()`. | Import has Windows/WeChat side effects and prevents isolated tests. |
| `bot.py:620-688` | `wx.GetAllSubWindow()`, `chat.ChatInfo()`, `chat.who` determine group chat. | Group classification depends on window/UI internals. |
| `bot.py:1248-1283`, `4539-4542`, `4617` | `wx.listen`, `wx.AddListenChat(..., callback=message_listener)`, `wx.KeepRunning()`. | Listener lifecycle is tied directly to wx object state and callback shape. |
| `bot.py:1289-1498` | Callback reads/writes raw `msg`/`chat`: `.who`, `.type`, `.content`, `.sender`, `.attr`, `.to_text()`, `.get_url()`, `.quote_content`, `.get_messages()`. | Application/group-policy code consumes library objects directly and mutates `msg.content`. |
| `bot.py:2016-2068` | Images use `msg.download()`; animated emotions use `msg.capture()`. | File acquisition/temp paths are provider-specific. |
| `bot.py:2321`, `2381` | `wx.SendFiles(filepath, who)` and `wx.SendMsg(msg, who)` with retry logic. | Sending semantics and recipient identifiers leak into reply orchestration. |
| `bot.py:1301-1307`, `2331-2376` | Raw message objects are retained for `.tickle()` and `.select_option('撤回')`; self messages are used to locate the last bot message. | Special actions require opaque UI elements and Chinese UI text. |
| `bot.py:3796`, `4034` | `wx.VoiceCall(user_id)`. | Reminder domain logic invokes the library directly. |
| `bot.py:2651-2657` | Deletes literal `wxautox文件下载/`. | Provider-owned filesystem convention leaks into generic cleanup. |
| `diagnostic_standalone/{diagnostic_tool.py,safe_send_script.py}` | Imports `wxautox_wechatbot` directly and tests live processes/interactions. | Diagnostics are not provider-neutral and are not a safe automated test suite. |

## Recommended adapter boundary and target layout

Introduce a small capability-based interface first, without moving business logic wholesale:

```text
src/wechatbot/
  app/                 # orchestration/use cases: receive, reply, reminders, proactive messages
  domain/              # Message, Conversation, Attachment, SendAction, capabilities/errors
  adapters/
    wechat/
      base.py           # WeChatAdapter protocol
      wxauto_legacy.py  # all wxauto/wxautox imports and object translation
      fake.py            # deterministic test adapter
  ai/                   # provider clients and retry policy
  memory/               # context/core-memory repositories
  scheduling/           # reminder and proactive-message services
  infrastructure/       # config, file storage, HTTP/logging
  webui/                # Flask routes/templates integration
  bootstrap.py          # composition root replacing bot.py startup gradually
tests/
  unit/ integration/ contract/
```

The initial `WeChatAdapter` should expose: `start(on_message)`, `listen(conversation)`, `list_conversations()`, `send_text()`, `send_file()`, `voice_call()`, `tap_last_inbound()`, `tap_last_outbound()`, and `recall_last_outbound()`. Its inbound callback must translate to a project-owned immutable `InboundMessage`, with optional capability handles stored inside the adapter rather than leaked to application code. Model special actions as `SendAction`s; the adapter reports unsupported capabilities rather than silently failing.

## Dependencies and platform assessment

`requirements.txt` is a direct-dependency list without hashes or complete pins. It does **not** declare `wxautox_wechatbot`, `wxautox`, or `wxauto`; `Run.bat` separately installs the latest two packages. That makes WeChat compatibility unreproducible.

| Dependency | Assessment |
| --- | --- |
| `wxautox_wechatbot`, `wxautox`, `wxauto` | WeChat-version-critical, dynamically imported but absent from `requirements.txt`; first two are described as private in `DEPENDENCIES.txt`; `Run.bat` upgrades them without a version pin. |
| `pywin32`, `comtypes`, `pyautogui` | Windows/UI-automation-specific. `pyautogui` is imported by `bot.py`; the others support Windows/process/UI paths. |
| `openai==1.84.0` | The only exact pin. Bundled `libs/` contains `openai-1.61.1`, so offline installation can conflict with the declared requirement. Any upgrade needs response-schema/retry/API compatibility tests. |
| `flask`, `flask-cors`, `flask-wtf`, `flask-limiter`, `waitress`, `werkzeug` | Unpinned WebUI/security stack. Upgrades can change session, CSRF, rate-limit and serving behaviour. The bundled wheels omit `flask-wtf` and `flask-limiter`, so the local wheel set is incomplete. |
| `sqlalchemy~=2.0.37` | Allows newer 2.0 releases; no SQLAlchemy import is present in the main Python entry files audited, so its necessity should be verified before keeping. |
| `requests`, `beautifulsoup4`, `lxml`, `Pillow` | Network/media parsing dependencies; all are unpinned. Parser upgrades need URL/media fixture tests. |
| `psutil`, `filelock`, `typing-extensions`, `pyperclip` | `psutil`/`filelock` are used; `pyperclip` has no import in the main Python source audited and should be verified before keeping. |

## Test baseline required before refactoring

There is no `tests/`, `pyproject.toml`, `tox`, or pytest/unittest suite. `diagnostic_standalone` is an operational Flask diagnostic and can inspect a live WeChat process; it is not a hermetic regression suite.

Before adapter extraction, add a pinned test environment and fixtures, then cover: configuration parsing/migration; prompt-memory merge and file safety; message normalization for every raw type; private/group trigger matrix; message/action segmentation; reminder parsing/persistence/quiet-time rules; URL fetching with mocked HTTP; model client retries with mocked OpenAI responses; and adapter contract tests against a fake. Keep a manually invoked Windows smoke matrix for supported WeChat/client-library combinations, with sending disabled by default.

The test split is mandatory: macOS runs pytest with the fake adapter and no Windows-only imports; Windows CI runs the same client-free suite plus packaging; Windows hardware or VM executes the real-client acceptance flow and capability matrix.

## Security, documentation, and repository hygiene

- `LICENSE` is GPL-3.0-or-later and identifies the project/original authors; `LICENSE_COMPLIANCE.md` and `DEPENDENCIES.txt` document the private-library assumption. This is a legal/distribution review point because the private libraries are not reproducibly declared in `requirements.txt`.
- `readme.md` says the project is stopped/unsupported, while this audit's purpose is long-term maintenance; its supported WeChat/Python/version statements should be reconciled before a new maintenance release.
- `config.py` currently has blank API-key fields, but it is the live editable configuration and stores `LOGIN_PASSWORD` in plaintext (default `123456`, with `PASSWORD_IS_VALID=False`). It is an immediate future commit risk once configured.
- Runtime user data is written under the project root (`chat_contexts.json`, `Memory_Temp/`, `CoreMemory/`, `user_timers.json`, `recurring_reminders.json`, `forum_data/`) and there was no `.gitignore`. The new ignore rules cover these generated/private paths; no Git metadata is present to establish whether any existing state file was historically tracked.
- The source scan found no non-empty API-key assignment in `config.py` and `recurring_reminders.json` is `[]` at audit time. This is not a credential-history scan because `.git` is absent.

## Top technical debt (priority order)

1. `bot.py` combines platform, domain, persistence, AI, scheduling, and lifecycle responsibilities in one ~4.6k-line module.
2. The automation library has no project-owned interface; raw wx objects flow through listener, group, media, send, tap, recall, and reminder code.
3. `bot.py` has WeChat initialization at import time and performs a second initialization in `main()`, blocking isolated import/testing and risking divergent state.
4. `Run.bat` explicitly rejects WeChat 4.x and forces latest automation-library installation, while the supported API surface is undocumented and unpinned.
5. Dependency installation is non-reproducible: incomplete, mostly unpinned requirements; undeclared automation dependencies; bundled wheels that conflict with requirements.
6. No hermetic automated test suite or compatibility contract exists; existing diagnostics can depend on a live client and real interaction.
7. Python-source `config.py` is mutable at runtime, re-parsed by regex/AST in separate components, and stores sensitive operational values in plaintext.
8. User data, logs, and generated state share the source root; the worktree initially lacked `.gitignore`.
9. Shared mutable globals and multiple daemon/polling threads coordinate queues, sending, timers, context, restarts, and lifecycle without a single supervisor or explicit shutdown protocol.
10. Special actions retain opaque raw UI message objects and depend on Chinese menu text (`'撤回'`), making them fragile across client versions/locales.

## Phased plan for current-WeChat support

1. **Baseline:** introduce Git hygiene, pinned environments, CI-safe tests, a macOS-capable fake adapter, fixtures, Windows GitHub Actions build/artifacts, and a Windows smoke-test matrix; document the currently supported legacy client/library tuple.
2. **Boundary:** add domain message/action types and a fake `WeChatAdapter`; route new tests through it while preserving `bot.py` behaviour.
3. **Legacy encapsulation:** move all three dynamic imports, client initialization, callback translation, media acquisition, and special UI actions into `wxauto_legacy.py`; make `bot.py` call the adapter only.
4. **Application extraction:** move queue/reply orchestration, media recognition, memory, scheduling, and AI providers into focused services without changing configuration semantics.
5. **Current-client prototype:** implement a separate adapter for the newest supported WeChat automation mechanism. Feature-detect and publish a capability matrix; do not claim parity for tap/recall/voice until verified.
6. **Compatibility rollout:** select adapters explicitly through version/capability detection, retain the legacy adapter as a supported fallback, run smoke tests, then only deprecate it after documented migration and telemetry-free user validation.

## Checks performed for this audit

- Enumerated source, templates, scripts, bundled wheels, and state files.
- Read architecture entry points, configuration, prompt assets, diagnostics, dependency declarations, README and license files.
- Searched WeChat automation imports/method use, test tooling, runtime-data paths, and credential-bearing configuration fields.
- Python syntax compilation and `git diff --check` are recorded in the final report after audit-document changes.
