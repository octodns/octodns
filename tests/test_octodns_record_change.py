#
#
#

from unittest import TestCase

from octodns.record import Record
from octodns.record.change import Create, Delete, Update
from octodns.zone import Zone


class TestChanges(TestCase):
    zone = Zone('unit.tests.', [])
    record_a_1 = Record.new(
        zone, '1', {'type': 'A', 'ttl': 30, 'value': '1.2.3.4'}
    )
    record_a_2 = Record.new(
        zone, '2', {'type': 'A', 'ttl': 30, 'value': '1.2.3.4'}
    )
    record_aaaa_1 = Record.new(
        zone,
        '1',
        {
            'type': 'AAAA',
            'ttl': 30,
            'value': '2601:644:500:e210:62f8:1dff:feb8:947a',
        },
    )
    record_aaaa_2 = Record.new(
        zone,
        '2',
        {
            'type': 'AAAA',
            'ttl': 30,
            'value': '2601:644:500:e210:62f8:1dff:feb8:947a',
        },
    )

    def test_sort_same_change_type(self):
        # expect things to be ordered by name and type since all the change
        # types are the same it doesn't matter
        changes = [
            Create(self.record_aaaa_1),
            Create(self.record_a_2),
            Create(self.record_a_1),
            Create(self.record_aaaa_2),
        ]
        self.assertEqual(
            [
                Create(self.record_a_1),
                Create(self.record_aaaa_1),
                Create(self.record_a_2),
                Create(self.record_aaaa_2),
            ],
            sorted(changes),
        )

    def test_sort_same_different_type(self):
        # this time the change type is the deciding factor, deletes come before
        # creates, and then updates. Things of the same type, go down the line
        # and sort by name, and then type
        changes = [
            Delete(self.record_aaaa_1),
            Create(self.record_aaaa_1),
            Update(self.record_aaaa_1, self.record_aaaa_1),
            Update(self.record_a_1, self.record_a_1),
            Create(self.record_a_1),
            Delete(self.record_a_1),
            Delete(self.record_aaaa_2),
            Create(self.record_aaaa_2),
            Update(self.record_aaaa_2, self.record_aaaa_2),
            Update(self.record_a_2, self.record_a_2),
            Create(self.record_a_2),
            Delete(self.record_a_2),
        ]
        self.assertEqual(
            [
                Delete(self.record_a_1),
                Delete(self.record_aaaa_1),
                Delete(self.record_a_2),
                Delete(self.record_aaaa_2),
                Create(self.record_a_1),
                Create(self.record_aaaa_1),
                Create(self.record_a_2),
                Create(self.record_aaaa_2),
                Update(self.record_a_1, self.record_a_1),
                Update(self.record_aaaa_1, self.record_aaaa_1),
                Update(self.record_a_2, self.record_a_2),
                Update(self.record_aaaa_2, self.record_aaaa_2),
            ],
            sorted(changes),
        )
