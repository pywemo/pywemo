import os
import re
import unittest.mock as mock
from http.server import HTTPServer

import pytest

from pywemo import SubscriptionRegistry


@pytest.fixture(scope='module')
def vcr_config():
    def scrub_identifiers(response):
        body = response['body']['string']
        body = re.sub(
            b'<serialNumber>[^<]+</serialNumber>',
            b'<serialNumber>SERIALNUMBER</serialNumber>',
            body,
        )
        body = re.sub(
            b'<SerialNo>[^<]+</SerialNo>',
            b'<SerialNo>SERIALNUMBER</SerialNo>',
            body,
        )
        body = re.sub(
            br'uuid:([A-Z][a-z]+-\d_\d)-[A-Za-z0-9]+',
            br'uuid:\1-SERIALNUMBER',
            body,
        )
        body = re.sub(
            b'<macAddress>[^<]+</macAddress>',
            b'<macAddress>001122334455</macAddress>',
            body,
        )
        body = re.sub(
            b'<MacAddr>[^<]+</MacAddr>',
            b'<MacAddr>001122334455</MacAddr>',
            body,
        )
        body = re.sub(
            b'<friendlyName>[^<]+</friendlyName>',
            b'<friendlyName>WeMo Device</friendlyName>',
            body,
        )
        body = re.sub(
            b'<hkSetupCode>[^<]+</hkSetupCode>',
            b'<hkSetupCode>012-34-567</hkSetupCode>',
            body,
        )
        response['body']['string'] = body
        return response

    return {
        'before_record_response': scrub_identifiers,
        'match_on': [
            'method',
            'scheme',
            'host',
            'port',
            'path',
            'query',
            'body',
        ],
    }


@pytest.fixture(scope='module')
def vcr_cassette_dir(request):
    # Put all cassettes in tests/vcr/{module}/{test}.yaml
    return os.path.join('tests/vcr', request.module.__name__)


@pytest.fixture
def subscription_registry():
    registry = SubscriptionRegistry()

    server = mock.create_autospec(HTTPServer, instance=True)
    server.server_address = ('localhost', 8989)
    with mock.patch("pywemo.subscribe._start_server", return_value=server):
        registry.start()
        yield registry

    registry.stop()
