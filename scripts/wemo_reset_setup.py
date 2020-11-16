#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Reset and setup Belkin Wemo devices without using the Belkin iOS/Android App.

python requirements:
    - pywemo, click, colorlog

external requirements (for setup only):
    - openssl: used to encrypt the password
    - nmcli (only if using --setup-all): used to find and connect to Wemo APs

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
import shutil
import base64
import pathlib
import logging
import datetime
import platform
import subprocess
from getpass import getpass
from typing import List, Tuple

import click
import colorlog

import pywemo
from pywemo.ouimeaux_device import Device


# -----------------------------------------------------------------------------
__version__ = '1.0.0'


# -----------------------------------------------------------------------------
LOG = colorlog.getLogger()
LOG.addHandler(logging.NullHandler())

DASHES = '-' * (shutil.get_terminal_size().columns - 11)

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
    LOG.addHandler(handler)
    filename = pathlib.Path('wemo_reset_setup.log')
    if verbose == 0:
        LOG.setLevel(logging.INFO)
    elif verbose == 1:
        # include debug messages from this script, but not others
        LOG.setLevel(logging.DEBUG)
        logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)
    elif verbose == 2:
        # include all debug messages
        LOG.setLevel(logging.DEBUG)
    else:
        # include all debug messages and also write the log to a file
        LOG.setLevel(logging.DEBUG)
        handler = logging.FileHandler(filename, mode='w')
        handler.setFormatter(formatter)
        LOG.addHandler(handler)

    # Record some system and program information
    date_time = datetime.datetime.now().astimezone()
    date_time = date_time.strftime('%B %d, %Y, %I:%M %p (%Z)')
    platinfo = ', '.join(platform.uname())
    LOG.debug('logging started:  %s', date_time)
    LOG.debug('program version:  %s', __version__)
    # pywemo does not provide version at this time (no pywemo.__version__)
    LOG.debug('platform:  %s', platinfo)
    LOG.debug('current directory:  %s', pathlib.Path.cwd())
    if verbose > 2:
        LOG.debug('logging to file:  %s', filename.resolve())


