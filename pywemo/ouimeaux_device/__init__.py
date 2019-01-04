"""Base WeMo Device class."""

import logging
import time

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

import requests

from .api.service import Service
from .api.xsd import device as deviceParser

LOG = logging.getLogger(__name__)

# Start with the most commonly used port
PROBE_PORTS = (49153, 49152, 49154, 49151, 49155, 49156, 49157, 49158, 49159)


def probe_wemo(host, ports=PROBE_PORTS, probe_timeout=10):
    """
    Probe a host for the current port.

    This probes a host for known-to-be-possible ports and
    returns the one currently in use. If no port is discovered
    then it returns None.
    """
    for port in ports:
        try:
            response = requests.get('http://%s:%i/setup.xml' % (host, port),
                                    timeout=probe_timeout)
            if ('WeMo' in response.text) or ('Belkin' in response.text):
                return port
        except requests.ConnectTimeout:
            # If we timed out connecting, then the wemo is gone,
            # no point in trying further.
            LOG.debug('Timed out connecting to %s on port %i, '
                      'wemo is offline', host, port)
            break
        except requests.Timeout:
            # Apparently sometimes wemos get into a wedged state where
            # they still accept connections on an old port, but do not
            # respond. If that happens, we should keep searching.
            LOG.debug('No response from %s on port %i, continuing',
                      host, port)
            continue
        except requests.ConnectionError:
            pass
    return None


def probe_device(device):
    """Probe a device for available port.

    This is an extension for probe_wemo, also probing current port.
    """
    ports = list(PROBE_PORTS)
    if device.port in ports:
        ports.remove(device.port)
    ports.insert(0, device.port)

    return probe_wemo(device.host, ports)


class UnknownService(Exception):
    """Exception raised when a non-existent service is called."""

    pass


class Device(object):
    """Base object for WeMo devices."""

    def __init__(self, url, mac, rediscovery_enabled=True):
        """Create a WeMo device."""
        self._state = None
        self.basic_state_params = {}
        base_url = url.rsplit('/', 1)[0]
        parsed_url = urlparse(url)
        self.host = parsed_url.hostname
        self.port = parsed_url.port
        self.retrying = False
        self.mac = mac
        self.rediscovery_enabled = rediscovery_enabled
        xml = requests.get(url, timeout=10)
        self._config = deviceParser.parseString(xml.content).device
        service_list = self._config.serviceList
        self.services = {}
        for svc in service_list.service:
            svcname = svc.get_serviceType().split(':')[-2]
            service = Service(self, svc, base_url)
            service.eventSubURL = base_url + svc.get_eventSubURL()
            self.services[svcname] = service
            setattr(self, svcname, service)

    def _reconnect_with_device_by_discovery(self):
        """
        Scan network to find the device again.

        Wemos tend to change their port number from time to time.
        Whenever requests throws an error, we will try to find the device again
        on the network and update this device.
        """
        # Put here to avoid circular dependency
        from ..discovery import discover_devices

        # Avoid retrying from multiple threads
        if self.retrying:
            return

        self.retrying = True
        LOG.info("Trying to reconnect with %s", self.name)
        # We will try to find it 5 times, each time we wait a bigger interval
        try_no = 0

        while True:
            found = discover_devices(ssdp_st=None, max_devices=1,
                                     match_mac=self.mac,
                                     match_serial=self.serialnumber)

            if found:
                LOG.info("Found %s again, updating local values", self.name)

                # pylint: disable=attribute-defined-outside-init
                self.__dict__ = found[0].__dict__
                self.retrying = False

                return

            wait_time = try_no * 5

            LOG.info(
                "%s Not found in try %i. Trying again in %i seconds",
                self.name, try_no, wait_time)

            if try_no == 5:
                LOG.error(
                    "Unable to reconnect with %s in 5 tries. Stopping.",
                    self.name)
                self.retrying = False

                return

            time.sleep(wait_time)

            try_no += 1

    def _reconnect_with_device_by_probing(self):
        """Attempt to reconnect to the device on the existing port."""
        port = probe_device(self)

        if port is None:
            LOG.error('Unable to re-probe wemo at %s', self.host)
            return False

        LOG.info('Reconnected to wemo at %s on port %i',
                 self.host, port)

        self.port = port
        url = 'http://{}:{}/setup.xml'.format(self.host, self.port)

        # pylint: disable=attribute-defined-outside-init
        self.__dict__ = self.__class__(url, None).__dict__

        return True

    def reconnect_with_device(self):
        """Re-probe & scan network to rediscover a disconnected device."""
        if self.rediscovery_enabled:
            if (not self._reconnect_with_device_by_probing() and
                    (self.mac or self.serialnumber)):
                self._reconnect_with_device_by_discovery()
        else:
            LOG.warning("Rediscovery was requested for device %s, "
                        "but rediscovery is disabled. Ignoring request.",
                        self.name)

    def parse_basic_state(self, params):
        """Parse the basic state response from the device."""
        # BinaryState
        # 1|1492338954|0|922|14195|1209600|0|940670|15213709|227088884
        (
            state,  # 0 if off, 1 if on,
            _x1,
            _x2,
            _x3,
            _x4,
            _x5,
            _x6,
            _x7,
            _x8,
            _x9
        ) = params.split('|')

        return {'state': state}

    def update_binary_state(self):
        """Update the cached copy of the basic state response."""
        # pylint: disable=maybe-no-member
        self.basic_state_params = self.basicevent.GetBinaryState()

    def subscription_update(self, _type, _params):
        """Update device state based on subscription event."""
        LOG.debug("subscription_update %s %s", _type, _params)
        if _type == "BinaryState":
            try:
                self._state = int(self.parse_basic_state(_params).get("state"))
            except ValueError:
                self._state = 0
            return True
        return False

    def get_state(self, force_update=False):
        """Return 0 if off and 1 if on."""
        if force_update or self._state is None:
            # pylint: disable=maybe-no-member
            state = self.basicevent.GetBinaryState() or {}

            try:
                self._state = int(state.get('BinaryState', 0))
            except ValueError:
                self._state = 0

        return self._state

    def get_service(self, name):
        """Get service object by name."""
        try:
            return self.services[name]
        except KeyError:
            raise UnknownService(name)

    def list_services(self):
        """Return list of services."""
        return list(self.services.keys())

    def explain(self):
        """Print information about the device and its actions."""
        for name, svc in self.services.items():
            print(name)
            print('-' * len(name))
            for aname, action in svc.actions.items():
                print("  %s(%s)" % (aname, ', '.join(action.args)))
            print()

    @property
    def model(self):
        """Return the model description of the device."""
        return self._config.get_modelDescription()

    @property
    def model_name(self):
        """Return the model name of the device."""
        return self._config.get_modelName()

    @property
    def name(self):
        """Return the name of the device."""
        return self._config.get_friendlyName()

    @property
    def serialnumber(self):
        """Return the serial number of the device."""
        return self._config.get_serialNumber()
