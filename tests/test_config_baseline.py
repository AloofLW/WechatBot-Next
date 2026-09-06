import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SENSITIVE_FIELDS = {
    'DEEPSEEK_API_KEY',
    'MOONSHOT_API_KEY',
    'ONLINE_API_KEY',
    'ASSISTANT_API_KEY',
    'FORUM_API_KEY',
    'LOGIN_PASSWORD',
}
REQUIRED_TEMPLATE_SETTINGS = {
    'LISTEN_LIST',
    'DEEPSEEK_API_KEY',
    'DEEPSEEK_BASE_URL',
    'MODEL',
    'MAX_GROUPS',
    'ENABLE_MEMORY',
    'CORE_MEMORY_DIR',
    'ENABLE_REMINDERS',
    'ENABLE_ONLINE_API',
    'ENABLE_ASSISTANT_MODEL',
    'ENABLE_FORUM_CUSTOM_MODEL',
    'ALLOW_OPEN_PORT',
    'LOGIN_PASSWORD',
    'PASSWORD_IS_VALID',
    'PORT',
}


def _assignments(path: Path) -> dict[str, object]:
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                values[target.id] = ast.literal_eval(node.value)
    return values


def test_config_example_contains_required_runtime_settings() -> None:
    example_settings = _assignments(ROOT / 'config.example.py')

    assert REQUIRED_TEMPLATE_SETTINGS.issubset(example_settings)


def test_config_example_contains_no_credentials() -> None:
    example_settings = _assignments(ROOT / 'config.example.py')

    assert {field: example_settings[field] for field in SENSITIVE_FIELDS} == {
        field: '' for field in SENSITIVE_FIELDS
    }
    assert example_settings['PASSWORD_IS_VALID'] is False
