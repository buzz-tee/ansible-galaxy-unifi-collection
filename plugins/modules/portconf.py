#!/usr/bin/env python

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


def get_networkconf_id(network, networks):
    network_filter = (lambda x: x.get('purpose', 'corporate') == 'corporate' and
                      x['name'] == network) if isinstance(network, str) else \
                     (lambda x: x.get('purpose', 'corporate') == 'corporate' and
                      x.get('vlan', None) == str(network))
    for n in networks:
        if network_filter(n):
            return n['_id']
    return None


def preprocess_portconf(unifi, portconf):
    site = unifi.get_site()
    if site is None:
        unifi.fail('Could not determine site for port profile {portconf}',
                   portconf=portconf['name'])
    portconf['site_id'] = site['_id']

    networkconfs = unifi.get_networkconfs()

    portconf['forward'] = 'disabled'

    # lookup native network
    native_networkconf = portconf.pop('native_networkconf', None)
    if native_networkconf:
        native_networkconf_id = get_networkconf_id(native_networkconf,
                                                   networkconfs)
        if native_networkconf_id is None:
            unifi.fail('Could not determine native network for port '
                       'profile {portconf}', portconf=portconf['name'])
        portconf['native_networkconf_id'] = native_networkconf_id
        portconf['forward'] = 'native'
    else:
        portconf['native_networkconf_id'] = ''

    # lookup tagged networks
    tagged_networkconfs = portconf.pop('tagged_networkconfs', None)
    if tagged_networkconfs:
        if tagged_networkconfs == 'all':
            # tagged_networkconf_ids = [n['_id'] for n in networkconfs
            #                           if n['purpose'] == 'corporate']
            # portconf['tagged_networkconf_ids'] = tagged_networkconf_ids
            portconf['forward'] = 'all'
        else:
            tagged_networkconf_ids = [
                get_networkconf_id(tagged_networkconf, networkconfs)
                for tagged_networkconf in tagged_networkconfs
            ]
            if None in tagged_networkconf_ids:
                unifi.fail('Could not determine all tagged networks for '
                           'port profile {portconf}', portconf=portconf['name'])
            if 'native_networkconf_id' in portconf and \
                    portconf['native_networkconf_id'] in tagged_networkconf_ids:
                tagged_networkconf_ids.remove(portconf['native_networkconf_id'])
            portconf['tagged_networkconf_ids'] = tagged_networkconf_ids
            portconf['forward'] = 'customize'
    else:
        portconf['tagged_networkconf_ids'] = []

    # update the PoE mode
    if 'poe_mode' not in portconf:
      UniFi.set_missing(portconf, 'poe_mode')


def main():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        portconf=dict(type='dict', required=True),
        **UniFi.DEFAULT_ARGS
    )

    # initialize UniFi helper object
    unifi = UniFi(argument_spec=module_args)

    # ensure that the input item will be reflected in the requested state
    # on the UniFi controller
    unifi.ensure_item('portconf',
                      preprocess_item=preprocess_portconf)

    # return the results
    unifi.exit()


if __name__ == '__main__':
    main()
