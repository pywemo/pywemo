import logging
import time

try:
  from urllib.parse import urlparse
except ImportError:
  from urlparse import urlparse

import requests

from .api.service import Service
from .api.xsd import device as deviceParser

log = logging.getLogger(__name__)

PROBE_PORTS = (45152, 49153, 49154)


def probe_wemo(host):
    """Probe a host for the current port.

    This probes a host for known-to-be-possible ports and
    returns the one currently in use. If no port is discovered
    then it returns None.
    """
    for port in PROBE_PORTS:
        try:
            r = requests.get('http://%s:%i/setup.xml' % (host, port),
                             timeout=10)
            if 'WeMo' in r.text:
              return port
        except requests.exceptions.ConnectTimeout:
            # If we timed out connecting, then the wemo is gone,
            # no point in trying further.
            log.debug('Timed out connecting to %s on port %i, '
                      'wemo is offline', host, port)
            break
        except requests.exceptions.Timeout:
            # Apparently sometimes wemos get into a wedged state where
            # they still accept connections on an old port, but do not
            # respond. If that happens, we should keep searching.
            log.debug('No response from %s on port %i, continuing',
                      host, port)
            continue
        except requests.exceptions.ConnectionError:
            pass
    return None


class UnknownService(Exception): pass


class Device(object):
    def __init__(self, url, mac):
        self._state = None
        base_url = url.rsplit('/', 1)[0]
        self.host = urlparse(url).hostname
        self.retrying = False
        #self.port = urlparse(url).port
        self.mac = mac
        xml = requests.get(url, timeout=10)
        self._config = deviceParser.parseString(xml.content).device
        sl = self._config.serviceList
        self.services = {}
        for svc in sl.service:
            svcname = svc.get_serviceType().split(':')[-2]
            service = Service(self, svc, base_url)
            service.eventSubURL = base_url + svc.get_eventSubURL()
            self.services[svcname] = service
            setattr(self, svcname, service)

    def _reconnect_with_device_by_discovery(self):
        """
        Wemos tend to change their port number from time to time.
        Whenever requests throws an error, we will try to find the device again
        on the network and update this device. """

        # Put here to avoid circular dependency
        from ..discovery import discover_devices

        # Avoid retrying from multiple threads
        if self.retrying:
           return

        self.retrying = True
        log.info("Trying to reconnect with {}".format(self.name))
        # We will try to find it 5 times, each time we wait a bigger interval
        try_no = 0

        while True:
            found = discover_devices(None, 1, self.mac)

            if found:
                log.info("Found {} again, updating local values".format(self.name))

                self.__dict__ = found[0].__dict__
                self.retrying = False
                return

            wait_time = try_no * 5

            log.info(
                "{} Not found in try {}. Trying again in {} seconds".format(
                    self.name, try_no, wait_time))

            if try_no == 5:
                log.error(
                    "Unable to reconnect with {} in 5 tries. Stopping.".format(self.name))
                self.retrying = False
                return

            time.sleep(wait_time)

            try_no += 1

    def _reconnect_with_device_by_probing(self):
        port = probe_wemo(self.host)
        if port is None:
            log.error('Unable to re-probe wemo at {}'.format(self.host))
            return False
        log.info('Reconnected to wemo at {} on port {}'.format(
            self.host, port))
        url = 'http://{}:{}/setup.xml'.format(self.host, port)
        self.__dict__ = self.__class__(url, None).__dict__
        return True

    def reconnect_with_device(self):
        if not self._reconnect_with_device_by_probing() and self.mac:
            self._reconnect_with_device_by_discovery()

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
            return self.services[name]
        except KeyError:
            raise UnknownService(name)

    def list_services(self):
        return list(self.services.keys())

    def explain(self):
        for name, svc in self.services.items():
            print(name)
            print('-' * len(name))
            for aname, action in svc.actions.items():
                print("  %s(%s)" % (aname, ', '.join(action.args)))
            print()

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
