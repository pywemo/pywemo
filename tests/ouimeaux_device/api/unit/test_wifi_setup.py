"""Unit tests for wifi_setup.py."""

import pytest

from pywemo.ouimeaux_device.api import wifi_setup


@pytest.mark.parametrize(
    "password, key, salt, iv, expected",
    [
        (
            "password",
            "XXXXXX123456A1234567XXXXXXb3{8t;80dIN{ra83eC1s?M70?683@2Yf",
            "XXXXXX12",
            "XXXXXX123456A123",
            "x/ef1yCNTONuU+ZT3c4kAg==",
        ),
        (
            "password",
            "XXXXXX123456A1234567XXXXXX",
            "XXXXXX12",
            "XXXXXX123456A123",
            "SQj7n2iACdGZnHNrbLM72w==",
        ),
    ],
)
def test_encrypt_password(
    password: str, key: str, salt: str, iv: str, expected: str
):
    """Test encrypt_password method."""
    assert wifi_setup.encrypt_password(password, key, salt, iv) == expected
