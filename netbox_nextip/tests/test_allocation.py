"""free_number(): the order and gap rules, without a database."""
from django.test import SimpleTestCase

from ..allocation import free_number
from ..choices import AddressOrderChoices

UP, DOWN = AddressOrderChoices.AFTER_LAST, AddressOrderChoices.BEFORE_FIRST


class FreeNumberTests(SimpleTestCase):
    def pick(self, used, order, fill_gaps, taken=()):
        return free_number(1, 10, [(n, n) for n in used] + list(taken), used, order, fill_gaps)

    def test_after_last_used(self):
        """Upwards: continue after the highest used address; gaps only with fill_gaps."""
        self.assertEqual(self.pick([], UP, False), 1)
        self.assertEqual(self.pick([2, 5], UP, False), 6)
        self.assertEqual(self.pick([2, 5], UP, True), 1)
        self.assertIsNone(self.pick([3, 10], UP, False))
        self.assertEqual(self.pick([3, 10], UP, True), 1)

    def test_before_first_used(self):
        """Downwards: continue below the lowest used address; gaps only with fill_gaps."""
        self.assertEqual(self.pick([], DOWN, False), 10)
        self.assertEqual(self.pick([5, 9], DOWN, False), 4)
        self.assertEqual(self.pick([5, 9], DOWN, True), 10)

    def test_ranges_are_skipped(self):
        """A range in the way is jumped over."""
        self.assertEqual(self.pick([2], UP, False, taken=[(3, 6)]), 7)
        self.assertEqual(self.pick([9], DOWN, False, taken=[(4, 8)]), 3)
