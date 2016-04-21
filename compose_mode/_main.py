#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import os

from compose import config
from compose.config import serialize, environment
import yaml

import compose_mode


DEFAULT_MODES_FILE = 'compose-modes.yml'
STATE_FILE = '.compose-mode.state'


def _search_up(filename, stop_at_git=True):
    prefix = ''
    while True:
        path = os.path.join(prefix, filename)

        if os.path.isfile(path):
            return path
        elif prefix == '/' or (os.path.isdir(os.path.join(prefix, '.git')) and
                               stop_at_git):
            # insisting that .git is a dir means we will traverse out of git
            # submodules, a behaviour I desire
            raise IOError('{} not found here or any directory above here'
                          .format(filename))
        prefix = os.path.realpath(os.path.join(prefix, '..'))


def get_modes(modes_filename=DEFAULT_MODES_FILE):
    modes_path = _search_up(modes_filename)
    with open(modes_path, 'r') as modes_file:
        return os.path.realpath(modes_path), yaml.safe_load(modes_file)


def fix_restart(restart_config):
    """ Fix output of docker-compose.

    docker-compose's "show config" mechanism--the internals of which we use to
    merge configs--doesn't actually return valid configurations for the
    "restart" property as they convert it to an internal representation which
    they then forget to convert back to the yaml format. We do that by hand
    here.
    """
    mrc = restart_config['MaximumRetryCount']
    name = restart_config['Name']

    if name in ['always', 'unless-stopped', 'no']:
        return name
    else:
        return '{}:{}'.format(name, mrc)


def fix_restarts(input_yaml):
    """ Run `fix_restart` on all found configurations.

    See docs for `fix_restart` for why.
    """
    config_dict = yaml.safe_load(input_yaml)
    for service in config_dict['services'].itervalues():
        try:
            service['restart'] = fix_restart(service['restart'])
        except KeyError:
            pass
    return yaml.safe_dump(config_dict,
                          default_flow_style=False,
                          indent=4,
                          width=80)


def get_current_mode():
    try:
        with open(STATE_FILE, 'r') as state_file:
            return state_file.read().strip()
    except IOError:
        return None


def set_current_mode(mode):
    with open(STATE_FILE, 'w') as state_file:
        state_file.write(mode)


def set_mode(output, selected_mode, modes_file):
    modes_path, modes = get_modes(modes_file)

    containing_dir = os.path.dirname(modes_path)

    # Easier than trying to join the paths up properly
    os.chdir(containing_dir)

    current_mode = get_current_mode()

    if selected_mode == 'list':
        for mode in sorted(modes.iterkeys()):
            if mode == current_mode:
                print mode + ' *'
            else:
                print mode
        print '\n'.join(sorted(modes.iterkeys()))
        return

    # project_name = os.path.basename(containing_dir)
    # entries in `modes` are each a list of filenames
    config_details = config.find(
        containing_dir,
        modes[selected_mode],
        environment.Environment.from_env_file(containing_dir)
    )
    loaded_config = config.load(config_details)

    broken_serialized = serialize.serialize_config(loaded_config)
    fixed_serialized = fix_restarts(broken_serialized)

    with open(output, 'w') as output_file:
        output_file.write(fixed_serialized)
    set_current_mode(selected_mode)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', '-V', action='version',
                        version='%(prog)s {}'.format(compose_mode.__version__))
    parser.add_argument('--modes-file', default=DEFAULT_MODES_FILE,
                        help='The name or path of the modes file, will search'
                             ' in containing directories if a relative name is'
                             ' given')
    parser.add_argument(
        '--output', default='docker-compose.yml',
        help='The file to output the effective configuration to')

    parser.add_argument('mode', nargs='?', default='list',
                        help='The mode to switch to, leave blank or set to '
                             '"list" to list available modes.')

    args = parser.parse_args()

    set_mode(args.output, args.mode, args.modes_file)


if __name__ == '__main__':
    main()
