# Minimal WeChat adapter contract

The contract lives in `wechatbot.adapters.wechat.base`. It is intentionally platform-neutral. The first legacy migration wires only bot startup, listener registration/keep-alive, and text/file sending through the adapter; raw-message business handling remains transitional.

## Input and actions

- `InboundMessage` is the project-owned normalized input: conversation, sender, content, private/group kind, type, optional attachment path, and metadata.
- `WeChatAdapter` owns lifecycle, normalized message delivery, text/file sending, voice call, tap actions, and recall.
- `AdapterCapability` is the capability matrix key. Production adapters must expose only capabilities verified for their WeChat client/library version.
- Calling an unsupported action raises `CapabilityNotSupportedError`; callers must not interpret it as a successful no-op.

## Fake implementation

`FakeWeChatAdapter` is an in-memory, client-free implementation for macOS pytest. It records outbound `OutboundAction` values and delivers emitted normalized messages to the registered handler. Its default capability set is receive, text send, and file send; tests may provide a different set to validate capability-specific paths.

## Legacy implementation

`LegacyWeChatAdapter` dynamically attempts `wxautox_wechatbot`, `wxautox`, then `wxauto` only when `initialize()` or `start()` runs. Importing the module does not load any of those packages. It owns instance construction, `Show`, `AddListenChat`, listener inspection, `KeepRunning`, text/file sending, voice call, normalized message conversion, media download/capture, URL/quote extraction, tap, and recall. Missing dependencies raise `LegacyWeChatDependencyError`; unavailable client/message operations raise `CapabilityNotSupportedError`.

The legacy adapter keeps raw message objects as private opaque handles. `normalize_message()` exposes only the project-owned `InboundMessage` and an opaque identifier in metadata. The raw listener bridge is temporary so the unchanged legacy message handler can continue to receive its existing callback arguments.
