# API Documentation

For example usage and installation instructions see
[README.rst](https://github.com/pywemo/pywemo/blob/main/README.rst)

## General structure of the pyWeMo API

### Discovery

The `pywemo.discovery` module contains methods to locate WeMo devices on a
network. For example, use the following to discover all devices on the
network:

```python
>>> import pywemo
>>> devices = pywemo.discover_devices()
>>> print(devices)
[<WeMo Insight "AC Insight">]
```

Or, if you know the IP address of the device, use this example.

```python
>>> import pywemo
>>> url = pywemo.setup_url_for_address("192.168.1.192")
>>> print(url)
http://192.168.1.192:49153/setup.xml
>>> device = pywemo.device_from_description(url)
>>> print(device)
[<WeMo Insight "AC Insight">]
```

### Devices

The device(s) returned by the discovery methods above will be instances of one
of the classes below. These classes, used for communicating with the various
WeMo devices, are in submodules under the `pywemo.ouimeaux_device` module. They
can also be accessed as top-level members of the pywemo module.

Example WeMo Model(s)   | Alias / Class
----------------------- | -------------
F7C031                  | `pywemo.Bridge` / `pywemo.ouimeaux_device.bridge.Bridge`
F7C046                  | `pywemo.Humidifier` / `pywemo.ouimeaux_device.humidifier.Humidifier`
F7C045                  | `pywemo.CrockPot` / `pywemo.ouimeaux_device.crockpot.CrockPot`
F7C050                  | `pywemo.CoffeeMaker` / `pywemo.ouimeaux_device.coffeemaker.CoffeeMaker`
F7C028                  | `pywemo.Motion` / `pywemo.ouimeaux_device.motion.Motion`
F7C043                  | `pywemo.Maker` / `pywemo.ouimeaux_device.maker.Maker`
F7C027, F7C063, WSP080  | `pywemo.Switch` / `pywemo.ouimeaux_device.switch.Switch`
F7C029, F7C029V2        | `pywemo.Insight` / `pywemo.ouimeaux_device.insight.Insight`
WLS0403, WLS040, F7C030 | `pywemo.LightSwitchLongPress` / `pywemo.ouimeaux_device.lightswitch.LightSwitchLongPress`
WDS060                  | `pywemo.DimmerV2` / `pywemo.ouimeaux_device.dimmer.DimmerV2`
F7C059                  | `pywemo.DimmerLongPress` / `pywemo.ouimeaux_device.dimmer.DimmerLongPress`
WSP090                  | `pywemo.OutdoorPlug` / `pywemo.ouimeaux_device.outdoor_plug.OutdoorPlug`

The following are base classes of all of the above device classes.

* pywemo.ouimeaux_device.Device: Provides common methods for getting/setting
  device state.
* pywemo.ouimeaux_device.api.xsd_types.DeviceDescription: Provides information
  about the device name, mac address, firmware version, serial number, etc.

Additional models and details can be found on [this wiki page](https://github.com/pywemo/pywemo/wiki/Device-Status-Registry).

### Subscriptions

Most WeMo devices support a push/callback model for reporting state changes.
The `pywemo.subscribe` module provides a way to subscribe to push events.
