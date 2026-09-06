# Minimal WeChat adapter contract

The contract lives in `wechatbot.adapters.wechat.base`. It is intentionally platform-neutral. The first legacy migration wires only bot startup, listener registration/keep-alive, and text/file sending through the adapter; raw-message business handling remains transitional.

## Input and actions

- `InboundMessage` is the project-owned normalized input: opaque `message_id`, conversation and sender IDs, private/group kind, normalized `MessageType`, content, self/friend/tickle flags, quote, URL, optional attachment path, timestamp, forwarded-message entries/fallback, and metadata. None of these fields names a wxauto class or exposes a raw object.
- `WeChatAdapter` owns lifecycle, normalized message delivery, text/file sending, voice call, tap actions, and recall.
- `AdapterCapability` is the capability matrix key. Production adapters must expose only capabilities verified for their WeChat client/library version.
- Calling an unsupported action raises `CapabilityNotSupportedError`; callers must not interpret it as a successful no-op.

## Fake implementation

`FakeWeChatAdapter` is an in-memory, client-free implementation for macOS pytest. It records outbound `OutboundAction` values and delivers emitted normalized messages to the registered handler. Its default capability set is receive, text send, and file send; tests may provide a different set to validate capability-specific paths.

## Legacy implementation

`LegacyWeChatAdapter` dynamically attempts `wxautox_wechatbot`, `wxautox`, then `wxauto` only when `initialize()` or `start()` runs. Importing the module does not load any of those packages. It owns instance construction, `Show`, `AddListenChat`, listener inspection, group lookup, `KeepRunning`, text/file sending, voice call, normalized message conversion, media download/capture, URL/quote extraction, tap, and recall. Missing dependencies raise `LegacyWeChatDependencyError`; unavailable client/message operations raise `CapabilityNotSupportedError`.

The legacy adapter keeps raw message objects as private opaque handles keyed by `InboundMessage.message_id`. `normalize_message()` exposes only project-owned data. The bot now uses the normalized callback path; no raw callback bridge is used by `bot.py`.

## Capability matrix

| Capability | Legacy adapter behavior |
| --- | --- |
| Receive/listen/show/keep-running | Delegates when the selected legacy client exposes the corresponding method. |
| Text/file send and voice call | Delegates to `SendMsg`, `SendFiles`, and `VoiceCall`; absent methods raise `CapabilityNotSupportedError`. |
| Group lookup | Delegates to `GetAllSubWindow`/`ChatInfo`; missing method raises `CapabilityNotSupportedError`, unknown conversation returns `None`. |
| Media/URL/quote | Uses the opaque message ID to access the internally retained legacy message. |
| Tap/recall | Uses retained handles; recall preserves the existing Chinese `撤回` menu action. Missing handle/method raises `CapabilityNotSupportedError`. |
