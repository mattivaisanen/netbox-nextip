from rest_framework import serializers

from dcim.api.serializers import (
    DeviceRoleSerializer, DeviceTypeSerializer, LocationSerializer, RegionSerializer, SiteGroupSerializer, SiteSerializer,
)
from ipam.api.serializers import VLANSerializer
from dcim.models import DeviceRole, DeviceType
from netbox.api.fields import SerializedPKRelatedField
from netbox.api.serializers import NetBoxModelSerializer
from virtualization.api.serializers import ClusterSerializer
from virtualization.models import Cluster

from ..models import IPRule


class IPRuleSerializer(NetBoxModelSerializer):
    # Written as a list of IDs, shown as nested objects (NetBox's own pattern for many-to-many fields).
    device_types = SerializedPKRelatedField(
        queryset=DeviceType.objects.all(), serializer=DeviceTypeSerializer, nested=True, many=True, required=False,
    )
    roles = SerializedPKRelatedField(
        queryset=DeviceRole.objects.all(), serializer=DeviceRoleSerializer, nested=True, many=True, required=False,
    )
    clusters = SerializedPKRelatedField(
        queryset=Cluster.objects.all(), serializer=ClusterSerializer, nested=True, many=True, required=False,
    )
    region = RegionSerializer(nested=True, required=False, allow_null=True)
    site_group = SiteGroupSerializer(nested=True, required=False, allow_null=True)
    site = SiteSerializer(nested=True, required=False, allow_null=True)
    location = LocationSerializer(nested=True, required=False, allow_null=True)
    vlan = VLANSerializer(nested=True)

    class Meta:
        model = IPRule
        fields = (
            'id', 'url', 'display_url', 'display', 'name', 'priority', 'enabled', 'description', 'object_type',
            'device_types', 'clusters', 'roles', 'region', 'site_group', 'site', 'location', 'vlan', 'interface_name',
            'interface_type', 'mgmt_only', 'order', 'fill_gaps', 'skip_first', 'skip_last', 'ip_status',
            'ip_role', 'dns_name', 'make_primary', 'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'name', 'description')

    def validate(self, data):
        data = super().validate(data)
        # On a partial update, fall back to the rule's current values.
        current = self.instance

        def value(field, many=False):
            if field in data:
                return data[field]
            if current is None:
                return [] if many else None
            return list(getattr(current, field).all()) if many else getattr(current, field)

        errors = IPRule.related_errors(
            value('object_type') or IPRule._meta.get_field('object_type').default,
            value('region'), value('vlan'), value('device_types', many=True), value('clusters', many=True),
        )
        if errors:
            raise serializers.ValidationError(errors)
        return data
