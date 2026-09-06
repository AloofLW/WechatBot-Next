# Legacy WeChat adapter migration

## Migrated in phase one

`bot.py` now imports only project-owned adapter types, not wxauto-family packages. The adapter initializes the WeChat client once in `main()`, supplies the nickname, shows the client, converts callbacks into `InboundMessage`, registers listeners, checks listener names for keep-alive, keeps the client running, sends text/files, performs group lookup, acquires media, and executes voice/tap/recall actions.

This preserves `Run.bat`, the listener callback shape, recipient identifiers, retry loops, and existing send success/failure branches. The old wxautox_wechatbot → wxautox → wxauto fallback order is retained inside the adapter.

## Still direct in bot.py

There are no executable direct wxauto/wxautox client or raw-message method calls remaining in `bot.py`. It retains only project-owned `InboundMessage` fields and opaque message IDs. The former `raw_client` transitional property was removed after its last bot.py usage was migrated.

## Next order

1. Run the full capability matrix on a supported Windows client with `tools/windows_wechat_smoke_test.py` and record the selected library and WeChat versions.
2. Compare a current-client experimental adapter exclusively against the public `InboundMessage` and capability contract; do not add a raw-client escape hatch.
3. Move platform-neutral callback orchestration into an application service only when a behavior-preserving test suite covers the existing queue/AI/memory behavior.
4. Keep Windows acceptance coverage focused on the public Adapter contract so no raw-client escape hatch is reintroduced.

## Pre-current-client baseline

`tests/test_wechat_behavior_fixtures.py` supplies client-free fixtures for
private message ordering/self filtering/unknown types; group sender/session and
@ trigger behavior; image and emoji media paths; quote, URL, and merged-message
fallback; special capabilities; and adapter lifecycle. The fixtures deliberately
do not import `bot.py`, start WeChat, or invoke an AI provider.

The accompanying capability matrix is
[`WECHAT_CAPABILITY_MATRIX.md`](WECHAT_CAPABILITY_MATRIX.md). Its macOS Legacy
results use a mock legacy client and validate isolation/mapping only. They do
not replace a Windows client acceptance run.

No current-client/WeChat 4.x adapter is part of this migration.
