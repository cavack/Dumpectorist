import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_safe_settings_are_valid():
    settings = Settings(
        _env_file=None,
        enable_live_actions=False,
        max_leverage=5,
    )

    assert settings.enable_live_actions is False
    assert settings.max_leverage == 5


def test_live_actions_are_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, enable_live_actions=True)


@pytest.mark.parametrize("value", [0, 6])
def test_invalid_leverage_is_rejected(value: int):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, max_leverage=value)


@pytest.mark.parametrize("value", [0, 65536])
def test_invalid_api_port_is_rejected(value: int):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, api_port=value)
