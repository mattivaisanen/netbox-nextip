import django_filters
from django.db.models import Q

from dcim.models import DeviceRole, Location, Region, Site, SiteGroup
from ipam.models import VLAN
from netbox.filtersets import NetBoxModelFilterSet

from .choices import RuleObjectChoices
from .models import IPRule


class IPRuleFilterSet(NetBoxModelFilterSet):
    object_type = django_filters.MultipleChoiceFilter(choices=RuleObjectChoices)
    role_id = django_filters.ModelMultipleChoiceFilter(field_name='roles', queryset=DeviceRole.objects.all())
    vlan_id = django_filters.ModelMultipleChoiceFilter(field_name='vlan', queryset=VLAN.objects.all())
    region_id = django_filters.ModelMultipleChoiceFilter(field_name='region', queryset=Region.objects.all())
    site_group_id = django_filters.ModelMultipleChoiceFilter(field_name='site_group', queryset=SiteGroup.objects.all())
    site_id = django_filters.ModelMultipleChoiceFilter(field_name='site', queryset=Site.objects.all())
    location_id = django_filters.ModelMultipleChoiceFilter(field_name='location', queryset=Location.objects.all())

    class Meta:
        model = IPRule
        fields = ('id', 'name', 'priority', 'enabled', 'interface_name', 'order', 'fill_gaps')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))
