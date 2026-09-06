# Minimal WeChat adapter contract

The contract lives in `wechatbot.adapters.wechat.base`. It is intentionally platform-neutral and is not connected to `bot.py` in this baseline.

## Input and actions

- `InboundMessage` is the project-owned normalized input: conversation, sender, content, private/group kind, type, optional attachment path, and metadata.
- `WeChatAdapter` owns lifecycle, normalized message delivery, text/file sending, voice call, tap actions, and recall.
- `AdapterCapability` is the capability matrix key. Production adapters must expose only capabilities verified for their WeChat client/library version.
- Calling an unsupported action raises `CapabilityNotSupportedError`; callers must not interpret it as a successful no-op.

## Fake implementation

`FakeWeChatAdapter` is an in-memory, client-free implementation for macOS pytest. It records outbound `OutboundAction` values and delivers emitted normalized messages to the registered handler. Its default capability set is receive, text send, and file send; tests may provide a different set to validate capability-specific paths.

No real wxauto/wxautox implementation is included yet. The future legacy adapter must translate all raw library objects at its boundary and must not expose them to application services.
