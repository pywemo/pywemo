"""Representation of Services and Actions for WeMo devices."""
# flake8: noqa E501
import logging
from urllib.parse import urljoin, urlparse

import urllib3
from lxml import etree as et

from pywemo.exceptions import ActionException, HTTPException

from .xsd import service as serviceParser

LOG = logging.getLogger(__name__)
REQUESTS_TIMEOUT = 10

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


class Session:
    """HTTP session with device.

    The Session provides timeouts and retries by default. The default
    parameters were chosen to provide for 3 attempts within 10 seconds, and
    further attempts beyond that to reestablish a link with the device without
    needing to attempt rediscovery. Retries continue for the duration that it
    would take the device to reboot, at which point reconnect_with_device
    should be able to find the device again by probing.

    It is important to not be too agressive with retries. The WeMo devices only
    have a small number of threads for servicing requests. If the timeout is
    too short or the retries are too frequent, it is easy to overwhelm the
    device with too many requests. This can result in a device that crashes
    and is unavailable until it reboots.

    The `urllib3` library is used as it provides better timeout/retry support
    than the `requests` library. Specifically, the `urllib3` library will
    retry in the case where the response body is not returned within timeout
    seconds. The `requests` library does not support retries of fetching the
    response body and will raise an exception if fetching the response body
    takes longer than the timeout.

    Since much of pywemo is built atop the requests library, a `content`
    field on HTTPResponse is populated from the `data` field.
    """

    # Retry strategy for requests that fail.
    retries = urllib3.Retry(
        total=6, backoff_factor=1.5, allowed_methods=['GET', 'POST']
    )

    # Seconds that a request can be idle before retrying.
    timeout = 3

    def __init__(self, url, retries=None, timeout=None):
        """Create a session with the specified default parameters."""
        self.url = url
        if retries is not None:
            self.retries = retries
        if timeout is not None:
            self.timeout = timeout

    def request(
        self,
        method: str,
        url: str,
        retries=None,
        timeout=None,
        **kwargs,
    ) -> urllib3.HTTPResponse:
        """Send request and gather response.

        A non-200 response code will result in a HTTPException
        exception.

        Args:
            method: HTTP method/verb to use for request (ex: 'GET' or 'POST').
            url: URL to to connect to.
            retries: Number of retries, or urllib3.Retry instance.
            timeout: Timeout in seconds for each request attempt.
            kwargs: Additional arguments for urllib3 pool.request(**kwargs).

        Raises:
            HTTPException for any urllib3 exception or if the response code is
            not 200.
        """
        if retries is None:
            retries = self.retries
        if timeout is None:
            timeout = self.timeout

        # Create and destroy the pool each time. WeMo devices do not support
        # http keep-alive. Forcing the pool to be destroyed ensures that the
        # http connection is also closed. This avoids tying up TCP sessions
        # on the device.
        with urllib3.PoolManager(retries=retries, timeout=timeout) as pool:
            try:
                response = pool.request(method=method, url=url, **kwargs)
                if response.status != 200:
                    raise urllib3.exceptions.HTTPError(
                        f"Received status {response.status} for {url}"
                    )
            except urllib3.exceptions.HTTPError as err:
                raise HTTPException(err) from err
            response.content = response.data  # For `requests` compatibility.
            return response

    def get(self, url: str, **kwargs) -> urllib3.HTTPResponse:
        """HTTP GET request."""
        return self.request('GET', url, **kwargs)

    def post(self, url: str, **kwargs) -> urllib3.HTTPResponse:
        """HTTP POST request."""
        return self.request('POST', url, **kwargs)

    def urljoin(self, path: str) -> str:
        """Build an absolute URL from a path."""
        return urljoin(self._url, path)

    @property
    def url(self) -> str:
        """Return the current URL for the session."""
        return self._url

    @url.setter
    def url(self, url: str) -> str:
        """Update the URL for the session."""
        parsed_url = urlparse(url)
        self._url = parsed_url.geturl()
        self._port = parsed_url.port or 80
        self._host = parsed_url.hostname
        return url

    @property
    def port(self) -> int:
        """TCP port associated with this session."""
        return self._port

    @property
    def host(self) -> str:
        """Hostname associated with this session."""
        return self._host


