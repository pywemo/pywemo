"""Tests for interfacing with the generated XSD classes."""

import ast
from unittest import mock

import pytest

from pywemo.exceptions import InvalidSchemaError
from pywemo.ouimeaux_device.api import xsd_types
from pywemo.ouimeaux_device.api.xsd import device as device_parser
from pywemo.ouimeaux_device.api.xsd import service as service_parser

DEVICE_PARSER = "pywemo.ouimeaux_device.api.xsd_types.device_parser"
SERVICE_PARSER = "pywemo.ouimeaux_device.api.xsd_types.service_parser"


def test_argument_default_values():
    xsd_argument = service_parser.ArgumentType()

    argument = xsd_types.ArgumentType.from_argument(xsd_argument)

    assert argument.name == ""
    assert argument.direction == ""


def test_action():
    argument = service_parser.ArgumentType(name="arg_name", direction="out")
    argument_list = service_parser.ArgumentListType(argument=[argument])
    xsd_action = service_parser.ActionType(
        name="action_name", argumentList=argument_list
    )

    action = xsd_types.ActionProperties.from_action(xsd_action)

    assert action.name == "action_name"
    assert action.arguments[0].name == "arg_name"
    assert action.arguments[0].direction == "out"


def test_action_missing_name():
    action = service_parser.ActionType()

    with pytest.raises(InvalidSchemaError):
        xsd_types.ActionProperties.from_action(action)


def test_action_missing_arguments():
    action = service_parser.ActionType(name="abc")

    assert isinstance(
        xsd_types.ActionProperties.from_action(action).arguments, list
    )


def test_service():
    action = service_parser.ActionType(name="action_name")
    action_list = service_parser.ActionListType(action=[action])
    xsd_scpd = service_parser.scpd(actionList=action_list)

    with mock.patch(SERVICE_PARSER) as mock_parser:
        mock_parser.parseString.return_value = xsd_scpd
        scpd = xsd_types.ServiceDescription.from_xml(b"")

    assert scpd.actions[0].name == "action_name"


def test_services_parse_string_raises():
    with mock.patch(SERVICE_PARSER) as mock_parser, pytest.raises(
        InvalidSchemaError
    ):
        mock_parser.parseString.side_effect = Exception
        xsd_types.ServiceDescription.from_xml(b"")


def test_service_no_action():
    xsd_scpd = service_parser.scpd()

    with mock.patch(SERVICE_PARSER) as mock_parser:
        mock_parser.parseString.return_value = xsd_scpd
        scpd = xsd_types.ServiceDescription.from_xml(b"")

    assert isinstance(scpd.actions, list)


SERVICE_PROPERTIES = {
    "serviceType_member": "ServiceTypeValue",
    "serviceId": "ServiceIdValue",
    "SCPDURL": "SCPDURLValue",
    "controlURL": "ControlURLValue",
    "eventSubURL": "EventSubURLValue",
}


def test_service_properties():
    xsd_service = device_parser.serviceType(**SERVICE_PROPERTIES)

    service = xsd_types.ServiceProperties.from_service(xsd_service)

    assert service.service_type == "ServiceTypeValue"
    assert service.service_id == "ServiceIdValue"
    assert service.description_url == "SCPDURLValue"
    assert service.control_url == "ControlURLValue"
    assert service.event_subscription_url == "EventSubURLValue"


@pytest.mark.parametrize("exclude", SERVICE_PROPERTIES.keys())
def test_service_properties_missing(exclude):
    args = {**SERVICE_PROPERTIES}
    del args[exclude]
    xsd_service = device_parser.serviceType(**args)

    with pytest.raises(InvalidSchemaError):
        xsd_types.ServiceProperties.from_service(xsd_service)


@pytest.mark.parametrize("exclude", SERVICE_PROPERTIES.keys())
def test_service_properties_empty(exclude):
    args = {**SERVICE_PROPERTIES, exclude: ""}
    xsd_service = device_parser.serviceType(**args)

    with pytest.raises(InvalidSchemaError):
        xsd_types.ServiceProperties.from_service(xsd_service)


DEVICE_PROPERTIES = {
    "friendlyName": "FriendlyNameValue",
    "macAddress": "MACAddressValue",
    "manufacturer": "Belkin International Inc.",
    "modelDescription": "ModelDescriptionValue",
    "modelName": "ModelNameValue",
    "serialNumber": "SerialNumberValue",
    "UDN": "UniqueDeviceName",
    "deviceType": "DeviceTypeValue",
    "anytypeobjs_": [
        "<firmwareVersion>FirmwareVersionValue</firmwareVersion>"
    ],
    "serviceList": device_parser.ServiceListType(
        service=[device_parser.serviceType(**SERVICE_PROPERTIES)]
    ),
}

