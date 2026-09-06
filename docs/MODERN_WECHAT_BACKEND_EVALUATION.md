# Modern Windows WeChat backend evaluation

Research date: 2026-09-06. This document records public upstream claims and
repository inspection only. `PASS` is reserved for this project's tests or a
recorded Windows acceptance run; every real-client capability below is
`NOT_TESTED` until then.

## Recommendation

Use **`fanyuantaier/wechatauto-replica` only as the Modern Adapter PoC
backend**, behind `ModernWeChatAdapter`. It is the best functional match among
the inspected candidates because it explicitly targets Windows 10/11, Python
3.9+, and WeChat 4.1.12+, and combines database-backed listening with a
separate send path. The upstream project describes version 1.2.0.3 in its
repository metadata, while the indexed PyPI 1.1.1 page is older; Windows
experimentation must record the exact installed distribution and commit rather
than assume the two are interchangeable.

This is not a production endorsement. The maintainer says future maintenance
time will be limited, and the backend reads encrypted local data, scans WeChat
process memory, and writes a Qt accessibility flag in `Weixin.dll`. A Windows
security/compliance review and manual acceptance are prerequisites for any
default-adapter decision. Sources: [upstream README](https://github.com/fanyuantaier/wechatauto-replica), [upstream package metadata](https://github.com/fanyuantaier/wechatauto-replica/blob/main/pyproject.toml), and [PyPI package page](https://pypi.org/project/wechatauto-replica/1.1.1/).

## Candidate summary

| Candidate | Stated client support | Windows / Python | Installation / license | Maintenance signal | Selection result |
| --- | --- | --- | --- | --- | --- |
| Existing Legacy adapter | Historical wxautox family; not a WeChat 4.x solution | Windows target; exact runtime is local-machine dependent | Existing optional runtime packages; versions not locked | Project-owned compatibility layer | Retain as production default during PoC |
| `wechatauto-replica` | WeChat 4.1.12+ | Windows 10/11; Python 3.9+ (3.12 claimed verified) | Upstream package declares `wechatauto-replica` 1.2.0.3, Apache-2.0; Windows-only dependency graph | Explicit maintainer notice of limited time after school starts | **Recommended PoC only** |
| Official `wxauto` v4 documentation | Current v4 documentation exists; exact compatible WeChat 4.x client version was not established in this review | Windows UI Automation | Activation-code purchase is documented; license/redistribution terms require separate procurement review | Official docs are active, but client compatibility is not established here | Do not select until commercial terms and 4.x behavior are verified |
| `chengamu/wechat-sdk` | README states WeChat 4.1.6–4.1.9 | Windows UIAutomation; Python requirement not established from reviewed README | `uv sync`; MIT shown by repository | Small visible community signal; selector profiles are version-specific | Secondary comparison only; stated range does not cover 4.1.12+ |
| `pywechat127` / pywechat fork | README states 4.1.4.10 partial support | Windows 10/11; Python 3.x | PyPI install is documented; license not verified in this review | Repository has history but no current 4.1.12 evidence reviewed | Not suitable for this PoC |

The `wechat-sdk` and pywechat details are based on their public repositories:
[wechat-sdk](https://github.com/chengamu/wechat-sdk) and
[pywechat fork](https://github.com/tianqixiangtian-ui/wechat). The official
wxauto documentation confirms a Windows UI Automation model and activation
workflow, but does not establish a compatible WeChat 4.x release in the
materials reviewed: [wxauto documentation](https://docs.wxauto.org/).

## Capability comparison

`DECLARED` means an upstream statement, not a project verification. For the
new implementation and every physical-client row, the correct status is
`NOT_TESTED` today.

| Capability | Legacy | wechatauto-replica | wxauto v4 | wechat-sdk | pywechat | Project result |
| --- | --- | --- | --- | --- | --- | --- |
| Private listener | Existing implementation; Windows `NOT_TESTED` | DECLARED | NOT_TESTED | DECLARED | DECLARED | Modern `NOT_TESTED` |
| Group listener / sender | Existing implementation; Windows `NOT_TESTED` | DECLARED; DB session model | NOT_TESTED | DECLARED listener, sender details `NOT_TESTED` | DECLARED | Modern `NOT_TESTED` |
| Global listener | `NOT_TESTED` | DECLARED by upstream demo (`--all`) | NOT_TESTED | `NOT_TESTED` | `NOT_TESTED` | Not in PoC |
| Text send | Existing implementation; Windows `NOT_TESTED` | DECLARED | NOT_TESTED | DECLARED | DECLARED | PoC code only; Windows `NOT_TESTED` |
| File send | Existing implementation; Windows `NOT_TESTED` | DECLARED | NOT_TESTED | DECLARED | DECLARED | Not in PoC |
| Image download | Existing implementation; Windows `NOT_TESTED` | DECLARED, AES-dependent | NOT_TESTED | `NOT_TESTED` | DECLARED save flow | Not in PoC |
| Emoji capture | Existing implementation; Windows `NOT_TESTED` | DECLARED | NOT_TESTED | `NOT_TESTED` | `NOT_TESTED` | Not in PoC |
| Quote / URL / merged messages | Existing implementation; Windows `NOT_TESTED` | `NOT_TESTED` per field | NOT_TESTED | NOT_TESTED | NOT_TESTED | Not in PoC |
| Tickle / recall / VoiceCall | Existing implementation; Windows `NOT_TESTED` | Tickle + voice declared; recall `NOT_TESTED` | NOT_TESTED | Voice declared; rest `NOT_TESTED` | Voice declared; rest `NOT_TESTED` | Not in PoC |
| Group query | Existing implementation; Windows `NOT_TESTED` | Session DB declared; query semantics `NOT_TESTED` | NOT_TESTED | DECLARED session/contact APIs | DECLARED group APIs | Not in PoC |

## `wechatauto-replica` technical and operational risks

| Area | Observed upstream approach | Risk / PoC requirement |
| --- | --- | --- |
| UIA path | Hot-activates Qt accessibility to expose `mmui::*` controls, then uses UIA first | `Weixin.dll` flag write is materially different from ordinary UI scripting. Require explicit security/compliance approval and test after each client update. |
| OCR / coordinates | OCR and coordinate fallback, per-machine layout calibration | Sensitive to DPI, scaling, window geometry, theme, lock screen, localization, and minor UI revisions. Test 100/125/150% DPI and locked/minimized states. |
| Local database | Decrypts local SQLCipher 4 databases and merges WAL data | Creates a local-data/privacy surface and can be sensitive to schema or encryption changes. Validate only against a test account and ensure caches stay ignored. |
| Process memory | Read-only scan for database keys; transient image AES key scan and persisted `image_keys.json` | Requires policy review and an explicit secrets/data-retention plan. Confirm where key/cache files are created before release. |
| Image handling | AES/XOR image decryption; original group image may require opening it first | Download success, thumbnail fallback, and user-visible UI side effects must be measured separately. |
| COM / threads | Listener callbacks run on per-chat worker threads; UI automation uses Windows components | COM initialization and thread-affinity behavior are **NOT_TESTED**. PoC must test callback isolation, stop/restart, and no deadlock under concurrent chats. |
| Native/runtime dependencies | Declares `uiautomation`, `pywin32`, `winsdk`, `pyautogui`, OpenCV, `imageio-ffmpeg`, crypto and process libraries | `ffmpeg` is declared through `imageio-ffmpeg`; whether a specific media action needs it is `NOT_TESTED`. Lock versions only after Windows validation. |
| Small-version drift | UIA uses binary/layout discovery and falls back to OCR/coordinates | Treat every WeChat update as a compatibility event; no capability is inherited automatically from 4.1.12. |

## PoC boundary and next evidence

`ModernWeChatAdapter` imports only the backend import name `wechatauto` during
Windows `initialize()`. It intentionally implements only current-user lookup,
one-text-session listener registration, raw-message normalization, text send,
lifecycle, and capability detection. It does not alter `bot.py`, the selected
startup adapter, requirements, or the existing WeChat 4.x launch restriction.

Before broadening the adapter, run `tools/windows_modern_wechat_poc.py` with a
disposable test contact. Record Windows version, Python, exact installed
distribution version, exact WeChat version, and the result in the capability
matrix. Do not store contact names, messages, media paths, message IDs, or
memory/database keys in Git.
