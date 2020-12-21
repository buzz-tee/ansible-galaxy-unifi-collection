#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright: (c) 2020, Sebastian Gmeiner <sebastian@gmeiner.eu>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.plugins.httpapi import HttpApiBase
from json import dumps as json_dumps, load as json_load
from datetime import datetime

from ansible_collections.gmeiner.unifi.plugins.module_utils.logging import \
    Logger


class HttpApi(HttpApiBase):
    """
    HttpApi implementation for the UniFi REST API

    :ivar __masked_errors: list of HTTP error codes that should not be treated
        as fatal errors for the current request
    :vartype __masked_errors: list
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
    def __init__(self, *args, **kwargs):
        """
        Initialize self.

        :see: ansible.plugins.httpapi.HttpApiBase
        """
        super(HttpApi, self).__init__(*args, **kwargs)
        self.__masked_errors = []
        self.set_logging(Logger.LEVEL_DISABLED, None)

    @property
    def is_unifi_os(self):
        """
        This property allows simple identification of the UniFi controller type.

        :returns: True if the controller is running unifi-os (e.g. embedded in
            a UniFi DreamMachine), or False for a classic controller (e.g.
            CloudKey)
        :rtype: bool
        """
        return self.connection.get_option('is_unifi_os') \
            if self.connection.has_option('is_unifi_os') else None
    
    def set_logging(self, loglevel, logfile):
        """
        Initialize the logging facility for this object

        :param loglevel: the minimum logging level
        :type loglevel: LogLevel
        :param logfile: an optional log file to write output to, may be None
        :type logfile: str
        """
        self.__logger = Logger(loglevel, logfile)
        self.info = self.__logger.info
        self.debug = self.__logger.debug
        self.trace = self.__logger.trace

    def __check_unifi_os(self):
        """
        Checks if the UniFi controller is running on unifi-os. Check is skipped
        if a cached result for that check is available.
        """
        if self.is_unifi_os is None:
            self.__masked_errors.append(400)
            self.__masked_errors.append(401)
            response, _ = self.connection.send('/api/system',
                                               None, method='GET')
            self.connection.set_option('is_unifi_os', response.status == 200)
            self.__masked_errors.remove(400)
            self.__masked_errors.remove(401)

    def get_logs(self):
        """
        Returns all logs that were captured by the logger.

        :returns: a list of log entries
        :rtype: list
        """
        return self.__logger.logs

    def send_request(self, data=None, path='/', proxy=None,
                     path_prefix='/api/s/', site='default', _id=None,
                     **message_kwargs):
        """
        Primary method for interaction with the UniFi REST API.

        Depending on different parameters different REST methods will be
        invoked:

        - GET (list of items) : if data is None and _id is None
        - DELETE (delete item) : if data is None and _id is not None or
        - DELETE (delete item) : data is a dict which only contains only the key
            '_id' and the _id parameter (passed to this method) is None
        - POST (create item) : data is not None and _id is None
        - PUT (update item) : data is not None and _id is not None or
        - PUT (update item) : data is not None and contains the key '_id' as
            well as further keys and the _id parameter (passed to this method)
            is None

        This method will also assemble the REST endpoint URI following the
        pattern **/proxy/{proxy}{path_prefix}{site}{path}** where

        - /proxy/{proxy} will only be inserted for unifi-os based Controllers
        - {path_prefix} by default is '/api/s/'
        - {site} is the name of the site, default is 'default'
        - {path} is the last part of the REST endpoint URI - needs to start with
          a '/' (forward slash)

        :param data: any data to submit to the UniFi REST endpoint
        :type data: dict
        :param path: the last part of the REST endpoint URI
        :type path: str
        :param proxy: optional, the component to proxy this request to, e.g.
            'network', only used for unifi-os based Controllers
        :type proxy: str
        :param path_prefix: optional, normally not required, defaults to
            '/api/s/'
        :type path_prefix: str
        :param site: optional, the site for which this request is intended,
            defaults to 'default'
        :type site: str
        :param _id: optional, explicit id of the object on the UniFi controller
        :type _id: str
        :param \\**message_kwargs: may contain 'method' to override the decision
            matrix above, other keyword arguments will be ignored
        :type \\**message_kwargs: any
        
        :returns: the response from the UniFi controller, parsed from its json
            format
        :rtype: dict
        """
        self.__check_unifi_os()

        if data is not None and not isinstance(data, str):
            if not _id and '_id' in data:
                _id = data['_id']
                if len(data) == 1:
                    data = None
            if data:
                data = json_dumps(data, indent=4)

        if self.is_unifi_os and proxy:
            proxy = '/proxy/{proxy}'.format(proxy=proxy)
        else:
            proxy = ''

        if data is not None:
            if _id:
                method = 'PUT'
                path_template = '{proxy}{path_prefix}{site}{path}/{id}'
            else:
                method = 'POST'
                path_template = '{proxy}{path_prefix}{site}{path}'
        else:
            if _id:
                method = 'DELETE'
                path_template = '{proxy}{path_prefix}{site}{path}/{id}'
            else:
                method = 'GET'
                path_template = '{proxy}{path_prefix}{site}{path}'

        if 'method' in message_kwargs:
            method = message_kwargs['method']

        path = path_template.format(proxy=proxy,
                                    path_prefix=path_prefix,
                                    site=site,
                                    path=path,
                                    id=_id)

        self.debug('Sending request: {method} {path}',
                    method=method, path=path)
        if data:
            self.trace('Data: {data}', data=data)

        response, response_data = self.connection.send(
            path, data, method=method
        )

        self.debug('Response received: {status} ({path})',
                    status=response.status, path=path)

        return json_load(response_data)

    def login(self, username, password):
        """
        Call the login endpoint for the UniFi REST API.

        :param username: the API username
        :type username: str
        :param password: the API password
        :type password: str
        """
        self.__check_unifi_os()

        data = {'username': username, 'password': password}
        path = '/api/auth/login' if self.is_unifi_os else '/api/login'

        self.info('Starting Authentication with username and password')
        self.connection.send(
            path, json_dumps(data), method='POST'
        )

    def update_auth(self, response, response_text):
        """
        Updates the cached authentication token(s) based on the response from
        the UniFi controller.

        Cookies values and the X-Csrf-Token will be cached if they are present
        in the response.

        :param response: the HTTP response object
        :type response: http.client.HTTPResponse
        :param response_text: the text body of the response
        :type response_text: str
        """
        headers = self.connection._auth if self.connection._auth else {}
        headers['Content-Type'] = 'application/json'

        if 'set-cookie' in response.headers:
            cookies = []
            for cookie in response.headers['set-cookie'].split(','):
                cookie = cookie.split(';')[0]
                if '=' in cookie:
                    cookies.append(cookie.strip())
            headers['Cookie'] = ','.join(cookies)

        if 'x-csrf-token' in response.headers:
            headers['X-Csrf-Token'] = response.headers['x-csrf-token']
        
        return headers

    def logout(self):
        """
        Method to clear session gracefully by invoking the logout REST endpoint.
        """
        self.info('Logging out')

        self.__check_unifi_os()
        data = {}
        path = '/api/auth/logout' if self.is_unifi_os else '/api/logout'

        self.connection.send(
            path, json_dumps(data), method='POST'
        )

    def handle_httperror(self, exc):
        """
        Handles non 2xx HTTP response codes.

        :param exc: the HTTP error object
        :type exc: urllib.error.HttpError

        :returns:
            * True if the code has been handled in a way that the request may be
              re-sent without changes.
            * False if the error cannot be handled or recovered from by the
              plugin. This will result in the HttpError being raised as an
              exception for the caller to deal with as appropriate (most likely
              by failing).
            * Any other value returned is taken as a valid response from the
              server without making another request. In many cases, this can
              just be the original exception.
        :rtype: any
        """
        if exc.code in self.__masked_errors:
            self.trace('Got masked error {code} {path}',
                        code=exc.code, path=exc.filename)
            return exc

        self.debug('Got error {code} {path}', code=exc.code, path=exc.filename)
        result = super(HttpApi, self).handle_httperror(exc)
        if result == exc:
            message = exc.read().decode('utf-8')
            self.trace('Message was {message}', message=message)
            raise Exception('Controller at {path} returned {exc}{message}'
                            .format(path=exc.filename,
                                    exc=str(exc),
                                    message=message))
        return result
