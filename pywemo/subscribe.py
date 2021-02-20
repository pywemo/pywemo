"""Module to listen for wemo events."""
import collections
import logging
import sched
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Iterable, List, Optional

import requests
from lxml import etree as et

from .exceptions import SubscriptionRegistryFailed
from .ouimeaux_device import Device
from .ouimeaux_device.api.long_press import VIRTUAL_DEVICE_UDN
from .ouimeaux_device.api.service import REQUESTS_TIMEOUT
from .util import get_ip_address

# Subscription event types.
EVENT_TYPE_BINARY_STATE = "BinaryState"
EVENT_TYPE_INSIGHT_PARAMS = "InsightParams"
EVENT_TYPE_LONG_PRESS = "LongPress"

LOG = logging.getLogger(__name__)
NS = "{urn:schemas-upnp-org:event-1-0}"
RESPONSE_SUCCESS = '<html><body><h1>200 OK</h1></body></html>'
RESPONSE_NOT_FOUND = '<html><body><h1>404 Not Found</h1></body></html>'
SUBSCRIPTION_RETRY = 60

VIRTUAL_SETUP_XML = f"""<?xml version="1.0"?>
<root xmlns="urn:Belkin:device-1-0">
  <specVersion>
    <major>1</major>
    <minor>0</minor>
  </specVersion>
  <device>
    <deviceType>urn:Belkin:device:switch:1</deviceType>
    <friendlyName>pywemo virtual device</friendlyName>
    <manufacturer>pywemo</manufacturer>
    <manufacturerURL>https://github.com/pavoni/pywemo</manufacturerURL>
    <modelDescription>pywemo virtual device</modelDescription>
    <modelName>LightSwitch</modelName>
    <modelNumber>1.0</modelNumber>
    <hwVersion>v1</hwVersion>
    <modelURL>http://www.belkin.com/plugin/</modelURL>
    <serialNumber>VirtualDevice</serialNumber>
    <UDN>{VIRTUAL_DEVICE_UDN}</UDN>
    <binaryState>0</binaryState>
    <serviceList>
      <service>
        <serviceType>urn:Belkin:service:basicevent:1</serviceType>
        <serviceId>urn:Belkin:serviceId:basicevent1</serviceId>
        <controlURL>/upnp/control/basicevent1</controlURL>
        <eventSubURL>/upnp/event/basicevent1</eventSubURL>
        <SCPDURL>/eventservice.xml</SCPDURL>
      </service>
    </serviceList>
</device>
</root>"""


