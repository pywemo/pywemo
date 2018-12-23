import logging
import time
import traceback

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

import requests
from requests import ConnectTimeout
from requests import ConnectionError
from requests import Timeout

from .api.service import Service
from .api.xsd import device as deviceParser

LOG = logging.getLogger(__name__)

# Start with the most commonly used port
PROBE_PORTS = (49153, 49152, 49154, 49151, 49155)


def probe_wemo(host, ports=PROBE_PORTS, probe_timeout=10):
    """Probe a host for the current port.

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
        except ConnectTimeout:
            # If we timed out connecting, then the wemo is gone,
            # no point in trying further.
            LOG.debug('Timed out connecting to %s on port %i, '
                      'wemo is offline', host, port)
            break
        except Timeout:
            # Apparently sometimes wemos get into a wedged state where
            # they still accept connections on an old port, but do not
            # respond. If that happens, we should keep searching.
            LOG.debug('No response from %s on port %i, continuing',
                      host, port)
            continue
        except ConnectionError:
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
    pass


class Device(object):
    def __init__(self, url, mac):
        self._state = None
        self._rediscovery_enabled = True
        self._config = None
        self._basic_state_params = {}
        self._services = {}
        self.mac = mac
        self.url = url
        self.rediscovery_pending = False

        # Get device config (one time only)
        xml = requests.get(self.url, timeout=10)
        self._config = deviceParser.parseString(xml.content).device

        # Setup device services (one time only)
        service_list = self._config.serviceList
        for service in service_list.service:
            service_name = service.get_serviceType().split(':')[-2]
            service_instance = Service(self, service)
            self._services[service_name] = service_instance
            setattr(self, service_name, service_instance)

    def update_config(self, device):
        """ Updates the cached device configuration data"""
        self.url = device.url
        LOG.debug("%s device configuration updated. New URL: %s", self.name, self.url)

    def _reconnect_with_device_by_discovery(self):
        """
        Wemos tend to change their port number from time to time.
        Whenever requests throws an error, we will try to find the device again
        on the network and update this device. """

        # Put here to avoid circular dependency
        from ..discovery import discover_devices

        LOG.info("Trying to reconnect with %s", self.name)
        # We will try to find it 5 times, each time we wait a bigger interval
        try_no = 0

        while True:
            found = discover_devices(st=None, max_devices=1,
                                     match_mac=self.mac,
                                     match_serial=self.serialnumber)

            if found:
                LOG.info("Found %s again at %s:%s, updating local values...",
                         self.name, found[0].host, found[0].port)

                return found[0]

            wait_time = try_no * 5

            LOG.info(
                "%s Not found in try %s. Trying again in %s seconds",
                self.name, try_no, wait_time)

            if try_no == 5:
                LOG.error(
                    "Unable to reconnect with %s in 5 tries. Stopping.",
                    self.name)
                return None

            time.sleep(wait_time)

            try_no += 1

    def _reconnect_with_device_by_probing(self):
        from ..discovery import device_from_description

        port = probe_device(self)

        if port is None:
            LOG.error('Unable to re-probe wemo at %s', self.host)
            return False

        LOG.info('Reconnecting to wemo at %s on port %s...',
                 self.host, port)

        url = 'http://{}:{}/setup.xml'.format(self.host, port)
        device = device_from_description(url, None)

        return device

    def reconnect_with_device(self):
        ret_val = None

        if self.rediscovery_enabled and not self.rediscovery_pending:
            try:
                self.rediscovery_pending = True

                LOG.debug("Attempting to rediscover wemo at %s by probing for a new port...", self.host)
                device = self._reconnect_with_device_by_probing()

                if not device and (self.mac or self.serialnumber):
                    LOG.debug("Attempting to rediscover wemo at %s by ssdp discovery...", self.host)
                    device = self._reconnect_with_device_by_discovery()

                if not device:
                    self.update_config(device)
#                    ret_val = device.url
            except Exception as err:
                LOG.error('Error while rediscovering wemo at %s: %s', self.url, traceback.format_exc())
            finally:
                self.rediscovery_pending = False

        return ret_val

    def parse_basic_state(self, params):
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
        self._basic_state_params = self.basicevent.GetBinaryState()

    def subscription_update(self, _type, _params):
        LOG.debug("subscription_update %s %s", _type, _params)
        if _type == "BinaryState":
            try:
                self._state = int(self.parse_basic_state(_params).get("state"))
            except ValueError:
                self._state = 0
            return True
        return False

    def get_state(self, force_update=False):
        """
        Returns 0 if off and 1 if on.
        """
        if force_update or self._state is None:
            state = self.basicevent.GetBinaryState() or {}

            try:
                self._state = int(state.get('BinaryState', 0))
            except ValueError:
                self._state = 0

        return self._state

    def get_service(self, name):
        try:
            return self._services[name]
        except KeyError:
            raise UnknownService(name)

    def list_services(self):
        return list(self._services.keys())

    def explain(self):
        for name, svc in self._services.items():
            print(name)
            print('-' * len(name))
            for aname, action in svc.actions.items():
                print("  %s(%s)" % (aname, ', '.join(action.args)))
            print()

    def disable_rediscovery(self):
        self._rediscovery_enabled = False
        LOG.debug("Rediscovery disabled for wemo at: %s", self.url)


    def enable_rediscovery(self):
        self._rediscovery_enabled = True
        LOG.debug("Rediscovery enabled for wemo at: %s", self.url)

    @property
    def _parsed_url(self):
        return urlparse(self.url)

    @property
    def event_sub_url(self):
        event_sub_url = self.base_url + self._config.serviceList.service[0].get_eventSubURL()
        return event_sub_url

    @property
    def model(self):
        return self._config.get_modelDescription()

    @property
    def model_name(self):
        return self._config.get_modelName()

    @property
    def name(self):
        return self._config.get_friendlyName()

    @property
    def serialnumber(self):
        return self._config.get_serialNumber()

    @property
    def rediscovery_enabled(self):
        return self._rediscovery_enabled

    @property
    def base_url(self):
        return self.url.rsplit('/', 1)[0]

    @property
    def host(self):
        return self._parsed_url.hostname

    @property
    def port(self):
        return self._parsed_url.port
