pyWeMo |Build Badge| |PyPI Version Badge| |Coverage| |PyPI Downloads Badge|
===========================================================================
Python 3 module to setup, discover and control WeMo devices.

Dependencies
------------
pyWeMo depends on Python packages: requests, ifaddr, lxml, urllib3

How to use
----------

.. code-block:: python

    >>> import pywemo
    >>> devices = pywemo.discover_devices()
    >>> print(devices)
    [<WeMo Insight "AC Insight">]

    >>> devices[0].toggle()

For advanced usage, the ``device.explain()`` method will print all known actions that the device reports to PyWeMo.

If discovery doesn't work on your network
-----------------------------------------
Automatic discovery may not work reliably on some networks.
In that case, you can use the device with an IP or hostname:

.. code-block:: python

    >>> import pywemo
    >>> url = pywemo.setup_url_for_address("192.168.1.192")
    >>> print(url)
    http://192.168.1.192:49153/setup.xml
    >>> device = pywemo.discovery.device_from_description(url)
    >>> print(device)
    <WeMo Maker "Hi Fi Systemline Sensor">

Please note that ``discovery.device_from_description`` requires a ``url`` with an IP address, rather than a hostname.
This is needed for the subscription update logic to work properly.
In addition, recent versions of the WeMo firmware may not accept connections from hostnames and will return a 500 error.

The ``setup_url_for_address`` function will lookup a hostname and provide a suitable ``url`` with an IP address.

If the WeMo device is not on your network, you can also connect to it directly.
After connecting, if the ``pywemo.discover_devices()`` doesn't work, you can get the IP Address by running an ``arp -a`` and use that in ``pywemo.setup_url_for_address``:

.. code-block::

    $ arp -a
    _gateway (10.22.22.1) at [MAC ADDRESS REMOVED] [ether]
    
.. code-block:: python

    >>> import pywemo
    >>> url = pywemo.setup_url_for_address("10.22.22.1")
    >>> device = pywemo.discovery.device_from_description(url)
    >>> print(device)
    <WeMo Switch "Wemo Mini">
    >>> device.setup(ssid='MY SSID', password='MY NETWORK PASSWORD')
    ('1', 'success')



Testing new products
--------------------
If both methods above are not successful, then ``pywemo`` may not support your WeMo product yet.
This may be particularly true if it is a new WeMo product.
To test this, you can use a debug flag, ``pywemo.discover_devices(debug=True)`` or ``pywemo.discovery.device_from_description(url, debug=True)``.
If an ``UnsupportedDevice`` is found, then it is highly likely that the product can be added to ``pywemo``.
This ``UnsupportedDevice`` will allow manual interaction, but please open an issue to get first class support for the device.

Device Reset and Setup
----------------------
PyWeMo includes the ability to reset and setup devices, without using the Belkin app or needing to create a Belkin account.
This can be particularly useful if the intended use is fully local control, such as using Home Assistant.

Reset
~~~~~
Reset can be performed with the ``reset`` method, which has 2 boolean input arguments, ``data`` and ``wifi``.
WeMo devices contain a hardware reset procedure as well, so use of ``pywemo`` is for convenience or if physical access is not available.
This ``reset`` method may not work on all devices.

=======================================  =================  =======================
Method in ``pywemo``                     Clears             Name in WeMo App
=======================================  =================  =======================
``device.reset(data=True, wifi=False)``  name, icon, rules  Clear Personalized Info
``device.reset(data=False, wifi=True)``  wifi information   Change Wi-Fi
``device.reset(data=True, wifi=True)``   everything         Factory Restore
=======================================  =================  =======================

Setup
~~~~~

Device setup is through the ``setup`` method, which has two required arguments: ``ssid`` and ``password``.
The user must first connect to the devices locally broadcast access point, which typically starts with "WeMo.", and then discover the device there.
Once done, pass the desired SSID and password (WPA2/AES encryption only) to the ``setup`` method to connect it to your wifi network.

``device.setup(ssid='wifi_name', password='special_secret')``

A few important notes:

- Not all devices are currently supported for setup.
- For a WeMo without internet access, see `this guide <https://github.com/pywemo/pywemo/wiki/WeMo-Cloud#disconnecting-from-the-cloud>`_ to stop any blinking lights.
- If connecting to an open network, the password argument is ignored and you can provide anything, e.g. ``password=None``.
- If connecting to a WPA2/AES-encrypted network, OpenSSL is used to encrypt the password by the ``pywemo`` library.
  It must be installed and available on your ``PATH`` via calling ``openssl`` from a terminal or command prompt.

Firmware Warning
----------------
Starting in May of 2020, Belkin started requiring users to create an account and login to the app (Android app version 1.25).
In addition to the account, most of the app functionality now requires a connection to the cloud (internet access), even for simple actions such as toggling a switch.
All of the commands that go through the cloud are encrypted and cannot be easily inspected.
This raises the possibility that Belkin could, in the future, update WeMo device firmware and make breaking API changes that can no longer be deciphered.
If this happens, ``pywemo`` may no longer function on that device.
Thus it would be prudent to upgrade firmware cautiously and preferably only after confirming that breaking API changes have not been introduced.

Developing
----------
Setup and builds are fully automated.
You can run the build pipeline locally via:

.. code-block::

    # setup, install, format, lint, test and build:
    ./scripts/build.sh

Note that this will install a git ``pre-commit`` hook.
For this hook to work correctly, ``poetry`` needs to be globally accessible on your ``PATH`` or the local virtual environment must be activated.
This virtual environment can be activated with:

.. code-block::

    . .venv/bin/activate

History
-------
This started as a stripped down version of `ouimeaux <https://github.com/iancmcc/ouimeaux>`_, copyright Ian McCracken, but has since taken its own path.

License
-------
All contents of the pywemo/ouimeaux_device directory are licensed under a BSD 3-Clause license. The full text of that license is maintained within the pywemo/ouimeaux_device/LICENSE file.
The rest of pyWeMo is released under the MIT license. See the top-level LICENSE file for more details.


.. |Build Badge| image:: https://github.com/pywemo/pywemo/workflows/Build/badge.svg
    :target: https://github.com/pywemo/pywemo/actions?query=workflow%3ABuild
    :alt: GitHub build status
.. |PyPI Version Badge| image:: https://img.shields.io/pypi/v/pywemo
    :target: https://pypi.org/project/pywemo/
    :alt: Latest PyPI version
.. |Coverage| image:: https://coveralls.io/repos/github/pywemo/pywemo/badge.svg?branch=main
    :target: https://coveralls.io/github/pywemo/pywemo?branch=main
    :alt: Coveralls coverage
.. |PyPI Downloads Badge| image:: https://img.shields.io/pypi/dm/pywemo
    :target: https://pypi.org/project/pywemo/
    :alt: Number of PyPI downloads
