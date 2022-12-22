#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2020, Sebastian Gmeiner <sebastian@gmeiner.eu>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)

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
from ansible_collections.gmeiner.unifi.plugins.module_utils.unifi_api import settings, ccode


def preprocess_settings(unifi: UniFi, settings):
    result = []
    for key, value in settings.items():
        value['key'] = key

        if key == 'country' and 'code' in value:
            ccodes = unifi.send(api=ccode)
            code = next(filter(lambda x: x.get('key', None)
                        == value['code'], ccodes), {}).get('code')
            if code is None:
                raise Exception('No such country code: ' + value)
            value['code'] = code

        result.append(value)
    return result

def compare_settings(setting_a, setting_b):
    return 'key' in setting_a and 'key' in setting_b and setting_a['key'] == setting_b['key']


def main():
    # define available arguments/parameters a user can pass to the module
    module_args = {
        settings.param_name: {
            'type': 'dict', 'required': True
        }
    }

    # initialize UniFi helper object
    unifi = UniFi(argument_spec=module_args)

    unifi.ensure_item(settings,
                      preprocess_item=preprocess_settings,
                      compare_items=compare_settings)

    # return the results
    unifi.exit()


if __name__ == '__main__':
    main()