# -----------------------------------------------------------------------------
def find_wemo_aps() -> Tuple[List[str], str]:
    """Use network manager cli to find wemo access points to connect to."""
    try:
        subprocess.run(
            [
                'nmcli',
                'device',
                'wifi',
                'rescan',
            ],
            check=False,
        )
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
            'nmcli command failed (this function requires network manager to '
            'be installed)'
        ) from exc
    except subprocess.CalledProcessError as exc:
        try:
            LOG.error('stdout:\n%s', networks.stdout.decode().strip())
            LOG.error('stderr:\n%s', networks.stderr.decode().strip())
        except UnboundLocalError:
            pass
        raise WemoException('nmcli command failed') from exc

    args = ' '.join(networks.args)
    stdout = networks.stdout.decode().strip()
    LOG.debug('result of "%s":\nstdout:\n%s', args, stdout)

    wemo_networks = []
    current_network = ''
    for line in stdout.split('\n'):
        ssid, in_use, channel, signal, security = line.rsplit(':', 4)
        if in_use == '*':
            LOG.debug(
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
            LOG.info(
                'expected wemo: %s (channel=%s, signal=%s, security=%s)',
                ssid,
                channel,
                signal,
                security,
            )
            wemo_networks.append(ssid)

    return wemo_networks, current_network


# -----------------------------------------------------------------------------
def log_details(device: Device, verbose: int = 0) -> None:
    """Log some basic details about the device."""
    # display some general information about the device that the
    # user may find useful in understanding it
    if verbose == 0:
        data_to_print = [
            ('basicevent', 'GetFriendlyName', 'FriendlyName'),
            ('basicevent', 'GetMacAddr', None),
            ('metainfo', 'GetMetaInfo', 'MetaInfo'),
        ]
    elif verbose == 1:
        data_to_print = [
            ('basicevent', 'GetFriendlyName', 'FriendlyName'),
            ('basicevent', 'GetSignalStrength', 'SignalStrength'),
            ('basicevent', 'GetMacAddr', None),
            ('firmwareupdate', 'GetFirmwareVersion', 'FirmwareVersion'),
            ('metainfo', 'GetMetaInfo', 'MetaInfo'),
            ('metainfo', 'GetExtMetaInfo', 'ExtMetaInfo'),
            ('deviceinfo', 'GetDeviceInformation', 'DeviceInformation'),
            # ('basicevent', 'GetSetupDoneStatus', None),
        ]
    else:
        data_to_print = []
        if verbose == 2:
            # skip the calls to GetApList and GetNetworkList since they are
            # slow, but do include them if higher verbose is requested
            skip_actions = {'getaplist', 'getnetworklist'}
        else:
            skip_actions = {}
        for service_name, service in device.services.items():
            for action_name in service.actions.keys():
                if action_name.lower() in skip_actions:
                    continue
                if action_name.lower().startswith('get'):
                    data_to_print.append((service_name, action_name, None))

    failed_calls = []
    for service_name, action_name, key in data_to_print:
        name = f'{service_name}.{action_name}'
        try:
            result = device.services[service_name].actions[action_name]()

            try:
                failed = result['faultstring'].lower() == 'upnperror'
                if failed:
                    # print the failed ones at the end for easier visual
                    # separation
                    failed_calls.append((name, result))
                    continue
            except KeyError:
                pass

            # try to display the requested key, but display the entire result
            # if it doesn't exist (or is None since that key shouldn't exist)
            try:
                name = f'{service_name}.{action_name}[{key}]'
                LOG.info('    %60s: %s', name, result[key])
            except KeyError:
                LOG.info('    %60s: %s', name, result)
        except (AttributeError, KeyError, TypeError) as exc:
            # something went wrong, hard coded services may not be available on
            # all platforms, or some Get methods may require an argument
            LOG.warning(
                '    %60s: %s', f'Failed to get result for s{name}', exc
            )

    if failed_calls:
        LOG.warning(
            '    The results below resulted in an error.  This may be due to '
            'the action no longer working or that the method requires an '
            'argument.'
        )
    for name, result in failed_calls:
        LOG.info('    %60s: %s', name, result)


# -----------------------------------------------------------------------------
def wemo_reset(device: Device, data: bool = True, wifi: bool = True) -> None:
    """Wemo device(s) reset."""
    LOG.info('information on device (may aid in re-setup): %s', device)
    log_details(device, verbose=1)

    if data and wifi:
        LOG.info('attempting a full factory reset (clear data and wifi info)')
        result = device.basicevent.ReSetup(Reset=2)
    elif data:
        LOG.info('attempting to reset data such as icon and rules')
        result = device.basicevent.ReSetup(Reset=1)
        try:
            info = device.deviceinfo.GetDeviceInformation()
            LOG.debug('device information: %s', info)
            original_name = info['DeviceInformation'].split('|')[-1]
            LOG.info('changing name to: %s', original_name)
            device.basicevent.ChangeFriendlyName(FriendlyName=original_name)
        except (AttributeError, KeyError):
            pass
    elif wifi:
        LOG.info('attempting to clear wifi information only')
        result = device.basicevent.ReSetup(Reset=5)
    else:
        raise WemoException('no action requested')

    status = result['Reset']
    if status.strip().lower() == 'success':
        LOG.info('result of reset: %s', status)
    else:
        # one unit always returns "reset_remote" here instead of "success",
        # but it appears to still do a reset...
        LOG.error('result of reset (it might still have worked): %s', status)

    return result


# -----------------------------------------------------------------------------
def encrypt_wifi_password_aes128(password: str, wemo_keydata: str) -> str:
    """Encrypt a password using OpenSSL.

    Function borrows heavily from Vadim Kantorov's "wemosetup" script:
    https://github.com/vadimkantorov/wemosetup
    """
    if not password:
        raise WemoException('non-empty password required for AES')

    # Wemo gets this data from the device meta data
    salt, initialization_vector = wemo_keydata[:8], wemo_keydata[:16]
    if len(salt) != 8 or len(initialization_vector) != 16:
        LOG.warning('device meta information may not be supported')
    LOG.debug('salt: %s', salt)
    LOG.debug('initialization_vector: %s', initialization_vector)

    # call OpenSSL to encrypt the data
    # NOTE: newer versions of OpenSSL may give a warning similar to the two
    # lines below.  But, at least currently, using those options are not
    # compatible with wemo.
    #     *** WARNING : deprecated key derivation used.
    #     Using -iter or -pbkdf2 would be better.
    try:
        openssl = subprocess.run(
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
            check=True,
            capture_output=True,
            input=password.encode('utf-8'),
        )
    except FileNotFoundError as exc:
        raise WemoException(
            'openssl command failed (this function requires that openssl be '
            'on your path)'
        ) from exc
    except subprocess.CalledProcessError as exc:
        try:
            LOG.error('stdout:\n%s', openssl.stdout.decode().strip())
            LOG.error('stderr:\n%s', openssl.stderr.decode().strip())
        except UnicodeDecodeError:
            LOG.error('stdout:\n%s', openssl.stdout)
            LOG.error('stderr:\n%s', openssl.stderr)
        except UnboundLocalError:
            pass
        raise WemoException('openssl command failed') from exc

    # removing 16byte magic and salt prefix inserted by OpenSSL, which is of
    # the form "Salted__XXXXXXXX" before the actual password
    encrypted_password = base64.b64encode(openssl.stdout[16:]).decode()

    # the last 4 digits that wemo expects should be xxyy, where:
    #     xx: length of the encrypted password
    #     yy: length of the original password
    n_encrypted = len(encrypted_password)
    n_password = len(password)
    LOG.debug('password length (before encryption): %s', n_password)
    LOG.debug('password length (after encryption): %s', n_encrypted)
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
    device: Device,
    ssid: str,
    password: str,
    timeout: float = 20,
    connection_attempts: int = 2,
) -> None:
    """Wemo device(s) setup (connect device to wifi/AP).

    The timeout is for each connection_attempt.
    """
    # find all access points that the device can see, and select the one
    # matching the desired SSID
    if timeout < 20:
        LOG.warning('setting timeout to minimum of 20 (received %s)', timeout)
        timeout = 20
    connection_attempts = int(max(1, connection_attempts))

    selected_ap = None
    LOG.info('searching for AP\'s...')
    access_points = device.WiFiSetup.GetApList()['ApList']
    for access_point in access_points.split('\n'):
        access_point = access_point.strip().rstrip(',')
        if not access_point.strip():
            continue
        LOG.debug('found AP: %s', access_point)
        if access_point.startswith(f'{ssid}|'):
            LOG.info('found AP with SSID: %s', ssid)
            # don't break here, so that all found AP's get logged, but select
            # only the first one from the list
            if selected_ap is None:
                selected_ap = access_point
                LOG.info('using this access point data: %s', selected_ap)

    if selected_ap is None:
        raise WemoException(
            f'AP with SSID {ssid} not found.  Run with -v flag to see all '
            'access points the wemo found.'
        )

    # get some information about the access point
    columns = selected_ap.split('|')
    channel = columns[1].strip()
    auth_mode, encryption_method = columns[-1].strip().split('/')
    LOG.debug('selected AP channel: %s', channel)
    LOG.debug('selected AP authorization mode(s): %s', auth_mode)
    LOG.debug('selected AP encryption method: %s', encryption_method)

    # check if the encryption type is supported by this script
    supported_encryptions = {'NONE', 'AES'}
    if encryption_method not in supported_encryptions:
        WemoException(
            f'Encryption {encryption_method} not supported, supported '
            f'encryptions are: {",".join(supported_encryptions)}'
        )

    # try to connect the device to the selected network
    if encryption_method == 'NONE':
        LOG.info('selected network has no encryption (ignoring any password)')
        LOG.warning(
            'it is advisable to use encryption, please consider enabling '
            'encryption on your network'
        )
        auth_mode = 'OPEN'
        encrypted_password = ''
    else:
        # get the meta information of the device
        meta_info = device.metainfo.GetMetaInfo()['MetaInfo']
        LOG.debug('device meta info: %s', meta_info)
        meta_info = meta_info.split('|')

        # select parts of the meta information for password use
        keydata = meta_info[0][:6] + meta_info[1] + meta_info[0][6:12]

        encrypted_password = encrypt_wifi_password_aes128(password, keydata)

    delta_delay = 2.0  # between network status checks
    success_statuses = {'1'}
    # success_statuses = {'1', '3'}

    # optionally make multiple connection attempts
    start_time = time.time()
    for attempt in range(connection_attempts):
        LOG.info('sending connection request (try %s)', attempt + 1)
        # success rate is *much* higher if the ConnectHomeNetwork command is
        # sent twice (not sure why!)
        for _ in range(2):
            result = device.WiFiSetup.ConnectHomeNetwork(
                ssid=ssid,
                auth=auth_mode,
                password=encrypted_password,
                encrypt=encryption_method,
                channel=channel,
            )
            time.sleep(0.15)
        try:
            LOG.info('pairing status: %s', result['PairingStatus'])
        except KeyError:
            LOG.info('pairing status: %s', result)
        stime = time.time()

        LOG.info('starting status checks (%s second timeout)', timeout)
        while time.time() - stime < timeout:
            time.sleep(delta_delay)
            status = device.WiFiSetup.GetNetworkStatus()['NetworkStatus']
            LOG.debug(
                'network status after %.2f seconds: %s',
                time.time() - stime,
                status,
            )
            if status in success_statuses:
                break
        if status in success_statuses:
            break

    close_status = device.WiFiSetup.CloseSetup()['status']
    LOG.debug('close status: %s', close_status)

    if status not in success_statuses or close_status != 'success':
        LOG.error(
            'Wemo device failed to connect to the network "%s", please try '
            'again (add -v for addition debug information).',
            ssid,
        )
    else:
        try:
            device.basicevent.SetSetupDoneStatus()
        except AttributeError:
            LOG.warning(
                'SetSetupDoneStatus not able to be set (some devices do not '
                'have this method)'
            )
        LOG.info(
            'Wemo device connected to network "%s", which took %.2f total '
            'seconds over %s connection attempt(s)',
            ssid,
            time.time() - start_time,
            attempt + 1,
        )


