import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable, columns

from .models import SuggestionRule


class SuggestionRuleTable(NetBoxTable):
    name = tables.Column(linkify=True)
    enabled = columns.BooleanColumn()
    roles = columns.ManyToManyColumn(linkify_item=True, verbose_name=_('Roles'))
    device_types = columns.ManyToManyColumn(linkify_item=True, verbose_name=_('Device types'))
    vlans = columns.ManyToManyColumn(linkify_item=True, verbose_name=_('VLANs'))

    class Meta(NetBoxTable.Meta):
        model = SuggestionRule
        fields = (
            'pk', 'id', 'priority', 'name', 'enabled', 'roles', 'device_types', 'vlans', 'interface_name',
            'description', 'created', 'last_updated',
        )
        default_columns = ('pk', 'priority', 'name', 'enabled', 'roles', 'device_types', 'vlans', 'interface_name')
