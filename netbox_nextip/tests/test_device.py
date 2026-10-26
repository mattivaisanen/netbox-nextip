"""Suggestion rules and the one-click Assign on device pages."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from dcim.models import Device, DeviceRole
from ipam.models import IPAddress, Prefix

from ..models import SuggestionRule
from ..plan import plan_for
from .utils import NetBoxData


class RuleTests(NetBoxData, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.make_netbox()

    def test_rules(self):
        """No rule, no suggestion; the first matching rule by priority wins; the VLAN comes from the rule."""
        self.assertEqual(plan_for(self.switch), [])
        server = DeviceRole.objects.create(name='Server', slug='server')
        SuggestionRule.objects.create(name='servers', priority=10).roles.set([server])
        anything = SuggestionRule.objects.create(name='anything', priority=20, interface_name='Gi1/0/1')
        plan = plan_for(self.switch)[0]
        self.assertEqual((plan.rule, plan.interface, plan.address), (anything, self.port, '10.0.10.1/24'))

        # With VLANs on the rule, only those count: not the access port's VLAN 10.
        anything.vlans.set([self.vlan20])
        Prefix.objects.create(prefix='10.0.20.0/24', vlan=self.vlan20)
        plan = plan_for(self.switch)[0]
        self.assertEqual((plan.interface, plan.address), (self.port, '10.0.20.1/24'))

@override_settings(LOGIN_REQUIRED=True, EXEMPT_VIEW_PERMISSIONS=['*'])
class AssignTests(NetBoxData, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.make_netbox()
        cls.user = get_user_model().objects.create(username='admin', is_superuser=True)

    def test_assign_creates_interface_and_primary_ip(self):
        """A device with no interfaces gets the rule's interface, the address and its primary IP in one click."""
        rule = SuggestionRule.objects.create(name='all', interface_name='mgmt0')
        rule.vlans.set([self.vlan])
        bare = Device.objects.create(name='odd1', site=self.switch.site, device_type=self.switch.device_type,
                                     role=self.switch.role)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(bare.get_absolute_url()), '10.0.10.1/24')

        url = reverse('plugins:netbox_nextip:assign_device', args=[bare.pk])
        response = self.client.post(url, {'address4': '10.0.10.1/24'})
        self.assertRedirects(response, bare.get_absolute_url(), fetch_redirect_response=False)
        bare.refresh_from_db()
        ip = IPAddress.objects.get(address='10.0.10.1/24')
        self.assertEqual((bare.primary_ip4, ip.assigned_object.name), (ip, 'mgmt0'))
        self.assertNotContains(self.client.get(bare.get_absolute_url()), 'Suggested IP')