# -----------------------------------------------------------------------------
def wemo_connect_and_setup(
    wemossid: str, ssid: str, password: str, timeout: float = 20.0
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
            'nmcli command failed (this function requires network manager to '
            'be installed)'
        ) from exc
    except subprocess.CalledProcessError as exc:
        try:
            LOG.error('stdout:\n%s', networks.stdout.decode().strip())
            LOG.error('stderr:\n%s', networks.stderr.decode().strip())
        except UnboundLocalError:
            pass
        raise WemoException(
            'nmcli command failed (network may not exist anymore?)'
        ) from exc

    args = ' '.join(networks.args)
    stdout = networks.stdout.decode().strip()
    LOG.debug('result of "%s":\nstdout:\n%s', args, stdout)

    # a short delay to make sure the connection is well established
    time.sleep(2.0)

    LOG.info('searching %s for wemo devices', wemossid)
    devices = discover_and_log_devices(only_needing_setup=True)
    # NOTE: if the user is connected to multiple networks (e.g. has multiple
    #       wireless adapters), then discovery will still return all devices,
    #       not only those on the current Wemo's AP.
    for device in devices:
        wemo_setup(device, ssid=ssid, password=password, timeout=timeout)


# -----------------------------------------------------------------------------
def discover_and_log_devices(
    only_needing_setup: bool = False,
    verbose: int = 0,
) -> List[Device]:
    """Click interface to list all discovered devices."""
    devices = pywemo.discover_devices()
    not_setup = []
    device = None
    for device in devices:
        if only_needing_setup:
            status = device.WiFiSetup.GetNetworkStatus()['NetworkStatus']
            if status not in {'1'}:
                not_setup.append(device)
                LOG.info('found device needing setup: %s', device)
        else:
            LOG.info(DASHES)
            LOG.info('found device: %s', device)
            log_details(device, verbose)

    if only_needing_setup:
        return not_setup

    if device:
        LOG.info(DASHES)
    LOG.info('found %s devices', len(devices))
    return devices


