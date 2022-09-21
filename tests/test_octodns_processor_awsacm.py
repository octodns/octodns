#
#
#

from unittest import TestCase


class TestAwsAcmMangingProcessor(TestCase):
    def test_missing(self):
        with self.assertRaises(ModuleNotFoundError):
            from octodns.processor.awsacm import AwsAcmMangingProcessor

            AwsAcmMangingProcessor
