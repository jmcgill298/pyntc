from pyntc.devices.ios_device import IOSDevice as IOS
from pyntc.errors import CommandError, CommandListError
from pyntc.devices.base_device import RebootTimerError
from pyntc.devices.system_features.file_copy.base_file_copy import FileTransferError
from .test_data import IOSData
from copy import deepcopy
import unittest
import time
import re
import os


class TestIOS(unittest.TestCase):

    switch = IOS(host='10.1.10.1', username='admin', password='password')
    test_dir = os.path.dirname(__file__)

    def _property(self, device_property):
        setattr(self.switch, '_{}'.format(device_property), None)
        assert getattr(self.switch, '_{}'.format(device_property)) is None
        start_time = time.time()
        prop = getattr(self.switch, device_property)
        generate_property = time.time()
        assert getattr(self.switch, '_{}'.format(device_property)) is not None
        getattr(self.switch, device_property)
        call_property = time.time()
        assert (generate_property - start_time) > (call_property - generate_property)
        assert prop == getattr(self.switch, '_{}'.format(device_property))

    def test_internal_uptime_to_string(self):
        assert self.switch._uptime_to_string(IOSData.uptime) == '04:12:17:00'

    def test_backup_config(self):
        backupfile = '{0}/runconf'.format(self.test_dir)
        if os.path.isfile(backupfile):
            os.remove(backupfile)

        self.switch.backup_running_config(backupfile)
        assert os.path.isfile(backupfile)

        os.remove(backupfile)
        assert not os.path.isfile(backupfile)

    def test_checkpoint(self):
        if re.search('ntctest\.cp', self.switch.show('dir')):
            self.switch.show('delete ntctest.cp')

        self.switch.checkpoint('ntctest.cp')
        assert re.search('ntctest\.cp', self.switch.show('dir'))

        cpfile = self.switch.show('more flash:ntctest.cp')
        cpfile_list = [line for line in cpfile.splitlines() if line and not line.lstrip().startswith("!")]
        runconf = re.match('.*?([vV]ersion.+)', self.switch.running_config, re.DOTALL).group(1)
        runconf_list = [line for line in runconf.splitlines() if line and not line.lstrip().startswith("!")]
        assert cpfile_list == runconf_list

        self.switch.show('delete ntctest.cp')
        assert re.search('ntctest\.cp', self.switch.show('dir')) is None

    def test_config(self):
        self.switch.config('vlan 2')
        assert set(self.switch._get_vlan_list()) == set(IOSData.vlan_list.copy() + ['2'])
        self.switch.config('no vlan 2')
        assert self.switch._get_vlan_list() == IOSData.vlan_list
        with self.assertRaises(CommandError):
            self.switch.config("fail")

    def test_config_list(self):
        self.switch.config_list(['vlan 2', 'vlan 3'])
        assert set(self.switch._get_vlan_list()) == set(IOSData.vlan_list.copy() + ['2', '3'])
        self.switch.config_list(['no vlan 2', 'no vlan 3'])
        assert self.switch._get_vlan_list() == IOSData.vlan_list
        with self.assertRaises(CommandListError):
            self.switch.config_list(["fail"])

    def test_facts(self):
        self._property('facts')
        device_facts = deepcopy(self.switch._facts)
        assert device_facts.pop('vendor') == IOSData.vendor
        assert device_facts.pop('model') == IOSData.model
        assert device_facts.pop('os_version') == IOSData.os_version
        assert device_facts.pop('hostname') == IOSData.hostname
        assert device_facts.pop('fqdn') == IOSData.fqdn
        assert device_facts.pop('interfaces') == IOSData.interface_list
        assert device_facts.pop('vlans') == IOSData.vlan_list
        assert device_facts['cisco_ios_ssh'].pop('config_register') == IOSData.config_register
        assert not device_facts['cisco_ios_ssh']

        for key in ('uptime', 'uptime_string', 'serial_number', 'cisco_ios_ssh'):
            device_facts.pop(key)

        assert not device_facts

    def test_file_copy(self):
        ntcfile = '{0}/ntc-test'.format(self.test_dir)
        with open(ntcfile, 'w') as ntc_file:
            ntc_file.write('a')

        self.switch.file_copy(ntcfile, 'ntc-test')
        file_existence = self.switch.file_copy_remote_exists(ntcfile, 'ntc-test')
        assert file_existence

        with open(ntcfile, 'a') as ntc_file:
            ntc_file.write('a')
        file_existence = self.switch.file_copy_remote_exists(ntcfile, 'ntc-test')
        assert not file_existence

        self.switch.file_copy(ntcfile, 'ntc-test')
        file_existence = self.switch.file_copy_remote_exists(ntcfile, 'ntc-test')
        assert file_existence

        self.switch.show('delete flash:ntc-test')
        file_existence = self.switch.file_copy_remote_exists(ntcfile, 'ntc-test')
        assert not file_existence

        with self.assertRaises(FileTransferError):
            self.switch.file_copy(ntcfile, file_system='this_file_system_does_not_exit')

        os.remove(ntcfile)

    def test_get_boot_options(self):
        boot_options = self.switch.get_boot_options()
        assert boot_options.pop('sys') == IOSData.image_name
        assert not boot_options

    def test_rollback(self):
        self.switch.config_list(['interface vlan 1', 'description default'])
        self.switch.checkpoint('ntctest.cp')
        self.switch.config_list(['interface vlan 1', 'description ntctest'])
        vlan_conf = self.switch.show('show interface vlan 1 description')
        assert re.search('.+(ntctest)\s*$', vlan_conf) is not None
        self.switch.rollback('ntctest.cp')
        vlan_conf = self.switch.show('show interface vlan 1 description')
        assert re.search('.+(default)\s*$', vlan_conf) is not None

        self.switch.show('delete /force flash:ntctest.cp')

    def test_running_config(self):
        self._property('running_config')

    def test_save(self):
        switch_time = self.switch.show('show clock')
        file_date = re.match('\S+\s+\S+\s+\S+\s+(.+)\s*$', switch_time).group(1)
        self.switch.save()
        switch_dir = self.switch.show('dir flash:nvram_config')
        assert re.search(file_date, switch_dir) is not None

        self.switch.save(filename='pyntc.cfg')
        assert 'pyntc.cfg' in self.switch.show('dir')

        self.switch.show('delete /force flash:pyntc.cfg')
        assert 'pyntc.cfg' not in self.switch.show('dir')

    def test_set_boot_options(self):
        bootfile = self.switch.get_boot_options()['sys']
        bootfile_copy = 'pyntc-{0}'.format(bootfile.lstrip('/'))
        self.switch.show('copy flash:{0} flash:{1}'.format(bootfile, bootfile_copy))
        self.switch.set_boot_options('flash:{0}'.format(bootfile_copy))
        assert self.switch.get_boot_options()['sys'].lstrip('/') == '{0}'.format(bootfile_copy)
        self.switch.set_boot_options(bootfile)
        assert self.switch.get_boot_options()['sys'] == bootfile
        self.switch.show('delete flash:{0}'.format(bootfile_copy))

    def test_show(self):
        with self.assertRaises(CommandError):
            self.switch.show('non command')

        show_vlans = self.switch.show('show vlan')
        assert show_vlans

        show_expect = self.switch.show('clear line aux 0', expect=True, expect_string='[confirm]')
        assert show_expect

    def test_show_list(self):
        with self.assertRaises(CommandListError):
            self.switch.show_list(['show vlan', 'non command'])

        show_data = self.switch.show_list(['show vlan', 'show version'])
        assert len(show_data) == 2
        assert show_data[0]
        assert show_data[1]

    def test_startup_config(self):
        self._property('startup_config')