class Subscription:
    """Subscription to a single UPnP service endpoint."""

    # Scheduler Event used to periodically maintain the subscription.
    # pylint: disable=unsubscriptable-object
    scheduler_event: Optional[sched.Event] = None
    # pylint: enable=unsubscriptable-object

    # Controls whether or not the subscription will continue to be periodically
    # scheduled by the Scheduler. Set to False when the device us unregistered.
    scheduler_active: bool = True

    # Time that the subscription will expire, or 0.0 if not subscribed.
    # time.time() value.
    expiration_time: float = 0.0

    # Has a notification event been received for this subscription?
    event_received: bool = False

    # Subscription Identifer (SID) used to maintain/refresh the subscription.
    # `None` when the subscription is not active.
    # pylint: disable=unsubscriptable-object
    subscription_id: Optional[str] = None
    # pylint: enable=unsubscriptable-object

    # Request that the device keep the subscription active for this number of
    # seconds.
    default_timeout_seconds: int = 300

    # WeMo device instance.
    device: Device

    # HTTP port used by devices to send event notifications.
    callback_port: int

    # Name of the subscription endpoint service.
    service_name: str

    def __init__(self, device: Device, callback_port: int, service_name: str):
        """Initialize a new subscription."""
        self.device = device
        self.callback_port = callback_port
        self.service_name = service_name

    def __repr__(self) -> str:
        """Return a string representation of the Subscription."""
        return f'<Subscription {self.service_name} "{self.device.name}">'

    def maintain(self) -> int:
        """Start/renew the UPnP subscription.

        Returns:
            The duration of the subscription in seconds.

        Raises:
            requests.RequestException on error.
        """
        try:
            response = self._subscribe()
            if response.status_code == 412:  # Precondition Failed.
                # Invalid parameters were used for the subscription request.
                # This typically happens when the subscription_id becomes
                # invalid. Send an UNSUBSCRIBE for safety and then attempt to
                # subscribe again.
                self._unsubscribe()

                # Also reset the `event_received` boolean at this point. A 412
                # response code to a subscription renewal also happens when a
                # device restarts. When a device loses power and power is
                # restored it's possible that the device's state has changed.
                # We need to reconfirm that the initial event is received again
                # so that the device state is reported properly. And for
                # devices that don't report their initial state, it's important
                # that clients are aware that they should begin polling the
                # device again.
                self.event_received = False

                # Try the subscription again.
                response = self._subscribe()
            response.raise_for_status()
        except requests.RequestException:
            self._reset_subscription()
            raise

        return self._update_subscription(response.headers)

    def _subscribe(self) -> requests.Response:
        """Start/renew a subscription with a UPnP SUBSCRIBE request.

        Will renew an existing subscription if one exists, otherwise a new
        subscription will be created.
        """
        if self.subscription_id:  # Renew existing subscription.
            headers = {'SID': self.subscription_id}
        else:  # Start a new subscription.
            host = get_ip_address(host=self.device.host)
            callback = f'<http://{host}:{self.callback_port}{self.path}>'
            headers = {'CALLBACK': callback, 'NT': 'upnp:event'}
        headers['TIMEOUT'] = f'Second-{self.default_timeout_seconds}'
        return requests.request(
            method='SUBSCRIBE',
            url=self.url,
            headers=headers,
            timeout=REQUESTS_TIMEOUT,
        )

    def _unsubscribe(self) -> None:
        """Remove the subscription on the WeMo with a UPnP UNSUBSCRIBE request.

        Only sends the UNSUBSCRIBE message if there is an existing
        subscription. Does nothing if there is no subscription.
        """
        if self.subscription_id:
            subscription_id = self.subscription_id
            self.subscription_id = None
            requests.request(
                method='UNSUBSCRIBE',
                url=self.url,
                headers={'SID': subscription_id},
                timeout=REQUESTS_TIMEOUT,
            )

    def _update_subscription(self, headers) -> int:
        """Update UPnP subscription parameters from SUBSCRIBE response headers.

        Returns:
            The duration of the subscription in seconds.
        """
        self.subscription_id = headers.get('SID', self.subscription_id)
        timeout_header = headers.get('TIMEOUT', None)
        if timeout_header:
            timeout = min(
                int(timeout_header.replace('Second-', '')),
                self.default_timeout_seconds,
            )
        else:
            timeout = self.default_timeout_seconds
        self.expiration_time = timeout + time.time()
        return timeout

    def _reset_subscription(self) -> None:
        """Mark a subscription as no longer active.

        `self.is_subscribed` will return False after this call.
        """
        self.event_received = False
        self.expiration_time = 0.0
        self.subscription_id = None

    @property
    def url(self) -> str:
        """URL for the UPnP subscription endoint."""
        return self.device.services[self.service_name].eventSubURL

    @property
    def path(self) -> str:
        """Path for the callback to disambiguate multiple subscriptions."""
        return f'/sub/{self.service_name}'

    @property
    def is_subscribed(self) -> bool:
        """Return True if the subscription is active, False otherwise.

        Verifies that the subscription is within its expected lifetime and that
        at least one event notification has been received.

        There will always be at least one event notification because the UPnP
        spec states that the device will send an event notification when the
        subscription is first accepted.
        """
        return self.event_received and self.expiration_time > time.time()


