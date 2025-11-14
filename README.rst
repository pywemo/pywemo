pyWeMo |Build Badge| |PyPI Version Badge| |Coverage| |PyPI Downloads Badge| |Docs Badge| |Scorecard Badge| |Best Practices Badge| |SLSA 3 Badge|
================================================================================================================================================
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
PyWeMo does not connect nor use the Belkin cloud for any functionality.

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
Once done, pass the desired SSID and password (WPA2/AES encryption only) to the ``setup`` method to connect it to your Wi-Fi network.

``device.setup(ssid='wifi', password='secret')``

A few important notes:

- If connecting to an open network, the password argument is ignored and you can provide anything, e.g. ``password=None``.
- If connecting to a WPA2/AES/TKIPAES-encrypted network, OpenSSL is used to encrypt the password by the ``pywemo`` library.
  It must be installed and available on your ``PATH`` via calling ``openssl`` from a terminal or command prompt.
- For a WeMo without internet access, see `this guide <https://github.com/pywemo/pywemo/wiki/WeMo-Cloud#disconnecting-from-the-cloud>`_ to stop any blinking lights.

If you have issues connecting, here are several things worth trying:

- Try again!
  WeMo devices sometimes just fail to connect and repeating the exact same steps may subsequently work.
- Bring the WeMo as close to the access point as possible.
  Some devices seem to require a very strong signal for setup, even if they will work normally with a weaker one.
- WeMo devices can only connect to 2.4GHz Wi-Fi and sometimes have trouble connecting if the 2.4Ghz and 5Ghz SSID are the same.
- If issues persist, consider performing a full factory reset and power cycle on the device before trying again.
- Enabled firewall rules may block the WeMo from connecting to the intended AP.
- Based on various differences in models and firmware, pywemo contains 3 different methods for encrypting the Wi-Fi password when sending it to the WeMo device.
  In addition to the encryption, WeMo devices sometimes expect the get password lengths appended to the end of the password.
  There is logic in pywemo that attempts to select the appropriate options for each device, but it maybe not be correct for all devices and firmware.
  Thus, you may want to try forcing each of the 6 possible combinations as shown below.
  If one of these other methods work, but now the automatic detection, then be sure to add a comment to the `this pywemo issue`_.

.. code-block:: python

    device.setup(ssid='wifi', password='secret', _encrypt_method=1, _add_password_lengths=True)
    device.setup(ssid='wifi', password='secret', _encrypt_method=2, _add_password_lengths=False)
    device.setup(ssid='wifi', password='secret', _encrypt_method=3, _add_password_lengths=True)
    # Only the top 3 should be valid, but go ahead and try these lower 3 too...
    device.setup(ssid='wifi', password='secret', _encrypt_method=1, _add_password_lengths=False)
    device.setup(ssid='wifi', password='secret', _encrypt_method=2, _add_password_lengths=True)
    device.setup(ssid='wifi', password='secret', _encrypt_method=3, _add_password_lengths=False)

Search for your device on `this pywemo issue`_ before opening a new issue if setup does not work for your device.

Firmware Warning
----------------
Starting in May of 2020, Belkin started requiring users to create an account and login to the app (Android app version 1.25).
In addition to the account, most of the app functionality now requires a connection to the cloud (internet access), even for simple actions such as toggling a switch.
All of the commands that go through the cloud are encrypted and cannot be easily inspected.
This raises the possibility that Belkin could, in the future, update WeMo device firmware and make breaking API changes that can no longer be deciphered.
If this happens, ``pywemo`` may no longer function on that device.
Thus it would be prudent to upgrade firmware cautiously and preferably only after confirming that breaking API changes have not been introduced.

Belkin Ends Support for WeMo
----------------------------
Note that Belkin is officially ending WeMo support on January 31, 2026.
After this date, the Belkin app will no longer work, including the required cloud access to use the current products.
This also means that you cannot use the Belkin app to connect a device to your network after this date either.
See `this link <https://www.belkin.com/support-article/?articleNum=335419>`_ for more details from Belkin.

The good news is that this change will **not** affect pywemo, which will continue to work as it currently does;
pywemo does not rely on the cloud connection for anything, including setup.
Many products can be setup and reset with pywemo, as discussed above.

Please see `this pywemo issue`_ to document the status of the various products and to update the table below on product status.

Product Status
--------------
This is a list of known products and the pywemo status of each, including for setup.
This list was started in November of 2025 in response to Belkin ending WeMo support.
Any entry with N/A is unreported since this table was added.
If you have any of these decvices and use them with PyWeMo, please let us know in `this pywemo issue`_ so that we can complete this list.

