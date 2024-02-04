"""Tests for SSDP and discovery."""

import queue
import socket
from unittest import mock

import pytest

from pywemo import ssdp

MOCK_CALLBACK_PORT = 8989
MOCK_IP_ADDRESS = "5.6.7.8"
MOCK_CALLBACK_ADDRESS = f"{MOCK_IP_ADDRESS}:{MOCK_CALLBACK_PORT}"
MOCK_DATE = "Tue, 20 Jun 2023 16:16:15 GMT"


@pytest.fixture()
def mock_interface_addresses():
    """Mock for util.interface_addresses."""
    addresses = ["127.0.0.1"]
    with mock.patch("pywemo.ssdp.interface_addresses", return_value=addresses):
        yield addresses


@pytest.fixture()
def mock_get_callback_address():
    """Mock for util.get_ip_address."""
    with mock.patch(
        "pywemo.ssdp.get_callback_address", return_value=MOCK_CALLBACK_ADDRESS
    ):
        yield MOCK_CALLBACK_ADDRESS


@pytest.fixture()
def mock_socket():
    """Mock socket instance returned from socket.socket."""
    sock = mock.create_autospec(socket.socket, instance=True)
    with mock.patch("socket.socket", return_value=sock):
        yield sock


@pytest.fixture()
def mock_select():
    """Queue for delivering return values from select.select.

    This will cause select.select to block until an item is put into the queue.
    The return value from the mock select.select call will be the value that
    was put into the queue.
    """
    return_queue = queue.Queue()

    def do_select(*_):
        return return_queue.get()

    with mock.patch("select.select", side_effect=do_select):
        yield return_queue


@pytest.fixture()
def discovery_responder(
    mock_select,
    mock_socket,
    mock_interface_addresses,
    mock_get_callback_address,
):
    """Fixture for DiscoveryResponder instance.

    Returns a callable(msg, addr). When called, (msg, addr) will be the
    return value from the mock sock.recvfrom. If it is expected that mock
    sock.sendto is called, the arguments to that mock will be returned from the
    callable. Example:

    sendto_msg, sendto_addr = discovery_responder(recvfrom_msg, recvfrom_addr)

    Within the DiscoveryResponder instance, the mock recvfrom/sendto will map
    to the values from the example callable above:
        (recvfrom_msg, recvfrom_addr) = sock.recvfrom(1024)
        sock.sendto(sendto_msg, sendto_addr)
    """
    sendto_count = 0

    def do_once(req, source, expect_sendto=True, sendto_exception=None):
        nonlocal sendto_count
        if sendto_exception:
            sendto_count += 1
            expect_sendto = False
            mock_socket.sendto.side_effect = sendto_exception

        if expect_sendto:
            sendto_count += 1
            send_queue = queue.Queue()

            def sendto(msg, addr):
                send_queue.put((msg, addr))

            mock_socket.sendto.side_effect = sendto
        mock_socket.recvfrom.return_value = (req.encode("UTF-8"), source)
        # Unblock the select.select call with a socket, indicating data
        # is ready.
        with mock.patch(
            "pywemo.ssdp.format_date_time", return_value=MOCK_DATE
        ):
            mock_select.put(([mock_socket],))
            if expect_sendto:
                return send_queue.get()

    resp = ssdp.DiscoveryResponder(callback_port=MOCK_CALLBACK_PORT)
    resp._notify_enabled = False
    resp._nls_uuid = "UUID"
    resp.start()
    try:
        yield do_once
    finally:
        # Signal that the thread should exit, and unblock
        # the select.select call
        resp._exit.set()
        mock_select.put(([],))

        # Stop the discovery responder
        resp.stop()

        # Make sure the expected number of calls were made to sock.sendto.
        assert mock_socket.sendto.call_count == sendto_count


def test_discovery_responder_notify(
    mock_socket, mock_interface_addresses, mock_get_callback_address
):
    resp = ssdp.DiscoveryResponder(callback_port=MOCK_CALLBACK_PORT)
    resp.send_notify("ssdp:alive")
    params = {
        "callback": MOCK_CALLBACK_ADDRESS,
        "nls": resp._nls_uuid,
        "nts": "ssdp:alive",
    }
    mock_socket.sendto.assert_called_with(
        (ssdp.SSDP_NOTIFY % params).encode("utf-8"),
        ("239.255.255.250", 1900),
    )


def test_discovery_responder_responds_to_wemo(discovery_responder):
    """The DiscoveryResponder responds to WeMo M-SEARCH messages."""
    from_addr = ("1.2.3.4", 54321)
    msg = """M-SEARCH * HTTP/1.1
ST: urn:Belkin:service:basicevent:1
MX: 1
MAN: "ssdp:discover"
HOST: 239.255.255.250:1900

"""
    resp_msg, resp_to_addr = discovery_responder(msg, from_addr)

    params = {
        "callback": MOCK_CALLBACK_ADDRESS,
        "nls": "UUID",
        "date": MOCK_DATE,
    }
    expected_response = ssdp.SSDP_REPLY % params

    assert resp_msg.decode("UTF-8") == expected_response
    # The reply should go back to the source.
    assert resp_to_addr == from_addr