def _start_server():
    """Find a valid open port and start the HTTP server."""
    for i in range(0, 128):
        port = 8989 + i
        try:
            return ThreadingHTTPServer(('', port), RequestHandler)
        except OSError:
            continue
    return None


def _cancel_events(
    scheduler: sched.scheduler, subscriptions: Iterable[Subscription]
) -> None:
    """Cancel pending scheduler events."""
    for subscription in subscriptions:
        try:
            scheduler.cancel(subscription.scheduler_event)
        except ValueError:
            # event might execute and be removed from queue
            # concurrently.  Safe to ignore
            pass
        # Prevent the subscription from being scheduled again.
        subscription.scheduler_active = False
        subscription.scheduler_event = None


class RequestHandler(BaseHTTPRequestHandler):
    """Handles subscription responses and long press actions from devices.

    Subscription responses:
      Pywemo can subscribe to Wemo devices. When subscribed, the Wemo device
      will send notifications when the state of the device changes. The
      do_NOTIFY method below is called when a Wemo device changes state.

    Long press actions:
      Wemo devices can control the state of other Wemo devices based on the
      rules configured for the device. A long press rule is activated whenever
      the button on the Wemo device is pressed for 2 seconds. The long press
      rule is meant to be used to control the state of another device (turn
      on/off/toggle). However for pywemo's use, a long press rule can be used
      to trigger an event notification. This is implemented by configuring the
      Wemo device to "control the state" of a virtual Wemo device. The virtual
      device is implemented by this class.

      The do_GET/do_POST/do_SUBSCRIBE methods below implement a virtual Wemo
      device. The virtual device receives requests to change its state from
      other Wemo devices on the network. When a Wemo device is configured to
      change the state of the virtual device via a long press rule the
      following sequence occurs:

      1. The Wemo device will attempt to locate the virtual device on the
      network. This is handled by the pywemo.ssdp.DiscoveryResponder class. See
      the documentation there for more information about this step.

      2. The Wemo device will fetch /setup.xml from do_GET to learn of the
      virtual device details.

      3. The Wemo device will subscribe to BinaryState notifications from the
      virtual device. The virtual device does not send any BinaryState
      notifications, but this step seems to be necessary before the next step
      can happen. This step is implemented by the do_SUBSCRIBE method.

      4. When a person presses the button on the Wemo for 2 seconds a long
      press rule is triggered. If the long press rule is configured with an
      action for the virtual device, the Wemo device will then call the do_POST
      method to update the BinaryState of the virtual device. This doesn't
      actually update any state, rather the virtual device then delivers the
      event notification to any event listeners configured to receive events
      from the pywemo SubscriptionRegistry. The event type for a long press
      action is EVENT_TYPE_LONG_PRESS.
    """

    # Do not wait for more than 10 seconds for any request to complete.
    timeout = 10

    def do_NOTIFY(self):  # pylint: disable=invalid-name
        """Handle subscription responses received from devices."""
        sender_ip, _ = self.client_address
        outer = self.server.outer
        device = outer.devices.get(sender_ip)
        if device is None:
            LOG.warning(
                'Received %s event for unregistered device %s',
                self.path,
                sender_ip,
            )
        else:
            doc = self._get_xml_from_http_body()
            for propnode in doc.findall('./{0}property'.format(NS)):
                for property_ in list(propnode):
                    text = property_.text
                    outer.event(device, property_.tag, text, path=self.path)

        self._send_response(200, RESPONSE_SUCCESS)

    def do_GET(self):  # pylint: disable=invalid-name
        """Handle GET requests for a Virtual WeMo device."""
        if self.path.endswith("/setup.xml"):
            self._send_response(
                200, VIRTUAL_SETUP_XML, content_type="text/xml"
            )
        else:
            self._send_response(404, RESPONSE_NOT_FOUND)

    def do_POST(self):  # pylint: disable=invalid-name
        """Handle POST requests for a Virtual WeMo device."""
        if self.path.endswith("/upnp/control/basicevent1"):
            sender_ip, _ = self.client_address
            outer = self.server.outer
            device = outer.devices.get(sender_ip)
            if device is None:
                LOG.warning(
                    'Received event for unregistered device %s', sender_ip
                )
            else:
                doc = self._get_xml_from_http_body()
                binary_state = doc.find('.//BinaryState')
                if binary_state is not None:
                    text = binary_state.text
                    outer.event(device, EVENT_TYPE_LONG_PRESS, text)
            self._send_response(200, RESPONSE_SUCCESS)
        else:
            self._send_response(404, RESPONSE_NOT_FOUND)

    def do_SUBSCRIBE(self):  # pylint: disable=invalid-name
        """Handle SUBSCRIBE requests for a Virtual WeMo device."""
        if self.path.endswith("/upnp/event/basicevent1"):
            self.send_response(200)
            self.send_header("CONTENT-LENGTH", "0")
            self.send_header("TIMEOUT", "Second-1801")
            # Using a randomly generated valid UUID (uuid.uuid4()).
            self.send_header(
                "SID", "uuid:a74b23d5-34b9-4f71-9f87-bed24353f304"
            )
            self.send_header('Connection', 'close')
            self.end_headers()
        else:
            self._send_response(404, RESPONSE_NOT_FOUND)

    def _send_response(self, code, body, *, content_type="text/html"):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', len(body))
        self.send_header('Connection', 'close')
        self.end_headers()
        if body:
            self.wfile.write(body.encode("UTF-8"))

    def _get_xml_from_http_body(self):
        """Build the element tree root from the body of the http request."""
        content_len = int(self.headers.get('content-length', 0))
        data = self.rfile.read(content_len)
        # trim garbage from end, if any
        data = data.strip()
        return et.fromstring(data)

    # pylint: disable=redefined-builtin
    def log_message(self, format, *args):
        """Disable error logging."""
        return


