import os
import re

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))


def send_command(command, **kwargs):
    """

    TODO: Add docstring
    TODO: Check that no code is passing in extra args and remove **kwargs
    """
    command = command.replace(' ', '_')
    command = command.replace('/', '_')

    if command == '\n':
        command = 'return'

    path = os.path.join(CURRENT_DIR, 'send_command', command)

    if not os.path.isfile(path):
        return '% Error: mock error'

    with open(path, 'r') as f:
        response = f.read()

    return response


def send_command_expect(command, expect_string=None, **kwargs):
    """

    TODO: Add docstring
    TODO: Check that no code is passing in extra args and remove **kwargs
    """
    response = send_command(command)

    if expect_string:
        if not re.search(expect_string, response):
            raise IOError('Search pattern never detected.')

    return response