def test_discovery_responder_ignores_notify(discovery_responder):
    """The DiscoveryResponder does not reply to NOTIFY messages."""
    from_addr = ("1.2.3.4", 54321)
    msg = (
        """NOTIFY * HTTP/1.1
HOST: 239.255.255.250:1900
CACHE-CONTROL: max-age=1800
LOCATION: http://%s:%d/setup.xml
SERVER: Unspecified, UPnP/1.0, Unspecified
NT: urn:Belkin:service:basicevent:1
NTS: ssdp:alive
USN: uuid:Socket-1_0-SERIALNUMBER::urn:Belkin:service:basicevent:1

"""
        % from_addr
    )
    discovery_responder(msg, from_addr, expect_sendto=False)


def test_discovery_responder_ignores_non_wemo(discovery_responder):
    """The DiscoveryResponder does not reply to non-WeMo M-SEARCH requests."""
    from_addr = ("1.2.3.4", 54321)
    msg = """M-SEARCH * HTTP/1.1
ST: ssdp:all
MX: 2
MAN: "ssdp:discover"
HOST: 239.255.255.250:1900

"""
    discovery_responder(msg, from_addr, expect_sendto=False)


def test_discovery_responder_ignores_sendto_exception(discovery_responder):
    """The DiscoveryResponder does not fail if sendto fails."""
    from_addr = ("1.2.3.4", 54321)
    msg = """M-SEARCH * HTTP/1.1
ST: urn:Belkin:service:basicevent:1
MX: 1
MAN: "ssdp:discover"
HOST: 239.255.255.250:1900

"""
    discovery_responder(msg, from_addr, sendto_exception=OSError)

    # Verify that the DiscoveryResponder is still working.
    test_discovery_responder_responds_to_wemo(discovery_responder)


class TestScan:
    """Tests for the ssdp.scan method."""

    _R1 = "\r\n".join(
        [
            "HTTP/1.1 200 OK",
            "HOST: 239.255.255.250:1900",
            "CACHE-CONTROL: max-age=1800",
            "LOCATION: http://192.168.1.100:49158/setup.xml",
            "SERVER: Unspecified, UPnP/1.0, Unspecified",
            "ST: urn:Belkin:service:basicevent:1",
            "USN: uuid:Socket-1_0-SERIAL::urn:Belkin:service:basicevent:1",
            "",
        ]
    ).encode()
    _R2 = "\r\n".join(
        [
            "HTTP/1.1 200 OK",
            "HOST: 239.255.255.250:1900",
            "CACHE-CONTROL: max-age=1800",
            "LOCATION: http://192.168.1.100:49158/setup.xml",
            "SERVER: Unspecified, UPnP/1.0, Unspecified",
            "ST: upnp:rootdevice",
            "USN: uuid:Socket-1_0-SERIAL2::upnp:rootdevice",
            "",
        ]
    ).encode()

    @pytest.mark.parametrize(
        "kwargs,expected_count",
        [
            ({"match_udn": "no_match"}, 0),
            ({}, 2),
            ({"match_udn": "uuid:Socket-1_0-SERIAL"}, 1),
            ({"match_udn": "uuid:Socket-1_0-SERIAL2"}, 1),
        ],
    )
    def test_scan(
        self,
        mock_interface_addresses,
        mock_socket,
        mock_select,
        kwargs,
        expected_count,
    ):
        mock_socket.recv.side_effect = [self._R1, self._R1, self._R2]
        mock_select.put(([mock_socket],))  # _R1.
        mock_select.put(([mock_socket],))  # _R1 is received twice.
        mock_select.put(([mock_socket],))  # _R2.
        mock_select.put(([],))  # Exit.

        entries = ssdp.scan(st=ssdp.ST, timeout=0, **kwargs)
        assert len(entries) == expected_count


class TestUPNPEntry:
    """Tests for the UPNPEntry class."""

    _R1 = TestScan._R1.decode()
    _R2 = TestScan._R2.decode()

    def test_properties(self):
        r1 = ssdp.UPNPEntry.from_response(self._R1)
        assert r1.st == "urn:Belkin:service:basicevent:1"
        assert (
            r1.usn == "uuid:Socket-1_0-SERIAL::urn:Belkin:service:basicevent:1"
        )
        assert r1.udn == "uuid:Socket-1_0-SERIAL"
        assert r1.location == "http://192.168.1.100:49158/setup.xml"

        r2 = ssdp.UPNPEntry.from_response(self._R2)
        assert r1 != r2

        r1_2 = ssdp.UPNPEntry.from_response(self._R1)
        assert r1_2 == r1

        items = set((r1, r2, r1_2))
        assert len(items) == 2
