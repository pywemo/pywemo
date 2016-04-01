"""Module to listen for wemo events."""
import collections
import logging
import sched
import socket
import time
import threading

from xml.etree import cElementTree

try:
    import BaseHTTPServer
except ImportError:
    import http.server as BaseHTTPServer

import requests

LOG = logging.getLogger(__name__)
NS = "{urn:schemas-upnp-org:event-1-0}"
SUCCESS = '<html><body><h1>200 OK</h1></body></html>'
SUBSCRIPTION_RETRY = 60


class SubscriptionRegistryFailed(Exception):
    pass


def get_ip_address():
  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  try:
    sock.connect(('1.2.3.4', 9))
    return sock.getsockname()[0]
  except socket.error:
    return None
  finally:
    del sock


class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
  def do_NOTIFY(self):
    sender_ip, _ = self.client_address
    outer = self.server.outer
    device = outer._devices.get(sender_ip)
    content_len = int(self.headers.get('content-length', 0))
    data = self.rfile.read(content_len)
    if device is None:
      LOG.error('Received event for unregistered device %s', sender_ip)
    else:
      # trim garbage from end, if any
      data = data.decode("UTF-8").split("\n\n")[0]
      doc = cElementTree.fromstring(data)
      for propnode in doc.findall('./{0}property'.format(NS)):
        for property_ in propnode.getchildren():
          text = property_.text
          outer._event(device, property_.tag, text)

    self.send_response(200)
    self.send_header('Content-Type', 'text/html')
    self.send_header('Content-Length', len(SUCCESS))
    self.send_header('Connection', 'close')
    self.end_headers()
    self.wfile.write(SUCCESS.encode("UTF-8"))

  def log_message(self, format, *args):
    return


class SubscriptionRegistry(object):
  """Class for subscribing to wemo events."""

  def __init__(self):
    self._devices = {}
    self._callbacks = collections.defaultdict(list)
    self._exiting = False

    self._event_thread = None
    self._event_thread_cond = threading.Condition()
    self._events = {}

    def sleep(secs):
      with self._event_thread_cond:
        self._event_thread_cond.wait(secs)
    self._sched = sched.scheduler(time.time, sleep)

    self._http_thread = None
    self._httpd = None

  def register(self, device):
    if not device:
      LOG.error("Called with an invalid device: %r", device)
      return

    LOG.info("Subscribing to events from %r", device)
    self._devices[device.host] = device

    with self._event_thread_cond:
      self._events[device.serialnumber] = (
          self._sched.enter(0, 0, self._resubscribe, [device]))
      self._event_thread_cond.notify()

  def _resubscribe(self, device, sid=None, retry=0):
    LOG.info("Resubscribe for %s", device)
    headers = {'TIMEOUT': 300}
    if sid is not None:
      headers['SID'] = sid
    else:
      host = get_ip_address()
      headers.update({
          "CALLBACK": '<http://%s:%d>' % (host, self._port),
          "NT": "upnp:event"
      })
    try:
      url = device.basicevent.eventSubURL
      response = requests.request(method="SUBSCRIBE", url=url,
                                  headers=headers)
      if response.status_code == 412 and sid:
        # Invalid subscription ID. Send an UNSUBSCRIBE for safety and
        # start over.
        requests.request(
            method='UNSUBSCRIBE', url=url, headers={'SID': sid})
        return self._resubscribe(device)
      timeout = int(response.headers.get('timeout', '1801').replace(
          'Second-', ''))
      sid = response.headers.get('sid', sid)
      with self._event_thread_cond:
        self._events[device.serialnumber] = (
            self._sched.enter(int(timeout * 0.75),
                              0, self._resubscribe, [device, sid]))
    except requests.exceptions.RequestException:
      LOG.warning(
          "Resubscribe error for %s, will retry in %ss",
          device, SUBSCRIPTION_RETRY)
      retry += 1
      if retry > 1:
        # If this wan't a one off try rediscovery in case device has changed
        device.reconnect_with_device()
      with self._event_thread_cond:
        self._events[device.serialnumber] = (
            self._sched.enter(SUBSCRIPTION_RETRY,
                              0, self._resubscribe, [device, sid, retry]))

  def _event(self, device, type_, value):
    LOG.info("Received event from %s(%s)", device, device.host)
    for type_filter, callback in self._callbacks.get(device, ()):
      if type_filter is None or type_ == type_filter:
        callback(device, value)

  def on(self, device, type_filter, callback):
    self._callbacks[device].append((type_filter, callback))

  def _find_port(self):
    for i in range(0, 128):
      port = 8989 + i
      try:
        self._httpd = BaseHTTPServer.HTTPServer(('', port), RequestHandler)
        self._port = port
        break
      except (OSError, socket.error):
        continue

  def start(self):
    self._port = None
    self._find_port()
    if self._port is None:
      raise SubscriptionRegistryFailed('Unable to bind a port for listening')
    self._http_thread = threading.Thread(target=self._run_http_server,
                                         name='Wemo HTTP Thread')
    self._http_thread.deamon = True
    self._http_thread.start()

    self._event_thread = threading.Thread(target=self._run_event_loop,
                                          name='Wemo Events Thread')
    self._event_thread.deamon = True
    self._event_thread.start()

  def stop(self):
    self._httpd.shutdown()

    with self._event_thread_cond:
      self._exiting = True

      # Remove any pending events
      for event in self._events.values():
        try:
          self._sched.cancel(event)
        except ValueError:
          # event might execute and be removed from queue
          # concurrently.  Safe to ignore
          pass

      # Wake up event thread if its sleeping
      self._event_thread_cond.notify()
    self.join()
    LOG.info(
      "Terminated threads")

  def join(self):
    self._http_thread.join()
    self._event_thread.join()

  def _run_http_server(self):
    self._httpd.allow_reuse_address = True
    self._httpd.outer = self
    LOG.info("Listening on port %d", self._port)
    self._httpd.serve_forever()

  def _run_event_loop(self):
    while not self._exiting:
      with self._event_thread_cond:
        while not self._exiting and self._sched.empty():
          self._event_thread_cond.wait(10)
      self._sched.run()
