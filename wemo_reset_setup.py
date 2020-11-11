#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This is a script used to reset and setup Belkin WeMo devices, without using the
Belkin iOS/Android App.

Note that OpenSSL should be installed to use this script for device setup, as
OpenSSL is used to encrypt the password (AES).

NOTE: this script has only been tested on linux (Ubuntu 20.04) with OpenSSL
(version 1.1.1f) and on the following devices (all US market devices):

    |--------------------------------------------------------------------------
    | Device Type        | FirmwareVersion
    |--------------------------------------------------------------------------
    | Socket (Mini)      | WeMo_WW_2.00.11452.PVT-OWRT-SNSV2
    | Lightswitch        | WeMo_WW_2.00.11408.PVT-OWRT-LS
    | Dimmer             | WeMo_WW_2.00.11453.PVT-OWRT-Dimmer
    |--------------------------------------------------------------------------

NOTE: You should be on the same network as the device you want to interact
      with!  To reset a device, you should be connected to your normal network.
      To setup a device, you should be connected to the devices locally
      broadcast network, usually something of the form: Wemo.Device.XXX where
      Device is the type of Wemo (e.g. Mini, Light, or Dimmer) and XXX is the
      last 3 digits of the device serial number.  The --setup-all option will
      use your wifi card to search for Wemo networks and try to setup all of
      those found.

NOTE: Wemo devices seem to have trouble connecting to an access point that
      uses the same name (SSID) for the 2.4GHz and 5GHz signals.  Thus it is
      recommended to disable the 5GHz signal while setting up the Wemo devices,
      and then re-enabling it upon completion.

NOTE: I've often found that when trying to setup the Wemo, it will fail to
      connect to my wifi the first time, but then re-running the setup again a
      second time will work.  So be sure to try again if it fails the first
      time.
