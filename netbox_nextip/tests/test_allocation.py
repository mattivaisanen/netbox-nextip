"""Which address an interface gets: ranges, the prefix fallback and the settings."""
from django.conf import settings as django_settings
from django.test import SimpleTestCase, TestCase, override_settings

from dcim.choices import InterfaceModeChoices
from ipam.models import Prefix, Role

from ..allocation import FIRST, FULL, LAST, NO_PREFIX, NO_RANGE, free_number, suggest
from .utils import NetBoxData


def plugin_settings(**settings):
    """The plugin's settings with some changed (the rest keep their defaults)."""
    current = django_settings.PLUGINS_CONFIG['netbox_nextip']
    return override_settings(PLUGINS_CONFIG={'netbox_nextip': {**current, **settings}})


class FreeNumberTests(SimpleTestCase):
    def test_first_and_last(self):
        self.assertEqual(free_number(1, 10, []), 1)
        self.assertEqual(free_number(1, 10, [], LAST), 10)

    def test_skips_taken_and_overlapping(self):
        taken = [(1, 1), (2, 5), (4, 6), (8, 8)]
        self.assertEqual(free_number(1, 10, taken, FIRST), 7)
        self.assertEqual(free_number(1, 10, taken + [(9, 12)], LAST), 7)

    def test_full(self):
        self.assertIsNone(free_number(1, 3, [(0, 2), (3, 3)]))
        self.assertIsNone(free_number(1, 3, [(1, 3)], LAST))


class SuggestTests(NetBoxData, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.make_netbox()

    def address(self, **kwargs):
        return suggest(self.port, **kwargs)[0].address

    def test_prefix_when_no_range(self):
        self.assertEqual(self.address(), '10.0.10.1/24')

    def test_existing_addresses_are_taken(self):
        self.ip('10.0.10.1/24')
        self.ip('10.0.10.2/32')
        self.assertEqual(self.address(), '10.0.10.3/24')

    def test_addresses_in_another_vrf_are_free(self):
        from ipam.models import VRF
        self.ip('10.0.10.1/24', vrf=VRF.objects.create(name='Other'))
        self.assertEqual(self.address(), '10.0.10.1/24')

    def test_range_wins_over_prefix(self):
        self.iprange('10.0.10.100/24', '10.0.10.199/24')
        self.ip('10.0.10.100/24')
        result = suggest(self.port)[0]
        self.assertEqual(result.address, '10.0.10.101/24')
        self.assertIsNotNone(result.range)

    def test_full_range_does_not_fall_back(self):
        self.iprange('10.0.10.100/24', '10.0.10.100/24')
        self.ip('10.0.10.100/24')
        self.assertEqual(suggest(self.port)[0].problem, FULL)
        with plugin_settings(prefix_fallback_when_full=True):
            self.assertEqual(self.address(), '10.0.10.1/24')

    def test_populated_range_is_skipped_in_prefix(self):
        self.iprange('10.0.10.1/24', '10.0.10.49/24', mark_populated=True)
        self.assertEqual(self.address(), '10.0.10.50/24')

    def test_prefix_skips_ranges_that_do_not_count(self):
        self.iprange('10.0.10.1/24', '10.0.10.9/24', status='reserved')
        self.assertEqual(self.address(), '10.0.10.10/24')

    def test_range_roles(self):
        static = Role.objects.create(name='Static', slug='static')
        self.iprange('10.0.10.100/24', '10.0.10.199/24')
        self.iprange('10.0.10.200/24', '10.0.10.250/24', role=static)
        with plugin_settings(range_roles=['static']):
            self.assertEqual(self.address(), '10.0.10.200/24')

    def test_order_last_and_skips(self):
        with plugin_settings(order='last'):
            self.assertEqual(self.address(), '10.0.10.254/24')
        with plugin_settings(prefix_skip_first=1, prefix_skip_last=4, order='last'):
            self.assertEqual(self.address(), '10.0.10.250/24')
        with plugin_settings(prefix_skip_first=1):
            self.assertEqual(self.address(), '10.0.10.2/24')

    def test_no_prefix_and_no_range(self):
        self.assertEqual(suggest(self.port, family=6)[0].problem, NO_PREFIX)
        with plugin_settings(prefix_fallback=False):
            self.assertEqual(suggest(self.port)[0].problem, NO_RANGE)

    def test_ipv6(self):
        Prefix.objects.create(prefix='2001:db8:10::/64', vlan=self.vlan)
        with plugin_settings(families=[4, 6]):
            self.assertEqual([s.address for s in suggest(self.port)], ['10.0.10.1/24', '2001:db8:10::1/64'])

    def test_tagged_vlans(self):
        Prefix.objects.create(prefix='10.0.20.0/24', vlan=self.vlan20)
        self.port.mode = InterfaceModeChoices.MODE_TAGGED
        self.port.save()
        self.port.tagged_vlans.set([self.vlan20])
        self.assertEqual(len(suggest(self.port)), 1)
        with plugin_settings(tagged_vlans=True):
            self.assertEqual([s.address for s in suggest(self.port)], ['10.0.10.1/24', '10.0.20.1/24'])

    def test_cable_peer_vlan(self):
        self.assertEqual(suggest(self.nic), [])
        nic = self.cable_server()
        result = suggest(nic)[0]
        self.assertEqual((result.address, result.via), ('10.0.10.1/24', self.port))
        with plugin_settings(cable_peer_vlans=False):
            self.assertEqual(suggest(nic), [])

    def test_interface_without_vlan(self):
        self.port.mode, self.port.untagged_vlan = None, None
        self.assertEqual(suggest(self.port), [])
