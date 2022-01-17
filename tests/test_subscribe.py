"""Tests for the subscription registry and http server module."""

import threading
import time
import unittest.mock as mock
from http.server import HTTPServer

import pytest
import requests

from pywemo import Bridge, Insight, LightSwitch, subscribe


@pytest.fixture
def device(vcr):
    """Mock WeMo Insight device."""
    with vcr.use_cassette('WeMo_WW_2.00.11408.PVT-OWRT-Insight.yaml'):
        return Insight('http://192.168.1.100:49153/setup.xml')


@pytest.fixture
def bridge(vcr):
    with vcr.use_cassette('WeMo_WW_2.00.11057.PVT-OWRT-Link.yaml'):
        return Bridge('http://192.168.1.100:49153/setup.xml')


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
            f"{server_url}/path",
            data='''<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0">
<e:property>
<BinaryState>0</BinaryState>
</e:property>
</e:propertyset>''',
        )
        assert response.status_code == 200
        assert response.content == subscribe.RESPONSE_SUCCESS.encode("UTF-8")
        outer.event.assert_called_once_with(
            mock_light_switch,
            subscribe.EVENT_TYPE_BINARY_STATE,
            '0',
            path='/path',
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


class Test_Subscription:
    """Base class for subscription tests."""

    http_port = 8989

    @pytest.fixture(autouse=True)
    def get_ip_address(self):
        with mock.patch('pywemo.subscribe.get_ip_address') as mock_ip_address:
            mock_ip_address.return_value = '192.168.1.1'
            yield mock_ip_address

    @pytest.fixture(
        params=subscribe.SubscriptionRegistry.subscription_service_names
    )
    def subscription(self, request, device, bridge):
        if request.param == 'bridge':
            return subscribe.Subscription(
                bridge, self.http_port, request.param
            )
        return subscribe.Subscription(device, self.http_port, request.param)

    def test_url(self, subscription):
        base_url = 'http://192.168.1.100:49153/upnp/event'
        assert subscription.url == f'{base_url}/{subscription.service_name}1'

    @mock.patch('requests.request')
    def test_maintain(self, mock_request, subscription):
        mock_response = mock.create_autospec(requests.Response, instance=True)
        mock_response.headers = {'SID': 'uuid:123', 'TIMEOUT': 'Second-222'}
        mock_response.status_code = requests.codes.ok
        mock_request.return_value = mock_response

        assert subscription.maintain() == 222
        assert subscription.subscription_id == 'uuid:123'
        assert subscription.expiration_time == pytest.approx(
            time.time() + 222, abs=2
        )
        mock_request.assert_called_once_with(
            method='SUBSCRIBE',
            url=subscription.url,
            headers={
                'CALLBACK': f'<http://192.168.1.1:8989{subscription.path}>',
                'NT': 'upnp:event',
                'TIMEOUT': 'Second-300',
            },
            timeout=subscribe.REQUESTS_TIMEOUT,
        )

        # Now test subscription renewal.
        mock_request.reset_mock()
        mock_response.headers = {'SID': 'uuid:321', 'TIMEOUT': 'Second-765'}
        mock_response.status_code = requests.codes.ok
        mock_request.return_value = mock_response

        assert subscription.maintain() == 300
        assert subscription.subscription_id == 'uuid:321'
        assert subscription.expiration_time == pytest.approx(
            time.time() + 300, abs=2
        )
        mock_request.assert_called_once_with(
            method='SUBSCRIBE',
            url=subscription.url,
            headers={'SID': 'uuid:123', 'TIMEOUT': 'Second-300'},
            timeout=subscribe.REQUESTS_TIMEOUT,
        )

        # Now test with the renewal failing with code 412.
        mock_request.reset_mock()
        mock_response = mock.Mock()
        mock_response.headers = {'SID': 'uuid:222', 'TIMEOUT': 'Second-333'}
        type(mock_response).status_code = mock.PropertyMock(
            side_effect=[412, requests.codes.ok, requests.codes.ok]
        )
        mock_request.return_value = mock_response

        assert subscription.maintain() == 300
        assert subscription.subscription_id == 'uuid:222'
        assert subscription.expiration_time == pytest.approx(
            time.time() + 300, abs=2
        )
        mock_request.assert_any_call(
            method='SUBSCRIBE',
            url=subscription.url,
            headers={'SID': 'uuid:321', 'TIMEOUT': 'Second-300'},
            timeout=subscribe.REQUESTS_TIMEOUT,
        )
        mock_request.assert_any_call(
            method='UNSUBSCRIBE',
            url=subscription.url,
            headers={'SID': 'uuid:321'},
            timeout=subscribe.REQUESTS_TIMEOUT,
        )
        mock_request.assert_called_with(
            method='SUBSCRIBE',
            url=subscription.url,
            headers={
                'CALLBACK': f'<http://192.168.1.1:8989{subscription.path}>',
                'NT': 'upnp:event',
                'TIMEOUT': 'Second-300',
            },
            timeout=subscribe.REQUESTS_TIMEOUT,
        )

    @mock.patch('requests.request', side_effect=requests.ReadTimeout)
    def test_maintain_requests_exception(self, mock_request, subscription):
        with pytest.raises(requests.ReadTimeout):
            subscription.maintain()

    @pytest.mark.vcr()
    def test_maintain_bad_status_code(self, subscription):
        with pytest.raises(requests.HTTPError):
            subscription.maintain()

    @mock.patch('requests.request')
    def test_unsubscribe(self, mock_request, subscription):
        subscription.subscription_id = 'uuid:321'
        subscription._unsubscribe()
        mock_request.called_once_with(
            method='UNSUBSCRIBE',
            url=subscription.url,
            headers={'SID': 'uuid:321'},
            timeout=subscribe.REQUESTS_TIMEOUT,
        )
        assert subscription.subscription_id is None

        mock_request.reset_mock()
        subscription._unsubscribe()
        mock_request.assert_not_called()

    def test_update_subscription(self, subscription):
        subscription._update_subscription({})
        assert subscription.subscription_id is None
        assert subscription.expiration_time == pytest.approx(
            time.time() + 300, abs=2
        )

        subscription._update_subscription({'SID': 'uuid:123'})
        assert subscription.subscription_id == 'uuid:123'
        assert subscription.expiration_time == pytest.approx(
            time.time() + 300, abs=2
        )

        subscription._update_subscription({'TIMEOUT': 'Second-200'})
        assert subscription.subscription_id == 'uuid:123'
        assert subscription.expiration_time == pytest.approx(
            time.time() + 200, abs=2
        )


class Test_SubscriptionRegistry:
    """Test the SubscriptionRegistry."""

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

        insight = subscription_registry._sched.queue[1]
        assert insight.time == pytest.approx(time.time() + 225, abs=2)
        assert insight.action == subscription_registry._resubscribe

        device._state = 1
        assert subscription_registry.is_subscribed(device) is False
        subscription_registry.event(device, '', '', path='/sub/insight')
        assert subscription_registry.is_subscribed(device) is False
        subscription_registry.event(device, '', '', path='/sub/basicevent')
        assert subscription_registry.is_subscribed(device) is True
        device._state = 0
        assert subscription_registry.is_subscribed(device) is False
        subscription_registry.event(device, '', '', path='invalid_path')

        assert subscription_registry.devices['192.168.1.100'] == device

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

        # Simulate a second failure to trigger a reconnect with the device.
        subscription_registry._sched.cancel(basic)
        with mock.patch.object(device, 'reconnect_with_device') as reconnect:

            def change_url():
                device.session.url = 'http://192.168.1.100:1234/'

            reconnect.side_effect = change_url

            basic.action(*basic.argument, **basic.kwargs)

            # Fail one more time to see that the correct changed URL is used.
            basic = subscription_registry._sched.queue[-1]
            subscription_registry._sched.cancel(basic)
            basic.action(*basic.argument, **basic.kwargs)

        mock_request.assert_called_with(
            method='SUBSCRIBE',
            url='http://192.168.1.100:1234/upnp/event/basicevent1',
            headers=mock.ANY,
            timeout=10,
        )
