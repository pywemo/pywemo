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


class UnknownService(Exception): pass


class Device(object):
    def __init__(self, url):
        self._state = None
        base_url = url.rsplit('/', 1)[0]
        self.host = urlparse(url).hostname
        self.retrying = False
        #self.port = urlparse(url).port
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

    def reconnect_with_device(self):
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
            found = discover_devices(self._config.get_UDN(), 1)

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
