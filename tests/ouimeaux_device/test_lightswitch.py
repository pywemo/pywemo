"""Tests for the LightSwitch class."""

import unittest.mock as mock

import pytest

from pywemo import LightSwitch

from .api.unit import long_press_helpers

RESPONSE_SETUP = '''<?xml version="1.0"?>
<root xmlns="urn:Belkin:device-1-0">
  <specVersion>
    <major>1</major>
    <minor>0</minor>
  </specVersion>
  <device>
<deviceType>urn:Belkin:device:lightswitch:1</deviceType>
<friendlyName>Wemo Light Switch</friendlyName>
    <manufacturer>Belkin International Inc.</manufacturer>
    <manufacturerURL>http://www.belkin.com</manufacturerURL>
    <modelDescription>Belkin Plugin Socket 1.0</modelDescription>
    <modelName>LightSwitch</modelName>
    <modelNumber>1.0</modelNumber>
<hwVersion>v3</hwVersion>
    <modelURL>http://www.belkin.com/plugin/</modelURL>
<serialNumber>NNNNLNNNLNNNNL</serialNumber>
<UDN>uuid:Lightswitch-3_0-NNNNLNNNLNNNNL</UDN>
    <UPC>123456789</UPC>
<macAddress>XXXXXXXXXXXX</macAddress>
<hkSetupCode>111-11-111</hkSetupCode>
<firmwareVersion>WeMo_WW_2.00.11451.PVT-OWRT-LIGHTV2</firmwareVersion>
<iconVersion>2|49152</iconVersion>
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


def mocked_requests_get(*args, **kwargs):
    """Mock a response from request.get()."""

    class MockResponse:
        """Mocked requests response."""

        def __init__(self, content, status_code):
            self.content = content
            self.status_code = status_code

    if args[0] == 'http://192.168.1.100:49153/setup.xml':
        return MockResponse(RESPONSE_SETUP.encode('utf-8'), 200)
    return MockResponse(None, 404)


@pytest.fixture
@mock.patch('requests.get', side_effect=mocked_requests_get)
def device(mock_get):
    """Return a Device as created by some actual XML."""
    # Note that the actions on the services will not be created since the
    # URL(s) for them will return a 404.
    return LightSwitch('http://192.168.1.100:49153/setup.xml', '')


#
# No LightSwitch specific tests at the moment. Only the tests from the imported
# TestLongPress test will run.
#
TestLongPress = long_press_helpers.TestLongPress
