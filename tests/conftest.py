"""Shared pytest fixtures."""

import os
import re
from unittest import mock
from http.server import HTTPServer

import pytest
from hypothesis import settings

from pywemo import SubscriptionRegistry

settings.register_profile(
    "ci", max_examples=1000, deadline=1000.0  # Milliseconds
)
settings.load_profile("ci" if os.getenv("CI") else "default")


@pytest.fixture(scope="module")
def vcr_config():
    """VCR Configuration."""

    def scrub_identifiers(response):
        body = response["body"]["string"]
        body = re.sub(
            b"<serialNumber>[^<]+</serialNumber>",
            b"<serialNumber>SERIALNUMBER</serialNumber>",
            body,
        )
        body = re.sub(
            b"<SerialNo>[^<]+</SerialNo>",
            b"<SerialNo>SERIALNUMBER</SerialNo>",
            body,
        )
        body = re.sub(
            rb"uuid:([A-Z][a-z]+-\d_\d)-[A-Za-z0-9]+",
            rb"uuid:\1-SERIALNUMBER",
            body,
        )
        body = re.sub(
            b"<macAddress>[^<]+</macAddress>",
            b"<macAddress>001122334455</macAddress>",
            body,
        )
        body = re.sub(
            b"<MacAddr>[^<]+</MacAddr>",
            b"<MacAddr>001122334455</MacAddr>",
            body,
        )
        body = re.sub(
            b"<friendlyName>[^<]+</friendlyName>",
            b"<friendlyName>WeMo Device</friendlyName>",
            body,
        )
        body = re.sub(
            b"<hkSetupCode>[^<]+</hkSetupCode>",
            b"<hkSetupCode>012-34-567</hkSetupCode>",
            body,
        )
        response["body"]["string"] = body
        return response

    return {
        "before_record_response": scrub_identifiers,
        "match_on": [
            "method",
            "scheme",
            "host",
            "port",
            "path",
            "query",
            "body",
        ],
    }


@pytest.fixture(scope="module")
def vcr_cassette_dir(request):
    """Specify the location for the VCR cassettes."""
    # Put all cassettes in tests/vcr/{module}/{test}.yaml
    return os.path.join("tests/vcr", request.module.__name__)


@pytest.fixture()
def subscription_registry():
    """Fixture to simulate HTTPServer for the SubscriptionRegistry."""
    registry = SubscriptionRegistry()

    server = mock.create_autospec(HTTPServer, instance=True)
    server.server_address = ("localhost", 8989)
    with mock.patch("pywemo.subscribe._start_server", return_value=server):
        registry.start()
        yield registry

    registry.stop()
