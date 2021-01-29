"""Tests for the Device class."""
# pylint: disable=protected-access, no-self-use, no-member
# pylint: disable=redefined-outer-name

import itertools
import logging
import unittest.mock as mock
from subprocess import CalledProcessError

import pytest
import requests

from pywemo.ouimeaux_device import (
    APNotFound,
    Device,
    ResetException,
    SetupException,
    ShortPassword,
    UnknownService,
)
from pywemo.ouimeaux_device.api.service import ActionException

RESPONSE_SETUP = '''<?xml version="1.0"?>
<root xmlns="urn:Belkin:device-1-0">
  <specVersion>
    <major>1</major>
    <minor>0</minor>
  </specVersion>
  <device>
<deviceType>urn:Belkin:device:controllee:1</deviceType>
<friendlyName>Wemo Mini</friendlyName>
    <manufacturer>Belkin International Inc.</manufacturer>
    <manufacturerURL>http://www.belkin.com</manufacturerURL>
    <modelDescription>Belkin Plugin Socket 1.0</modelDescription>
<modelName>Socket</modelName>
    <modelNumber>1.0</modelNumber>
<hwVersion>v2</hwVersion>
    <modelURL>http://www.belkin.com/plugin/</modelURL>
<serialNumber>XXXXXXXXXXXXXX</serialNumber>
<UDN>uuid:Socket-1_0-XXXXXXXXXXXXXX</UDN>
    <UPC>123456789</UPC>
<macAddress>XXXXXXXXXXXX</macAddress>
<hkSetupCode>111-11-111</hkSetupCode>
<firmwareVersion>WeMo_WW_2.00.11452.PVT-OWRT-SNSV2</firmwareVersion>
<iconVersion>1|49152</iconVersion>
<binaryState>0</binaryState>
    <new_algo>1</new_algo>
    <iconList>
      <icon>
        <mimetype>jpg</mimetype>
        <width>100</width>
        <height>100</height>
        <depth>100</depth>
         <url>icon.jpg</url>
      </icon>
    </iconList>
    <serviceList>
      <service>
        <serviceType>urn:Belkin:service:WiFiSetup:1</serviceType>
        <serviceId>urn:Belkin:serviceId:WiFiSetup1</serviceId>
        <controlURL>/upnp/control/WiFiSetup1</controlURL>
        <eventSubURL>/upnp/event/WiFiSetup1</eventSubURL>
        <SCPDURL>/setupservice.xml</SCPDURL>
      </service>
      <service>
        <serviceType>urn:Belkin:service:timesync:1</serviceType>
        <serviceId>urn:Belkin:serviceId:timesync1</serviceId>
        <controlURL>/upnp/control/timesync1</controlURL>
        <eventSubURL>/upnp/event/timesync1</eventSubURL>
        <SCPDURL>/timesyncservice.xml</SCPDURL>
      </service>
      <service>
        <serviceType>urn:Belkin:service:basicevent:1</serviceType>
        <serviceId>urn:Belkin:serviceId:basicevent1</serviceId>
        <controlURL>/upnp/control/basicevent1</controlURL>
        <eventSubURL>/upnp/event/basicevent1</eventSubURL>
        <SCPDURL>/eventservice.xml</SCPDURL>
      </service>
      <service>
        <serviceType>urn:Belkin:service:firmwareupdate:1</serviceType>
        <serviceId>urn:Belkin:serviceId:firmwareupdate1</serviceId>
        <controlURL>/upnp/control/firmwareupdate1</controlURL>
        <eventSubURL>/upnp/event/firmwareupdate1</eventSubURL>
        <SCPDURL>/firmwareupdate.xml</SCPDURL>
      </service>
      <service>
        <serviceType>urn:Belkin:service:rules:1</serviceType>
        <serviceId>urn:Belkin:serviceId:rules1</serviceId>
        <controlURL>/upnp/control/rules1</controlURL>
        <eventSubURL>/upnp/event/rules1</eventSubURL>
        <SCPDURL>/rulesservice.xml</SCPDURL>
      </service>
      <service>
        <serviceType>urn:Belkin:service:metainfo:1</serviceType>
        <serviceId>urn:Belkin:serviceId:metainfo1</serviceId>
        <controlURL>/upnp/control/metainfo1</controlURL>
        <eventSubURL>/upnp/event/metainfo1</eventSubURL>
        <SCPDURL>/metainfoservice.xml</SCPDURL>
      </service>
      <service>
        <serviceType>urn:Belkin:service:remoteaccess:1</serviceType>
        <serviceId>urn:Belkin:serviceId:remoteaccess1</serviceId>
        <controlURL>/upnp/control/remoteaccess1</controlURL>
        <eventSubURL>/upnp/event/remoteaccess1</eventSubURL>
        <SCPDURL>/remoteaccess.xml</SCPDURL>
      </service>
      <service>
        <serviceType>urn:Belkin:service:deviceinfo:1</serviceType>
        <serviceId>urn:Belkin:serviceId:deviceinfo1</serviceId>
        <controlURL>/upnp/control/deviceinfo1</controlURL>
        <eventSubURL>/upnp/event/deviceinfo1</eventSubURL>
        <SCPDURL>/deviceinfoservice.xml</SCPDURL>
      </service>
      <service>
        <serviceType>urn:Belkin:service:smartsetup:1</serviceType>
        <serviceId>urn:Belkin:serviceId:smartsetup1</serviceId>
        <controlURL>/upnp/control/smartsetup1</controlURL>
        <eventSubURL>/upnp/event/smartsetup1</eventSubURL>
        <SCPDURL>/smartsetup.xml</SCPDURL>
      </service>
      <service>
        <serviceType>urn:Belkin:service:manufacture:1</serviceType>
        <serviceId>urn:Belkin:serviceId:manufacture1</serviceId>
        <controlURL>/upnp/control/manufacture1</controlURL>
        <eventSubURL>/upnp/event/manufacture1</eventSubURL>
        <SCPDURL>/manufacture.xml</SCPDURL>
      </service>
    </serviceList>
   <presentationURL>/pluginpres.html</presentationURL>
</device>
</root>'''

