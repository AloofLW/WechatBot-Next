import sys


def test_platform_neutral_adapter_package_does_not_load_windows_automation() -> None:
    import wechatbot.adapters.wechat  # noqa: F401

    forbidden = {'wxauto', 'wxautox', 'wxautox_wechatbot', 'win32gui', 'pythoncom'}
    assert forbidden.isdisjoint(sys.modules)
