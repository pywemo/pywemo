pyWeMo |Build Badge| |PyPI Version Badge| |PyPI Downloads Badge|
================================================================
Lightweight Python 2 and Python 3 module to discover and control WeMo devices.

This is a stripped down version of the Python API for WeMo devices, `ouimeaux <https://github.com/iancmcc/ouimeaux>`_, with simpler dependencies.

Dependencies
------------
pyWeMo depends on Python packages: requests, ifaddr and six

How to use
----------

.. code-block:: python

    >> import pywemo

    >> devices = pywemo.discover_devices()
    >> print(devices)
    [<WeMo Insight "AC Insight">]

    >> devices[0].toggle()


If discovery doesn't work on your network
-----------------------------------------
On some networks discovery doesn't work reliably, in that case if you can find the ip address of your Wemo device you can use the following code.

.. code-block:: python

    >>> import pywemo
    >>> url = pywemo.setup_url_for_address("192.168.1.192", None)
    >>> print(url)
    http://192.168.1.192:49153/setup.xml
    >>> device = pywemo.discovery.device_from_description(url, None)
    >>> print(device)
    <WeMo Maker "Hi Fi Systemline Sensor">

Please note that `discovery.device_from_description` call requires a `url` with an IP address, rather than a hostnames. This is needed for the subscription update logic to work properly. In addition recent versions of the WeMo firmware may not accept connections from hostnames, and will return a 500 error.

The `setup_url_for_address` function will lookup a hostname and provide a suitable `url` with an IP addesss.

Developing
----------
Setup and builds are fully automated. You can run build pipeline locally by running.

.. code-block::

    # Setup, build, lint and test the code:

    ./scripts/build.sh

License
-------
The code in pywemo/ouimeaux_device is written and copyright by Ian McCracken and released under the BSD license. The rest is released under the MIT license.

.. |Build Badge| image:: https://travis-ci.org/pavoni/pywemo.svg?branch=master
   :target: https://travis-ci.org/pavoni/pywemo
   :alt: Status of latest Travis CI build
.. |PyPI Version Badge| image:: https://pypip.in/v/pywemo/badge.png
    :target: https://pypi.org/project/pywemo/
    :alt: Latest PyPI version
.. |PyPI Downloads Badge| image:: https://pypip.in/d/pywemo/badge.png
    :target: https://pypi.org/project/pywemo/
    :alt: Number of PyPI downloads
