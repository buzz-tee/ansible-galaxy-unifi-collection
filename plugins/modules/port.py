#!/usr/bin/env python

# Copyright: (c) 2020, Sebastian Gmeiner <sebastian@gmeiner.eu>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

DOCUMENTATION = r'''
---
module: unifi_port
version_added: "1.0"
author: "Sebastian Gmeiner (@bastig)"
short_description: Assigns a port profile to a UniFi device port
description:
  - This modules provides an interface to assign a switch port profile
    to a port on a UniFi device
extends_documentation_fragment: gmeiner.unifi
options:
  state:
    description:
      - Specifies if the switchport profile needs to be added or deleted
    required: false
    choices: ['present','absent','ignore']
  port:
    description:
      - The port where the profile will be assigned
    required: true
  device:
    description:
      - The device where the port is located
    required: true
  portconf:
    description:
      - The switch port profile that will be assigned to the port
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


def get_port_idx(port, device):
    port_idx = None
    port_name = None
    if isinstance(port, int) or (isinstance(port, str) and port.isnumeric()):
        port_idx = int(port)
    else:
        port_name = port

    for device_port in device['port_table']:
        if device_port['port_idx'] == port_idx or \
                device_port['name'] == port_name:
            return device_port['port_idx']

def update_port_overrides(unifi, port_overrides, port_idx):
    port = unifi.param('override')
    port['port_idx'] = port_idx

    portconf = unifi.param('portconf', default=None)
    if portconf is not None:
        portconf = unifi.get_portconf(name=portconf)
        if not portconf:
            unifi.fail('Could not find portconf {portconf}',
                       portconf=unifi.param('portconf'))
        port['portconf_id'] = portconf['_id']

    require_absent = []

    for key in ['name', 'autoneg', 'full_duplex', 'poe_mode', 'speed']:
        if key not in port:
            require_absent.append(key)

    found = False
    change_required = False
    remove_items = []
    for port_override in port_overrides:
        if port_override['port_idx'] == port_idx:
            found = True
            if unifi.param('state') == 'present':
                change_required = UniFi.update_item(port, port_override,
                                                    require_absent,
                                                    log=unifi.log)
            elif unifi.param('state') == 'absent':
                remove_items.append(port_override)
                change_required = True
    
    if unifi.param('state') == 'present':
        if not found:
            port_overrides.append(port)
            change_required = True
    else:
        for item in remove_items:
            port_overrides.remove(item)

    return change_required

def main():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        port=dict(required=True),
        device=dict(type='str', required=True),
        portconf=dict(type='str'),
        override=dict(type='dict', required=False, default={}),

        **UniFi.DEFAULT_ARGS
    )
    required_if = [
        ('state', 'present', ('portconf',))
    ]

    # initialize UniFi helper object
    unifi = UniFi(argument_spec=module_args,
                  required_if=required_if)

    device = unifi.get_device()
    port_idx = get_port_idx(unifi.param('port'), device)
    port_overrides = device['port_overrides']
    change_required = update_port_overrides(unifi, port_overrides, port_idx)
    if change_required and not unifi.check_mode:
        unifi.send('/rest/device', _id=device['_id'], data={
            'port_overrides': port_overrides
        })
        unifi.result['changed'] = True
    unifi.result['ports'] = port_overrides

    # return the results
    unifi.exit()


if __name__ == '__main__':
    main()
