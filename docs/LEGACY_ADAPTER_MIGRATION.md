# Legacy WeChat adapter migration

## Migrated in phase one

`bot.py` now imports only `LegacyWeChatAdapter`, not wxauto-family packages. The adapter initializes the WeChat client once in `main()`, supplies the nickname, shows the client, registers the existing callback, checks listener names for keep-alive, keeps the client running, and sends text/files.

This preserves `Run.bat`, the listener callback shape, recipient identifiers, retry loops, and existing send success/failure branches. The old wxautox_wechatbot → wxautox → wxauto fallback order is retained inside the adapter.

## Still direct in bot.py

The following old paths still require the temporary `wx` raw-client reference or raw callback objects:

| Area | Current direct dependency |
| --- | --- |
| Group detection | `wx.GetAllSubWindow()`, `chat.ChatInfo()`, `chat.who` |
| Callback processing | `msg.type`, `msg.content`, `msg.sender`, `msg.attr`, `msg.to_text()`, `msg.get_url()`, `msg.quote_content`, `msg.get_messages()` |
| Media recognition input | `msg.download()` and `msg.capture()` |
| Special actions | retained raw message `.tickle()` and `.select_option('撤回')` handles |
| Reminder voice call | `wx.VoiceCall()` in short and recurring reminder flows |

## Next order

1. Change the listener bridge to pass `InboundMessage` into a new message-normalization service while preserving command/group behaviour with fixtures.
2. Migrate group classification and media extraction to adapter methods.
3. Move stored self/inbound message handles, tap, recall, and voice reminders to adapter methods.
4. Remove the temporary `wx_adapter.raw_client` escape hatch only after every row above has adapter tests and Windows acceptance coverage.

No current-client/WeChat 4.x adapter is part of this migration.
