#
#
#

from __future__ import annotations

from argparse import ArgumentParser as _Base
from argparse import Namespace
from logging import DEBUG, INFO, WARNING, Formatter, StreamHandler, getLogger
from logging.config import dictConfig
from logging.handlers import SysLogHandler
from sys import stderr, stdout
from typing import Optional

from octodns import __version__
from octodns.yaml import safe_load


class ArgumentParser(_Base):
    '''
    Manages argument parsing and adds some defaults and takes action on them.

    Also manages logging setup.
    '''

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)

    def parse_args(
        self,
        args: Optional[list[str]] = None,
        namespace: Optional[Namespace] = None,
        default_log_level: int = INFO,
    ) -> Namespace:
        version = f'octoDNS {__version__}'
        self.add_argument(
            '--version',
            action='version',
            version=version,
            help='Print octoDNS version and exit',
        )
        self.add_argument(
            '--log-stream-stdout',
            action='store_true',
            default=False,
            help='Log to stdout instead of stderr',
        )
        _help = 'Send logging data to syslog in addition to stderr'
        self.add_argument(
            '--log-syslog', action='store_true', default=False, help=_help
        )
        self.add_argument(
            '--syslog-device', default='/dev/log', help='Syslog device'
        )
        self.add_argument(
            '--syslog-facility', default='local0', help='Syslog facility'
        )

        _help = 'Increase verbosity to get details and help track down issues'
        self.add_argument(
            '--debug', action='store_true', default=False, help=_help
        )

        _help = 'Decrease verbosity to show only warnings, errors, and the plan'
        self.add_argument(
            '--quiet', action='store_true', default=False, help=_help
        )

        _help = 'Configure logging with a YAML file, see https://docs.python.org/3/library/logging.config.html#logging-config-dictschema for schema details'
        self.add_argument('--logging-config', default=False, help=_help)

        parsed = super().parse_args(args, namespace)  # type: ignore[arg-type]
        self._setup_logging(parsed, default_log_level)
        return parsed

    def _setup_logging(self, args: Namespace, default_log_level: int) -> None:
        logging_config_path: Optional[str] = (
            getattr(args, 'logging_config', None) or None
        )
        if logging_config_path:
            with open(logging_config_path) as fh:  # type: ignore[arg-type]
                config = safe_load(fh.read(), enforce_order=False)
            dictConfig(config)
            # if we're provided a logging_config we won't do any of our normal
            # configuration
            return

        # 7 is the length of the largest logging level, warning, that we're concerned with aligning.
        fmt = '%(asctime)s [%(thread)d] %(levelname)-7s %(name)s %(message)s'
        formatter = Formatter(fmt=fmt, datefmt='%Y-%m-%dT%H:%M:%S ')
        log_stream_stdout: bool = getattr(args, 'log_stream_stdout', False)
        stream = stdout if log_stream_stdout else stderr
        handler = StreamHandler(stream=stream)
        handler.setFormatter(formatter)
        logger = getLogger()
        logger.addHandler(handler)

        log_syslog: bool = getattr(args, 'log_syslog', False)
        if log_syslog:
            fmt = (
                'octodns[%(process)-5s:%(thread)d]: %(name)s '
                '%(levelname)-5s %(message)s'
            )
            syslog_device: str = getattr(args, 'syslog_device', '/dev/log')
            syslog_facility: str = getattr(args, 'syslog_facility', 'local0')
            handler = SysLogHandler(
                address=syslog_device, facility=syslog_facility
            )
            handler.setFormatter(Formatter(fmt=fmt))
            logger.addHandler(handler)

        logger.level = default_log_level
        debug: bool = getattr(args, 'debug', False)
        quiet: bool = getattr(args, 'quiet', False)
        if debug:
            logger.level = DEBUG
        elif quiet:
            logger.level = WARNING
            # we still want plans to come out during quiet so set the plan
            # logger output to info in case the PlanLogger is being used
            getLogger('Plan').setLevel(INFO)
