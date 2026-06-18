#
#
#

from os.path import dirname, join
from unittest import TestCase
from unittest.mock import patch

from octodns.cmds.validate import main

config_dir = join(dirname(__file__), 'config')


def get_config_filename(which):
    return join(config_dir, which)


class TestValidateMain(TestCase):
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

    def test_all_and_honor_lenient_are_mutually_exclusive(self):
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
            with self.assertRaises(SystemExit) as ctx:
                main()
            # argparse parser.error() exits with code 2
            self.assertEqual(2, ctx.exception.code)

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
