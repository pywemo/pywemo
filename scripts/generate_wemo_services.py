#!/usr/bin/env python3
"""Generate Python type stubs for WeMo services.

This script generates a Python type stub file (.pyi). The stub file contains
the names and actions for all known WeMo services. The source of truth comes
from the VCR cassette files that contain the service xml files.

This stub file is then used by the mypy type checker so it can be aware of the
services and the names of the methods (actions) within each service.

Usage:
  scripts/generate_wemo_services.py > \
      pywemo/ouimeaux_device/api/wemo_services.pyi
"""
from __future__ import annotations

import collections
from typing import Iterable, cast

import vcr
from pywemo.ouimeaux_device.api.xsd_types import (
    DeviceDescription,
    ServiceDescription,
)

FIRMWARE_VCR_CASSETTE_FILES = [
    f"tests/vcr/tests.ouimeaux_device.test_{cassette}"
    for cassette in [
        "bridge/WeMo_WW_2.00.11057.PVT-OWRT-Link.yaml",
        "dimmer/WeMo_WW_2.00.11453.PVT-OWRT-Dimmer.yaml",
        "dimmer/WEMO_WW_2.00.20110904.PVT-RTOS-DimmerV2.yaml",
        "insight/WeMo_WW_2.00.11408.PVT-OWRT-Insight.yaml",
        "lightswitch/WeMo_WW_2.00.11408.PVT-OWRT-LS.yaml",
        "lightswitch/WeMo_WW_2.00.11563.PVT-OWRT-LIGHTV2-WLS040.yaml",
        "lightswitch/WeMo_WW_2.00.11563.PVT-OWRT-LIGHTV2-WLS0403.yaml",
        "maker/WeMo_WW_2.00.11423.PVT-OWRT-Maker.yaml",
        "outdoor_plug/WEMO_WW_1.00.20081401.PVT-RTOS-OutdoorV1.yaml",
        "switch/WeMo_US_2.00.2769.PVT.yaml",
        "switch/WeMo_WW_2.00.11420.PVT-OWRT-SNSV2.yaml",
        "switch/WEMO_WW_4.00.20101902.PVT-RTOS-SNSV4.yaml",
    ]
]

FILE_HEADER = '''"""WeMo service types.

Do not hand edit. This file is automatically generated. Any manual changes
will be erased the next time it is re-generated.

To regenerate this file, run:
  scripts/generate_wemo_services.py > \\
      pywemo/ouimeaux_device/api/wemo_services.pyi
"""

from typing import Callable

UPnPMethod = Callable[..., dict[str, str]]
'''

ALL_SERVICES: dict[str, set[str]] = collections.defaultdict(set)


def get_response_for_url_endswith(
    cassette: vcr.cassette.Cassette, ending: str
) -> bytes:
    """Fetch the response body for a url ending with 'ending'."""
    request = [
        request
        for request in cassette.requests
        if request.url.endswith(ending)
    ][0]
    response = cassette.responses_of(request)[0]
    return cast(bytes, response['body']['string'])


def update_services_from_cassette(cassette_file_name: str) -> None:
    """Populate ALL_SERVICES from the data found within a cassette."""
    cassette = vcr.cassette.Cassette.load(path=cassette_file_name)
    device = DeviceDescription.from_xml(
        get_response_for_url_endswith(cassette, "/setup.xml")
    )

    for service in device._services:  # pylint: disable=protected-access
        service_name = service.service_type.split(':')[-2]
        scpd = ServiceDescription.from_xml(
            get_response_for_url_endswith(cassette, service.description_url),
        )
        ALL_SERVICES[service_name].update(
            action.name for action in scpd.actions
        )


def class_name(service_name: str) -> str:
    """Map service name to .pyi class name."""
    return f"Service_{service_name}"


def output_service_as_class(service_name: str, actions: Iterable[str]) -> None:
    """Output a service class with actions as fields."""
    print(f"class {class_name(service_name)}:")
    for action in sorted(actions):
        print(f"    {action}: UPnPMethod")
    print("")


def generate() -> None:
    """Output the Python type stub file to stdout."""
    print(FILE_HEADER)

    # Read all services from the cassette files and populate ALL_SERVICES.
    for file_name in FIRMWARE_VCR_CASSETTE_FILES:
        update_services_from_cassette(file_name)

    sorted_services = sorted(ALL_SERVICES)

    # Output each service as it's own class. Add a field in the class for each
    # action/method within the service.
    for service_name in sorted_services:
        output_service_as_class(service_name, ALL_SERVICES[service_name])

    # When instantiating a Device class, each of the services are added as
    # fields on the instance. WeMoServiceTypesMixin is intended to be a
    # super-class of the Device class. It will contain fields for all known
    # WeMo services. Each service property will correspond to a service class
    # type that contains all known actions/methods as fields. In this way, the
    # type checker will know that device.basicevent is a valid service, and
    # that GetBinaryState is a method that can be called within that service.
    print("class WeMoServiceTypesMixin:")
    for service_name in sorted_services:
        print(f"    {service_name}: {class_name(service_name)}")
    print("")

    # When instantiating a Service class, each of the services actions are
    # added as fields on the instance. WeMoAllActionsMixin is intended to be a
    # super-class of the Service class. It will contain fields for all known
    # WeMo actions.
    print("class WeMoAllActionsMixin(")
    for service_name in sorted_services:
        print(f"    {class_name(service_name)},")
    print("):")
    print("    pass")


if __name__ == "__main__":
    generate()
