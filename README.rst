pyWeMo |Build Badge| |PyPI Version Badge| |Coverage| |PyPI Downloads Badge| |Docs Badge| |Scorecard Badge| |Best Practices Badge| |SLSA 3 Badge|
================================================================================================================================================
Python 3 module to setup, discover and control WeMo devices.

How to use
----------

.. code-block:: python

    >>> import pywemo
    >>> devices = pywemo.discover_devices()
    >>> print(devices)
    [<WeMo Insight "AC Insight">]

    >>> device = devices[0]
    >>> device.toggle()

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

Unknown Products
----------------
If both methods above are not successful, then ``pywemo`` may not support your WeMo product yet.
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
- For a WeMo without internet access, see `this guide <https://github.com/pywemo/pywemo/wiki/WeMo-Cloud#disconnecting-from-the-cloud>`_ to stop any blinking lights.

Windows Setup Scripts
~~~~~~~~~~~~~~~~~~~~~
These checkout-local scripts use an existing Python environment with pywemo's
dependencies installed. No internet connection is needed during provisioning.
Run the commands from the repository root in PowerShell.

Copy ``wemo-setup.example.json`` to ``wemo-setup.json`` and set ``ssid`` to your
2.4 GHz WPA2/AES network name. Set ``password`` or leave it empty for a hidden
prompt. The local configuration is ignored by Git; it stores any saved password
in plaintext, so do not share it.

For one device, connect Windows to its open ``WeMo.*`` setup network, then run:

.. code-block:: powershell

    .\.venv\Scripts\python.exe scripts\setup_wifi.py

The script checks the connected SSID, detects its gateway, identifies the device,
lists its visible networks, and attempts Wi-Fi setup. Failed attempts try the
remaining password-encoding combinations. Logs include the encoding used and
exception causes. If the setup endpoint disappears, the outcome is uncertain:
reconnect to home Wi-Fi and verify discovery before retrying.

Additional single-device options:

.. code-block:: powershell

    .\.venv\Scripts\python.exe scripts\setup_wifi.py --diagnose
    .\.venv\Scripts\python.exe scripts\setup_wifi.py --ip 10.22.22.1
    .\.venv\Scripts\python.exe scripts\setup_wifi.py --encrypt-method 3 --password-lengths yes
    .\.venv\Scripts\python.exe scripts\setup_wifi.py --factory-reset

Diagnostics do not change settings. Factory reset requires typing ``RESET`` and
erases the identified device's name, rules and Wi-Fi settings.

For a batch, start connected to the configured home network with a saved Windows
Wi-Fi profile. Put the intended devices into setup mode, then run:

.. code-block:: powershell

    .\.venv\Scripts\python.exe scripts\setup_all_wifi.py --list
    .\.venv\Scripts\python.exe scripts\setup_all_wifi.py

The batch scans visible open ``WeMo.*`` networks once, connects to each in turn,
runs the same setup logic, and restores the home connection between devices.
It asks for the password once if absent from the config. Temporary open-network
profiles are removed after use. It does not reset devices. Only run where all
visible WeMo setup devices are ones you intend to configure. Devices outside
Wi-Fi range or absent from the initial scan need another run.

These scripts currently require English Windows ``netsh`` output, one connected
Wi-Fi adapter, and Windows permission to scan/connect Wi-Fi (including location
access where required). Setup success is the device's reported result, not
independent home-network discovery verification.

Setup Troubleshooting
~~~~~~~~~~~~~~~~~~~~~
If you have issues connecting, here are several things worth trying:

- Try again!
  WeMo devices sometimes just fail to connect and repeating the exact same steps may subsequently work.
- Bring the WeMo as close to the access point as possible.
  Some devices seem to require a very strong signal for setup, even if they will work normally with a weaker one.
- WeMo devices can only connect to 2.4GHz Wi-Fi and sometimes have trouble connecting if the 2.4Ghz and 5Ghz SSID are the same.
- If issues persist, consider performing a full factory reset and power cycle on the device before trying again.
- Enabled firewall rules may block the WeMo from connecting to the intended AP.
- One user indicated that switching the 2.4Ghz channel bandwidth from 40Mhz to 20Mhz (not verified, and this was regarding the Belkin app, not pywemo).
- Based on various differences in models and firmware, pywemo contains 3 different methods for encrypting the Wi-Fi password when sending it to the WeMo device.
  In addition to the encryption, WeMo devices sometimes expect the get password lengths appended to the end of the password.
  There is logic in pywemo that attempts to select the appropriate options for each device, but it maybe not be correct for all devices and firmware.
  Thus, you may want to try forcing each of the 6 possible combinations as shown below.
  If one of these other methods work, but not the automatic detection, then be sure to add a comment to `this pywemo issue`_.

.. code-block:: python

    device.setup(ssid='wifi', password='secret', _encrypt_method=1, _add_password_lengths=True)
    device.setup(ssid='wifi', password='secret', _encrypt_method=2, _add_password_lengths=False)
    device.setup(ssid='wifi', password='secret', _encrypt_method=3, _add_password_lengths=True)
    # bottom three may not be valid, but try them too
    device.setup(ssid='wifi', password='secret', _encrypt_method=1, _add_password_lengths=False)
    device.setup(ssid='wifi', password='secret', _encrypt_method=2, _add_password_lengths=True)
    device.setup(ssid='wifi', password='secret', _encrypt_method=3, _add_password_lengths=False)

Belkin Ends Support for WeMo
----------------------------
Belkin is officially ending WeMo support on January 31, 2026.
After this date, the Belkin app will no longer work, including the required cloud access to use the current products.
This likely means that you cannot use the Belkin app to connect a device to your network after this date either.
See `this link <https://www.belkin.com/support-article/?articleNum=335419>`_ for more details from Belkin.

The good news is that this change will **not** affect pywemo, which will continue to work as it currently does;
pywemo does not rely on the cloud connection for anything, including setup (connecting to a new AP).
Many products can be setup and reset with pywemo, as discussed above.

Product Status
--------------
`This pywemo wiki page`_ includes a table of all known WeMo products and the status within pywemo, including whether setup (connecting to a new network) works or not.

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
.. _This pywemo wiki page: https://github.com/pywemo/pywemo/wiki/Device-Status-Registry

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
