import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable, columns

from .models import IPRule


class IPRuleTable(NetBoxTable):
    name = tables.Column(linkify=True)
    enabled = columns.BooleanColumn()
    device_types = columns.ManyToManyColumn(linkify_item=True, verbose_name=_('Device types'))
    roles = columns.ManyToManyColumn(linkify_item=True, verbose_name=_('Roles'))
    clusters = columns.ManyToManyColumn(linkify_item=True, verbose_name=_('Clusters'))
    region = tables.Column(linkify=True)
    site_group = tables.Column(linkify=True)
    site = tables.Column(linkify=True)
    location = tables.Column(linkify=True)
    vlan = tables.Column(linkify=True)
    fill_gaps = columns.BooleanColumn()
    make_primary = columns.BooleanColumn()

    class Meta(NetBoxTable.Meta):
        model = IPRule
        fields = (
            'pk', 'id', 'priority', 'name', 'enabled', 'object_type', 'device_types', 'clusters', 'roles', 'region',
            'site_group', 'site', 'location', 'vlan', 'interface_name', 'interface_type', 'order', 'fill_gaps',
            'ip_status', 'ip_role', 'make_primary', 'description', 'created', 'last_updated',
        )
        default_columns = (
            'pk', 'priority', 'name', 'enabled', 'object_type', 'device_types', 'roles', 'region', 'site', 'vlan',
            'interface_name',
        )
