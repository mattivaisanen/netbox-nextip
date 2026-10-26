"""
Shared test data: a switch with an access port in VLAN 10 (10.0.10.0/24),
and a server whose NIC (no VLAN) is cabled to it with cable_server().
"""
from netaddr import IPNetwork

from dcim.choices import InterfaceModeChoices
from dcim.models import Cable, Device, DeviceRole, DeviceType, Interface, Manufacturer, Site
from ipam.models import IPAddress, IPRange, Prefix, VLAN


class NetBoxData:
    @classmethod
    def make_netbox(cls):
        site = Site.objects.create(name='Tampere', slug='tampere')
        maker = Manufacturer.objects.create(name='Cisco', slug='cisco')
        device_type = DeviceType.objects.create(manufacturer=maker, model='C9300', slug='c9300')
        role = DeviceRole.objects.create(name='Switch', slug='switch')
        cls.switch = Device.objects.create(name='sw1', site=site, device_type=device_type, role=role)
        cls.vlan = VLAN.objects.create(vid=10, name='Office')
        cls.vlan20 = VLAN.objects.create(vid=20, name='Printers')
        cls.prefix = Prefix.objects.create(prefix='10.0.10.0/24', vlan=cls.vlan)
        cls.port = Interface.objects.create(
            device=cls.switch, name='Gi1/0/1', type='1000base-t',
            mode=InterfaceModeChoices.MODE_ACCESS, untagged_vlan=cls.vlan,
        )
        server = Device.objects.create(name='srv1', site=site, device_type=device_type, role=role)
        cls.nic = Interface.objects.create(device=server, name='eth0', type='1000base-t')

    def cable_server(self):
        """Cable the NIC to the port; returns the NIC fresh (its path is cached)."""
        Cable(a_terminations=[self.nic], b_terminations=[self.port]).save()
        return Interface.objects.get(pk=self.nic.pk)

    @staticmethod
    def ip(address, **fields):
        return IPAddress.objects.create(address=address, **fields)

    @staticmethod
    def iprange(start, end, **fields):
        return IPRange.objects.create(start_address=IPNetwork(start), end_address=IPNetwork(end), **fields)
