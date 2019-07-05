pyWeMo |Build Status|
=====================
Lightweight Python 2 and Python 3 module to discover and control WeMo devices.

This is a stripped down version of the Python API for WeMo devices [ouimeaux](https://github.com/iancmcc/ouimeaux) with simpler dependencies.

Dependencies
------------
pyWeMo depends on Python packages requests, ifaddr and six.

How to use
----------

.. code:: python

    >> import pywemo

    >> devices = pywemo.discover_devices()
    >> print(devices)
    [<WeMo Insight "AC Insight">]

    >> devices[0].toggle()
    
    
If discovery doesn't work on your network
-----------------------------------------
On some networks discovery doesn't work reliably, in that case if you can find the ip address of your Wemo device you can use the following code.

.. code:: python

    >> import pywemo
    
    >> address = "192.168.100.193"
    >> port = pywemo.ouimeaux_device.probe_wemo(address)
    >> url = 'http://%s:%i/setup.xml' % (address, port)
    >> device = pywemo.discovery.device_from_description(url, None)
    >> print(device)
    <WeMo Insight "AC Insight">
    
Please note that you need to use ip addresses as shown above, rather than hostnames, otherwise the subscription update logic won't work.

License
-------
The code in pywemo/ouimeaux_device is written and copyright by Ian McCracken and released under the BSD license. The rest is released under the MIT license.

.. |Build Status| image:: https://travis-ci.org/pavoni/pywemo.svg?branch=master
   :target: https://travis-ci.org/pavoni/pywemo