# -----------------------------------------------------------------------------
def get_device_by_name(name: str) -> Device:
    """Get a device by the friendly name."""
    selected_device = None
    LOG.info('starting discovery...this may take a few seconds')
    devices = pywemo.discover_devices()
    for device in devices:
        LOG.debug('found device: %s', device)
        if device.name.lower() == name.lower():
            LOG.info('found device with name: %s', name)
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
def cli(verbose: int) -> None:
    """Wemo script to reset and setup Wemo devices.

    This script can be used to reset and setup Belkin Wemo devices, without
    using the Belkin iOS/Android App.

    \b
    External Requirements (for setup only)
    --------------------------------------
      - OpenSSL should be installed to use this script for device setup on
        a network using encryption, as OpenSSL is used to encrypt the password
        (AES only supported in this script).
      - nmcli (network manager cli) is used (only if --setup-all flag is used)
        to find and connect to Wemo APs.


    NOTE: This script has been tested on the following devices:

        \b
        |---------------------------------------------------------------------|
        | Device Type      | Market | FirmwareVersion                         |
        |---------------------------------------------------------------------|
        | Socket (Mini)    | US     | WeMo_WW_2.00.11452.PVT-OWRT-SNSV2       |
        | Lightswitch      | US     | WeMo_WW_2.00.11408.PVT-OWRT-LS          |
        | Dimmer           | US     | WeMo_WW_2.00.11453.PVT-OWRT-Dimmer      |
        | Insight Switch   | UK     | WeMo_WW_2.00.11483.PVT-OWRT-Insight     |
        | Switch           | UK     | WeMo_WW_2.00.11408.PVT-OWRT-SNS         |
        | Maker            | UK     | WeMo_WW_2.00.11423.PVT-OWRT-Maker       |
        |---------------------------------------------------------------------|
    """  # noqa: D301  # need to keep the \b with raw string for click
    setup_logger(verbose)


