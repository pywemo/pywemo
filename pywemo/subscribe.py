"""Module to listen for wemo events."""
import BaseHTTPServer
import collections
import functools
import logging
import sched
import socket
import time
import threading

from xml.etree import cElementTree

import requests

LOG = logging.getLogger(__name__)
NS = "{urn:schemas-upnp-org:event-1-0}"
SUCCESS = '<html><body><h1>200 OK</h1></body></html>'
PORT = 8989


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
    LOG.info("Got wemo event")
    outer = self.server.outer
    device = outer._devices.get(self.client_address)
    if device is not None:
      content_len = int(self.headers.getheader('content-length', 0))
      data = self.rfile.read(content_len)
      # trim garbage from end, if any
      data = data.split("\n\n")[0]
      LOG.info(data)
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
    self.wfile.write(SUCCESS)


class SubscriptionRegistry(object):
  """Class for subscribing to wemo events."""

  def __init__(self):
    self._devices = {}
    self._callbacks = collections.defaultdict(list)
    self._sched = sched.scheduler(time.time, time.sleep)
    self._exiting = False
    self._http_thread = None
    self._event_thread = None
    self._httpd = None

  def register(self, device):
    if not device:
      LOG.error("Received an invalid device: %r", device)
      return

    LOG.info("Subscribing to basic events from %r", device)
    # Provide a function to register a callback when the device changes
    # state
    device.register_listener = functools.partial(self.on, device, 'BinaryState')
    self._devices[device.host] = device
    self._sched.enter(0, 0, self._resubscribe, [device.basicevent.eventSubURL])

  def _resubscribe(self, url, sid=None):
    headers = {'TIMEOUT': 300}
    if sid is not None:
      headers['SID'] = sid
    else:
      host = get_ip_address()
      headers.update({
          "CALLBACK": '<http://%s:%d>' % (host, PORT),
          "NT": "upnp:event"
      })
    response = requests.request(method="SUBSCRIBE", url=url,
                                headers=headers)
    if response.status_code == 412 and sid:
      # Invalid subscription ID. Send an UNSUBSCRIBE for safety and
      # start over.
      requests.request(method='UNSUBSCRIBE', url=url,
                         headers={'SID': sid})
      return self._resubscribe(url)
    timeout = int(response.headers.get('timeout', '1801').replace(
        'Second-', ''))
    sid = response.headers.get('sid', sid)
    self._sched.enter(int(timeout * 0.75), 0, self._resubscribe, [url, sid])

  def _event(self, device, type_, value):
    for type__, callback in self._callbacks.get(device, ()):
      if type_ == type__:
        callback(value)

  def on(self, device, type_, callback):
    self._callbacks[device].append((type_, callback))

  def start(self):
    self._http_thread = threading.Thread(target=self._run_http_server,
                                         name='Wemo HTTP Thread')
    self._http_thread.deamon = True
    self._http_thread.start()

    self._event_thread = threading.Thread(target=self._run_event_loop,
                                          name='Wemo Events Thread')
    self._event_thread.deamon = True
    self._event_thread.start()

  def stop(self):
    self._exiting = True
    self._httpd.shutdown()
    self._sched.enter(0, 0, lambda: None, [])
    self._http_thread.join()
    self._event_thread.join()

  def _run_http_server(self):
    self._httpd = BaseHTTPServer.HTTPServer(('', PORT), RequestHandler)
    self._httpd.allow_reuse_address = True
    self._httpd.outer = self
    LOG.info("Wemo listening on port %d", PORT)
    self._httpd.serve_forever()

  def _run_event_loop(self):
    while not self._exiting:
      if self._sched.empty():
        time.sleep(10)
      self._sched.run()
