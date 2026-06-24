#
#
#

from logging import getLogger
from os.path import dirname, join
from unittest import TestCase
from unittest.mock import patch

from octodns.cmds.validate import FlaggingHandler, main

config_dir = join(dirname(__file__), 'config')


def get_config_filename(which):
    return join(config_dir, which)


class TestValidateMain(TestCase):
    def tearDown(self):
        for logger_name in ('Zone', 'Record'):
            log = getLogger(logger_name)
            log.handlers = [
                h for h in log.handlers if not isinstance(h, FlaggingHandler)
            ]

    def test_no_flags_clean_config_exits_0(self):
        with patch(
            'sys.argv',
            [
                'octodns-validate',
                '--config-file',
                get_config_filename('simple-validate.yaml'),
            ],
        ):
            # Should not raise — clean config, no validation errors
            main()

    def test_all_and_honor_lenient_non_lenient_issue_exits_1(self):
        from octodns.record.base import Record
        from octodns.zone import Zone
        from octodns.zone.validator import ValidationReason

        non_lenient_record = Record.new(
            Zone('unit.tests.', []),
            'test',
            {'type': 'A', 'ttl': 300, 'value': '1.2.3.4'},
        )
        with patch(
            'sys.argv',
            [
                'octodns-validate',
                '--config-file',
                get_config_filename('simple-validate.yaml'),
                '--all',
                '--honor-lenient',
            ],
        ):
            with patch.object(
                Zone.validators,
                'process_zone',
                return_value=[
                    ValidationReason('non-lenient issue', [non_lenient_record])
                ],
            ):
                with self.assertRaises(SystemExit) as ctx:
                    main()
                self.assertEqual(1, ctx.exception.code)

    def test_all_and_honor_lenient_only_lenient_issues_exits_0(self):
        from octodns.record.base import Record
        from octodns.zone import Zone
        from octodns.zone.validator import ValidationReason

        lenient_record = Record.new(
            Zone('unit.tests.', []),
            'test',
            {'type': 'A', 'ttl': 300, 'value': '1.2.3.4'},
            lenient=True,
        )
        with patch(
            'sys.argv',
            [
                'octodns-validate',
                '--config-file',
                get_config_filename('simple-lenient-zone.yaml'),
                '--all',
                '--honor-lenient',
            ],
        ):
            with patch.object(
                Zone.validators,
                'process_zone',
                return_value=[
                    ValidationReason('lenient issue', [lenient_record])
                ],
            ):
                # Only lenient issues — suppressed, flagging never fires → exit 0
                main()

    def test_honor_lenient_exits_0_when_only_lenient_issues(self):
        # simple-lenient-zone.yaml has empty. with lenient:true
        # With no real validation issues, this should exit cleanly
        with patch(
            'sys.argv',
            [
                'octodns-validate',
                '--config-file',
                get_config_filename('simple-lenient-zone.yaml'),
                '--honor-lenient',
            ],
        ):
            # Should not raise or exit 1
            main()

    def test_all_flag_causes_exit_1_on_lenient_issues(self):
        from octodns.zone import Zone
        from octodns.zone.validator import ValidationReason

        with patch(
            'sys.argv',
            [
                'octodns-validate',
                '--config-file',
                get_config_filename('simple-lenient-zone.yaml'),
                '--all',
            ],
        ):
            with patch.object(
                Zone.validators,
                'process_zone',
                return_value=[ValidationReason('zone is broken', [])],
            ):
                with self.assertRaises(SystemExit) as ctx:
                    main()
                self.assertEqual(1, ctx.exception.code)

    def test_honor_lenient_suppresses_lenient_warnings_exit_0(self):
        from octodns.zone import Zone
        from octodns.zone.validator import ValidationReason

        with patch(
            'sys.argv',
            [
                'octodns-validate',
                '--config-file',
                get_config_filename('simple-lenient-zone.yaml'),
                '--honor-lenient',
            ],
        ):
            with patch.object(
                Zone.validators,
                'process_zone',
                return_value=[ValidationReason('zone is broken', [])],
            ):
                # With --honor-lenient, lenient zone warnings are suppressed →
                # FlaggingHandler never fires → no exit(1)
                main()

    def test_honor_lenient_non_lenient_issue_exits_1(self):
        from octodns.record.base import Record
        from octodns.zone import Zone
        from octodns.zone.exception import ValidationError
        from octodns.zone.validator import ValidationReason

        non_lenient_record = Record.new(
            Zone('unit.tests.', []),
            'www',
            {'type': 'A', 'ttl': 300, 'value': '1.2.3.4'},
        )
        with patch(
            'sys.argv',
            [
                'octodns-validate',
                '--config-file',
                get_config_filename('simple-validate.yaml'),
                '--honor-lenient',
            ],
        ):
            with patch.object(
                Zone.validators,
                'process_zone',
                return_value=[
                    ValidationReason('non-lenient issue', [non_lenient_record])
                ],
            ):
                # Without --all, non-lenient issues raise ValidationError directly
                # (not demoted to a warning, so FlaggingHandler is never involved)
                with self.assertRaises(ValidationError):
                    main()
