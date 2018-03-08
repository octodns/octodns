#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from argparse import ArgumentParser as _Base
from logging import DEBUG, INFO, WARN, Formatter, StreamHandler, \
    getLogger
from logging.handlers import SysLogHandler
from sys import stderr, stdout


class ArgumentParser(_Base):
    '''
    Manages argument parsing and adds some defaults and takes action on them.

    Also manages logging setup.
    '''

    def __init__(self, *args, **kwargs):
        super(ArgumentParser, self).__init__(*args, **kwargs)

    def parse_args(self, default_log_level=INFO):
        self.add_argument('--log-stream-stdout', action='store_true',
                          default=False,
                          help='Log to stdout instead of stderr')
        _help = 'Send logging data to syslog in addition to stderr'
        self.add_argument('--log-syslog', action='store_true', default=False,
                          help=_help)
        self.add_argument('--syslog-device', default='/dev/log',
                          help='Syslog device')
        self.add_argument('--syslog-facility', default='local0',
                          help='Syslog facility')

        _help = 'Increase verbosity to get details and help track down issues'
        self.add_argument('--debug', action='store_true', default=False,
                          help=_help)

        args = super(ArgumentParser, self).parse_args()
        self._setup_logging(args, default_log_level)
        return args

    def _setup_logging(self, args, default_log_level):
        fmt = '%(asctime)s [%(thread)d] %(levelname)-5s %(name)s %(message)s'
        formatter = Formatter(fmt=fmt, datefmt='%Y-%m-%dT%H:%M:%S ')
        stream = stdout if args.log_stream_stdout else stderr
        handler = StreamHandler(stream=stream)
        handler.setFormatter(formatter)
        logger = getLogger()
        logger.addHandler(handler)

        if args.log_syslog:
            fmt = 'octodns[%(process)-5s:%(thread)d]: %(name)s ' \
                '%(levelname)-5s %(message)s'
            handler = SysLogHandler(address=args.syslog_device,
                                    facility=args.syslog_facility)
            handler.setFormatter(Formatter(fmt=fmt))
            logger.addHandler(handler)

        logger.level = DEBUG if args.debug else default_log_level

        # boto is noisy, set it to warn
        getLogger('botocore').level = WARN
        # DynectSession is noisy too
        getLogger('DynectSession').level = WARN