REQUIRED_KEYS = (
    "friendlyName",
    "manufacturer",
    "modelName",
    "UDN",
    "deviceType",
)


def test_device():
    xsd_device = device_parser.DeviceType(**DEVICE_PROPERTIES)
    root = device_parser.root(device=xsd_device)

    with mock.patch(DEVICE_PARSER) as mock_parser:
        mock_parser.parseString.return_value = root
        device = xsd_types.DeviceDescription.from_xml(b"")

    assert device.firmware_version == "FirmwareVersionValue"
    assert device.name == "FriendlyNameValue"
    assert device.mac == "MACAddressValue"
    assert device.manufacturer == "Belkin International Inc."
    assert device.model == "ModelDescriptionValue"
    assert device.model_name == "ModelNameValue"
    assert device.serial_number == "SerialNumberValue"
    assert device.udn == "UniqueDeviceName"
    assert device._config_any["firmwareVersion"] == "FirmwareVersionValue"
    assert device._device_type == "DeviceTypeValue"
    assert device._services[0].service_type == "ServiceTypeValue"


@pytest.mark.parametrize("exclude", REQUIRED_KEYS)
def test_device_missing_required_fields(exclude):
    args = {**DEVICE_PROPERTIES}
    del args[exclude]
    xsd_device = device_parser.DeviceType(**args)
    root = device_parser.root(device=xsd_device)

    with mock.patch(DEVICE_PARSER) as mock_parser, pytest.raises(
        InvalidSchemaError
    ):
        mock_parser.parseString.return_value = root
        xsd_types.DeviceDescription.from_xml(b"")


def test_device_missing_optional_fields():
    optional_keys = set(DEVICE_PROPERTIES.keys()).difference(REQUIRED_KEYS)
    args = {**DEVICE_PROPERTIES}
    for optional_key in optional_keys:
        del args[optional_key]

    xsd_device = device_parser.DeviceType(**args)
    root = device_parser.root(device=xsd_device)
    with mock.patch(DEVICE_PARSER) as mock_parser:
        mock_parser.parseString.return_value = root
        device = xsd_types.DeviceDescription.from_xml(b"")

    assert device.firmware_version == ""
    assert device.mac == ""
    assert device.model == ""
    assert device.serial_number == ""
    assert device._config_any == {}
    assert device._services == []


def test_device_missing_device():
    root = device_parser.root()

    with mock.patch(DEVICE_PARSER) as mock_parser, pytest.raises(
        InvalidSchemaError
    ):
        mock_parser.parseString.return_value = root
        xsd_types.DeviceDescription.from_xml(b"")


def test_device_wrong_manufacturer():
    args = {**DEVICE_PROPERTIES, "manufacturer": "pywemo"}
    xsd_device = device_parser.DeviceType(**args)
    root = device_parser.root(device=xsd_device)

    with mock.patch(DEVICE_PARSER) as mock_parser, pytest.raises(
        InvalidSchemaError
    ):
        mock_parser.parseString.return_value = root
        xsd_types.DeviceDescription.from_xml(b"")


def test_device_parser_raises():
    with mock.patch(DEVICE_PARSER) as mock_parser, pytest.raises(
        InvalidSchemaError
    ):
        mock_parser.parseString.side_effect = Exception
        xsd_types.DeviceDescription.from_xml(b"")


def test_no_six_import():
    # device.py & service.py were manually edited to remove the dependency on
    # 'six' for https://github.com/pywemo/pywemo/issues/344. Ensure this
    # dependency is not added again next time these files are re-generated.
    with open("pywemo/ouimeaux_device/api/xsd/device.py") as device_py:
        device_ast = ast.parse(device_py.read())
    import_modules = [
        e.module for e in device_ast.body if isinstance(e, ast.ImportFrom)
    ]
    assert "six.moves" not in import_modules

    with open("pywemo/ouimeaux_device/api/xsd/service.py") as service_py:
        service_ast = ast.parse(service_py.read())
    import_modules = [
        e.module for e in service_ast.body if isinstance(e, ast.ImportFrom)
    ]
    assert "six.moves" not in import_modules
