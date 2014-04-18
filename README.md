pyWeMo
======
Lightweight Python 3 module to discover and control WeMo devices.

This is a stripped down version of the Python API for WeMo devices [ouimeaux](https://github.com/iancmcc/ouimeaux). It is stripped down because in my opinion it had a bunch of unnecessary dependencies and functionality.

Dependencies
------------
pyWeMo depends on Python package requests.

How to use
----------

    >> import pywemo

    >> devices = pywemo.discover_devices()
    >> print devices
    [<WeMo Insight "AC Insight">]

    >> devices[0].toggle()

License
-------
The code in pywemo/ouimeaux_device is written and copyright by Ian McCracken and released under the BSD license. The rest is released under the MIT license.
