import os
import re

import pytest


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
            b'uuid:([A-Z][a-z]+-\d_\d)-[A-Za-z0-9]+',
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
        response['body']['string'] = body
        return response

    return {'before_record_response': scrub_identifiers}


@pytest.fixture(scope='module')
def vcr_cassette_dir(request):
    # Put all cassettes in tests/vcr/{module}/{test}.yaml
    return os.path.join('tests/vcr', request.module.__name__)
