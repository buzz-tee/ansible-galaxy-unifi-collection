#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2020, Sebastian Gmeiner <sebastian@gmeiner.eu>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from traceback import format_exc
from os import environ

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection

from ansible_collections.gmeiner.unifi.plugins.module_utils.unifi_api import ApiDescriptor
from ansible_collections.gmeiner.unifi.plugins.module_utils.logging import \
    Logger, LogLevel



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
        debug=dict(type='str', default=LogLevel.DISABLED.name),
        state=dict(choices=['present','absent','ignore'], default='present'),
        site=dict(type='str', required=False, default='default')
    )

    #: the default result structure
    __RESULT_STUB = {'changed': False}
    #: the key that identifies attributes which are missing
    __MISSING_KEY = '__missing__'

    @classmethod
    def default_id_extractor(cls, item):
        return item['_id']

    @classmethod
    def name_comparator(cls, item_a, item_b):
        """
        Shorthand method which compares two items by their names

        :param item_a: the first item
        :type item_a: dict:
        'param item_b: the second item
        :type item_b: dict:

        :rtype: bool
        """
        return 'name' in item_a and 'name' in item_b and \
            item_a['name'].lower() == item_b['name'].lower()

    @classmethod
    def build_id_comparator(cls, id_extractor):
        """
        Shorthand method which compares two items by their id's

        :param item_a: the first item
        :type item_a: dict:
        'param item_b: the second item
        :type item_b: dict:

        :rtype: bool
        """
        def id_comparator(item_a, item_b):
            try:
                return id_extractor(item_a) == id_extractor(item_b)
            except:
                return False

        return id_comparator
    

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
        argument_spec = module_specs.get('argument_spec', {})
        for key, value in UniFi.DEFAULT_ARGS.items():
            if key not in argument_spec:
                argument_spec[key] = value
        module_specs['argument_spec'] = argument_spec

        self.__module = AnsibleModule(**module_specs)

        self.__result = result if result is not None else UniFi.__RESULT_STUB
        self.__connection = None
        self.__logger = Logger(
            LogLevel[self.param('debug')],
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

    def update_item(self, api: ApiDescriptor, input_item, existing_item, require_absent, prepare_update):
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

        if prepare_update:
            prepare_update(input_item, existing_item)

        for key, value in input_item.items():
            if key not in existing_item or existing_item[key] != value:
                changed = True
                self.debug('Field {id}.{key} ({type}) differs on controller: '
                           'expected {expected} but got {value}',
                           id=api.extract_id(input_item), type=api.param_name,
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


    def ensure_item(self, api: ApiDescriptor, preprocess_item=None, compare_items=None, prepare_update=None):
        """
        Convenience method to ensure the provided item state is reflected by the
        corresponding object on the UniFi controller.

        The item is refered to by the API descriptor which in turns will be
        used to

        - lookup the input item from the Ansible module parameter according to
          information from the API descriptor
        - store the resulting objects in a field of the result object under
          item_type as key

        :param api: the API descriptor
        :type api: ApiDescriptor
        :param preprocess_item: optional callback function that accepts this
            object and the item that was retrieved from the Ansible module
            paramters to preprocess the item for further operation
        :type preprocess_item: function
        :param compare_items: optional callback function that compares two items
            based on custom attributes, if ommitted the default comparison checks
            two items based on their name attributes (case invariant)
        :type compare: function
        """

        def _set_result(result_item, changed):
            """
            Inner shorthand method which appends a resulting item to the
            appropriate list in the result structure. Creates the list if it is
            not already present

            :param result_item: the result item that should be appended to the
                result list
            :type result_item: dict:
            :param changed: indicates that the item was changed
            :type changed: bool:
            """
            result_data = self.__result.get(api.param_name, [])
            if isinstance(result_item, list):
                result_data.extend(result_item)
            else:
                result_data.append(result_item)
            self.__result[api.param_name] = result_data
            self.__result['changed'] = (changed or self.__result.get('changed', False))


        def _state_ignore(input_item, matching_items):
            """
            Handles item operation for state 'ignore'.
            In this case it does nothing and adds the matching items to the
            result

            :param input_item: the input item
            :type input_item: dict:
            :param matching_items: the items which will be affected by input_item
            :type matching_items: list:
            """
            for matching_item in matching_items:
                _set_result(matching_item, False)
        
        def _state_present(input_item, matching_items):
            """
            Handles item operation for state 'present'.
            In this case it ensures an existing item is updated or a new object
            is created on the controller which represents the input item

            :param input_item: the input item
            :type input_item: dict:
            :param matching_items: the items which will be affected by input_item
            :type matching_items: list:
            """
            require_absent = UniFi.pop_missing(input_item)

            if matching_items:
                for matching_item in matching_items:
                    changed = self.update_item(api, input_item, matching_item,
                                            require_absent, prepare_update)
            
                    if changed and not self.check_mode:
                        matching_item = self.send(api=api, data=matching_item,
                                                _id=api.extract_id(matching_item))
                    _set_result(matching_item, changed and not self.check_mode)
            else:
                if not self.check_mode:
                    input_item = self.send(api=api, data=input_item)
                _set_result(input_item, not self.check_mode)
        
        def _state_absent(input_item, matching_items):
            """
            Handles item operation for state 'absent'.
            In this case it ensures that no configuration exists on the
            controller which matches the input item

            :param input_item: the input item
            :type input_item: dict:
            :param matching_items: the items which will be affected by input_item
            :type matching_items: list:
            """
            for matching_item in matching_items:
                if not self.check_mode:
                    self.send(api=api, _id=api.extract_id(matching_item))
                _set_result(matching_item, not self.check_mode)

        try:
            match self.param('state'):
                case 'ignore' | None:
                    state_handler = _state_ignore
                case 'present' | True:
                    state_handler = _state_present
                case 'absent' | False:
                    state_handler = _state_absent
                case other_state:
                    raise ValueError(f'Got unexpected value for requested state: {other_state}')

            existing_items = self.send(api=api.getter)

            if preprocess_item:
                input_items = preprocess_item(self, self.param(api.param_name))
                if not isinstance(input_items, list):
                    input_items = [input_items]
            else:
                input_items = [self.param(api.param_name)]

            for input_item in input_items:
                self.trace(f'Preparing input item {input_item}')
                comparators = [UniFi.name_comparator, UniFi.build_id_comparator(api.extract_id)]
                if compare_items:
                    comparators.append(compare_items)

                matching_items = []
                while not matching_items and comparators:
                    comparator = comparators.pop()
                    self.trace(f'Comparing items using {comparator}')
                    matching_items = list(filter(lambda existing_item: 
                        comparator(input_item, existing_item), existing_items))

                self.trace('Processing input item')
                state_handler(input_item, matching_items)

        except Exception as e:
            if self.__logger.enabled:
                self.__result['trace'] = format_exc()
            self.fail(str(e))

    def send(self, api: ApiDescriptor, site=None, result_path=['data'], **kwargs):
        """
        Convenience method that sends a request to the UniFi REST API.

        Note about paths: paths are assembled by the UniFi connection plugin and
        the path here usually contains the one or two last path elements, e.g.
        /rest/networkconf

        :raises KeyError: if the UniFi response object doesn't match the
            expected structure

        :param api: the API descriptor
        :type api: ApiDescriptor
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

        request_kwargs = api.request_kwargs

        for key, value in request_kwargs.items():
            if key not in kwargs:
                kwargs[key] = value
        path = kwargs.pop('path')

        if not site:
            site = self.param('site', default='default')

        result_item = self.connection.send_request(path=path,
                                                   site=site,
                                                   **kwargs)
        for attr in api.result_path:
            if attr not in result_item:
                raise KeyError('UniFi API response does not include {path}, '
                               'misses attribute {attr}'
                               .format(path=', '.join(api.result_path), attr=attr))
            result_item = result_item.get(attr, None)
        return result_item