class SubscriptionRegistry:
    """Holds device subscriptions and callbacks for wemo events."""

    # Potential service endpoints for subscriptions. A Subscription will be
    # created for each entry as long as the service is supported by the device.
    subscription_service_names: Iterable[str] = ('basicevent', 'insight')

    def __init__(self):
        """Create the subscription registry object."""
        self.devices = {}
        self._callbacks = collections.defaultdict(list)
        self._exiting = False

        self._event_thread = None
        self._event_thread_cond = threading.Condition()
        self._subscriptions: Dict[Device, List[Subscription]] = {}

        def sleep(secs):
            with self._event_thread_cond:
                self._event_thread_cond.wait(secs)

        self._sched = sched.scheduler(time.time, sleep)

        self._http_thread = None
        self._httpd = None

    @property
    def port(self) -> int:
        """Return the port that the http server is listening on."""
        return self._httpd.server_address[1]

    def register(self, device):
        """Register a device for subscription updates."""
        if not device:
            LOG.error("Called with an invalid device: %r", device)
            return

        LOG.info("Subscribing to events from %r", device)
        self.devices[device.host] = device

        with self._event_thread_cond:
            subscriptions = self._subscriptions[device] = []
            for service in self.subscription_service_names:
                if service in device.services:
                    subscription = Subscription(device, self.port, service)
                    subscriptions.append(subscription)
                    self._schedule(0, subscription)
            self._event_thread_cond.notify()

    def unregister(self, device):
        """Unregister a device from subscription updates."""
        if not device:
            LOG.error("Called with an invalid device: %r", device)
            return

        LOG.info("Unsubscribing to events from %r", device)

        with self._event_thread_cond:
            # Remove any events, callbacks, and the device itself
            if device in self._callbacks:
                del self._callbacks[device]
            if device in self._subscriptions:
                _cancel_events(self._sched, self._subscriptions[device])
                del self._subscriptions[device]
            if device.host in self.devices:
                del self.devices[device.host]
            self._event_thread_cond.notify()

    def _resubscribe(self, subscription: Subscription, retry: int = 0) -> None:
        LOG.info("Resubscribe for %r", subscription)
        try:
            timeout = subscription.maintain()
            with self._event_thread_cond:
                self._schedule(int(timeout * 0.75), subscription)
        except requests.RequestException as exc:
            LOG.warning(
                "Resubscribe error for %r (%s), will retry in %ss",
                subscription,
                exc,
                SUBSCRIPTION_RETRY,
            )
            retry += 1
            if retry > 1:
                # If this wasn't a one-off, try rediscovery
                # in case the device has changed.
                subscription.device.reconnect_with_device()
            with self._event_thread_cond:
                self._schedule(SUBSCRIPTION_RETRY, subscription, retry=retry)

    def _schedule(
        self, delay: int, subscription: Subscription, **kwargs
    ) -> None:
        """Schedule a subscription.

        It is expected that the caller will hold the `_event_thread_cond` lock
        before calling this method.

        This method will not schedule a subscription when the
        `subscription.scheduler_active` property is False. This is done to
        avoid a race condition with the `unregister` method. Once `unregister`
        removes the subscription, it should not be scheduled again.
        """
        if subscription.scheduler_active:
            subscription.scheduler_event = self._sched.enter(
                delay,
                0,  # priority
                self._resubscribe,
                argument=(subscription,),
                kwargs=kwargs,
            )

    def event(self, device, type_, value, path=None):
        """Execute the callback for a received event."""
        LOG.info(
            "Received %s event from %s(%s) - %s %s",
            path or 'an',
            device,
            device.host,
            type_,
            value,
        )
        if path:
            # Update the event_received property for the subscription.
            for subscription in self._subscriptions.get(device, []):
                if subscription.path == path:
                    subscription.event_received = True
                    break
            else:
                LOG.warning(
                    'Received unexpected subscription path (%s) for device %s',
                    path,
                    device,
                )
        for type_filter, callback in self._callbacks.get(device, ()):
            if type_filter is None or type_ == type_filter:
                callback(device, type_, value)

    def on(self, device, type_filter, callback):
        """Add an event callback for a device."""
        self._callbacks[device].append((type_filter, callback))

    def is_subscribed(self, device: Device) -> bool:
        """Return True if all of the device's subscriptions are active."""
        subscriptions = self._subscriptions.get(device, [])
        return subscriptions and all(s.is_subscribed for s in subscriptions)

    def start(self):
        """Start the subscription registry."""
        self._httpd = _start_server()
        if self._httpd is None:
            raise SubscriptionRegistryFailed(
                'Unable to bind a port for listening'
            )
        self._http_thread = threading.Thread(
            target=self._run_http_server, name='Wemo HTTP Thread'
        )
        self._http_thread.deamon = True
        self._http_thread.start()

        self._event_thread = threading.Thread(
            target=self._run_event_loop, name='Wemo Events Thread'
        )
        self._event_thread.deamon = True
        self._event_thread.start()

    def stop(self):
        """Shutdown the HTTP server."""
        self._httpd.shutdown()

        with self._event_thread_cond:
            self._exiting = True

            # Remove any pending events
            for device_subscriptions in self._subscriptions.values():
                _cancel_events(self._sched, device_subscriptions)

            # Wake up event thread if its sleeping
            self._event_thread_cond.notify()
        self.join()
        LOG.info("Terminated threads")

    def join(self):
        """Block until the HTTP server and event threads have terminated."""
        self._http_thread.join()
        self._event_thread.join()

    def _run_http_server(self):
        """Start the HTTP server."""
        self._httpd.allow_reuse_address = True
        self._httpd.outer = self
        LOG.info("Listening on port %d", self.port)
        self._httpd.serve_forever()

    def _run_event_loop(self):
        """Run the event thread loop."""
        while not self._exiting:
            with self._event_thread_cond:
                while not self._exiting and self._sched.empty():
                    self._event_thread_cond.wait(10)
            self._sched.run()
