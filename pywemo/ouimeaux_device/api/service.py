"""Representation of Services and Actions for WeMo devices."""
# flake8: noqa E501
import logging
from xml.etree import cElementTree as et

import requests

from .xsd import service as serviceParser


LOG = logging.getLogger(__name__)
MAX_RETRIES = 3

REQUEST_TEMPLATE = """
<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
<s:Body>
<u:{action} xmlns:u="{service}">
{args}
</u:{action}>
</s:Body>
</s:Envelope>
"""


class ActionException(Exception):
    """Generic exceptions when dealing with Actions."""

    pass


class Action:
    """Representation of an Action for a WeMo device."""

    def __init__(self, device, service, action_config):
        """Create an instance of an Action."""
        self._device = device
        self._action_config = action_config
        self.name = action_config.get_name()
        # pylint: disable=invalid-name
        self.serviceType = service.serviceType
        self.controlURL = service.controlURL
        self.args = {}
        self.headers = {
            'Content-Type': 'text/xml',
            'SOAPACTION': '"%s#%s"' % (self.serviceType, self.name)
        }

        arglist = action_config.get_argumentList()
        if arglist is not None:
            for arg in arglist.get_argument():
                self.args[arg.get_name()] = 0

    def __call__(self, **kwargs):
        """Representations a method or function call."""
        arglist = '\n'.join('<{0}>{1}</{0}>'.format(arg, value)
                            for arg, value in kwargs.items())
        body = REQUEST_TEMPLATE.format(
            action=self.name,
            service=self.serviceType,
            args=arglist
        )
        for attempt in range(3):
            try:
                response = requests.post(
                    self.controlURL, body.strip(),
                    headers=self.headers, timeout=10)
                response_dict = {}
                # pylint: disable=deprecated-method
                for response_item in et.fromstring(
                        response.content
                ).getchildren()[0].getchildren()[0].getchildren():
                    response_dict[response_item.tag] = response_item.text
                return response_dict
            except requests.exceptions.RequestException:
                LOG.warning("Error communicating with %s at %s:%i, retry %i",
                            self._device.name, self._device.host,
                            self._device.port, attempt)

                if self._device.rediscovery_enabled:
                    self._device.reconnect_with_device()

        LOG.error("Error communicating with %s after %i attempts. Giving up.",
                  self._device.name, MAX_RETRIES)

        raise ActionException(
            "Error communicating with {0} after {1} attempts."
            "Giving up.".format(self._device.name, MAX_RETRIES))

    def __repr__(self):
        """Return a string representation of the Action."""
        return "<Action %s(%s)>" % (self.name, ", ".join(self.args))


class Service:
    """Representation of a service for a WeMo device."""

    def __init__(self, device, service, base_url):
        """Create an instance of a Service."""
        self._base_url = base_url.rstrip('/')
        self._config = service
        self.name = self._config.get_serviceType().split(':')[-2]
        self.actions = {}

        url = '%s/%s' % (base_url, service.get_SCPDURL().strip('/'))
        xml = requests.get(url, timeout=10)
        if xml.status_code != 200:
            return

        self._svc_config = serviceParser.parseString(xml.content).actionList
        for action in self._svc_config.get_action():
            act = Action(device, self, action)
            name = action.get_name()
            self.actions[name] = act
            setattr(self, name, act)

    @property
    def hostname(self):
        """Get the hostname from the base URL."""
        return self._base_url.split('/')[-1]

    # pylint: disable=invalid-name
    @property
    def controlURL(self):
        """Get the controlURL for interacting with this Service."""
        return '%s/%s' % (self._base_url,
                          self._config.get_controlURL().strip('/'))

    @property
    def serviceType(self):
        """Get the type of this Service."""
        return self._config.get_serviceType()

    def __repr__(self):
        """Return a string representation of the Service."""
        return "<Service %s(%s)>" % (self.name, ", ".join(self.actions))
