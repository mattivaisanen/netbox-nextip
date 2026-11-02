from netbox.api.viewsets import NetBoxModelViewSet

from ..filtersets import IPRuleFilterSet
from ..models import IPRule
from .serializers import IPRuleSerializer


class IPRuleViewSet(NetBoxModelViewSet):
    queryset = IPRule.objects.select_related('vlan', 'region', 'site_group', 'site', 'location').prefetch_related(
        'device_types', 'roles', 'clusters', 'tags',
    )
    serializer_class = IPRuleSerializer
    filterset_class = IPRuleFilterSet
