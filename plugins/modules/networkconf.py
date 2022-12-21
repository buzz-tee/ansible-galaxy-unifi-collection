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
module: unifi_networkconf
version_added: "1.0"
author: "Sebastian Gmeiner (@bastig)"
short_description: Defines UniFi network configurations
description:
  - This modules provides an interface to define network configuration
    on a UniFi controller
extends_documentation_fragment: gmeiner.unifi
options:
  state:
    description:
      - Specifies if the network configuration needs to be added or deleted
    required: false
    choices: ['present','absent','ignore']
  networkconf:
    description:
      - The network configuration that will be submitted to the controller
    required: true
'''

EXAMPLES = r'''
- name: Create a test network
  unifi_networkconf:
    debug: true
    state: present
    networkconf:
      name: Test network 503
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
    debug: true
    state: present
    networkconf:
      name: Test network 503
      vlan: "504"

- name: Remove a network
  unifi_networkconf:
    debug: true
    state: absent
    networkconf:
      vlan: "504"

'''

RETURN = r'''
networkconf:
    description: The resulting network configurations (typically one)
    type: list
    returned: always
'''

from ansible_collections.gmeiner.unifi.plugins.module_utils.unifi import UniFi
from ansible_collections.gmeiner.unifi.plugins.module_utils.unifi_api import networkconf


def preprocess_networkconf(unifi, input):
    if 'vlan' in input:
        input['vlan_enabled'] = True
    if 'purpose' not in input:
        input['purpose'] = 'corporate'
    if 'networkgroup' not in input:
        input['networkgroup'] = 'LAN'
    return [input]
        

def compare_networkconf(net_a, net_b):
    if net_a.get('purpose', 'corporate') != net_b.get('purpose', 'corporate'):
        return False

    has_vlan_a = 'vlan_enabled' in net_a
    has_vlan_b = 'vlan_enabled' in net_b

    if has_vlan_a != has_vlan_b:
        return False

    if has_vlan_a and has_vlan_b:
        return (
            (not net_a['vlan_enabled'] and not net_b['vlan_enabled']) or
            (net_a['vlan_enabled'] and net_b['vlan_enabled'] and
             net_a['vlan'] == net_b['vlan'])
        )

    return net_a['name'].lower() == net_b['name'].lower()

def prepare_update_networkconf(input, existing):
  if 'ip_subnet' in input and \
      'dhcpd_start' not in input and \
      'dhcpd_stop' not in input and \
      input['ip_subnet'] != existing.get('ip_subnet'):
    dhcpd_start = 6
    dhcpd_stop = -1
    if 'ip_subnet' in existing and 'dhcpd_start' in existing:
      dhcpd_start = int(ip_address(existing['dhcpd_start'])) \
                    - int(ip_interface(existing['ip_subnet']).network.network_address)
    if 'ip_subnet' in existing and 'dhcpd_stop' in existing:
      dhcpd_stop = int(ip_address(existing['dhcpd_stop'])) \
                   - int(ip_interface(existing['ip_subnet']).network.broadcast_address)

    hosts = list(ip_interface(input['ip_subnet']).network.hosts())
    if dhcpd_start < len(hosts) + dhcpd_stop:
      input['dhcpd_start'] = format(hosts[dhcpd_start - 1])
      input['dhcpd_stop'] = format(hosts[dhcpd_stop])

def main():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        networkconf=dict(type='dict', required=True)
    )

    # initialize UniFi helper object
    unifi = UniFi(argument_spec=module_args)

    # ensure that the input item will be reflected in the requested state
    # on the UniFi controller
    unifi.ensure_item(networkconf,
                      preprocess_item=preprocess_networkconf,
                      compare_items=compare_networkconf,
                      prepare_update=prepare_update_networkconf)

    # return the results
    unifi.exit()


if __name__ == '__main__':
    main()
