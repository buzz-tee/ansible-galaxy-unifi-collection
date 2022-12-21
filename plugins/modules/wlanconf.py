#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2020, Sebastian Gmeiner <sebastian@gmeiner.eu>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

DOCUMENTATION = r'''
---
module: unifi_portconf
version_added: "1.0"
author: "Sebastian Gmeiner (@bastig)"
short_description: Defines UniFi switch port profiles
description:
  - This modules provides an interface to define switch port profiles
    on a UniFi controller
extends_documentation_fragment: gmeiner.unifi
options:
  state:
    description:
      - Specifies if the switchport profile needs to be added or deleted
    required: false
    choices: ['present','absent','ignore']
  portconf:
    description:
      - The switch port profile that will be submitted to the controller
    required: true
'''

EXAMPLES = r'''
- name: Create custom trunk
  unifi_portconf:
    state: present
    portconf:
      name: DMZ networks trunk
      native_networkconf:
      tagged_networkconfs:
        - 110
        - Test 502 network
      poe_mode: unchanged

- name: Create access port profile
  unifi_portconf:
    state: present
    portconf:
      name: LAN access with PoE
      native_networkconf: 501
      tagged_networkconfs:
      poe_mode: on

- name: Delete a port profile
  unifi_portconf:
    state: absent
    portconf:
      name: DMZ networks trunk
'''

RETURN = r'''
portconf:
    description: The resulting switch port profile (typically one)
    type: list
    returned: always
'''

from ansible_collections.gmeiner.unifi.plugins.module_utils.unifi import UniFi
from ansible_collections.gmeiner.unifi.plugins.module_utils.unifi_api import wlanconf, apgroups

def preprocess_wlanconf(unifi: UniFi, input):
    # TODO resolve ap_group_ids
    # if ap_group_ids is missing on input -> use attr_hidden_id = default
    # else for each resolve to _id of apgroup entry

    ap_groups = unifi.send(api=apgroups)
    unifi.debug(f'Got AP Groups {ap_groups}')

    return [input]

def main():
    # define available arguments/parameters a user can pass to the module
    module_args = {
        wlanconf.param_name: {
            'type': 'dict', 'required':True
        }
    }

    # initialize UniFi helper object
    unifi = UniFi(argument_spec=module_args)

    # ensure that the input item will be reflected in the requested state
    # on the UniFi controller
    unifi.ensure_item(wlanconf,
                      preprocess_item=preprocess_wlanconf)

    # return the results
    unifi.exit()

if __name__ == '__main__':
    main()
