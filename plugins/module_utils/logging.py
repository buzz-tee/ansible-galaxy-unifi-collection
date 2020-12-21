#!/usr/bin/env python

from enum import Enum
from datetime import datetime

class LogLevel(Enum):
    '''
    A simple enumeration of log levels
    '''
    DISABLED = 0    #: logging is disabled, don't do anything
    FATAL = 1       #: marks a fatal event, i.e. error
    ERROR = 2       #: marks an error in processing
    WARNING = 3     #: marks a warning
    INFO = 4        #: marks an informational entry
    VERBOSE = 5     #: marks a more verbose informational entry
    DEBUG = 6       #: marks debug information
    DEBUG_2 = 7     #: marks more verbose debug information
    TRACE = 8       #: marks a trace entry
    TRACE_2 = 9     #: marks a more verbose trace entry
    MAXIMUM = 10    #: maximum log level

    def __lt__(self, other):
        if isinstance(other, LogLevel):
            return self.value < other.value
        else:
            return self.value < other
    
    def __gt__(self, other):
        if isinstance(other, LogLevel):
            return self.value > other.value
        else:
            return self.value > other

class Logger(object):
    '''
    A simple logging facility.
    '''

    #: convenience accessor for LogLevel.DISABLED
    LEVEL_DISABLED = LogLevel.DISABLED

    def __init__(self, log_level, log_file):
        '''
        Initialize self.

        :ivar __log_level: the minimum log level for this logger
        :type __log_level: LogLevel
        :ivar __log_file: the handle of the log file if file logging is enabled
            else None
        :type __log_file: file

        :param log_level: the minimum log level for this logger
        :type log_level: LogLevel
        :param log_file: name of a log file where logs will be written to, may be
          None to disable file logging
        :type log_file: str
        '''
        self.__logs = []
        if LogLevel.DISABLED > log_level:
            self.__log_level = LogLevel.DISABLED
        elif LogLevel.MAXIMUM < log_level:
            self.__log_level = LogLevel.MAXIMUM
        else:
            self.__log_level = LogLevel(log_level)
        
        if self.__log_level > LogLevel.DISABLED and log_file is not None:
            self.__log_file = open(log_file, 'a')
        else:
            self.__log_file = None

    @property
    def level(self):
        '''
        This property gives access to the minimum log level for this logger.

        :returns: the minimum log level
        :rtype: LogLevel
        '''
        return self.__log_level
    
    @property
    def enabled(self):
        '''
        Gives information whether logging is enabled or not.

        :returns: `True` if logging is enabled else `False`
        :rtype: bool
        '''
        return self.__log_level != LogLevel.DISABLED

    @property
    def logs(self):
        '''
        Provides access to the gathered logs of this logger.

        :returns: all logs which were gathered by this logger
        :rtype: list
        '''
        return self.__logs

    @classmethod
    def join(cls, *logs):
        '''
        Joins multiple log lists in chronological order and converts the
        timestamp information to human readable format.

        :param \\*logs: one or multiple log lists as returned by `Logger.logs`
        :type \\*logs: list

        :returns: the joined and chronologically ordered log list
        :rtype: list
        '''
        logs = [log_entry for log in logs for log_entry in log]
        logs.sort(key=lambda x: x['timestamp'])
        for log_entry in logs:
            log_entry['timestamp'] = str(
                datetime.fromtimestamp(log_entry['timestamp']))
        return logs

    def error(self, log_message, *args, **kwargs):
        '''
        Method for error logging.

        :param log_message: the message, will be passed to `Logger.__log()`
        :type log_message: str
        :param \\*args: unnamed format parameters, passed to `Logger.__log()`
        :type \\*args: any
        :param \\*kwargs: keyword format parameters, passed to `Logger.__log()`
        :type \\*kwargs: any
        '''
        self.__log(LogLevel.ERROR, log_message, *args, **kwargs)

    def info(self, log_message, *args, **kwargs):
        '''
        Method for informational logging.

        :param log_message: the message, will be passed to `Logger.__log()`
        :type log_message: str
        :param \\*args: unnamed format parameters, passed to `Logger.__log()`
        :type \\*args: any
        :param \\*kwargs: keyword format parameters, passed to `Logger.__log()`
        :type \\*kwargs: any
        '''
        self.__log(LogLevel.INFO, log_message, *args, **kwargs)

    def debug(self, log_message, *args, **kwargs):
        '''
        Method for debug logging.

        :param log_message: the message, will be passed to `Logger.__log()`
        :type log_message: str
        :param \\*args: unnamed format parameters, passed to `Logger.__log()`
        :type \\*args: any
        :param \\*kwargs: keyword format parameters, passed to `Logger.__log()`
        :type \\*kwargs: any
        '''
        self.__log(LogLevel.DEBUG, log_message, *args, **kwargs)

    def trace(self, log_message, *args, **kwargs):
        '''
        Method for trace logging.

        :param log_message: the message, will be passed to `Logger.__log()`
        :type log_message: str
        :param \\*args: unnamed format parameters, passed to `Logger.__log()`
        :type \\*args: any
        :param \\*kwargs: keyword format parameters, passed to `Logger.__log()`
        :type \\*kwargs: any
        '''
        self.__log(LogLevel.TRACE, log_message, *args, **kwargs)

    def __log(self, log_level, log_message, *args, **kwargs):
        '''
        Method for logging. If the log level is sufficiently high, then a log
        entry will be stored in the list of logs and - if enabled - also written
        to the log file.

        :param log_level: the level of this log entry
        :type log_level: LogLevel
        :param log_message: the message of this log entry
        :type log_message: str
        :param \\*args: unnamed format parameters, used by
            `log_message.format()`
        :type \\*args: any
        :param \\*kwargs: keyword format parameters, used by
            `log_message.format()`
        :type \\*kwargs: any
        '''
        if log_level > self.__log_level or log_level <= LogLevel.DISABLED:
            return
        
        timestamp = datetime.now()

        if isinstance(log_message, str) and (args or kwargs):
            try:
                log_message = log_message.format(*args, **kwargs)
            except Exception as e:
                log_message += '\nBad log message format: ' + str(e)

        self.__logs.append({
            'timestamp': timestamp.timestamp(),
            'level': log_level.name,
            'message': str(log_message)
        })

        if self.__log_file:
            self.__log_file.write('{timestamp} | {level}: {message}\n'.format(
                                  timestamp=str(timestamp),
                                  level=log_level.name,
                                  message=str(log_message)))
            self.__log_file.flush()
