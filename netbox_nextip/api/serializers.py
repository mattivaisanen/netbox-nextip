from rest_framework import serializers

from dcim.api.serializers import DeviceRoleSerializer, DeviceTypeSerializer, InterfaceSerializer
from dcim.models import Interface
from ipam.api.serializers import IPRangeSerializer, PrefixSerializer, VLANSerializer, VRFSerializer
from ipam.models import VLAN
from netbox.api.serializers import NetBoxModelSerializer
from virtualization.models import VMInterface

from ..models import SuggestionRule


class SuggestionSerializer(serializers.Serializer):
    """An allocation.Suggestion."""
    vlan = VLANSerializer(nested=True, read_only=True)
    family = serializers.IntegerField(read_only=True)
    address = serializers.CharField(read_only=True, allow_null=True)
    vrf = VRFSerializer(nested=True, read_only=True, allow_null=True)
    prefix = PrefixSerializer(nested=True, read_only=True, allow_null=True)
    range = IPRangeSerializer(nested=True, read_only=True, allow_null=True)
    problem = serializers.CharField(read_only=True, allow_null=True)
    via = InterfaceSerializer(nested=True, read_only=True, allow_null=True)


class InterfaceQuerySerializer(serializers.Serializer):
    """
    Which interface, and optionally which VLAN and family. Querysets are
    restricted to what the user may view by the view.
    """
    interface = serializers.PrimaryKeyRelatedField(queryset=Interface.objects.all(), required=False)
    vminterface = serializers.PrimaryKeyRelatedField(queryset=VMInterface.objects.all(), required=False)
    vlan = serializers.PrimaryKeyRelatedField(queryset=VLAN.objects.all(), required=False)
    family = serializers.ChoiceField(choices=(4, 6), required=False)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            for name in ('interface', 'vminterface', 'vlan'):
                field = self.fields[name]
                field.queryset = field.queryset.restrict(user, 'view')

    def validate(self, data):
        if bool(data.get('interface')) == bool(data.get('vminterface')):
            raise serializers.ValidationError('Give either interface or vminterface.')
        data['object'] = data.get('interface') or data.get('vminterface')
        return data


class SuggestionRuleSerializer(NetBoxModelSerializer):
    roles = DeviceRoleSerializer(nested=True, many=True, required=False)
    device_types = DeviceTypeSerializer(nested=True, many=True, required=False)
    vlans = VLANSerializer(nested=True, many=True, required=False)

    class Meta:
        model = SuggestionRule
        fields = (
            'id', 'url', 'display_url', 'display', 'name', 'priority', 'enabled', 'roles', 'device_types',
            'vlans', 'interface_name', 'description', 'tags', 'custom_fields', 'created', 'last_updated',
        )
        brief_fields = ('id', 'url', 'display', 'name', 'description')
