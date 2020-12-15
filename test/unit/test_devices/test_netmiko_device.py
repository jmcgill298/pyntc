from unittest import mock

import pytest

from netmiko.cisco import CiscoAsaSSH
from netmiko.cisco import CiscoIosSSH
from netmiko.cisco import CiscoWlcSSH

from pyntc.devices import netmiko_device as netmiko_module
from pyntc.devices import AIREOSDevice, ASADevice, IOSDevice


CLASS_IDS = ("aireos", "asa", "ios")


def get_mock_class(pyntc_class):
    pyntc_class.__init__ = mock.Mock(return_value=None)
    return pyntc_class()


@pytest.mark.parametrize("pyntc_class", (AIREOSDevice, ASADevice, IOSDevice), ids=CLASS_IDS)
def test_command_output_has_error(pyntc_class):
    device = get_mock_class(pyntc_class)
    command_fails = device._command_output_has_error("valid output")
    assert command_fails is False


@pytest.mark.parametrize(
    "pyntc_class,output",
    (
        (AIREOSDevice, "Incorrect usage: invalid output"),
        (ASADevice, "Error: invalid output"),
        (IOSDevice, r"% Invalid command"),
    ),
    ids=CLASS_IDS,
)
def test_command_output_has_error_error(pyntc_class, output):
    device = get_mock_class(pyntc_class)
    command_fails = device._command_output_has_error(output)
    assert command_fails is True
