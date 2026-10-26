from django import forms
from django.utils.translation import gettext_lazy as _

from dcim.models import DeviceRole, DeviceType
from ipam.models import VLAN
from netbox.forms import NetBoxModelFilterSetForm, NetBoxModelForm
from utilities.forms.fields import DynamicModelMultipleChoiceField
from utilities.forms.rendering import FieldSet

from .models import SuggestionRule


class SuggestionRuleForm(NetBoxModelForm):
    roles = DynamicModelMultipleChoiceField(
        queryset=DeviceRole.objects.all(), required=False, label=_('Roles'),
        help_text=SuggestionRule._meta.get_field('roles').help_text,
    )
    device_types = DynamicModelMultipleChoiceField(
        queryset=DeviceType.objects.all(), required=False, label=_('Device types'),
        help_text=SuggestionRule._meta.get_field('device_types').help_text,
    )
    vlans = DynamicModelMultipleChoiceField(
        queryset=VLAN.objects.all(), required=False, label=_('VLANs'),
        help_text=SuggestionRule._meta.get_field('vlans').help_text,
    )

    fieldsets = (
        FieldSet('name', 'priority', 'enabled', 'description', name=_('Rule')),
        FieldSet('roles', 'device_types', name=_('Applies to')),
        FieldSet('vlans', 'interface_name', name=_('Address')),
    )

    class Meta:
        model = SuggestionRule
        fields = (
            'name', 'priority', 'enabled', 'description', 'roles', 'device_types', 'vlans',
            'interface_name', 'tags',
        )


class SuggestionRuleFilterForm(NetBoxModelFilterSetForm):
    model = SuggestionRule
    enabled = forms.NullBooleanField(required=False, widget=forms.Select(choices=(
        ('', '---------'), ('true', _('Yes')), ('false', _('No')),
    )))