This list is mostly from the Belkin article mentioned above, but it may not be a complete list of all products.
SKU's with an asterisk at the end, like F7C029V2*, are not listed in the article.

=========  =======================================  ====================  ===================  ========================================
SKU's      Description                              PyWeMo Object         PyWeMo Setup Status  Known Working Firmware(s)
=========  =======================================  ====================  ===================  ========================================
F7C031     Wemo Link                                Bridge                N/A                  N/A
F7C046     Wemo Humidifier                          Humidifier            N/A                  N/A
F7C045     Wemo CrockPot                            CrockPot              N/A                  N/A
F7C048     Wemo Heater B                            N/A                   N/A                  N/A
F7C049     Wemo Air Purifier                        N/A                   N/A                  N/A
F7C047     Wemo Heater A                            N/A                   N/A                  N/A
F7C050     Wemo Coffee Maker (Mr. Coffee)           CoffeeMaker           N/A                  N/A
F8J007     Wi-Fi Baby Monitor                       N/A                   N/A                  N/A
F5Z0489    Wemo LED Lighting Bundle                 N/A                   N/A                  N/A
F7C028     Wemo Motion Sensor                       Motion                N/A                  N/A
F5Z0340    Wemo Switch + Motion Sensor              N/A                   N/A                  N/A
F7C043     Wemo Maker Module                        Maker                 Works                WeMo_WW_2.00.11423.PVT-OWRT-Maker
F7C033     Wemo Zigbee Bulb, E27                    N/A                   N/A                  N/A
F7C061     Wemo Insight v2                          N/A                   N/A                  N/A
F7C027     Wemo Switch                              Switch                Works                WeMo_WW_2.00.11851.PVT-OWRT-SNS
F7C062     Wemo Light Switch v2                     N/A                   N/A                  N/A
F7C029     Wemo Insight                             Insight               Works                WeMo_WW_2.00.11483.PVT-OWRT-Insight
F7C029V2*  Wemo Insight V2                          Insight               Works                WeMo_WW_2.00.10062.PVT-OWRT-InsightV2
WLS0403    Wemo Smart Light Switch 3-Way            LightSwitchLongPress  N/A                  N/A
WSP070     Wemo Mini Smart Plug                     N/A                   N/A                  N/A
WDS060     Wemo Wi-Fi Smart Light Switch w/ Dimmer  DimmerV2              N/A                  WEMO_WW_2.00.20110904.PVT-RTOS-DimmerV2
WLS040     Wemo Smart Light Switch                  LightSwitchLongPress  N/A                  N/A
F7C064     Wemo HomeKit                             N/A                   N/A                  N/A
F7C059     Wemo Dimmer Light Switch                 DimmerLongPress       Works                WeMo_WW_2.00.11453.PVT-OWRT-Dimmer
F7C063     Wemo Mini Plugin Switch                  Switch                Works                WeMo_WW_2.00.11452.PVT-OWRT-SNSV2
F7C030     Wemo Light Switch                        LightSwitchLongPress  Works                WeMo_WW_2.00.11408.PVT-OWRT-LS
WSP090     Wemo Outdoor Plug                        OutdoorPlug           Works                WEMO_WW_1.00.20081401.PVT-RTOS-OutdoorV1
WSP080     Wemo Mini Smart Plug                     Switch                Works                WEMO_WW_4.00.20101902.PVT-RTOS-SNSV4
=========  =======================================  ====================  ===================  ========================================

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

.. _this pywemo issue: https://github.com/pywemo/pywemo/issues/773

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
.. |Docs Badge| image:: https://github.com/pywemo/pywemo/actions/workflows/docs.yml/badge.svg
    :target: https://pywemo.github.io/pywemo/
    :alt: API Documentation
.. |Scorecard Badge| image:: https://api.securityscorecards.dev/projects/github.com/pywemo/pywemo/badge
    :target: https://securityscorecards.dev/viewer/?uri=github.com/pywemo/pywemo
    :alt: OpenSSF Scorecard
.. |Best Practices Badge| image:: https://bestpractices.coreinfrastructure.org/projects/7467/badge
    :target: https://bestpractices.coreinfrastructure.org/projects/7467
    :alt: OpenSSF Best Practices
.. |SLSA 3 Badge| image:: https://slsa.dev/images/gh-badge-level3.svg
    :target: https://github.com/pywemo/pywemo/releases/latest#user-content-SLSA
    :alt: SLSA level 3
