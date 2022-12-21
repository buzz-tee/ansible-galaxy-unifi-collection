#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2020, Sebastian Gmeiner <sebastian@gmeiner.eu>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
from ipaddress import ip_interface, ip_address
from itertools import islice

__metaclass__ = type

DOCUMENTATION = r'''
---
module: unifi_settings
version_added: "1.0"
author: "Sebastian Gmeiner (@bastig)"
short_description: Defines UniFi global settings
description:
  - This modules provides an interface to define global settings
    on a UniFi controller
extends_documentation_fragment: gmeiner.unifi
options:
  state:
    description:
      - Specifies if the configuration should be applied to the key or deleted
    required: false
    choices: ['present','absent','ignore']
  setting:
    description:
      - The global settings that will be submitted to the controller
    required: true
'''

EXAMPLES = r'''

'''

RETURN = r'''
settings:
    description: The resulting global settings (typically one)
    type: list
    returned: always
'''

from ansible_collections.gmeiner.unifi.plugins.module_utils.unifi import UniFi


def preprocess_setting(unifi, setting):
    pass

def compare_setting(setting_a, setting_b):
    pass

def preprocess_update_setting(input, existing):
    pass

def main():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        settings=dict(type='dict', required=True),
        **UniFi.DEFAULT_ARGS
    )

    # initialize UniFi helper object
    unifi = UniFi(argument_spec=module_args)

    unifi.result['changed'] = False

    state = unifi.param('state')
    settings = unifi.send(item_type='get_settings')
    input_settings = unifi.param('settings', True)
    for section, section_settings in input_settings.items():
      setting = next(filter(lambda x: x.get('key') == section, settings), None)
      
      changed = False
      for key, value in section_settings.items():
        if state == 'present' and section == 'country' and key == 'code':
          ccodes = unifi.send(item_type='ccode')
          code = next(filter(lambda x: x.get('key', None) == value, ccodes), {}).get('code')
          if code is None:
            raise Exception('No such country code: ' + value)
          value = code

        if state == 'present' and setting.get(key) != value:
          setting[key] = value
          changed = True
        elif state == 'absent' and key in setting:
          setting[key] = ''
          changed = True

      if changed:
        setting = unifi.send(item_type='settings', data=setting, _id=section)
        unifi.result['changed'] = True

      result = unifi.result.get('settings', [])
      if isinstance(setting, list):
        result.extend(setting)
      else:
        result.append(setting)
      unifi.result['settings'] = result

    # return the results
    unifi.exit()


if __name__ == '__main__':
    main()
