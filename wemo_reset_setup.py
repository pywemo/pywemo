#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Reset and setup Belkin Wemo devices without using the Belkin iOS/Android App.

This script uses click for a cli interface.  To see informational and help
message(s), you can run:
    wemo_reset_setup.py --help

Each of the Commands listed within help also have their own help
documentation with additional information, for example:
    wemo_reset_setup.py reset --help
    wemo_reset_setup.py setup --help

It is highly recommended to read each of the --help pages for helping details
and information.
"""


# -----------------------------------------------------------------------------
# ---[ Imports ]---------------------------------------------------------------
# -----------------------------------------------------------------------------
import time
import base64
import pathlib
import logging
import datetime
import platform
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

# context for -h/--help usage with click
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


# -----------------------------------------------------------------------------
class WemoException(Exception):
    """Base class for exceptions in this module."""

    pass


# -----------------------------------------------------------------------------
def setup_logger(verbose: int) -> None:
    """Logger setup."""
    handler = colorlog.StreamHandler()
    formatter = colorlog.ColoredFormatter(
        '%(log_color)s[%(levelname)-8s] %(message)s'
    )
    handler.setFormatter(formatter)
    log.addHandler(handler)
    filename = pathlib.Path('wemo_reset_setup.log')
    if verbose == 0:
        log.setLevel(logging.INFO)
    elif verbose == 1:
        # include debug messages from this script, but not others
        log.setLevel(logging.DEBUG)
        logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
    elif verbose == 2:
        # include all debug messages
        log.setLevel(logging.DEBUG)
    else:
        # include all debug messages and also write the log to a file
        log.setLevel(logging.DEBUG)
        handler = logging.FileHandler(filename, mode='w')
        handler.setFormatter(formatter)
        log.addHandler(handler)

    # Record some system and program information
    date_time = datetime.datetime.now().astimezone()
    date_time = date_time.strftime('%B %d, %Y, %I:%M %p (%Z)')
    platinfo = ', '.join(platform.uname())
    log.debug('logging started:  %s', date_time)
    log.debug('program version:  %s', __version__)
    # pywemo does not provide version at this time
    # log.debug('pywemo version:  %s', pywemo.__version__)
    log.debug('platform:  %s', platinfo)
    log.debug('current directory:  %s', pathlib.Path.cwd())
    if verbose > 2:
        log.debug('logging to file:  %s', filename.resolve())


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
            # decide which card to use and will simply try to reconnect them
            # back to the the first one listed
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
            # some devices might not support these services/actions?
            pass
    for key, value in setup_details.items():
        log.info('  %-42s: %s', '[DETAILS FOR RE-SETUP] ' + key, value)


# -----------------------------------------------------------------------------
def wemo_reset(device: Device, data: bool = True, wifi: bool = True) -> None:
    """Wemo device(s) reset."""
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

    Function borrows heavily from Vadim's "wemosetup" script:
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
    n_encrypted = len(encrypted_password)
    n_password = len(password)
    log.debug('password length (before encryption): %s', n_password)
    log.debug('password length (after encryption): %s', n_encrypted)
    if n_encrypted > 255 or n_password > 255:
        raise WemoException(
            'Wemo requires the wifi password, including after encryption, '
            'to be 255 or less characters, but found password of length '
            f'{n_password} and {n_encrypted} length after encryption.'
        )

    encrypted_password += f'{n_encrypted:#04x}'[2:]
    encrypted_password += f'{n_password:#04x}'[2:]
    return encrypted_password


# -----------------------------------------------------------------------------
def wemo_setup(
    device: Device, ssid: str, password: str, timeout: int = 20
) -> None:
    """Wemo device(s) setup (connect device to wifi/AP).

    Function inspired by Vadim's "wemosetup" code:
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
        encrypted_password = ''
    else:
        # get the meta information of the device
        meta_info = device.metainfo.GetMetaInfo()['MetaInfo']
        log.debug('device meta info: %s', meta_info)
        meta_info = meta_info.split('|')

        # select parts of the meta information for password use
        keydata = meta_info[0][:6] + meta_info[1] + meta_info[0][6:12]

        encrypted_password = encrypt_wifi_password_aes128(password, keydata)

    result = device.WiFiSetup.ConnectHomeNetwork(
        ssid=ssid,
        auth=auth_mode,
        password=encrypted_password,
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
    """Connect to a Wemo devices AP and then set up the device."""
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
    #       wireless adapters), then discovery will still return all devices,
    #       not only those on the current Wemo's AP.
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
@click.group(
    context_settings=CONTEXT_SETTINGS,
    epilog='''Each of the Commands listed above also have their own help
    documentation with additional details and information.  It is highly
    recommended to check those help messages as well.  You can see that by
    specifying the command first, for example:

    wemo_reset_setup.py reset --help
    ''',
)
@click.version_option(version=__version__)
@click.option(
    '-v',
    '--verbose',
    count=True,
    help='''Print debug messages.  Use -v to enable debug messages from this
    script, -vv to also enable debug messages from upstream libraries,
    and -vvv also output the log to a file.''',
)
def click_main(verbose: int) -> None:
    r"""Wemo script to reset and setup Wemo devices.

    This script can be used to reset and setup Belkin Wemo devices, without
    using the Belkin iOS/Android App.

    NOTE: OpenSSL should be installed to use this script for device setup on
    a network using encryption, as OpenSSL is used to encrypt the password
    (AES only).

    NOTE: This script has only been tested on linux (Ubuntu 20.04) with OpenSSL
    (version 1.1.1f) and on the following devices:

        \b
        |---------------------------------------------------------------------|
        | Device Type      | Market | FirmwareVersion                         |
        |---------------------------------------------------------------------|
        | Socket (Mini)    | US     | WeMo_WW_2.00.11452.PVT-OWRT-SNSV2       |
        | Lightswitch      | US     | WeMo_WW_2.00.11408.PVT-OWRT-LS          |
        | Dimmer           | US     | WeMo_WW_2.00.11453.PVT-OWRT-Dimmer      |
        |---------------------------------------------------------------------|

    NOTE: You should be on the same network as the device you want to interact
    with!
    """
    setup_logger(verbose)


# -----------------------------------------------------------------------------
@click_main.command(name='list', context_settings=CONTEXT_SETTINGS)
def wemo_discover() -> List[Device]:
    """Discover and print information about devices on current network(s)."""
    discover_and_log_devices(details=True)


# -----------------------------------------------------------------------------
@click_main.command(name='reset', context_settings=CONTEXT_SETTINGS)
@click.option('--data', is_flag=True, help='Set flag to clear the device data')
@click.option(
    '--wifi',
    is_flag=True,
    help='Set flag to clear the device wifi information',
)
@click.option(
    '--full',
    is_flag=True,
    help='Full factory reset, implies --data and --wifi',
)
@click.option(
    '--reset-all',
    is_flag=True,
    help='''Scan network(s) for devices and reset all found devices (will be
    prompted to continue after discovery).''',
)
@click.option(
    '--name',
    help='''Friendly name of the device to reset.  This option is required (and
    only used) if --reset-all is NOT used.  You must be conencted to whatever
    network the device is connected to.''',
)
def click_wemo_reset(
    data: bool,
    wifi: bool,
    full: bool,
    reset_all: bool,
    name: str,
) -> None:
    """Wemo device(s) reset (cli interface).

    NOTE: You should be on the same network as the device you want to interact
    with!  To reset a device, you should be connected to your normal network
    that the device is connected to.
    """
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
@click_main.command(name='setup', context_settings=CONTEXT_SETTINGS)
@click.option(
    '--ssid',
    required=True,
    help='The SSID of the network you want the Wemo device to join',
)
@click.option(
    '--password',
    prompt=True,
    hide_input=True,
    help='Password for the provided SSID (will be prompted)',
)
@click.option(
    '--setup-all',
    is_flag=True,
    help='''Scan for available Wemo device networks and try to setup any device
    on all discovered networks (requires Linux and nmcli to find and connect to
    the networks)''',
)
@click.option(
    '--name',
    help='''Friendly name of the device to setup.  This option is required (and
    only used) if --setup-all is NOT used.  You must be connected to the
    devices local network (usually of the form Wemo.Device.XXX).''',
)
def click_wemo_setup(
    ssid: str, password: str, setup_all: bool, name: str
) -> None:
    """Wemo device(s) setup (cli interface).

    NOTE: You should be on the same network as the device you want to interact
    with!  To setup a device, you should be connected to the devices locally
    broadcast network, usually something of the form: Wemo.Device.XXX where
    Device is the type of Wemo (e.g. Mini, Light, or Dimmer) and XXX is the
    last 3 digits of the device serial number.  The --setup-all option will
    attempt to search for all networks of the form Wemo.* and try to setup
    any wemo it finds on those network(s).

    NOTE: Wemo devices seem to have trouble connecting to an access point that
    uses the same name (SSID) for the 2.4GHz and 5GHz signals.  Thus it is
    recommended to disable the 5GHz signal while setting up the Wemo devices,
    and then re-enabling it upon completion.

    NOTE: Often times the Wemo will fail to connect to wifi the first time it
    is attempted, but then will connect when setup is re-run on the device.
    So be sure to try again if it fails the first time.
    """
    try:
        if setup_all:
            wemo_aps, current = find_wemo_aps()
            if not wemo_aps:
                raise WemoException(
                    'no valid Wemo device AP\'s found, first try running this '
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
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        # just skip re-connection, the OS will likely
                        # auto-reconnect anyway
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
