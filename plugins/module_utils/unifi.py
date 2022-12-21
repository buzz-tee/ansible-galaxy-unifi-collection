#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2020, Sebastian Gmeiner <sebastian@gmeiner.eu>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from json import loads as json_loads, dumps as json_dumps
from traceback import format_exc
from os import environ

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection

from ansible_collections.gmeiner.unifi.plugins.module_utils.logging import \
    Logger

class UniFi(object):
    """
    Wraps all interactions with the UniFi controller REST API.

    :ivar __module: the Ansible module object
    :vartype __module: AnsibleModule
    :ivar __result: the result structure for the Ansible module operation
    :vartype __result: dict
    :ivar __connection: the Ansible connection object
    :vartype __connection: Connection
    :ivar __logger: logging facility, only used for log_levels > 0
    :vartype __logger: Logger
    :ivar error: shorthand to the same method of the logger
    :vartype error: function
    :ivar info: shorthand to the same method of the logger
    :vartype info: function
    :ivar debug: shorthand to the same method of the logger
    :vartype debug: function
    :ivar trace: shorthand to the same method of the logger
    :vartype trace: function
    """

    #: default parameters the UniFi Ansible module should accept
    DEFAULT_ARGS = dict(
        debug=dict(type='int', default=Logger.LEVEL_DISABLED.value),
        state=dict(choices=['present','absent','ignore'], default='present'),
        site=dict(type='str', required=False, default='default')
    )

    #: the default result structure
    __RESULT_STUB = {'changed': False}
    #: the key that identifies attributes which are missing
    __MISSING_KEY = '__missing__'

    #: how item types match to requests to the UniFi REST API
    __API_CONFIG = {
        'site': { 'request_kwargs': {
            'path': '/sites', 'path_prefix': '/api/', 'site': 'self',
            'proxy': 'network' } },
        'get_settings': { 'request_kwargs': {
            'path': '/get/setting', 'proxy': 'network' } },
        'settings': { 'request_kwargs': {
            'path': '/set/setting', 'proxy': 'network' },
            'getter': 'get_settings' },
        'device': { 'request_kwargs': { 'path': '/stat/device',
            'proxy': 'network' } },
        'networkconf': { 'request_kwargs': { 'path': '/rest/networkconf',
            'proxy': 'network' } },
        'portconf': { 'request_kwargs': { 'path': '/rest/portconf',
            'proxy': 'network' } },
        'ccode': { 'request_kwargs': { 'path': '/stat/ccode',
            'proxy': 'network' } },
    }

    @classmethod
    def set_missing(cls, item, attribute):
        """
        Class method that annotates a particular attribute of an item as missing
        in the sense that it is required to be absent in the object on the UniFi
        controller. Use pop_missing to remove these annotations.

        :param item: The item that should be annotated
        :type item: dict
        :param attribute: The attribute that should be marked missing
        :type attribute: str
        :returns: The list of attributes which have been marked missing so far
        :rtype: list
        """
        missing = item.get(UniFi.__MISSING_KEY, [])
        missing.append(attribute)
        item[UniFi.__MISSING_KEY] = missing
        return missing

    @classmethod
    def pop_missing(cls, item):
        """
        Class method that removes any previous annotations for attributes that
        have been marked missing from an item. Use this method before submitting
        an item via REST to the controller.

        :param item: The item where the annotations should be removed
        :type item: dict
        :returns: The list of attributes which have been marked missing
        :rtype: list
        """
        return item.pop(UniFi.__MISSING_KEY, [])


    def __init__(self, result=None, **module_specs):
        """
        Constructor for the UniFi API wrapper.

        :param result: A dictionary that may contain any data which will be used
            in the result that is returned by the Ansible module
        :type result: dict
        :param \\**module_specs: Any parameter that can be passed to the
            constructor of AnsibleModule
        """
        module_specs['supports_check_mode'] = True
        self.__module = AnsibleModule(**module_specs)

        self.__result = result if result is not None else UniFi.__RESULT_STUB
        self.__connection = None
        self.__logger = Logger(
            self.param('debug', Logger.LEVEL_DISABLED),
            environ.get('ANSIBLE_UNIFI_LOG_PATH')
        )
        self.error = self.__logger.error
        self.info = self.__logger.info
        self.debug = self.__logger.debug
        self.trace = self.__logger.trace

    def __generate_setter(self, name):
        """
        Factory for a setter method that allows to upload an object to the UniFi
        REST API. The generated method passes all keyword arguments on to the
        connection plugin.

        Example:

        * set_networkconf(_id=my_networkconf_id)
        * set_portconf(data=my_portconf)

        :param name: The name (or type) of a UniFi API object
        :type name: str
        :returns: A setter method
        :rtype: function
        """

        def __item_setter(name, **item_kwargs):
            """
            Inner method that implements the actual setter

            :param name: The name (or type) of a UniFi API object
            :type name: str
            :param \\**kwargs: Any parameter will be passed on to the connection
                plugin
            :returns: The resulting UniFi object
            :rtype: dict
            """
            result = self.send(**UniFi.__API_CONFIG[name]['request_kwargs'],
                               **item_kwargs)
            return result

        if name in UniFi.__API_CONFIG:
            return lambda **item_kwargs: __item_setter(name, **item_kwargs)

    def __generate_getter(self, name):
        """
        Factory for a getter method that allows the retrieval of an object via
        the UniFi REST API. Depending on the usage of singular or plural of the
        name parameter the generated method will return all objects or only a
        single object that passes the filter test.
        
        In case of a single item all keyword arguments passed to the getter will
        be used to filter the results. If multiple objects would match a filter,
        then only the first match will be returned.

        Example:
        * get_networkconfs()
        * get_networkconf(vlan=500)

        :param name: The name (or type) of a UniFi API object
        :type name: str
        :returns: A setter method
        :rtype: function
        """
        def __items_getter(name):
            """
            Inner method that implements the actual getter for a list of objects

            :param name: The name (or type) of a UniFi API object
            :type name: str
            :returns: The resulting list of UniFi object
            :rtype: list
            """
            items = self.send(**UniFi.__API_CONFIG[name]['request_kwargs'])
            return items
        
        def __item_getter(name, **filter_kwargs):
            """
            Inner method that implements the actual getter for a single object

            :param name: The name (or type) of a UniFi API object
            :type name: str
            :param \\**kwargs: All parameters will be used as filter
            :returns: The resulting UniFi object
            :rtype: dict
            """
            if not filter_kwargs:
                default = self.param(name, default=None)
                if default is not None:
                    filter_kwargs['name'] = default

            items = __items_getter(name)

            for item in items:
                match = True
                for key, value in filter_kwargs.items():
                    if item.get(key, None) != value and \
                            item.get(key, None) != str(value):
                        match = False
                        break
                if match:
                    return item

            return None

        if name in UniFi.__API_CONFIG:
            return lambda **filter_kwargs: __item_getter(name, **filter_kwargs)
        if name[-1] == 's' and name[:-1] in UniFi.__API_CONFIG:
            return lambda: __items_getter(name[:-1])
        return None

    def __getattribute__(self, name):
        """
        Override of the normal __getattribute__ method to return UniFi getter
        and setter methods.

        :param name: The name (or type) of a UniFi API object
        :type name: str
        :returns: the generated getter or setter or the appropriate attribute
        :rtype: any
        """
        if name.startswith('get_'):
            getter = self.__generate_getter(name[4:])
            if getter:
                return getter
        if name.startswith('set_'):
            setter = self.__generate_setter(name[4:])
            if setter:
                return setter
        
        return super(UniFi, self).__getattribute__(name)


    @property
    def connection(self):
        """
        Property to initialize the Ansible Connection object if needed and
        return the object
        """
        if self.__connection:
            return self.__connection

        if not self.__module._socket_path:
            raise ConnectionError('please use this module with a host httpapi '
                                  'connection of type "unifi"')

        self.__connection = Connection(self.__module._socket_path)
        self.__connection.set_logging(self.__logger.level.value,
                                      environ.get('ANSIBLE_UNIFI_LOG_PATH'))
        return self.__connection

    @property
    def result(self):
        """
        Gives access to the structure containing the result of the Ansible
        module operation
        """
        return self.__result

    @property
    def check_mode(self):
        """
        Shorthand property to identify if Ansible check mode is enabled
        """
        return self.__module.check_mode


    def has_param(self, key):
        """
        Shorthand method to check if a particular param has been passed to the
        Ansible module

        :param key: the name of the param
        :type key: str
        :returns: True if the Module param is available, else False
        :rtype: bool
        """
        return key in self.__module.params

    def param(self, key, fail_on_error=True, **kwargs):
        """
        Shorthand method to retrieve the value of an Ansible module parameter or
        an optional default value or fail if it is not present.

        :raises KeyError: if a required parameter is missing and fail_on_error
            was set to False

        :param key: the name of the param
        :type key: str
        :param fail_on_error: if True, then the Module will fail if the param
            is missing and no default value is provided (this behavior is
            default) - otherwise a KeyError is thrown and can be handled by the
            calling code
        :type fail_on_error: bool
        :param default: an optional default value that is returned if the param
            is missing, in this case the method will never fail
        :type default: any
        :returns: the value of the Ansible module parameter
        :rtype: any
        """
        if key in self.__module.params:
            return self.__module.params[key]
        if 'default' in kwargs:
            return kwargs['default']
        if fail_on_error:
            self.fail('No such module parameter: {key}', key=key)
        else:
            raise KeyError('No such module parameter: {key}'.format(key=key))

    def exit(self):
        """
        This method concludes the Ansible module operation and provides the
        required clean-up of new-style Ansible modules
        """
        if self.__logger.enabled:
            self.__result['logs'] = Logger.join(
                self.connection.get_logs(), self.__logger.logs)

        self.__module.exit_json(**self.__result)
    
    def fail(self, message, **message_kwargs):
        """
        This method concludes the Ansible module operation with an error and
        provides the required clean-up of new-style Ansible modules.

        :param message: an error message
        :type message: str
        :param \\**message_kwargs: format parameters for the error message
        :type \\**message_kwargs: any
        """
        if self.__logger.enabled:
            self.__result['logs'] = Logger.join(
                self.connection.get_logs(), self.__logger.logs)

        try:
            message = message.format(**message_kwargs)
        except:
            pass
        self.__module.fail_json(msg=message, **self.__result)

    def update_item(self, input_item, existing_item, require_absent, preprocess_update):
        """
        Convenience method to verify if an (existing) item matches another
        (input) item by all attributes of the (input) item and update the former
        if needed. The method also pays attention to attributes that may not
        occur on the (existing) item and removes those if present.

        :param input_item: the item which contains the desired state
        :type input_item: dict
        :param existing_item: the existing item which should be verified
        :type existing_item: dict
        :param require_absent: the names of attributes which may not occur on
            the existing item
        :type require_absent: list
        :param preprocess_update: perform operations to prepare input item
        :returns: True if the existing item was changed, else False
        :rtype: bool
        """
        changed = False

        if preprocess_update:
            preprocess_update(input_item, existing_item)

        for key, value in input_item.items():
            if key not in existing_item or existing_item[key] != value:
                changed = True
                self.debug('Field {key} differs on controller: '
                           'expected {expected} but got {value}',
                           key=key, expected=value,
                           value=existing_item.get(key, '<missing>'))
                existing_item[key] = value
        for key in require_absent:
            if key in existing_item:
                changed = True
                self.debug('Field {key} exists on controller '
                           'but it should be absent', key=key)
                del existing_item[key]
        return changed


    def update_list(self, input_item, existing_items, state, compare=None, preprocess_update=None):
        """
        Convenience method that updates a list of (existing) items to contain an
        (input) item in a desired state.

        Valid states include the Ansible states 'present' and 'absent' as well
        as 'ignore' or None (only lists matching items), True (same as present),
        False (same as absent)

        :raises ValueError: if not no valid (Ansible) state is passed

        :param input_item: the item which contains the desired state
        :type input_item: dict
        :param existing_items: the existing items which should be verified
        :type existing_items: list
        :param state: a valid (Ansible) state
        :type state: str
        :param compare: an optional function that accepts two items as
            parameters and checks if an existing item matches the input item, if
            ommited items will be compared by name (case invariant)
        :type compare: function

        :returns:
            - ignored_items (:py:class:`list`) - the list of ignored items
              (those which only match but should neither be changed nor deleted)
            - changed_items (:py:class:`list`) - the list items that should be
              changed or created
            - deleted_items (:py:class:`list`) - the list of _id values of all
              the items that should be deleted
        """
        def _do_compare(existing_item, compare):
            """
            Inner shorthand method which either calls the passed compare
            function or compares the passed existing item to the input item
            based on the name attributes. The method is used to determine which
            existing item (if any) from a list of all existing items should be
            affected by the surrounding update method.

            Note: the input_item does not change throughout that process and is
            retrieved from the scope of the surrounding method.

            :param existing_item: the existing item that should be matched
                against the input item
            :type existing_item: dict
            :param compare: a custom compare function which accepts two items
                and returns True if the check succeeds
            :type compare: function:
            :returns: the result of the comparison, True if the input item
                matches the existing item
            :rtype: bool
            """
            if compare:
                return compare(input_item, existing_item)
            else:
                return ('name' in input_item and 'name' in existing_item and
                        input_item['name'].lower() == existing_item['name'].lower())
        
        matching_items = list(
            filter(lambda x: _do_compare(x, compare), existing_items)
        )
        if not matching_items and compare is not None:
            # second attempt, compare by name only
            self.trace('No matches, fallback to comparison by name')
            matching_items = list(
                filter(lambda x: _do_compare(x, None), existing_items)
            )
        self.debug('Got {count} match(es) for input item',
                   count=len(matching_items))

        ignored_items = []
        changed_items = []
        deleted_items = []

        if state in ['ignore', None]:
            for matching_item in matching_items:
                ignored_items.append(matching_item)

        elif state in ['present', True]:
            require_absent = UniFi.pop_missing(input_item)

            if matching_items:
                for matching_item in matching_items:
                    changed = self.update_item(input_item, matching_item,
                                               require_absent, preprocess_update)
            
                    if changed:
                        changed_items.append(matching_item)
            else:
                changed_items.append(input_item)

        elif state in ['absent', False]:
            for matching_item in matching_items:
                deleted_items.append(matching_item['_id'])

        else:
            raise ValueError('Got unexpected value for requested state: {state}'
                             .format(state=state))

        return ignored_items, changed_items, deleted_items


    def ensure_item(self, item_type, preprocess_item=None, compare=None, preprocess_update=None):
        """
        Convenience method to ensure the provided item state is reflected by the
        corresponding object on the UniFi controller.

        The item is refered to by the item_type which in turns will be used to

        - lookup the input item from the Ansible module parameter with the same
          name as the item_type
        - lookup the API config based on item_type as key
        - store the resulting objects in a field of the result object under
          item_type as key

        :param item_type: the name of the item type
        :type item_type: str
        :param preprocess_item: optional callback function that accepts this
            object and the item that was retrieved from the Ansible module
            paramters to preprocess the item for further operation
        :type preprocess_item: function
        :param compare: optional callback function that compares two items based
            on custom attributes, if ommitted the default comparison checks two
            items based on their name attributes (case invariant)
        :type compare: function
        """
        def _set_result(result_item):
            """
            Inner shorthand method which appends a resulting item to the
            appropriate list in the result structure. Creates the list if it is
            not already present

            :param result_item: the result item that should be appended to the
                result list
            :type result_item: dict:
            """
            result_data = self.__result.get(item_type, [])
            if isinstance(result_item, list):
                result_data.extend(result_item)
            else:
                result_data.append(result_item)
            self.__result[item_type] = result_data

        try:
            item = self.param(item_type)
            if preprocess_item:
                preprocess_item(self, item)
            
            existing_items = self.send(item_type=item_type)

            ignored_items, changed_items, deleted_items = self.update_list(
                item, existing_items, self.param('state'), compare=compare,
                preprocess_update=preprocess_update)
            
            changed = False

            for item in ignored_items:
                _set_result(item)
            for item in changed_items:
                if not self.check_mode:
                    item = self.send(item_type=item_type, data=item)
                    changed = True
                _set_result(item)
            for item in deleted_items:
                if not self.check_mode:
                    self.send(item_type=item_type, _id=item)
                    changed_items = True
                _set_result(item)

            self.__result['changed'] = (changed or self.__result['changed'])

        except Exception as e:
            if self.__logger.enabled:
                self.__result['trace'] = format_exc()
            self.fail(str(e))

    def send(self, path=None, item_type=None, site=None, result_path=['data'], **kwargs):
        """
        Convenience method that sends a request to the UniFi REST API.

        Note about paths: paths are assembled by the UniFi connection plugin and
        the path here usually contains the one or two last path elements, e.g.
        /rest/networkconf

        :raises KeyError: if the UniFi response object doesn't match the
            expected structure

        :param path: the path of the REST endpoint
        :type path: str
        :param site: the optional name of the site, if ommitted will be taken
            from the Ansible module param
        :type site: str
        :param result_path: a list of path elements to navigate the response
            from the UniFi REST API (typically contains the actual response data
            under the attribute 'data' of the response object)
        :type result_path: list
        :param \\**kwargs: any further keyword arguments will be passed on to
            the UniFi connection plugin
        :type \\**kwargs: any
        :returns: the UniFi response object
        :rtype: dict
        """

        if not path and item_type:
            if not item_type in UniFi.__API_CONFIG:
                self.fail('No API configuration found for type {item}',
                          item=item_type)

            request_kwargs = UniFi.__API_CONFIG[item_type]['request_kwargs']

            for key, value in request_kwargs.items():
                if key not in kwargs:
                    kwargs[key] = value
            path = kwargs.pop('path')

        if not site:
            site = self.param('site', default='default')

        result_item = self.connection.send_request(path=path,
                                                   site=site,
                                                   **kwargs)
        for attr in result_path:
            if attr not in result_item:
                raise KeyError('UniFi API response does not include {path}, '
                               'misses attribute {attr}'
                               .format(path=', '.join(result_path), attr=attr))
            result_item = result_item.get(attr, None)
        return result_item
