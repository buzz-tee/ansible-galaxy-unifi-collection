#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2020, Sebastian Gmeiner <sebastian@gmeiner.eu>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

DOCUMENTATION = r'''
---
module: unifi_wlanconf
version_added: "1.0"
author: "Sebastian Gmeiner (@bastig)"
short_description: Defines UniFi wlan configurations
description:
  - This modules provides an interface to define wlan configurations
    on a UniFi controller
extends_documentation_fragment: gmeiner.unifi
options:
  state:
    description:
      - Specifies if the wlan configuration needs to be added (default) or
        deleted
    required: false
    choices: ['present','absent','ignore']
  wlans:
    description:
      - A list of wlan configurations that will be submitted to the controller
    required: true
'''

EXAMPLES = r'''
- name: Create a test wlan
  gmeiner.unifi.unifi_wlanconf:
    state: present
    networks:
      - name: Test network 503
        domain_name: test.network.lan
        ip_subnet: 172.20.100.1/24
        dhcpd_enabled: false
        ipv6_interface_type: none
        dhcpdv6_enabled: false
        vlan: "503"
        vlan_enabled: true
        networkgroup: LAN
        purpose: corporate

- name: Change the VLAN id
  unifi_networkconf:
    state: present
    networks:
      - name: Test network 503
        vlan: "504"

- name: Remove a network
  unifi_networkconf:
    state: absent
    networks:
      - vlan: "504"

'''

RETURN = r'''
wlans:
    description: The resulting wlan configurations
    type: list
    returned: always
'''

from ansible_collections.gmeiner.unifi.plugins.module_utils.unifi import UniFi
from ansible_collections.gmeiner.unifi.plugins.module_utils.unifi_api import wlanconf, apgroups, networkconf

def preprocess_wlanconf(unifi: UniFi, wlans):

    ap_groups = unifi.send(api=apgroups)
    networkconfs = unifi.send(api=networkconf)

    for wlan in wlans:
        if 'ap_group_ids' in wlan or 'ap_groups' in wlan:
            ap_group_ids = []
            for ap_group_id in wlan.get('ap_group_ids', wlan.get('ap_groups', [])):
                ap_group = next(filter(lambda x: x['_id'] == ap_group_id or x['name'] == ap_group_id, ap_groups), None)
                ap_group_ids.append(ap_group['_id'] if ap_group else ap_group_id)
            wlan.pop('ap_groups', None)
            wlan['ap_group_ids'] = ap_group_ids
        else:
            wlan['ap_group_ids'] = [ap_group['_id'] for ap_group in filter(lambda x: x.get('attr_hidden_id') == 'default', ap_groups)]

        if 'networkconf_id' in wlan or 'networkconf' in wlan:
            network = wlan.get('networkconf_id', wlan.get('networkconf', None))
            if isinstance(network, str):
                network = next(filter(lambda networkconf: networkconf['_id'] == network or networkconf['name'] == network, networkconfs), None)
            elif isinstance(network, int):
                network = next(filter(lambda networkconf: networkconf['vlan'] == network, networkconfs), None)
            else:
                network = None

            wlan.pop('networkconf', None)
            if network:
                wlan['networkconf_id'] = network['_id']
            else:
                unifi.info(f'Could not identify network {wlan["networkconf_id"]}')

    return wlans

def main():
    # define available arguments/parameters a user can pass to the module
    module_args = {
        wlanconf.param_name: {
            'type': 'list', 'required': True
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
