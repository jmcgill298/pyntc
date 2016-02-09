import re

from jnpr.junos import Device as JunosNativeDevice
from jnpr.junos.utils.config import Config as JunosNativeConfig
from jnpr.junos.op.ethport import EthPortTable
from jnpr.junos.op.phyport import PhyPortTable

from .base_device import BaseDevice

JNPR_DEVICE_TYPE = 'juniper_junos_netconf'

class JunosDevice(BaseDevice):

    def __init__(self, host, username, password, *args, **kwargs):
        super(JunosDevice, self).__init__(host,
                                          username,
                                          password,
                                          *args,
                                          vendor='juniper',
                                          device_type=JNPR_DEVICE_TYPE,
                                          **kwargs)

        self.native = JunosNativeDevice(*args, host=host, user=username, passwd=password, **kwargs)
        self.connected = False
        self.open()

        self.cu = JunosNativeConfig(self.native)

    def open(self):
        if not self.connected:
            self.native.open()
            self.connected = True

    def close(self):
        if self.connected:
            self.native.close()
            self.connected = False

    def show(self, command, raw_text=True):
        if not command.startswith('show'):
            return ''

        return self.native.cli(command, warning=False)

    def backup_running_config(self, filename):
        with open(filename, 'w') as f:
            f.write(self.running_config)

    def checkpoint(self):
        pass

    def config(self, command):
        self.cu.load(command, format='set')
        self.cu.commit()

    def config_list(self, commands):
        for command in commands:
            self.cu.load(command, format='set')

        self.cu.commit()

    def _uptime_components(self, uptime_full_string):
        match_days = re.search(r'(\d+) days?', uptime_full_string)
        match_hours = re.search(r'(\d+) hours?', uptime_full_string)
        match_minutes = re.search(r'(\d+) minutes?', uptime_full_string)
        match_seconds = re.search(r'(\d+) seconds?', uptime_full_string)

        days = int(match_days.group(1)) if match_days else 0
        hours = int(match_hours.group(1)) if match_hours else 0
        minutes = int(match_minutes.group(1)) if match_minutes else 0
        seconds = int(match_seconds.group(1)) if match_seconds else 0

        return days, hours, minutes, seconds

    def _uptime_to_string(self, uptime_full_string):
        days, hours, minutes, seconds = self._uptime_components(uptime_full_string)
        return '%02d:%02d:%02d:%02d' % (days, hours, minutes, seconds)

    def _uptime_to_seconds(self, uptime_full_string):
        days, hours, minutes, seconds = self._uptime_components(uptime_full_string)

        seconds += days * 24 * 60 * 60
        seconds += hours * 60 * 60
        seconds += minutes * 60

        return seconds

    def _get_interfaces(self):
        phys = PhyPortTable(self.native)
        phys.get()

        return phys.keys()

    @property
    def facts(self):
        if hasattr(self, '_facts'):
            return self._facts

        native_facts = self.native.facts

        facts = {}
        facts['hostname'] = native_facts['hostname']
        facts['fqdn'] = native_facts['fqdn']
        facts['model'] = native_facts['model']

        native_uptime_string = native_facts['RE0']['up_time']
        facts['uptime'] = self._uptime_to_seconds(native_uptime_string)
        facts['uptime_string'] = self._uptime_to_string(native_uptime_string)

        facts['serial_number'] = native_facts['serialnumber']

        facts['interfaces'] = self._get_interfaces()

        for fact_key in native_facts:
            if fact_key.startswith('version') and fact_key != 'version_info':
                facts['os_version'] = native_facts[fact_key]
                break

        facts['vendor'] = self.vendor
        self._facts = facts
        return self._facts

    def file_copy(self):
        pass

    def file_copy_remote_exists(self):
        pass

    def get_boot_options(self):
        pass

    def reboot(self):
        pass

    def rollback(self):
        pass

    @property
    def running_config(self):
        return self.show('show config')

    def save(self):
        pass

    def set_boot_options(self):
        pass

    def show_list(self):
        pass

    @property
    def startup_config(self):
        return self.show('show config')