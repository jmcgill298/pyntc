from pyntc.devices.nxos_device import NXOSDevice as NXOS
from pyntc.errors import CommandError, CommandListError
from pyntc.devices.system_features.file_copy.base_file_copy import FileTransferError
from .test_data import NXOSData
from copy import deepcopy
import unittest
import time
import re
import os


class TestNXOS(unittest.TestCase):

    switch = NXOS(host='10.1.1.1', username='admin', password='passsword')
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

    def test_backup_config(self):
        backupfile = '{0}/runconf'.format(self.test_dir)
        if os.path.isfile(backupfile):
            os.remove(backupfile)

        self.switch.backup_running_config(backupfile)
        assert os.path.isfile(backupfile)

        os.remove(backupfile)
        assert not os.path.isfile(backupfile)

    def test_checkpoint(self):
        if re.search('ntctest\.cp', self.switch.show('dir', raw_text=True)):
            self.switch.show('delete ntctest.cp')

        self.switch.checkpoint('ntctest.cp')
        assert re.search('ntctest\.cp', self.switch.show('dir', raw_text=True))
        assert not self.switch.show("show diff rollback-patch file bootflash:ntctest.cp running-config")

        self.switch.show('delete ntctest.cp', raw_text=True)
        assert re.search('ntctest\.cp', self.switch.show('dir', raw_text=True)) is None

    def test_config(self):
        self.switch.config('vlan 2')
        assert self.switch.show('show vlan id 2')
        self.switch.config('no vlan 2')
        assert not self.switch.show('show vlan id 2')
        with self.assertRaises(CommandError):
            self.switch.config("fail")

    def test_config_list(self):
        self.switch.config_list(['vlan 2', 'vlan 3'])
        assert self.switch.show('show vlan id 2')
        assert self.switch.show('show vlan id 3')

        self.switch.config_list(['no vlan 2', 'no vlan 3'])
        assert not self.switch.show('show vlan id 2')
        assert not self.switch.show('show vlan id 3')

        with self.assertRaises(CommandListError):
            self.switch.config_list(["fail"])

    def test_facts(self):
        self._property('facts')
        device_facts = deepcopy(self.switch._facts)
        assert device_facts.pop('vendor') == NXOSData.vendor
        assert device_facts.pop('model') == NXOSData.model
        assert device_facts.pop('os_version') == NXOSData.os_version
        assert device_facts.pop('hostname') == NXOSData.hostname
        assert device_facts.pop('fqdn') == NXOSData.fqdn
        assert device_facts.pop('interfaces') == NXOSData.interface_list
        assert device_facts.pop('vlans') == NXOSData.vlan_list

        for key in ('uptime', 'uptime_string', 'serial_number'):
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

        self.switch.show('delete bootflash:ntc-test')
        file_existence = self.switch.file_copy_remote_exists(ntcfile, 'ntc-test')
        assert not file_existence

        with self.assertRaises(FileTransferError):
            self.switch.file_copy("thisfiledoesnotexist")

        os.remove(ntcfile)

    def test_get_boot_options(self):
        boot_options = self.switch.get_boot_options()
        assert boot_options.pop('sys') == NXOSData.image_name
        boot_options.pop('status')
        assert not boot_options

    def test_rollback(self):
        self.switch.config_list(['interface vlan 1', 'description default'])
        self.switch.checkpoint('ntctest.cp')
        self.switch.config_list(['interface vlan 1', 'description ntctest'])
        vlan_conf = self.switch.show('show interface vlan 1 description')
        assert vlan_conf['LINE'] == 'ntctest'
        self.switch.rollback('ntctest.cp')
        vlan_conf = self.switch.show('show interface vlan 1 description')
        assert vlan_conf['LINE'] == 'default'

        self.switch.show('delete bootflash:ntctest.cp')

    def test_running_config(self):
        self._property('running_config')

    def test_save(self):
        switch_time = self.switch.show('show clock')['simple_time']
        file_day, file_year = re.match('\S+\s+\S+\s+\S+\s+(.+)\s+(\d+)\s*$', switch_time).groups()
        self.switch.save()
        switch_save = self.switch.show('show startup-config', raw_text=True)
        assert re.search('{0}.+{1}'.format(file_day, file_year), switch_save) is not None

        self.switch.save(filename='pyntc.cfg')
        assert 'pyntc.cfg' in self.switch.show('dir', raw_text=True)

        self.switch.show('delete bootflash:pyntc.cfg')
        assert 'pyntc.cfg' not in self.switch.show('dir', raw_text=True)

    def test_set_boot_options(self):
        with self.assertRaises(NotImplementedError):
            self.switch.set_boot_options('image')

    def test_show(self):
        with self.assertRaises(CommandError):
            self.switch.show('non command')

        show_vlans = self.switch.show('show vlan')
        assert show_vlans

    def test_show_list(self):
        with self.assertRaises(CommandListError):
            self.switch.show_list(['show vlan', 'non command'])

        show_data = self.switch.show_list(['show vlan', 'show version'])
        assert len(show_data) == 2
        assert show_data[0]
        assert show_data[1]

    def test_startup_config(self):
        self._property('startup_config')
