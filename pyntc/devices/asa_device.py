"""Module for using a Cisco ASA device over SSH.
"""

import os
import re
import signal

from netmiko import ConnectHandler
from netmiko import FileTransfer

from .system_features.file_copy.base_file_copy import FileTransferError
from pyntc.errors import CommandError, CommandListError, NTCError
from pyntc.templates import get_structured_data
from .base_device import BaseDevice, fix_docs


@fix_docs
class ASADevice(BaseDevice):

    def __init__(self, host, username, password, secret='', port=22, **kwargs):
        super(BaseDevice, self).__init__(host, username, password, vendor='cisco', device_type='cisco_asa_ssh')

        self.native = None
        self.host = host
        self.username = username
        self.password = password
        self.secret = secret
        self.port = int(port)
        self.global_delay_factor = kwargs.get('global_delay_factor', 1)
        self.delay_factor = kwargs.get('delay_factor', 1)
        self._connected = False
        self.open()

    def _enable(self):
        self.native.exit_config_mode()
        if not self.native.check_enable_mode():
            self.native.enable()

    def _enter_config(self):
        self._enable()
        self.native.config_mode()

    def _file_copy_instance(self, src, dest=None, file_system='flash:'):
        if dest is None:
            dest = os.path.basename(src)

        fc = FileTransfer(self.native, src, dest, file_system=file_system)

        return fc

    def _interfaces_detailed_list(self):
        ip_int = self.show('show interface')
        ip_int_data = get_structured_data('cisco_asa_show_interface.template', ip_int)

        return ip_int_data

    def _raw_version_data(self):
        show_version_out = self.show('show version')
        try:
            version_data = get_structured_data('cisco_asa_show_version.template', show_version_out)[0]
            return version_data
        except IndexError:
            return {}

    def _send_command(self, command, expect=False, expect_string=''):
        if expect:
            if expect_string:
                response = self.native.send_command_expect(command, expect_string=expect_string)
            else:
                response = self.native.send_command_expect(command)
        else:
            response = self.native.send_command_timing(command)

        if '% ' in response or 'Error:' in response:
            raise CommandError(command, response)

        return response

    @staticmethod
    def _uptime_components(uptime_full_string):
        match_days = re.search(r'(\d+) days?', uptime_full_string)
        match_hours = re.search(r'(\d+) hours?', uptime_full_string)
        match_minutes = re.search(r'(\d+) minutes?', uptime_full_string)

        days = int(match_days.group(1)) if match_days else 0
        hours = int(match_hours.group(1)) if match_hours else 0
        minutes = int(match_minutes.group(1)) if match_minutes else 0

        return days, hours, minutes

    def _uptime_to_seconds(self, uptime_full_string):
        days, hours, minutes = self._uptime_components(uptime_full_string)

        seconds = days * 24 * 60 * 60
        seconds += hours * 60 * 60
        seconds += minutes * 60

        return seconds

    def _uptime_to_string(self, uptime_full_string):
        days, hours, minutes = self._uptime_components(uptime_full_string)
        return '%02d:%02d:%02d:00' % (days, hours, minutes)

    def backup_running_config(self, filename):
        with open(filename, 'w') as f:
            f.write(self.running_config)

    def checkpoint(self, checkpoint_file):
        self.save(filename=checkpoint_file)

    def close(self):
        if self._connected:
            self.native.disconnect()
            self._connected = False

    def config(self, command):
        self._enter_config()
        self._send_command(command)
        self.native.exit_config_mode()

    def config_list(self, commands):
        self._enter_config()
        entered_commands = []
        for command in commands:
            entered_commands.append(command)
            try:
                self._send_command(command)
            except CommandError as e:
                raise CommandListError(entered_commands, command, e.cli_error_msg)
        self.native.exit_config_mode()

    @property
    def facts(self):
        """Implement this once facts' re-factor is done. """
        return {}

    def file_copy(self, src, dest=None, file_system='flash:'):
            fc = self._file_copy_instance(src, dest, file_system=file_system)
            self._enable()
            #        if not self.fc.verify_space_available():
            #            raise FileTransferError('Not enough space available.')

            try:
                fc.enable_scp()
                fc.establish_scp_conn()
                fc.transfer_file()
            # TODO: Discover expected exceptions and raise appropriately
            except:
                raise FileTransferError
            finally:
                fc.close_scp_chan()

    def file_copy_remote_exists(self, src, dest=None, file_system='flash:'):
        fc = self._file_copy_instance(src, dest, file_system=file_system)
        self._enable()
        if fc.check_file_exists() and fc.compare_md5():
            return True

        return False

    def get_boot_options(self):
        show_boot_out = self.show('show boot | i BOOT variable')
        # Improve regex to get only the first boot $var in the sequence!
        boot_path_regex = r'Current BOOT variable = (\S+):\/(\S+)'

        match = re.search(boot_path_regex, show_boot_out)
        if match:
            boot_image = match.group(2)
        else:
            boot_image = None

        return {'sys': boot_image}

    def install_os(self, image_name, **vendor_specifics):
        # TODO: Validate this works
        self.set_boot_options(image_name)
        self.reboot()

    def open(self):
        if self._connected:
            try:
                self.native.find_prompt()
            except:
                self._connected = False

        if not self._connected:
            self.native = ConnectHandler(device_type='cisco_asa',
                                         ip=self.host,
                                         username=self.username,
                                         password=self.password,
                                         port=self.port,
                                         global_delay_factor=self.global_delay_factor,
                                         secret=self.secret,
                                         verbose=False)
            self._connected = True

    def reboot(self, timer=0):
        def handler():
            raise RebootSignal('Interrupting after reload')

        signal.signal(signal.SIGALRM, handler)
        signal.alarm(10)

        try:
            if timer > 0:
                first_response = self.show('reload in %d' % timer)
            else:
                first_response = self.show('reload')

            if 'System configuration' in first_response:
                self.native.send_command_timing('no')

            self.native.send_command_timing('\n')
        except RebootSignal:
            signal.alarm(0)

        signal.alarm(0)

    def rollback(self, rollback_to):
        raise NotImplementedError

    @property
    def running_config(self):
        if self._running_config is None:
            self._running_config = self.show('show running-config', expect=True)

        return self._running_config

    def save(self, filename='startup-config'):
        command = 'copy running-config %s' % filename
        # Changed to send_command_timing to not require a direct prompt return.
        self.native.send_command_timing(command)
        # If the user has enabled 'file prompt quiet' which dose not require any confirmation or feedback.
        # This will send return without requiring an OK.
        # Send a return to pass the [OK]? message - Increase delay_factor for looking for response.
        self.native.send_command_timing('\n', delay_factor=2)
        # Confirm that we have a valid prompt again before returning.
        self.native.find_prompt()

    def set_boot_options(self, image_name, **vendor_specifics):
        current_boot = self.show("show running-config | inc ^boot system ")

        if current_boot:
            current_images = current_boot.splitlines()
        else:
            current_images = []

        commands_to_exec = ["no {}".format(image) for image in current_images]
        commands_to_exec.append("boot system {}{}".format(vendor_specifics.get('image_location', ''), image_name))

        self.config_list(commands_to_exec)

    def show(self, command, expect=False, expect_string=''):
        self._enable()
        return self._send_command(command, expect=expect, expect_string=expect_string)

    def show_list(self, commands, raw_text=False):
        self._enable()

        responses = []
        entered_commands = []
        for command in commands:
            entered_commands.append(command)
            try:
                responses.append(self._send_command(command))
            except CommandError as e:
                raise CommandListError(entered_commands, command, e.cli_error_msg)

        return responses

    @property
    def startup_config(self):
        if self._startup_config is None:
            self._startup_config = self.show('show startup-config')

        return self._startup_config


class RebootSignal(NTCError):
    pass
