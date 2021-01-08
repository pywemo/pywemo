"""Tests for the subscription registry and http server module."""
import threading
import unittest.mock as mock
from http.server import HTTPServer

import pytest
import requests

from pywemo import LightSwitch, subscribe


@pytest.fixture()
def outer():
    """Mock SubscriptionRegistry used for testing the http server."""
    obj = mock.create_autospec(subscribe.SubscriptionRegistry, instance=True)
    obj.devices = {}
    return obj


@pytest.fixture()
def http_server(outer):
    """RequestHandler http server."""
    server = HTTPServer(("localhost", 0), subscribe.RequestHandler)
    server.outer = outer
    exception = None

    def run_server():
        try:
            server.serve_forever(poll_interval=0.1)
        except Exception as exp:
            nonlocal exception
            exception = exp
            raise

    thread = threading.Thread(target=run_server, name="Server Thread")
    try:
        thread.start()
        yield server
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
        # Re-raise exceptions from the thread so they are visible in the test.
        if exception is not None:
            raise exception


@pytest.fixture()
def server_address(http_server):
    """IP address of the http server."""
    return http_server.server_address[0]


@pytest.fixture()
def server_url(http_server):
    """URL for accessing the http server."""
    host, port = http_server.server_address
    return f"http://{host}:{port}"


@pytest.fixture()
def mock_light_switch():
    """Mock LightSwitch device."""
    return mock.create_autospec(LightSwitch, instance=True)


def test_NOTIFY_unknown_device(server_url):
    """NOTIFY returns sucess status for unknown devices."""
    response = requests.request("NOTIFY", f"{server_url}")
    assert response.status_code == 200
    assert response.content == subscribe.RESPONSE_SUCCESS.encode("UTF-8")


def test_NOTIFY_known_device(
    outer, server_address, server_url, mock_light_switch
):
    """NOTIFY calls the event callback for known devices."""
    outer.devices[server_address] = mock_light_switch
    response = requests.request(
        "NOTIFY",
        f"{server_url}",
        data='''<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0">
<e:property>
<BinaryState>0</BinaryState>
</e:property>
</e:propertyset>''',
    )
    assert response.status_code == 200
    assert response.content == subscribe.RESPONSE_SUCCESS.encode("UTF-8")
    outer.event.assert_called_once_with(
        mock_light_switch, subscribe.EVENT_TYPE_BINARY_STATE, '0'
    )


def test_GET_setup_xml(server_url):
    """GET request for /setup.xml returns the VIRTUAL_SETUP_XML."""
    xml = requests.get(f"{server_url}/setup.xml")
    assert xml.status_code == 200
    assert xml.content == subscribe.VIRTUAL_SETUP_XML.encode("UTF-8")


def test_GET_default_404(server_url):
    """GET request for unrecognized path returns 404 error."""
    response = requests.get(f"{server_url}/")
    assert response.status_code == 404


def test_POST_unknown_device(server_url):
    """POST returns sucess status for unknown devices."""
    response = requests.post(f"{server_url}/upnp/control/basicevent1")
    assert response.status_code == 200
    assert response.content == subscribe.RESPONSE_SUCCESS.encode("UTF-8")


def test_POST_known_device(
    outer, server_address, server_url, mock_light_switch
):
    """POST (LongPress) for known device delivers the appropriate event."""
    outer.devices[server_address] = mock_light_switch
    response = requests.post(
        f"{server_url}/upnp/control/basicevent1",
        data='''<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
<s:Body>
<u:SetBinaryState xmlns:u="urn:Belkin:service:basicevent:1">
<BinaryState>0</BinaryState>
</u:SetBinaryState>
</s:Body>
</s:Envelope>''',
    )
    assert response.status_code == 200
    assert response.content == subscribe.RESPONSE_SUCCESS.encode("UTF-8")
    outer.event.assert_called_once_with(
        mock_light_switch, subscribe.EVENT_TYPE_LONG_PRESS, '0'
    )


def test_POST_default_404(server_url):
    """POST request for unrecognized path returns 404 error."""
    response = requests.post(f"{server_url}/")
    assert response.status_code == 404


def test_SUBSCRIBE_state(server_url):
    """SUBSCRIBE response contains appropriate UPnP headers."""
    response = requests.request(
        "SUBSCRIBE", f"{server_url}/upnp/event/basicevent1"
    )
    assert response.status_code == 200
    assert response.content == b""
    assert response.headers["CONTENT-LENGTH"] == "0"
    assert response.headers["TIMEOUT"] == "Second-1801"
    assert (
        response.headers["SID"] == "uuid:a74b23d5-34b9-4f71-9f87-bed24353f304"
    )


def test_SUBSCRIBE_default_404(server_url):
    """SUBSCRIBE request for unrecognized path returns 404 error."""
    response = requests.request("SUBSCRIBE", f"{server_url}/")
    assert response.status_code == 404
