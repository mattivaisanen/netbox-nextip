"""The next-ip endpoint and the VLAN panel."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from ipam.models import IPAddress

from .test_allocation import plugin_settings
from .utils import NetBoxData

NEXT_IP = 'plugins-api:netbox_nextip-api:next-ip'


@override_settings(LOGIN_REQUIRED=True, EXEMPT_VIEW_PERMISSIONS=['*'])
class APITests(NetBoxData, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.make_netbox()
        cls.user = get_user_model().objects.create(username='admin', is_superuser=True)

    def setUp(self):
        self.client.force_login(self.user)

    def test_get(self):
        response = self.client.get(reverse(NEXT_IP), {'interface': self.port.pk})
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data[0]['address'], '10.0.10.1/24')
        self.assertEqual(data[0]['vlan']['id'], self.vlan.pk)
        self.assertEqual(data[0]['prefix']['id'], self.prefix.pk)

    def test_get_needs_an_interface(self):
        self.assertEqual(self.client.get(reverse(NEXT_IP)).status_code, 400)

    def test_post_creates_and_assigns(self):
        url = reverse(NEXT_IP)
        for expected in ('10.0.10.1/24', '10.0.10.2/24'):
            response = self.client.post(url, {'interface': self.port.pk, 'description': 'printer'},
                                        content_type='application/json')
            self.assertEqual(response.status_code, 201, response.content)
            self.assertEqual(response.json()['address'], expected)
        ip = IPAddress.objects.get(address='10.0.10.2/24')
        self.assertEqual((ip.assigned_object, ip.description), (self.port, 'printer'))

    def test_post_when_full(self):
        self.iprange('10.0.10.100/24', '10.0.10.100/24')
        self.ip('10.0.10.100/24')
        response = self.client.post(reverse(NEXT_IP), {'interface': self.port.pk}, content_type='application/json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['problems'], ['full'])

    def test_dns_name_and_primary_ip(self):
        with plugin_settings(dns_name='{device}-{interface}.example.com', primary_ip=True):
            for _ in range(2):
                response = self.client.post(reverse(NEXT_IP), {'interface': self.port.pk},
                                            content_type='application/json')
                self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['dns_name'], 'sw1-gi1-0-1.example.com')
        self.switch.refresh_from_db()
        self.assertEqual(str(self.switch.primary_ip4.address), '10.0.10.1/24')  # the second did not replace it

    def test_vlan_panel(self):
        self.assertContains(self.client.get(self.vlan.get_absolute_url()), '10.0.10.1/24')
