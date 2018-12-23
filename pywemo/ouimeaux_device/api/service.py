import logging
from xml.etree import cElementTree as et

import requests

from .xsd import service as serviceParser


LOG = logging.getLogger(__name__)

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


class Action(object):
    def __init__(self, service, action_config):
        self.service = service
        self._action_config = action_config
        self._name = action_config.get_name()
        self._args = {}
        self._headers = {
            'Content-Type': 'text/xml',
            'SOAPACTION': '"%s#%s"' % (self.service.service_type, self._name)
        }
        arglist = action_config.get_argumentList()
        if arglist is not None:
            for arg in arglist.get_argument():
                self._args[arg.get_name()] = None

    def __call__(self, **kwargs):
        arglist = '\n'.join('<{0}>{1}</{0}>'.format(arg, value)
                            for arg, value in kwargs.items())

        body = REQUEST_TEMPLATE.format(
            action=self._name,
            service=self.service.service_type,
            args=arglist
        )

        ret_val = None

        for attempt in range(3):
            try:
                response = requests.post(
                    self.service.control_url, body.strip(),
                    headers=self._headers, timeout=10)

                ret_val = {}

                el_tree = et.fromstring(response.content)
                items = el_tree.getchildren()[0].getchildren()[0].getchildren()

                for item in items:
                    ret_val[item.tag] = item.text

                break
            except requests.exceptions.RequestException as err:
                LOG.warning(
                    "Error communicating with %s, retry %s (error: %s)",
                    self.service.device.name, attempt, err)
                if self.service.device.rediscovery_enabled:
                    self.service.device.reconnect_with_device()
#                    rediscovered_device = self.service.device.reconnect_with_device()

#                    if rediscovered_device is not None:
#                        self.service.update_device_config(rediscovered_device)

        if ret_val is None or not ret_val:
            LOG.error(
                "Error communicating with %s. Giving up", self.service.device.name)

        return ret_val

    def __repr__(self):
        return "<Action %s(%s)>" % (self._name, ", ".join(self._args))


class Service(object):
    """
    Represents an instance of a service on a device.
    """

    def __init__(self, device, service):
        self.device = device
        self._config = service
        url = '%s/%s' % (self.device.base_url, service.get_SCPDURL().strip('/'))
        xml = requests.get(url, timeout=10)
        if xml.status_code != 200:
            return
        self._svc_config = serviceParser.parseString(xml.content).actionList
        self._actions = {}
        for action in self._svc_config.get_action():
            action_instance = Action(self, action)
            action_name = action.get_name()
            self._actions[action_name] = action_instance
            setattr(self, action_name, action_instance)

    def update_device_config(self, device):
        self.device.update_config(device)

    @property
    def hostname(self):
        return self.device.base_url.rstrip('/').split('/')[-1]

    @property
    def control_url(self):
        return '%s/%s' % (self.device.base_url.rstrip('/'),
                          self._config.get_controlURL().strip('/'))

    @property
    def service_type(self):
        return self._config.get_serviceType()

    @property
    def name(self):
        return self.service_type.split(':')[-2]

    @property
    def eventSubURL(self):
        return self.device.event_sub_url
