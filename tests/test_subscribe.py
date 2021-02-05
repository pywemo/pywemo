"""Tests for the subscription registry and http server module."""

import threading
import time
import unittest.mock as mock
from http.server import HTTPServer

import pytest
import requests

from pywemo import Insight, LightSwitch, subscribe


class Test_RequestHandler:
    """Test the server request handler."""

    @pytest.fixture
    def outer(self):
        """Mock SubscriptionRegistry used for testing the http server."""
        obj = mock.create_autospec(
            subscribe.SubscriptionRegistry, instance=True
        )
        obj.devices = {}
        return obj

    @pytest.fixture
    def http_server(self, outer):
        """Fixture for RequestHandler http server."""
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
            # Re-raise exceptions from the thread so they are visible
            # in the test.
            if exception is not None:
                raise exception

    @pytest.fixture
    def server_address(self, http_server):
        """IP address of the http server."""
        return http_server.server_address[0]

    @pytest.fixture
    def server_url(self, http_server):
        """URL for accessing the http server."""
        host, port = http_server.server_address
        return f"http://{host}:{port}"

    @pytest.fixture
    def mock_light_switch(self):
        """Mock LightSwitch device."""
        return mock.create_autospec(LightSwitch, instance=True)

    def test_NOTIFY_unknown_device(self, server_url):
        """NOTIFY returns success status for unknown devices."""
        response = requests.request("NOTIFY", f"{server_url}")
        assert response.status_code == 200
        assert response.content == subscribe.RESPONSE_SUCCESS.encode("UTF-8")

    def test_NOTIFY_known_device(
        self, outer, server_address, server_url, mock_light_switch
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

    def test_GET_setup_xml(self, server_url):
        """GET request for /setup.xml returns the VIRTUAL_SETUP_XML."""
        xml = requests.get(f"{server_url}/setup.xml")
        assert xml.status_code == 200
        assert xml.content == subscribe.VIRTUAL_SETUP_XML.encode("UTF-8")

    def test_GET_default_404(self, server_url):
        """GET request for unrecognized path returns 404 error."""
        response = requests.get(f"{server_url}/")
        assert response.status_code == 404

    def test_POST_unknown_device(self, server_url):
        """POST returns success status for unknown devices."""
        response = requests.post(f"{server_url}/upnp/control/basicevent1")
        assert response.status_code == 200
        assert response.content == subscribe.RESPONSE_SUCCESS.encode("UTF-8")

    def test_POST_known_device(
        self, outer, server_address, server_url, mock_light_switch
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
</s:Envelope>''',  # noqa: E501
        )
        assert response.status_code == 200
        assert response.content == subscribe.RESPONSE_SUCCESS.encode("UTF-8")
        outer.event.assert_called_once_with(
            mock_light_switch, subscribe.EVENT_TYPE_LONG_PRESS, '0'
        )

    def test_POST_default_404(self, server_url):
        """POST request for unrecognized path returns 404 error."""
        response = requests.post(f"{server_url}/")
        assert response.status_code == 404

    def test_SUBSCRIBE_state(self, server_url):
        """SUBSCRIBE response contains appropriate UPnP headers."""
        response = requests.request(
            "SUBSCRIBE", f"{server_url}/upnp/event/basicevent1"
        )
        assert response.status_code == 200
        assert response.content == b""
        assert response.headers["CONTENT-LENGTH"] == "0"
        assert response.headers["TIMEOUT"] == "Second-1801"
        assert (
            response.headers["SID"]
            == "uuid:a74b23d5-34b9-4f71-9f87-bed24353f304"
        )

    def test_SUBSCRIBE_default_404(self, server_url):
        """SUBSCRIBE request for unrecognized path returns 404 error."""
        response = requests.request("SUBSCRIBE", f"{server_url}/")
        assert response.status_code == 404


class Test_SubscriptionRegistry:
    """Test the SubscriptionRegistry."""

    @pytest.fixture
    def device(self, vcr):
        """Mock WeMo Insight device."""
        with vcr.use_cassette('WeMo_WW_2.00.11408.PVT-OWRT-Insight.yaml'):
            return Insight('http://192.168.1.100:49153/setup.xml', '')

    def _wait_for_registry(self, subscription_registry):
        # Wait for registry to be ready to make sure the Insight device has
        # been registered.
        ready = threading.Event()
        subscription_registry._sched.enter(0, 100, ready.set)
        ready.wait()

    @pytest.mark.vcr()
    def test_register_unregister(self, device, subscription_registry):
        """Test that the device can be registered and unregistered."""
        subscription_registry.register(device)
        self._wait_for_registry(subscription_registry)

        basic = subscription_registry._sched.queue[0]
        assert basic.time == pytest.approx(time.time() + 225, abs=2)
        assert basic.action == subscription_registry._resubscribe
        assert basic.argument == (
            device,
            subscribe._basic_event_subscription_url,
        )
        assert basic.kwargs == {
            'sid': 'uuid:84915076-1dd2-11b2-b5fd-dcf7b6ec9aaa'
        }

        insight = subscription_registry._sched.queue[1]
        assert insight.time == pytest.approx(time.time() + 225, abs=2)
        assert insight.action == subscription_registry._resubscribe
        assert insight.argument == (
            device,
            subscribe._insight_event_subscription_url,
        )
        assert insight.kwargs == {
            'sid': 'uuid:849c1a56-1dd2-11b2-b5fd-dcf7b6ec9aaa'
        }

        subscription_registry.unregister(device)

        assert len(subscription_registry._sched.queue) == 0

    @mock.patch(
        'requests.request', side_effect=requests.exceptions.ReadTimeout
    )
    def test_subscribe_read_timeout_and_reconnect(
        self, mock_request, device, subscription_registry
    ):
        """Test that retries happen on failure and reconnect works."""
        subscription_registry.register(device)
        self._wait_for_registry(subscription_registry)

        basic = subscription_registry._sched.queue[0]
        assert basic.time == pytest.approx(
            time.time() + subscribe.SUBSCRIPTION_RETRY, abs=2
        )
        assert basic.action == subscription_registry._resubscribe
        assert basic.argument == (
            device,
            subscribe._basic_event_subscription_url,
        )
        assert basic.kwargs == {'retry': 1, 'sid': None}

        # Simulate a second failure to trigger a reconnect with the device.
        subscription_registry._sched.cancel(basic)
        with mock.patch.object(device, 'reconnect_with_device') as reconnect:

            def change_url():
                device.basicevent.eventSubURL = 'http://192.168.1.100:1234/'

            reconnect.side_effect = change_url

            basic.action(*basic.argument, **basic.kwargs)

            # Fail one more time to see that the correct changed URL is used.
            basic = subscription_registry._sched.queue[-1]
            subscription_registry._sched.cancel(basic)
            basic.action(*basic.argument, **basic.kwargs)

        mock_request.assert_called_with(
            method='SUBSCRIBE',
            url='http://192.168.1.100:1234/',
            headers=mock.ANY,
            timeout=10,
        )

    @pytest.mark.vcr()
    @mock.patch('time.time')
    def test_is_subscribed(self, mock_time, device, subscription_registry):
        curr_time = 1000.0

        def get_time():
            nonlocal curr_time
            curr_time += 1.0
            return curr_time

        mock_time.side_effect = get_time
        subscription_registry.register(device)
        self._wait_for_registry(subscription_registry)

        # Not subscribed until after the first event.
        assert subscription_registry.is_subscribed(device) is False

        subscription_registry.event(device, 'type', 'params')
        assert subscription_registry.is_subscribed(device) is True

        # No event received before timeout.
        curr_time += 300
        assert subscription_registry.is_subscribed(device) is False

        # Trigger the UNSUBSCRIBE behavior.
        with mock.patch.object(subscription_registry, '_schedule'):
            event = subscription_registry._sched.queue[0]
            event.action(*event.argument, **event.kwargs)
