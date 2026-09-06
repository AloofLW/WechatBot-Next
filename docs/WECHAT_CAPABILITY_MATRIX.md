# WeChat capability matrix

This is the comparison baseline for a future current-client adapter. A status
means only what has been verified in the named environment; it is not a claim
about another WeChat client, adapter package, or platform.

| Capability | Fake | Legacy macOS Test | Legacy Windows | New Adapter |
| --- | --- | --- | --- | --- |
| Import without Windows packages | PASS | PASS | NOT_TESTED | NOT_IMPLEMENTED |
| Adapter lifecycle / one initialization | PASS | PASS (mock client) | NOT_TESTED | NOT_IMPLEMENTED |
| Normalized private text / self flag / unknown fallback | PASS | PASS (mock callback) | NOT_TESTED | NOT_IMPLEMENTED |
| Normalized group session and sender | PASS | PASS (mock callback) | NOT_TESTED | NOT_IMPLEMENTED |
| Listener registration / keep-running / Show | NOT_APPLICABLE | PASS (mock client) | NOT_TESTED | NOT_IMPLEMENTED |
| Text send | PASS | PASS (mock client) | NOT_TESTED | NOT_IMPLEMENTED |
| File send | PASS | PASS (mock client) | NOT_TESTED | NOT_IMPLEMENTED |
| Image download | PASS | PASS (mock message) | NOT_TESTED | NOT_IMPLEMENTED |
| Emoji capture | PASS | PASS (mock message) | NOT_TESTED | NOT_IMPLEMENTED |
| Quote and URL extraction | PASS (contract fixture) | PASS (mock message) | NOT_TESTED | NOT_IMPLEMENTED |
| Merged / forwarded-message fallback | PASS (contract fixture) | PASS (mock message) | NOT_TESTED | NOT_IMPLEMENTED |
| Group query | PASS | PASS (mock windows) | NOT_TESTED | NOT_IMPLEMENTED |
| Inbound/outbound tickle | PASS (capability fixture) | PASS (mock message) | NOT_TESTED | NOT_IMPLEMENTED |
| Recall | PASS (capability fixture) | PASS (mock message) | NOT_TESTED | NOT_IMPLEMENTED |
| Voice-call reminder | PASS (capability fixture) | PASS (mock client) | NOT_TESTED | NOT_IMPLEMENTED |
| Callback exception isolation | NOT_APPLICABLE | PASS (mock callback) | NOT_TESTED | NOT_IMPLEMENTED |

`NOT_APPLICABLE` means the adapter intentionally does not implement that
legacy client operation. `NOT_IMPLEMENTED` means no current-client adapter is
present. In particular, all Legacy Windows rows remain `NOT_TESTED` until a
Windows operator has completed the manual smoke test against an actual client.

## Windows record template

Record a completed run in the release/acceptance evidence, not in a chat log or
personal configuration. Do not record contacts, message text, nickname, local
media paths, or message IDs.

| Date | Windows version | Python | WeChat client | Provider selected | Provider version | Commit | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TBD | TBD | TBD | TBD | `wxautox_wechatbot` / `wxautox` / `wxauto` | TBD | TBD | NOT_TESTED |

The repository's legacy implementation may dynamically load only these
providers, in this priority order: `wxautox_wechatbot`, `wxautox`, then
`wxauto`. They are intentionally not locked from macOS. Their exact installed
versions and the compatible WeChat client version must be confirmed in the
Windows record above before a release claim is made.

## Manual acceptance command

On a prepared Windows test machine, with a logged-in supported legacy WeChat
client and a disposable contact/group chosen by the operator:

```powershell
python tools/windows_wechat_smoke_test.py --contact "<test contact>" --group "<test group>" --send --file "C:\path\to\disposable.txt" --special --voice --wechat-version "<observed version>"
```

The script first reports the operating system, Python version, selected
provider and provider version. It then waits at each receive/send/special step
for explicit operator confirmation. Without optional flags it runs only the
environment and initialization checks. It never persists the supplied contact,
group, nickname, text, message ID, or media path.

Use a non-production account and disposable content. `recall_outbound` is
reported as `NOT_TESTED` unless a self-sent text callback yields a valid opaque
message handle; this limitation is deliberate rather than an assumed success.