ENC_PASSWORD = b'Salted__XXXXXX12\xc0\xd4\xd4v4\xfep\rikEmk\xf8\xe0\x12'

APLIST = (
    'Page:1/1/2$\n'
    'ap_aes|6|100|WPA2PSK/AES,\n'
    'ap_tkip|6|50|WPA2PSK/TKIP,\n'
    'ap_open|1|85|OPEN/NONE,\n'
)


class MockResponse:
    """Mocked requests response."""

    def __init__(self, content, status_code):
        self.content = content
        self.text = content.decode('utf-8') if content else ''
        self.status_code = status_code


def mocked_requests_get(*args, **kwargs):
    """Mock a response from request.get()."""
    # mocked class

    if args[0] == 'http://192.168.1.100:49158/setup.xml':
        return MockResponse(RESPONSE_SETUP.encode('utf-8'), 200)
    return MockResponse(None, 404)


@pytest.fixture
@mock.patch('requests.get', side_effect=mocked_requests_get)
def device(mock_get):
    """Return a Device as created by some actual XML."""
    # Note that the actions on the services will not be created since the
    # URL(s) for them will return a 404.
    device = Device('http://192.168.1.100:49158/setup.xml', '')
    device.WiFiSetup.GetApList = mock.Mock(return_value={'ApList': APLIST})
    device.WiFiSetup.ConnectHomeNetwork = mock.Mock(
        return_value={'PairingStatus': 'Connecting'}
    )
    device.WiFiSetup.CloseSetup = mock.Mock(return_value={'status': 'success'})
    return device


@pytest.fixture(autouse=True)
def lightspeed():
    """Skip sleeps in the code and auto-increment time.time calls."""
    with mock.patch('time.sleep', return_value=None), mock.patch(
        'time.time', side_effect=itertools.count(0, 15)
    ):
        yield


