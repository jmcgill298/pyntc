"""Supported devices are stored here. Every supported device needs a
device_type stored as a string, and a class subclassed from BaseDevice.
"""

from .eos_device import EOSDevice
from .nxos_device import NXOSDevice
from .ios_device import IOSDevice
from .jnpr_device import JunosDevice
from .asa_device import ASADevice
from .f5_device import F5Device
from .base_device import BaseDevice


supported_devices = {
    'arista_eos_eapi': EOSDevice,
    'cisco_nxos_nxapi': NXOSDevice,
    'cisco_ios_ssh': IOSDevice,
    'juniper_junos_netconf': JunosDevice,
    'cisco_asa_ssh': ASADevice,
    'f5_tmos_icontrol': F5Device,
}
