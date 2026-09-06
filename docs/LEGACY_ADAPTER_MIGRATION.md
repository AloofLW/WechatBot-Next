# Legacy WeChat adapter migration

## Migrated in phase one

`bot.py` now imports only project-owned adapter types, not wxauto-family packages. The adapter initializes the WeChat client once in `main()`, supplies the nickname, shows the client, converts callbacks into `InboundMessage`, registers listeners, checks listener names for keep-alive, keeps the client running, sends text/files, performs group lookup, acquires media, and executes voice/tap/recall actions.

This preserves `Run.bat`, the listener callback shape, recipient identifiers, retry loops, and existing send success/failure branches. The old wxautox_wechatbot → wxautox → wxauto fallback order is retained inside the adapter.

## Still direct in bot.py

There are no executable direct wxauto/wxautox client or raw-message method calls remaining in `bot.py`. It retains only project-owned `InboundMessage` fields and opaque message IDs. The former `raw_client` transitional property was removed after its last bot.py usage was migrated.

## Next order

1. Add fixture-based behavior tests for group triggers, merged-message images, and special actions before extracting the remaining callback orchestration from `bot.py`.
2. Move platform-neutral callback orchestration into an application service while retaining the existing queue/AI/memory behavior.
3. Run the full capability matrix on a supported Windows client and record the selected library versions.
4. Keep Windows acceptance coverage focused on the public Adapter contract so no raw-client escape hatch is reintroduced.

No current-client/WeChat 4.x adapter is part of this migration.