class TestDevice:
    """Test the Device object."""

    METAINFO = 'XXXXXXXXXXXX|123456A1234567|dummy'

    def test_initialization(self, device):
        """Test device initialization."""
        assert device.model == 'Belkin Plugin Socket 1.0'
        assert device.model_name == 'Socket'
        assert device.name == 'Wemo Mini'
        assert device.serialnumber == 'XXXXXXXXXXXXXX'
        assert device.host == '192.168.1.100'
        assert device.port == 49158
        assert device._config.macAddress == 'XXXXXXXXXXXX'

    def test_services(self, device):
        """Test device initialization."""
        assert len(device.services) == 10
        assert device.list_services() == [
            'WiFiSetup',
            'timesync',
            'basicevent',
            'firmwareupdate',
            'rules',
            'metainfo',
            'remoteaccess',
            'deviceinfo',
            'smartsetup',
            'manufacture',
        ]

    def test_reset(self, device):
        """Test device reset."""
        device.basicevent.ReSetup = mock.Mock(
            return_value={'Reset': 'success'}
        )
        with pytest.raises(ResetException) as execinfo:
            device.reset(False, False)
        assert str(execinfo.value) == 'no action requested'

        assert device.reset(True, False) == 'success'
        assert device.reset(False, True) == 'success'
        assert device.reset(True, True) == 'success'

        assert device.basicevent.ReSetup.call_count == 3
        assert device.basicevent.ReSetup.call_args_list == [
            ({'Reset': 1},),
            ({'Reset': 5},),
            ({'Reset': 2},),
        ]

    def test_factory_reset(self, device):
        """Test device reset."""
        device.basicevent.ReSetup = mock.Mock(
            return_value={'Reset': 'success'}
        )
        assert device.factory_reset() == 'success'

        assert device.basicevent.ReSetup.call_count == 1
        assert device.basicevent.ReSetup.call_args_list == [({'Reset': 2},)]

    @mock.patch('subprocess.run', side_effect=FileNotFoundError)
    def test_encryption_no_openssl(self, mock_run, device):
        """Test device encryption (openssl not found/not installed)."""
        with pytest.raises(SetupException):
            assert device.encrypt_aes128('password', self.METAINFO)
        assert mock_run.call_count == 1

    @mock.patch('subprocess.run', side_effect=CalledProcessError(-1, 'error'))
    def test_encryption_openssl_error(self, mock_run, device):
        """Test device encryption (error in openssl)."""
        with pytest.raises(SetupException):
            assert device.encrypt_aes128('password', self.METAINFO)
        assert mock_run.call_count == 1

    @mock.patch('subprocess.run', return_value=mock.Mock(stdout=ENC_PASSWORD))
    def test_encryption_successful(self, mock_run, device):
        """Test device encryption (good result)."""
        correct = 'wNTUdjT+cA1pa0Vta/jgEg==1808'
        assert device.encrypt_aes128('password', self.METAINFO) == correct
        assert mock_run.call_count == 1

    def test_setup_unknown_service(self, device):
        """Test device setup (WiFiSetup service not available)."""
        device.get_service = mock.Mock(side_effect=UnknownService)
        with pytest.raises(SetupException) as execinfo:
            device.setup('ap_aes', 'password')
        assert isinstance(execinfo.value.__cause__, UnknownService)
        assert device.get_service.call_count == 1

    def test_setup_no_getaplist(self, device):
        """Test device setup (GetApList not found)."""
        device.WiFiSetup.GetApList = mock.Mock(side_effect=AttributeError)
        with pytest.raises(SetupException) as execinfo:
            device.setup('ap_aes', 'password')
        assert isinstance(execinfo.value.__cause__, AttributeError)
        assert device.WiFiSetup.GetApList.call_count == 1

    def test_setup_aplist_missing(self, device):
        """Test device setup (ApList not found)."""
        device.WiFiSetup.GetApList = mock.Mock(return_value={'NoApList': 1})
        with pytest.raises(SetupException) as execinfo:
            device.setup('ap_aes', 'password')
        assert isinstance(execinfo.value.__cause__, KeyError)
        assert device.WiFiSetup.GetApList.call_count == 1

    def test_setup_ap_not_found(self, device):
        """Test device setup (APNotFound)."""
        with pytest.raises(APNotFound):
            device.setup('ap_does_not_exist', 'password')

    def test_setup_action_exception1(self, lightspeed, device):
        """Test device setup (ActionException, device cannot be re-probed)."""
        device.WiFiSetup.GetApList = mock.Mock(side_effect=ActionException)
        with pytest.raises(SetupException) as execinfo:
            device.setup('ap_aes', 'password')
        assert isinstance(execinfo.value.__cause__, ActionException)
        assert device.WiFiSetup.GetApList.call_count == 1

    def test_setup_action_exception2(self, lightspeed, device):
        """Test device setup (ActionException, device cannot be re-probed)."""
        device.WiFiSetup.GetNetworkStatus = mock.Mock(
            side_effect=ActionException
        )
        with pytest.raises(SetupException) as execinfo:
            device.setup('ap_open', 'password')
        assert isinstance(execinfo.value.__cause__, ActionException)
        assert device.WiFiSetup.GetNetworkStatus.call_count == 1

    def test_setup_unsupported_encryption(self, device, caplog):
        """Test device setup (unsupported encryption method)."""
        caplog.set_level(logging.DEBUG)
        with pytest.raises(SetupException) as execinfo:
            device.setup('ap_tkip', 'password')
        assert 'Encryption TKIP not currently supported' in str(execinfo.value)

        # piggyback on this test to check AP information
        assert 'AP channel: 6' in caplog.text
        assert 'AP authorization mode(s): WPA2PSK' in caplog.text
        assert 'AP encryption method: TKIP' in caplog.text

    def test_setup_short_password(self, lightspeed, device):
        """Test device setup (password is too short, status 2)."""
        device.WiFiSetup.GetNetworkStatus = mock.Mock(
            return_value={'NetworkStatus': '2'}
        )
        with pytest.raises(ShortPassword):
            # no need to run encryption code, it is tested above already, so
            # instead use an open AP even though the password wouldn't actually
            # be used in this case.  Just need to make sure that status 2 from
            # Wemo will raise the ShortPassword exception.
            device.setup('ap_open', 'short')

    def test_setup_status_3(self, lightspeed, device):
        """Test device setup (status 3, uncertain status)."""
        device.WiFiSetup.GetNetworkStatus = mock.Mock(
            return_value={'NetworkStatus': '3'}
        )
        with pytest.raises(SetupException) as execinfo:
            device.setup('ap_open', 'password', timeout=20)
        assert 'but has status=3' in str(execinfo.value)

    def test_setup_unsuccessful(self, lightspeed, device):
        """Test device setup (successful on first try)."""
        device.WiFiSetup.GetNetworkStatus = mock.Mock(
            return_value={'NetworkStatus': '0'}
        )
        with pytest.raises(SetupException) as execinfo:
            device.setup('ap_open', 'password', timeout=20)
        assert 'failed to connect ' in str(execinfo.value)

    def test_setup_successful_1_try(self, lightspeed, device):
        """Test device setup (successful on first try)."""
        device.WiFiSetup.GetNetworkStatus = mock.Mock(
            return_value={'NetworkStatus': '1'}
        )
        status, close = device.setup('ap_open', 'password', timeout=20)
        assert device.WiFiSetup.ConnectHomeNetwork.call_count == 2
        assert status == '1'
        assert close == 'success'

    def test_setup_successful_2_tries(self, lightspeed, device):
        """Test device setup (successful on second try)."""
        # first loop fails, second succeeds --- note that the timing is
        # important here to make sure that GetNetworkStatus is only called
        # once per loop!
        device.WiFiSetup.GetNetworkStatus = mock.Mock(
            side_effect=[{'NetworkStatus': '0'}, {'NetworkStatus': '1'}]
        )
        device.setup('ap_open', 'password', timeout=20, connection_attempts=2)
        assert device.WiFiSetup.ConnectHomeNetwork.call_count == 4

    def test_supports_long_press_is_false(self, lightspeed, device):
        """Test that the base Device does not have support for long press."""
        assert device.supports_long_press() is False

    @mock.patch('requests.get', side_effect=requests.ConnectTimeout)
    def test_reconnect_with_device_by_probing_ConnectTimeout(
        self, get, device
    ):
        with mock.patch.object(device, '_reconnect_with_device_by_discovery'):
            device.reconnect_with_device()
        get.assert_called_once()

    @mock.patch('requests.get', side_effect=requests.Timeout)
    def test_reconnect_with_device_by_probing_Timeout(self, get, device):
        with mock.patch.object(device, '_reconnect_with_device_by_discovery'):
            device.reconnect_with_device()
        assert get.mock_calls == [
            # First call should have the original port.
            mock.call(f'http://{device.host}:49158/setup.xml', timeout=10),
            mock.call(f'http://{device.host}:49153/setup.xml', timeout=10),
            mock.call(f'http://{device.host}:49152/setup.xml', timeout=10),
            mock.call(f'http://{device.host}:49154/setup.xml', timeout=10),
            mock.call(f'http://{device.host}:49151/setup.xml', timeout=10),
            mock.call(f'http://{device.host}:49155/setup.xml', timeout=10),
            mock.call(f'http://{device.host}:49156/setup.xml', timeout=10),
            mock.call(f'http://{device.host}:49157/setup.xml', timeout=10),
            mock.call(f'http://{device.host}:49159/setup.xml', timeout=10),
        ]

    @mock.patch('requests.get', side_effect=requests.ConnectionError)
    def test_reconnect_with_device_by_probing_ConnectionError(
        self, get, device
    ):
        with mock.patch.object(device, '_reconnect_with_device_by_discovery'):
            device.reconnect_with_device()
        assert len(get.mock_calls) == 9

    @mock.patch('requests.get')
    def test_reconnect_with_device_by_probing_PortChanged(self, get, device):
        new_port = 49155

        def get_resp(url, *args, **kwargs):
            if url == f'http://{device.host}:{new_port}/setup.xml':
                return MockResponse(RESPONSE_SETUP.encode('utf-8'), 200)
            return MockResponse(None, 404)

        get.side_effect = get_resp
        device.sentinel = 'SeNtInEl'  # Should not exist in the new device.
        device.reconnect_with_device()

        assert device.port == new_port
        assert getattr(device, 'sentinel', None) is None

    @mock.patch('requests.get')
    def test_reconnect_with_device_by_probing_WrongDevice(self, get, device):
        new_response = RESPONSE_SETUP.replace(
            'XXXXXXXXXXXXXX', 'YYYYYYYYYYYYYY'
        )

        def get_resp(url, *args, **kwargs):
            if url == f'http://{device.host}:{device.port}/setup.xml':
                return MockResponse(new_response.encode('utf-8'), 200)
            return MockResponse(None, 404)

        get.side_effect = get_resp

        device.sentinel = 'SeNtInEl'  # Make sure this still exists.
        with mock.patch.object(device, '_reconnect_with_device_by_discovery'):
            device.reconnect_with_device()

        assert getattr(device, 'sentinel', None) == 'SeNtInEl'
