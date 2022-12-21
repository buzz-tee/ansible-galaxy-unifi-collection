#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2020, Sebastian Gmeiner <sebastian@gmeiner.eu>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

class ApiDescriptor(object):

    def __init__(self, param_name, request_kwargs, id_extractor=None, getter=None, result_path=None):
        self.__param_name = param_name
        self.__request_kwargs = request_kwargs
        self.__id_extractor = id_extractor
        self.__getter = getter
        self.__result_path = result_path

    @property
    def param_name(self):
        return self.__param_name

    @property
    def request_kwargs(self):
        return self.__request_kwargs

    def extract_id(self, item):
        from ansible_collections.gmeiner.unifi.plugins.module_utils.unifi import UniFi

        id_extractor = self.__id_extractor or UniFi.default_id_extractor
        return id_extractor(item)

    @property
    def getter(self):
        return self.__getter or self

    @property
    def result_path(self):
        return self.__result_path if self.__result_path is not None else ['data']

site = ApiDescriptor(
            param_name='site',
            request_kwargs={
                'path': '/sites',
                'path_prefix': '/api/',
                'site': 'self',
                'proxy': 'network'
            }
        )

__key_id_extractor = lambda x: x['key']
settings = ApiDescriptor(
            param_name='settings',
            request_kwargs={
                'path': '/set/setting',
                'proxy': 'network'
            },
            id_extractor=__key_id_extractor,
            getter=ApiDescriptor(
                param_name='settings',
                request_kwargs={
                    'path': '/get/setting',
                    'proxy': 'network'
                },
                id_extractor=__key_id_extractor
            )
        )
    
device = ApiDescriptor(
            param_name='device',
            request_kwargs={
                'path': '/stat/device',
                'proxy': 'network'
            }
        )

networkconf = ApiDescriptor(
            param_name='networkconf',
            request_kwargs={
                'path': '/rest/networkconf',
                'proxy': 'network'
            }
        )

apgroups = ApiDescriptor(
            param_name='apgroups',
            request_kwargs={
                'path_prefix': '/v2/api/site/',
                'path': '/apgroups'
            },
            result_path=[]
        )

wlanconf = ApiDescriptor(
            param_name='wlanconf',
            request_kwargs={
                'path': '/rest/wlanconf',
                'proxy': 'network'
            }
        )

portconf = ApiDescriptor(
            param_name='portconf',
            request_kwargs={
                'path': '/rest/portconf',
                'proxy': 'network'
            }
        )
    
ccode = ApiDescriptor(
            param_name='ccode',
            request_kwargs={
                'path': '/stat/ccode',
                'proxy': 'network'
            }
        )
