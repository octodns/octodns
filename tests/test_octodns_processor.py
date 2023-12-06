#
#
#

from unittest import TestCase

from octodns.processor.base import BaseProcessor


class BaseProcessorTest(TestCase):
    proc = BaseProcessor('test')

    def test_process_zone_config(self):
        def get_sources(name, config):
            return []

        zones = {}
        got = self.proc.process_zone_config(zones, get_sources)
        self.assertIs(zones, got)

    def test_process_source_zone(self):
        desired = 42
        got = self.proc.process_source_zone(desired, [])
        self.assertIs(desired, got)

    def test_process_target_zone(self):
        existing = 43
        got = self.proc.process_target_zone(existing, None)
        self.assertIs(existing, got)

    def test_process_source_and_target_zones(self):
        desired = 42
        existing = 43
        got_desired, got_existing = self.proc.process_source_and_target_zones(
            desired, existing, None
        )
        self.assertIs(desired, got_desired)
        self.assertIs(existing, got_existing)

    def test_process_plan(self):
        plan = 42
        got = self.proc.process_plan(plan, [], None)
        self.assertIs(plan, got)