# -----------------------------------------------------------------------------
@cli.command(name='list', context_settings=CONTEXT_SETTINGS)
@click.option(
    '-v',
    '--verbose',
    count=True,
    help='''How much information to print.  Use -v to print all actions for
    the device that start with "Get", except for those that scan for APs or
    networks (slow).  Use -vv to also include those AP/network scans.  If no -v
    is provided, a smaller hand-selected subset of functions are run.''',
)
def wemo_discover(verbose=0) -> List[Device]:
    """Discover and print information about devices on current network(s)."""
    discover_and_log_devices(verbose=verbose + 1)


# -----------------------------------------------------------------------------
@cli.command(name='reset', context_settings=CONTEXT_SETTINGS)
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
                LOG.warning(
                    'name %s ignored, all discovered devices will be reset'
                )
            if devices and click.confirm(
                f'Are you sure you want to reset all {len(devices)} devices '
                'listed above?'
            ):
                for device in devices:
                    LOG.info(DASHES)
                    wemo_reset(device, data=data, wifi=wifi)
                LOG.info(DASHES)
        elif name is not None:
            device = get_device_by_name(name)
            wemo_reset(device, data=data, wifi=wifi)
        else:
            raise WemoException(
                'either --name=<str> must be provided or --reset-all flag used'
            )
        LOG.info('devices will take approximately 90 seconds to reset')
    except WemoException as exc:
        LOG.critical(exc)


# -----------------------------------------------------------------------------
@cli.command(name='setup', context_settings=CONTEXT_SETTINGS)
@click.option(
    '--ssid',
    required=True,
    type=str,
    help='The SSID of the network you want the Wemo device to join',
)
@click.option(
    '--password',
    default='',
    type=str,
    help='Password for the provided SSID (skip to be prompted)',
)
@click.option(
    '--setup-all',
    is_flag=True,
    help='''Scan for available Wemo device networks and try to setup any device
    on all discovered networks (requires nmcli to find and connect to the
    networks)''',
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

    User will be prompted for wifi password, if not provided.

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

            if wemo_aps and click.confirm(
                f'Are you sure you want to setup all {len(wemo_aps)} '
                '"expected wemo" devices listed above?'
            ):
                LOG.info(DASHES)
                LOG.info(
                    'NOTE: If some or all devices fail to connect, try '
                    're-running the same command a second time!'
                )
                if not password:
                    password = getpass()
                for wemo_ap in wemo_aps:
                    LOG.info(DASHES)
                    try:
                        wemo_connect_and_setup(
                            wemo_ap, ssid=ssid, password=password
                        )
                    except WemoException as exc:
                        LOG.error(exc)
                        LOG.error('|-- thus skipping ap: %s', wemo_ap)
                LOG.info(DASHES)

                if current and not current.lower().startswith('wemo.'):
                    try:
                        LOG.info('attempting to reconnect host to %s', current)
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
                'either --name=<str> must be provided or --setup-all flag used'
            )
    except WemoException as exc:
        LOG.critical(exc)


# -----------------------------------------------------------------------------
# Run the script
if __name__ == '__main__':
    # pylint: disable= no-value-for-parameter
    cli()


# ---[ END OF FILE ]-----------------------------------------------------------
