"""Which rule a device gets, and what Add IP creates."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from dcim.models import Device, DeviceRole, DeviceType, Interface, Manufacturer, Region, Site
from ipam.models import IPAddress, Prefix, VLAN, VLANGroup

from ..assign import assign
from ..models import IPRule
from ..plan import plan_for


class RuleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.north = Region.objects.create(name='North', slug='north')
        cls.city = Region.objects.create(name='City', slug='city', parent=cls.north)
        cls.site = Site.objects.create(name='Site 1', slug='site-1', region=cls.city)
        maker = Manufacturer.objects.create(name='Maker', slug='maker')
        cls.ap = DeviceType.objects.create(manufacturer=maker, model='AP', slug='ap')
        cls.switch = DeviceType.objects.create(manufacturer=maker, model='Switch', slug='switch')
        cls.role = DeviceRole.objects.create(name='Network', slug='network')
        cls.device = Device.objects.create(name='ap1', site=cls.site, device_type=cls.ap, role=cls.role)
        cls.vlan = VLAN.objects.create(vid=110, name='Mgmt')
        Prefix.objects.create(prefix='10.1.10.0/24', vlan=cls.vlan)
        IPAddress.objects.create(address='10.1.10.5/24')
        cls.user = get_user_model().objects.create(username='admin', is_superuser=True)

    def rule(self, name, **fields):
        return IPRule.objects.create(name=name, vlan=self.vlan, **fields)

    def test_scope_is_required(self):
        """A rule with no region and a VLAN outside a scoped VLAN group would apply everywhere."""
        with self.assertRaises(ValidationError):
            IPRule(name='everywhere', vlan=self.vlan).full_clean()

    def test_rule_that_lost_its_scope_matches_nothing(self):
        """A rule scoped only by its VLAN group stops matching when the group loses its scope."""
        group = VLANGroup.objects.create(name='Site 1 VLANs', slug='site-1-vlans', scope=self.site)
        VLAN.objects.filter(pk=self.vlan.pk).update(group=group)
        rule = IPRule.objects.create(name='by-group', vlan=VLAN.objects.get(pk=self.vlan.pk))
        self.assertEqual(IPRule.for_object(self.device), rule)
        # update(): no other plugin may hold the change back.
        VLANGroup.objects.filter(pk=group.pk).update(scope_type=None, scope_id=None)
        self.assertIsNone(IPRule.for_object(self.device))

    def test_narrowest_rule_wins(self):
        """Same priority: the rule for the child region beats the parent's; other types never match."""
        self.rule('a-north', region=self.north)
        city = self.rule('city', region=self.city)
        self.rule('switches', region=self.city).device_types.set([self.switch])
        plan = plan_for(self.device)
        self.assertEqual((plan.rule, plan.interface_name, plan.address), (city, 'Vlan110', '10.1.10.6/24'))

    def test_role_rule(self):
        """A rule with roles only matches devices of those roles, and beats one without roles."""
        printers = DeviceRole.objects.create(name='Printer', slug='printer')
        self.rule('any-role', region=self.city)
        network = self.rule('network', region=self.city)
        network.roles.set([self.role])
        self.rule('printers', region=self.city, priority=1).roles.set([printers])
        self.assertEqual(IPRule.for_object(self.device), network)

    @override_settings(LOGIN_REQUIRED=True, EXEMPT_VIEW_PERMISSIONS=['*'])
    def test_add_ip(self):
        """Add IP creates the interface in the rule's VLAN, the address and the primary IP."""
        self.rule('city', region=self.city, dns_name='{device}.example.net')
        self.client.force_login(self.user)
        url = reverse('plugins:netbox_nextip:add_ip_device', args=[self.device.pk])
        self.client.post(url, {'address': '10.1.10.6/24'})

        self.device.refresh_from_db()
        ip = self.device.primary_ip4
        self.assertEqual(str(ip.address), '10.1.10.6/24')
        self.assertEqual((ip.assigned_object.name, ip.assigned_object.untagged_vlan), ('Vlan110', self.vlan))
        self.assertEqual(ip.dns_name, 'ap1.example.net')
        self.assertIsNone(plan_for(self.device))
        self.assertNotContains(self.client.get(self.device.get_absolute_url()), 'Add IP address')

    def test_second_click_adds_nothing(self):
        """A click with a stale page (the primary IP was set after it loaded) adds nothing."""
        self.rule('city', region=self.city)
        stale = Device.objects.get(pk=self.device.pk)
        # The first click's result, written with update() so no other plugin can hold the change back.
        ip = IPAddress.objects.create(address='10.1.10.6/24')
        Device.objects.filter(pk=self.device.pk).update(primary_ip4=ip)
        self.assertIsNone(assign(stale, self.user))
        self.assertEqual(IPAddress.objects.count(), 2)

    def test_only_interface_is_used(self):
        """A device with one interface gets the address there, unless it is a trunk; with two, a new interface."""
        self.rule('city', region=self.city)
        eth0 = Interface.objects.create(device=self.device, name='eth0', type='1000base-t', mode='tagged')
        self.assertEqual(plan_for(self.device).interface_name, 'Vlan110')
        Interface.objects.filter(pk=eth0.pk).update(mode='')
        self.assertEqual(plan_for(self.device).interface.name, 'eth0')
        Interface.objects.create(device=self.device, name='eth1', type='1000base-t')
        plan = plan_for(self.device)
        self.assertEqual((plan.interface, plan.interface_name), (None, 'Vlan110'))

    @override_settings(LOGIN_REQUIRED=True, EXEMPT_VIEW_PERMISSIONS=['*'])
    def test_popup_without_rule(self):
        """No rule: the popup's VLAN gives the address, on a new Vlan<vid> interface."""
        self.client.force_login(self.user)
        popup = reverse('plugins:netbox_nextip:add_ip_popup_device', args=[self.device.pk])
        page = self.client.get(self.device.get_absolute_url())
        self.assertContains(page, popup)
        self.assertContains(page, 'Add IP address')
        # Nothing is picked for the user without a rule; picking the VLAN shows what Add IP will do.
        self.assertNotContains(self.client.get(popup), '10.1.10.6/24')
        self.assertContains(self.client.get(popup, {'vlan': self.vlan.pk}), '10.1.10.6/24')
        url = reverse('plugins:netbox_nextip:add_ip_device', args=[self.device.pk])
        self.client.post(url, {'vlan': self.vlan.pk})
        self.device.refresh_from_db()
        self.assertEqual(
            (str(self.device.primary_ip4.address), self.device.primary_ip4.assigned_object.name),
            ('10.1.10.6/24', 'Vlan110'),
        )

    @override_settings(LOGIN_REQUIRED=True, EXEMPT_VIEW_PERMISSIONS=['*'])
    def test_typed_address(self):
        """A typed address alone picks the VLAN from its prefix; taken or reserved ones are refused."""
        self.rule('city', region=self.city)
        self.client.force_login(self.user)
        popup = reverse('plugins:netbox_nextip:add_ip_popup_device', args=[self.device.pk])
        page = self.client.get(popup, {'ip_address': '10.1.10.50'})
        self.assertRegex(page.content.decode(), rf'value="{self.vlan.pk}"\s+selected')
        self.assertContains(page, '10.1.10.50/24')
        for taken in ('10.1.10.5', '10.1.10.1', '10.1.10.255', '10.9.9.9'):
            self.assertNotContains(self.client.get(popup, {'vlan': self.vlan.pk, 'ip_address': taken}), 'name="address"')

        url = reverse('plugins:netbox_nextip:add_ip_device', args=[self.device.pk])
        self.client.post(url, {'popup': '1', 'vlan': self.vlan.pk, 'ip_address': '10.1.10.5'})
        self.assertEqual(IPAddress.objects.count(), 1)
        self.client.post(url, {'popup': '1', 'ip_address': '10.1.10.50'})
        self.device.refresh_from_db()
        self.assertEqual(str(self.device.primary_ip4.address), '10.1.10.50/24')
