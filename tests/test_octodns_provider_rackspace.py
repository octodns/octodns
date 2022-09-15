#
#
#

from unittest import TestCase


class TestRackspaceShim(TestCase):
    def test_missing(self):
        with self.assertRaises(ModuleNotFoundError):
            from octodns.provider.rackspace import RackspaceProvider

            RackspaceProvider