"""


# -----------------------------------------------------------------------------
# ---[ Imports ]---------------------------------------------------------------
# -----------------------------------------------------------------------------
import time
import base64
import logging
import subprocess
from typing import List, Tuple

import click
import colorlog

import pywemo
from pywemo.ouimeaux_device import Device


# -----------------------------------------------------------------------------
__version__ = '1.0.0'


# -----------------------------------------------------------------------------
log = colorlog.getLogger()
log.addHandler(logging.NullHandler())


# -----------------------------------------------------------------------------
class WemoException(Exception):
    """Base class for exceptions in this module."""

    pass


# -----------------------------------------------------------------------------
def setup_logger(verbose: int) -> None:
    """Logger setup."""
    handler = colorlog.StreamHandler()
    handler.setFormatter(
        colorlog.ColoredFormatter('%(log_color)s[%(levelname)-8s] %(message)s')
    )
    log.addHandler(handler)
    if verbose == 0:
        log.setLevel(logging.INFO)
    elif verbose == 1:
        # include debug messages from this script, but not others
        log.setLevel(logging.DEBUG)
        logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
    else:
        # include all debug messages if multiple verbose flags are given
        log.setLevel(logging.DEBUG)


# -----------------------------------------------------------------------------
def find_wemo_aps() -> Tuple[List[str], str]:
    """Use linux network manager to find wemo access points to connect to."""
    try:
        networks = subprocess.run(
            [
                'nmcli',
                '--get-values',
                'SSID,IN-USE,CHAN,SIGNAL,SECURITY',
                'device',
                'wifi',
            ],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise WemoException(
            'nmcli command failed (this function requires linux with network '
            'manager installed)'
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = networks.stderr.decode().strip()
        log.error('stderr:\n%s', stderr)
        raise WemoException('nmcli command failed') from exc

    args = ' '.join(networks.args)
    stdout = networks.stdout.decode().strip()
    log.debug('result of "%s":\nstdout:\n%s', args, stdout)

    wemo_networks = []
    current_network = ''
    for line in stdout.split('\n'):
        ssid, in_use, channel, signal, security = line.rsplit(':', 4)
        if in_use == '*':
            log.debug(
                'current network: %s (channel=%s, signal=%s, security=%s)',
                ssid,
                channel,
                signal,
                security,
            )
            # it is possible that the user could be connected to multiple
            # access points - for example, if they have multiple wireless
            # cards installed and in use - but we won't bother trying to
            # decide which card to use or anything and will simply try to
            # recommect them back to the the first one listed
            current_network = current_network or ssid
        if ssid.lower().startswith('wemo.'):
            log.info(
                'expected wemo: %s (channel=%s, signal=%s, security=%s)',
                ssid,
                channel,
                signal,
                security,
            )
            wemo_networks.append(ssid)

    return wemo_networks, current_network


# -----------------------------------------------------------------------------
def log_details(device: Device) -> None:
    """Log some basic details about the device."""
    # display some general information about the device that the
    # user may find useful in understanding it
    setup_details = {}
    for service, action, key in [
        ('basicevent', 'GetFriendlyName', 'FriendlyName'),
        ('basicevent', 'GetSignalStrength', 'SignalStrength'),
        ('basicevent', 'GetMacAddr', None),
        ('firmwareupdate', 'GetFirmwareVersion', 'FirmwareVersion'),
        ('metainfo', 'GetMetaInfo', 'MetaInfo'),
        ('metainfo', 'GetExtMetaInfo', 'ExtMetaInfo'),
        ('deviceinfo', 'GetDeviceInformation', 'DeviceInformation'),
    ]:
        try:
            result = device.services[service].actions[action]()
            if key:
                # display a specific result
                log.info('    %40s: %s', key, result[key])
                if key == 'MetaInfo':
                    ssid = result[key].split('|')[-2]
                    setup_details['Default SSID'] = ssid
            else:
                # display entire result (dictionary)
                log.info('    %40s: %s', action, result)
        except (AttributeError, KeyError, TypeError):
            # some devices might not support these sevices/actions?
            pass
    for key, value in setup_details.items():
        log.info('  %-42s: %s', '[DETAILS FOR RE-SETUP] ' + key, value)


# -----------------------------------------------------------------------------
def wemo_reset(device: Device, data: bool = True, wifi: bool = True) -> None:
    """Reset a wemo device."""
    log.info('information on device (may aid in re-setup): %s', device)
    log_details(device)

    if data and wifi:
        log.info('attempting a full factory reset (clear data and wifi info)')
        result = device.basicevent.ReSetup(Reset=2)
    elif data:
        log.info('attempting to reset data such as icon and rules')
        result = device.basicevent.ReSetup(Reset=1)
        try:
            info = device.deviceinfo.GetDeviceInformation()
            log.debug('device information: %s', info)
            original_name = info['DeviceInformation'].split('|')[-1]
            log.info('changing name to: %s', original_name)
            device.basicevent.ChangeFriendlyName(FriendlyName=original_name)
        except (AttributeError, KeyError):
            pass
    elif wifi:
        log.info('attempting to clear wifi information only')
        result = device.basicevent.ReSetup(Reset=5)
    else:
        raise WemoException('no action requested')

    log.info('result of reset: %s', result['Reset'])

    return result


# -----------------------------------------------------------------------------
def encrypt_wifi_password_aes128(password: str, wemo_keydata: str) -> str:
    """Encrypt a password using OpenSSL.

    This function is borrowed heavily from Vadim's "wemosetup" script here:
    https://github.com/vadimkantorov/wemosetup
    """
    if not password:
        raise WemoException('non-empty password required for AES')

    # Wemo gets this data from the device meta data
    salt, initialization_vector = wemo_keydata[:8], wemo_keydata[:16]
    if len(salt) != 8 or len(initialization_vector) != 16:
        log.warning('device meta information may not be supported')
    log.debug('salt: %s', salt)
    log.debug('initialization_vector: %s', initialization_vector)

    # call OpenSSL to encrypt the data
    # NOTE: newer versions of OpenSSL may give a warning similar to the two
    # lines below.  But, at least currently, using those options are not
    # compatible with wemo.
    #     *** WARNING : deprecated key derivation used.
    #     Using -iter or -pbkdf2 would be better.
    stdout, _ = subprocess.Popen(
        [
            'openssl',
            'enc',
            '-aes-128-cbc',
            '-md',
            'md5',
            '-salt',
            '-S',
            salt.encode('utf-8').hex(),
            '-iv',
            initialization_vector.encode('utf-8').hex(),
            '-pass',
            'pass:' + wemo_keydata,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    ).communicate(password.encode('utf-8'))

    # removing 16byte magic and salt prefix inserted by OpenSSL, which is of
    # the form "Salted__XXXXXXXX" before the actual password
    encrypted_password = base64.b64encode(stdout[16:]).decode()

    # the last 4 digits that wemo expects should be xxyy, where:
    #     xx: length of the encrypted password
    #     yy: length of the original password
    nencrypted = len(encrypted_password)
    npassword = len(password)
    log.debug('password length (before encryption): %s', npassword)
    log.debug('password length (after encryption): %s', nencrypted)
    if nencrypted > 255 or npassword > 255:
        raise WemoException(
            'Wemo requires the wifi password, including after encryption, '
            'to be 255 or less characters, but found password of length '
            f'{npassword} and {nencrypted} length after encryption.'
        )

    encrypted_password += f'{nencrypted:#04x}'[2:]
    encrypted_password += f'{npassword:#04x}'[2:]
    return encrypted_password


# -----------------------------------------------------------------------------
def wemo_setup(
    device: Device, ssid: str, password: str, timeout: int = 20
) -> None:
    """Setup a wemo device (connect it to your wifi/AP).

    This function is inspired by Vadim's "wemosetup" code here:
    https://github.com/vadimkantorov/wemosetup
    """
    # find all access points that the device can see, and select the one
    # matching the desired SSID
    selected_ap = None
    log.info('searching for AP\'s...')
    access_points = device.WiFiSetup.GetApList()['ApList']
    for access_point in access_points.split('\n'):
        access_point = access_point.strip().rstrip(',')
        if not access_point.strip():
            continue
        log.debug('found AP: %s', access_point)
        if access_point.startswith(f'{ssid}|'):
            log.info('found AP with SSID: %s', ssid)
            # don't break here, so that all found AP's get logged, but select
            # only the first one from the list
            if selected_ap is None:
                selected_ap = access_point
                log.info('using this access point data: %s', selected_ap)

    if selected_ap is None:
        raise WemoException(
            f'AP with SSID {ssid} not found.  Run with -v flag to see all '
            'access points the wemo found.'
        )

    # get some information about the access point
    columns = selected_ap.split('|')
    channel = columns[1].strip()
    auth_mode, encryption_method = columns[-1].strip().split('/')
    log.debug('selected AP channel: %s', channel)
    log.debug('selected AP authorization mode(s): %s', auth_mode)
    log.debug('selected AP encryption method: %s', encryption_method)

    # check if the encryption type is supported by this script
    supported_encryptions = {'NONE', 'AES'}
    if encryption_method not in supported_encryptions:
        WemoException(
            f'Encryption {encryption_method} not supported, supported '
            f'encryptions are: {",".join(supported_encryptions)}'
        )

    # try to connect the device to the selected network
    if encryption_method == 'NONE':
        log.info('selected network has no encryption (ignoring any password)')
        log.warning(
            'it is advisable to use encryption, please consider enabling '
            'encryption on your network'
        )
        auth_mode = 'OPEN'
        encryped_password = ''
    else:
        # get the meta information of the device
        meta_info = device.metainfo.GetMetaInfo()['MetaInfo']
        log.debug('device meta info: %s', meta_info)
        meta_info = meta_info.split('|')

        # select parts of the meta information for password use
        keydata = meta_info[0][:6] + meta_info[1] + meta_info[0][6:12]

        encryped_password = encrypt_wifi_password_aes128(password, keydata)

    result = device.WiFiSetup.ConnectHomeNetwork(
        ssid=ssid,
        auth=auth_mode,
        password=encryped_password,
        encrypt=encryption_method,
        channel=channel,
    )
    pairing_status = result['PairingStatus']
    log.debug('pairing status: %s', pairing_status)

    log.info('waiting an initial 5 seconds...')
    time.sleep(5.0)

    log.info('starting status checks...(timeout of %s seconds)', timeout)
    timeout = int(timeout)
    for i in range(timeout):
        time.sleep(1.0)
        network_status = device.WiFiSetup.GetNetworkStatus()['NetworkStatus']
        log.debug('network status (%s seconds): %s', i + 1, network_status)
        if network_status == '1':
            break

    network_status = device.WiFiSetup.GetNetworkStatus()['NetworkStatus']
    log.debug('network status (need 1 or 3): %s', network_status)

    close_status = device.WiFiSetup.CloseSetup()['status']
    log.debug('close status (need success): %s', close_status)

    if network_status not in ['1', '3'] or close_status != 'success':
        log.error(
            'device failed to connect to the network "%s", please try again '
            '(add -v for addition debug information).  Wemo devices often '
            'need to try wifi setup a second time.',
            ssid,
        )
    else:
        try:
            device.basicevent.SetSetupDoneStatus()
        except AttributeError:
            log.warning('SetSetupDoneStatus not able to be set')
            pass
        log.info('device connected to network "%s"', ssid)


# -----------------------------------------------------------------------------
def wemo_connect_and_setup(
    wemossid: str, ssid: str, password: str, timeout: int = 20
) -> None:
    """Connect to a wemo devices AP and then set up the device."""
    try:
        networks = subprocess.run(
            [
                'nmcli',
                'device',
                'wifi',
                'connect',
                wemossid,
            ],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise WemoException(
            'nmcli command failed (this function requires linux with network '
            'manager installed)'
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = networks.stderr.decode().strip()
        log.error('stderr:\n%s', stderr)
        raise WemoException(
            'nmcli command failed (network may not exist anymore?)'
        ) from exc

    args = ' '.join(networks.args)
    stdout = networks.stdout.decode().strip()
    log.debug('result of "%s":\nstdout:\n%s', args, stdout)

    # a short delay to make sure the connection is well established
    time.sleep(2.0)

    devices = discover_and_log_devices(only_needing_setup=True)
    # NOTE: if the user is connected to multiple networks (e.g. has multiple
    #       wireless adappters), then discovery will still return all devices,
    #       not only those on the current wemo's AP.
    for device in devices:
        wemo_setup(device, ssid=ssid, password=password, timeout=timeout)


# -----------------------------------------------------------------------------
def discover_and_log_devices(
    only_needing_setup: bool = False, details: bool = False
) -> List[Device]:
    """Click interface to list all discovered devices."""
    devices = pywemo.discover_devices()
    not_setup = []
    device = None
    for device in devices:
        if only_needing_setup:
            status = device.WiFiSetup.GetNetworkStatus()['NetworkStatus']
            if status not in ['1', '3']:
                not_setup.append(device)
                log.info('found device needing setup: %s', device)
        else:
            log.info('-' * 50)
            log.info('found device: %s', device)
            if details:
                log_details(device)
    if device:
        log.info('-' * 50)

    if only_needing_setup:
        return not_setup
    return devices


# -----------------------------------------------------------------------------
def get_device_by_name(name: str) -> Device:
    """Get a device by the friendly name."""
    selected_device = None
    log.info('starting discovery...this may take a few seconds')
    devices = pywemo.discover_devices()
    for device in devices:
        log.debug('found device: %s', device)
        if device.name.lower() == name.lower():
            log.info('found device with name: %s', name)
            # don't break here, so that all found devices get logged, but
            # select only the first one from the list
            if selected_device is None:
                selected_device = device

    if selected_device is None:
        raise WemoException(f'device named "{name}" not found')
    return selected_device


# -----------------------------------------------------------------------------
@click.group()
@click.version_option(version=__version__)
@click.option('-v', '--verbose', count=True, help='Print debug messages')
def click_main(verbose: int) -> None:
    """Main entry point for this script."""
    setup_logger(verbose)


# -----------------------------------------------------------------------------
@click_main.command(name='list')
def wemo_discover() -> List[Device]:
    """Click interface to list all discovered devices."""
    discover_and_log_devices(details=True)


# -----------------------------------------------------------------------------
@click_main.command(name='reset')
@click.option(
    '--data', is_flag=True, help='Set this flag to clear the device data'
)
@click.option(
    '--wifi',
    is_flag=True,
    help='Set this flag to clear the device wifi information',
)
@click.option(
    '--full',
    is_flag=True,
    help='This flag implies --data and --wifi',
)
@click.option(
    '--reset-all',
    is_flag=True,
    help='Reset ALL devices found',
)
@click.option('--name', help='Friendly name of device to work on')
def click_wemo_reset(
    data: bool,
    wifi: bool,
    full: bool,
    reset_all: bool,
    name: str,
) -> None:
    """Click interface to reset a device."""
    if full:
        data = True
        wifi = True
    try:
        if reset_all:
            devices = discover_and_log_devices()
            if name is not None:
                log.warning(
                    'name %s ignored, all discovered devices will be reset'
                )
            if click.confirm(
                'Are you sure you want to reset all devices listed above?'
            ):
                for device in devices:
                    wemo_reset(device, data=data, wifi=wifi)
        elif name is not None:
            device = get_device_by_name(name)
            wemo_reset(device, data=data, wifi=wifi)
        else:
            raise WemoException(
                'either --name=<str> must be provided or --all flag used'
            )
    except WemoException as exc:
        log.critical(exc)


# -----------------------------------------------------------------------------
@click_main.command(name='setup')
@click.option(
    '--ssid',
    required=True,
    help='Provide the SSID of the network you want the wemo device to join',
)
@click.option(
    '--password',
    prompt=True,
    hide_input=True,
    help='Password for the provided SSID',
)
@click.option(
    '--setup-all',
    is_flag=True,
    help='Try to connect all available devices (requires Linux)',
)
@click.option(
    '--name',
    help=(
        'Friendly name of device to work on (must be connected to the devices'
        'local network)'
    ),
)
def click_wemo_setup(
    ssid: str, password: str, setup_all: bool, name: str
) -> None:
    """Click interface to setup a device."""
    try:
        if setup_all:
            wemo_aps, current = find_wemo_aps()
            if not wemo_aps:
                raise WemoException(
                    'no valid wemo device AP\'s found, first try running this '
                    'again, otherwise consider directly connecting to the '
                    'devices network yourself and using the --name option'
                )
            elif click.confirm(
                'Are you sure you want to setup all "expected wemo" devices '
                'listed above?'
            ):
                for wemo_ap in wemo_aps:
                    try:
                        wemo_connect_and_setup(
                            wemo_ap, ssid=ssid, password=password
                        )
                    except WemoException as exc:
                        log.error(exc)
                        log.error('|-- thus skipping ap: %s', wemo_ap)

                if current and not current.lower().startswith('wemo.'):
                    try:
                        log.info('attempting to reconnect host to %s', current)
                        subprocess.run(
                            ['nmcli', 'device', 'wifi', 'connect', current],
                            check=True,
                            capture_output=True,
                        )
                    except (
                        subprocess.CalledProcessError,
                        FileNotFoundError,
                    ) as exc:
                        pass
        elif name is not None:
            device = get_device_by_name(name)
            wemo_setup(device, ssid=ssid, password=password)
        else:
            raise WemoException(
                'either --name=<str> must be provided or --all flag used'
            )
    except WemoException as exc:
        log.critical(exc)


# -----------------------------------------------------------------------------
# Run the script
if __name__ == '__main__':
    # pylint: disable= no-value-for-parameter
    click_main()


# ---[ END OF FILE ]-----------------------------------------------------------
