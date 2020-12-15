"""Module for netmiko base driver."""
import warnings

from typing import Any, List, Union, Iterable, Callable, Mapping

from .base_device import BaseDevice, fix_docs
from pyntc.errors import CommandError, CommandListError


@fix_docs
class NetmikoBaseDevice(BaseDevice):
    """Netmiko Base Driver."""

    error_keywords = ["Error:", "% ", "Incorrect usage"]

    def __init__(self, host, username, password, device_type=None, **kwargs):
        super().__init__(host, username, password, device_type=device_type, **kwargs)

    def _command_output_has_error(self, command_response: str) -> bool:
        """
        Check response from device to see if an error was reported.

        Args:
            command_response (str): The response from sending a command to the device.

        Returns:
            bool: True when an error is detected in ``command_response``, else False.

        Example:
            >>> device = IOSDevice(**connection_args)
            >>> command = "show version"
            >>> command_response = "output from show version"
            >>> device._command_output_has_error(command_response)
            False
            >>> command = "invalid command"
            >>> command_response = "Incorrect Usage: invalid command"
            >>> device._command_output_has_error(command_resposne)
            True
            >>>
        """
        for error_keyword in self.error_keywords:
            if error_keyword in command_response:
                return True
        
        return False

    def _send_commands(
        self,
        netmiko_method: Callable[..., str],
        commands: Iterable[str],
        command_args: Mapping[str, Any],
    ) -> List[str]:
        """
        Send commands to device using ``netmiko_method``.

        Args:
            netmiko_method (netmiko.BaseConnection.send_command|netmiko.BaseConnection.send_config_set): The method to use to send the command(s) to the device.
            commands (list): The commands to send to the device.
            command_args (dict): The args to send when calling the netmiko method.
        
        Returns:
            list: The responses from sending ``commands`` to the device.

        Example:
            >>> device = IOSDevice(**connection_args)
            >>> netmiko_method = device.native.send_command
            >>> commands = ["show version", "show inventory"]
            >>> netmiko_args = {"delay_factor": 5}
            >>> device._send_commands(netmiko_method, commands, netmiko_args)
            ['...', '...']
            >>>
        """
        entered_commands = []
        command_responses = []
        try:
            for command in commands:
                entered_commands.append(command)
                command_response = netmiko_method(command, **command_args)
                command_responses.append(command_response)
                if self._command_output_has_error(command_response):
                    raise CommandError(command, command_response, entered_commands)
        except TypeError as err:
            raise TypeError(f"Netmiko Driver's {err.args[0]}")

        return command_responses

    def config(self, command: Union[str, Iterable[str]], **netmiko_args) -> Union[str, List[str]]:
        """
        Send config commands to device.

        By default, entering and exiting config mode is handled automatically.
        To disable entering and exiting config mode, pass `enter_config_mode` and `exit_config_mode` in ``**netmiko_args``.
        This supports all arguments supported by Netmiko's `send_config_set` method using ``netmiko_args``.
        This will send each command in ``command`` until either an Error is caught or all commands have been sent.

        Args:
            command (str|list): The command or commands to send to the device.
            **netmiko_args: Any argument supported by ``netmiko.ConnectHandler.send_config_set``.

        Returns:
            str: When ``command`` is a str, the config session input and ouput from sending ``command``.
            list: When ``command`` is a list, the config session input and ouput from sending ``command``.

        Raises:
            TypeError: When sending an argument in ``**netmiko_args`` that is not supported.
            CommandError: When ``command`` is a str and its results report an error.
            CommandListError: When ``command`` is a list and one of the commands reports an error.

        Example:
            >>> device = IOSDevice(**connection_args)
            >>> device.config("no service pad")
            'configure terminal\nEnter configuration commands, one per line.  End with CNTL/Z.\n'
            'host(config)#no service pad\nhost(config)#end\nhost#'
            >>> device.config(["interface Gig0/1", "description x-connect"])
            ['host(config)#interface Gig0/1\nhost(config-if)#, 'description x-connect\nhost(config-if)#']
            >>>
        """
        original_command_is_str = isinstance(command, str)

        if original_command_is_str:
            command = [command]

        original_exit_config_setting = netmiko_args.get("exit_config_mode")
        netmiko_args["exit_config_mode"] = False
        # Ignore None or invalid args passed for enter_config_mode
        if netmiko_args.get("enter_config_mode") is not False:
            self._enter_config()
            netmiko_args["enter_config_mode"] = False

        try:
            command_responses = self._send_commands(self.native.send_config_set, command, netmiko_args)
        # TODO: Remove this when deprecating CommandListError
        except CommandError as err:
            if not original_command_is_str:
                warnings.warn("This will raise CommandError in the future", FutureWarning)
                raise CommandListError(err.commands, err.command, err.cli_error_msg)
            else:
                raise err
        # Don't let exception prevent exiting config mode
        finally:
            # Ignore None or invalid args passed for exit_config_mode
            if original_exit_config_setting is not False:
                self.native.exit_config_mode()

        if original_command_is_str:
            return command_responses[0]

        return command_responses

    def config_list(self, commands: Iterable[str], **netmiko_args) -> List[str]:
        """
        DEPRECATED - Use the `config` method.

        Send config commands to device.

        By default, entering and exiting config mode is handled automatically.
        To disable entering and exiting config mode, pass `enter_config_mode` and `exit_config_mode` in ``**netmiko_args``.
        This supports all arguments supported by Netmiko's `send_config_set` method using ``netmiko_args``.

        Args:
            commands (list): The commands to send to the device.
            **netmiko_args: Any argument supported by ``netmiko.ConnectHandler.send_config_set``.

        Returns:
            list: Each command's input and ouput from sending the command in ``commands``.

        Raises:
            TypeError: When sending an argument in ``**netmiko_args`` that is not supported.
            CommandListError: When one of the commands reports an error on the device.

        Example:
            >>> device = IOSDevice(**connection_args)
            >>> device.config_list(["interface Gig0/1", "description x-connect"])
            ['host(config)#interface Gig0/1\nhost(config-if)#, 'description x-connect\nhost(config-if)#']
            >>>
        """
        warnings.warn("config_list() is deprecated; use config.", DeprecationWarning)
        return self.config(commands, **netmiko_args)

    def show(self, command: Union[str, Iterable[str]], expect_string: str = None, **netmiko_args) -> Union[str, List[str]]:
        """
        Send an operational command to the device.

        Args:
            command (str|list): The commands to send to the device.
            expect_string (str): The expected prompt after running the command.
            **netmiko_args: Any argument supported by ``netmiko.ConnectHandler.send_command``.

        Returns:
            str: When ``command`` is str, the data returned from the device.
            list: When ``command`` is list, the data returned from the device for each command.

        Raises:
            TypeError: When sending an argument in ``**netmiko_args`` that is not supported.
            CommandError: When ``command`` is str, and the returned data indicates the command failed.
            CommandListError: When ``command`` is list, and the return data indicates the command failed.

        Example:
            >>> device = AIREOSDevice(**connection_args)
            >>> sysinfo = device._send_command("show sysinfo")
            >>> print(sysinfo)
            Product Version.....8.2.170.0
            System Up Time......3 days 2 hrs 20 mins 30 sec
            ...
            >>> sysinfo = device._send_command(["show sysinfo"])
            >>> print(sysinfo[0])
            Product Version.....8.2.170.0
            System Up Time......3 days 2 hrs 20 mins 30 sec
            ...
            >>>
        """
        original_command_is_str = isinstance(command, str)

        if original_command_is_str:
            command = [command]

        if expect_string is not None:
            netmiko_args["expect_string"] = expect_string

        try:
            command_responses = self._send_commands(self.native.send_command, command, netmiko_args)
        # TODO: Remove this when deprecating CommandListError
        except CommandError as err:
            if not original_command_is_str:
                raise CommandListError(err.commands, err.command, err.cli_error_msg)
            else:
                raise err

        if original_command_is_str:
            return command_responses[0]

        return command_responses

    def show_list(self, commands: Iterable[str], **netmiko_args) -> List[str]:
        """
        DEPRECATED - Use the `show` method.
        Send operational commands to the device.

        Args:
            commands (list): The list of commands to send to the device.
            **netmiko_args: Any argument supported by ``netmiko.ConnectHandler.send_command``.

        Returns:
            list: The data returned from the device for all commands.

        Raises:
            TypeError: When sending an argument in ``**netmiko_args`` that is not supported.
            CommandListError: When the returned data indicates one of the commands failed.

        Example:
            >>> device = AIREOSDevice(**connection_args)
            >>> command_data = device._send_command(["show sysinfo", "show boot"])
            >>> print(command_data[0])
            Product Version.....8.2.170.0
            System Up Time......3 days 2 hrs 20 mins 30 sec
            ...
            >>> print(command_data[1])
            Primary Boot Image............................... 8.2.170.0 (default) (active)
            Backup Boot Image................................ 8.5.110.0
            >>>
        """
        warnings.warn("show_list() is deprecated; use show.", DeprecationWarning)
        return self.show(commands, **netmiko_args)
