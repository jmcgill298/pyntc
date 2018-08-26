from pyntc.devices.eos_device import EOSDevice as EOS
from pyntc.errors import CommandError, CommandListError
from pyntc.devices.base_device import RebootTimerError
from .test_data import EOSData
from copy import deepcopy
import unittest
import time
import re
import os


class TestEOS(unittest.TestCase):

    switch = EOS(host='10.1.1.1', username='admin', password='password')
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

    def test_internal_get_interfaces_list(self):
        assert self.switch._get_interface_list() == EOSData.interface_list

    def test_internal_get_vlan_list(self):
        assert self.switch._get_vlan_list() == ["1"]

    def test_internal_interfaces_status_list(self):
        assert self.switch._interfaces_status_list() == EOSData.interface_status_list

    def test_internal_parse_response(self):
        data = [{'result': {'output': 'a'}}, {'result': {'output': 'b'}}]
        raw = self.switch._parse_response(response=data, raw_text=True)
        assert raw == ['a', 'b']

        raw = self.switch._parse_response(response=data, raw_text=False)
        assert raw == [{'output': 'a'}, {'output': 'b'}]

    def test_internal_uptime_to_string(self):
        assert self.switch._uptime_to_string(EOSData.uptime) == '04:12:17:00'

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

        cpfile = self.switch.show('more flash:ntctest.cp')['output']
        cpfile_list = [line for line in cpfile.splitlines() if not line.lstrip().startswith("!")]
        runconf_list = [line for line in self.switch.running_config.splitlines() if not line.lstrip().startswith("!")]
        assert cpfile_list == runconf_list

        self.switch.show('delete ntctest.cp')
        assert re.search('ntctest\.cp', self.switch.show('dir', raw_text=True)) is None

    def test_config(self):
        self.switch.config('vlan 2')
        assert set(self.switch._get_vlan_list()) == set(EOSData.vlan_list.copy() + ['2'])
        self.switch.config('no vlan 2')
        assert self.switch._get_vlan_list() == EOSData.vlan_list
        with self.assertRaises(CommandError):
            self.switch.config("fail")

    def test_config_list(self):
        self.switch.config_list(['vlan 2', 'vlan 3'])
        assert set(self.switch._get_vlan_list()) == set(EOSData.vlan_list.copy() + ['2', '3'])
        self.switch.config_list(['no vlan 2', 'no vlan 3'])
        assert self.switch._get_vlan_list() == EOSData.vlan_list
        with self.assertRaises(CommandListError):
            self.switch.config_list(["fail"])

    def test_facts(self):
        self._property('facts')
        device_facts = deepcopy(self.switch._facts)
        assert device_facts.pop('vendor') == EOSData.vendor
        assert device_facts.pop('model') == EOSData.model
        assert device_facts.pop('os_version') == EOSData.os_version
        assert device_facts.pop('hostname') == EOSData.hostname
        assert device_facts.pop('fqdn') == EOSData.fqdn
        assert device_facts.pop('interfaces') == EOSData.interface_list
        assert device_facts.pop('vlans') == EOSData.vlan_list

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

        self.switch.show('delete flash:ntc-test')
        file_existence = self.switch.file_copy_remote_exists(ntcfile, 'ntc-test')
        assert not file_existence

        os.remove(ntcfile)

    def test_get_boot_options(self):
        boot_options = self.switch.get_boot_options()
        assert boot_options.pop('sys') == EOSData.image_name
        assert not boot_options

    def test_reboot(self):
        with self.assertRaises(RebootTimerError):
            self.switch.reboot(timer=1)

    def test_rollback(self):
        self.switch.config_list(['vlan 1', 'name default'])
        self.switch.checkpoint('ntctest.cp')
        self.switch.config_list(['vlan 1', 'name ntctest'])
        vlan_conf = self.switch.show('show vlan id 1')
        assert vlan_conf['vlans']['1']['name'] == 'ntctest'

        self.switch.rollback('ntctest.cp')
        vlan_conf = self.switch.show('show vlan id 1')
        assert vlan_conf['vlans']['1']['name'] == 'default'

        self.switch.show('delete flash:ntctest.cp')

    def test_running_config(self):
        self._property('running_config')

    def test_save(self):
        switch_time = self.switch.show('show clock')
        file_date = ''.join(re.match('\S+\s+(\S+\s)\s*(\d+\s)\s*(\d+:)\d+', switch_time['output']).groups())
        self.switch.save()
        switch_dir = self.switch.show('dir')
        startup_config = ''
        for file in switch_dir['messages'][0].splitlines():
            if re.search(file_date, file):
                startup_config = file
                break
        assert startup_config

        self.switch.save(filename='pyntc.cfg')
        assert 'pyntc.cfg' in self.switch.show('dir')['messages'][0]

        self.switch.show('delete flash:pyntc.cfg')
        assert 'pyntc.cfg' not in self.switch.show('dir')['messages'][0]

    def test_set_boot_options(self):
        bootfile = self.switch.get_boot_options()['sys']
        bootfile_copy = 'pyntc-{0}'.format(bootfile.lstrip('/'))
        self.switch.show('copy flash:{0} flash:{1}'.format(bootfile, bootfile_copy))
        self.switch.set_boot_options('flash:{0}'.format(bootfile_copy))
        assert self.switch.get_boot_options()['sys'] == '/{0}'.format(bootfile_copy)
        self.switch.set_boot_options(bootfile)
        assert self.switch.get_boot_options()['sys'] == bootfile
        self.switch.show('delete flash:{0}'.format(bootfile_copy))

    def test_show(self):
        with self.assertRaises(CommandError):
            self.switch.show('non command')

        show_vlans = self.switch.show('show vlan')
        assert show_vlans['vlans']['1']

    def test_show_list(self):
        with self.assertRaises(CommandListError):
            self.switch.show_list(['show vlan', 'non command'])

        show_data = self.switch.show_list(['show vlan', 'show version'])
        assert len(show_data) == 2
        assert show_data[0]['vlans']
        assert show_data[1]['version']

        show_data = self.switch.show_list(['show vlan', 'show version'], raw_text=True)
        assert len(show_data) == 2
        for data in show_data:
            self.assertIsInstance(data, str)

    def test_startup_config(self):
        self._property('startup_config')