class Action:
    """Representation of an Action for a WeMo device."""

    # A few actions take longer than the default timeout. Override the default
    # timeout value for those actions.
    soap_action_timeout_override = {
        "urn:Belkin:service:bridge:1#AddDevice": 30,
        "urn:Belkin:service:bridge:1#OpenNetwork": 30,
        "urn:Belkin:service:WiFiSetup:1#GetApList": 10,
    }

    max_rediscovery_attempts = 3

    def __init__(self, service, action_config):
        """Create an instance of an Action."""
        self.service = service
        self._action_config = action_config
        self.name = action_config.get_name()
        self.soap_action = f'{service.serviceType}#{self.name}'
        self.headers = {
            'Content-Type': 'text/xml',
            'SOAPACTION': f'"{self.soap_action}"',
        }

        self.args = []
        arglist = action_config.get_argumentList()
        if arglist is not None:
            self.args.extend(a.get_name() for a in arglist.get_argument())

    def __call__(self, *, pywemo_timeout=None, **kwargs):
        """Representations a method or function call."""
        arglist = '\n'.join(
            '<{0}>{1}</{0}>'.format(arg, value)
            for arg, value in kwargs.items()
        )
        body = REQUEST_TEMPLATE.format(
            action=self.name, service=self.service.serviceType, args=arglist
        ).strip()
        timeout = pywemo_timeout or self.soap_action_timeout_override.get(
            self.soap_action
        )
        last_exception = None

        for attempt in range(self.max_rediscovery_attempts):
            session = self.service.device.session
            try:
                response = session.post(
                    self.service.controlURL,
                    headers=self.headers,
                    body=body,
                    timeout=timeout,
                )
            except HTTPException as err:
                LOG.warning(
                    "Error communicating with %s at %s:%i, %r retry %i",
                    self.service.device.name,
                    session.host,
                    session.port,
                    err,
                    attempt,
                )
                last_exception = err
            else:
                response_dict = {}

                for response_item in list(
                    list(et.fromstring(response.content))[0]
                )[0]:
                    response_dict[response_item.tag] = response_item.text
                return response_dict

            self.service.device.reconnect_with_device()

        msg = (
            f"Error communicating with {self.service.device.name} after "
            f"{self.max_rediscovery_attempts} attempts. Giving up."
        )
        LOG.error(msg)
        raise ActionException(msg) from last_exception

    def __repr__(self):
        """Return a string representation of the Action."""
        return "<Action %s(%s)>" % (self.name, ", ".join(self.args))


class Service:
    """Representation of a service for a WeMo device."""

    def __init__(self, device, service):
        """Create an instance of a Service."""
        self.device = device
        self._config = service
        self.name = self.serviceType.split(':')[-2]
        self.actions = {}

        xml = device.session.get(device.session.urljoin(service.get_SCPDURL()))

        self._svc_config = serviceParser.parseString(
            xml.content, silence=True, print_warnings=False
        ).actionList
        for action in self._svc_config.get_action():
            act = Action(self, action)
            self.actions[act.name] = act
            setattr(self, act.name, act)

    @property
    def controlURL(self):
        """Get the controlURL for interacting with this Service."""
        return self.device.session.urljoin(self._config.get_controlURL())

    @property
    def eventSubURL(self):
        """Get the eventSubURL for interacting with this Service."""
        return self.device.session.urljoin(self._config.get_eventSubURL())

    @property
    def serviceType(self):
        """Get the type of this Service."""
        return self._config.get_serviceType()

    def __repr__(self):
        """Return a string representation of the Service."""
        return "<Service %s(%s)>" % (self.name, ", ".join(self.actions))
