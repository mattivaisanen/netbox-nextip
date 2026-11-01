from django import forms
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from dcim.models import DeviceRole, DeviceType, Location, Region, Site, SiteGroup
from ipam.models import VLAN, VLANGroup
from netbox.forms import NetBoxModelFilterSetForm, NetBoxModelForm
from utilities.forms.fields import DynamicModelChoiceField, DynamicModelMultipleChoiceField
from utilities.forms.rendering import FieldSet
from utilities.forms.utils import get_field_value
from utilities.forms.widgets import HTMXSelect
from virtualization.models import Cluster

from .choices import RuleObjectChoices
from .models import IPRule
from .allocation import containing_prefixes, parse_address
from .plan import available_vlans, is_device, placed


def _help(field):
    return IPRule._meta.get_field(field).help_text


class IPRuleForm(NetBoxModelForm):
    device_types = DynamicModelMultipleChoiceField(
        queryset=DeviceType.objects.all(), required=False, label=_('Device types'), help_text=_help('device_types'),
    )
    clusters = DynamicModelMultipleChoiceField(
        queryset=Cluster.objects.all(), required=False, label=_('Clusters'), help_text=_help('clusters'),
    )
    region = DynamicModelChoiceField(
        queryset=Region.objects.all(), required=False, label=_('Region'), help_text=_help('region'),
    )
    site_group = DynamicModelChoiceField(
        queryset=SiteGroup.objects.all(), required=False, label=_('Site group'), help_text=_help('site_group'),
    )
    site = DynamicModelChoiceField(
        queryset=Site.objects.all(), required=False, label=_('Site'),
        query_params={'region_id': '$region', 'group_id': '$site_group'},
    )
    location = DynamicModelChoiceField(
        queryset=Location.objects.all(), required=False, label=_('Location'), help_text=_help('location'),
        query_params={'site_id': '$site'},
    )
    vlan = DynamicModelChoiceField(
        queryset=VLAN.objects.all(), label=_('VLAN'), help_text=_help('vlan'),
    )

    fieldsets = (
        FieldSet('name', 'priority', 'enabled', 'description', name=_('Rule')),
        FieldSet('object_type', 'device_types', 'clusters', name=_('Applies to')),
        FieldSet('region', 'site_group', 'site', 'location', name=_('Scope')),
        FieldSet('vlan', 'interface_name', 'interface_type', 'mgmt_only', name=_('Interface')),
        FieldSet('order', 'fill_gaps', 'skip_first', 'skip_last', name=_('Address')),
        FieldSet('ip_status', 'ip_role', 'dns_name', 'make_primary', name=_('New IP address')),
    )

    # Fields only one kind of rule uses; the form leaves out the other kind's (see __init__).
    DEVICE_ONLY = ('device_types', 'location', 'interface_type', 'mgmt_only')
    VM_ONLY = ('clusters',)

    class Meta:
        model = IPRule
        widgets = {
            # Changing "applies to" reloads the form, so it only shows the fields that kind of rule uses.
            'object_type': HTMXSelect(),
        }
        fields = (
            'name', 'priority', 'enabled', 'description', 'object_type', 'device_types', 'clusters', 'region',
            'site_group', 'site', 'location', 'vlan', 'interface_name', 'interface_type', 'mgmt_only', 'order',
            'fill_gaps', 'skip_first', 'skip_last', 'ip_status', 'ip_role', 'dns_name', 'make_primary', 'tags',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.for_vms = get_field_value(self, 'object_type') == RuleObjectChoices.VIRTUAL_MACHINE
        for name in self.DEVICE_ONLY if self.for_vms else self.VM_ONLY:
            del self.fields[name]

    def clean(self):
        super().clean()
        data = self.cleaned_data
        if self.for_vms:
            # Hidden for VM rules: drop a location left over from when the rule was for devices.
            self.instance.location = None
        errors = IPRule.related_errors(
            data.get('object_type'), data.get('region'), data.get('vlan'),
            data.get('device_types'), data.get('clusters'),
        )
        if errors:
            raise ValidationError(errors)
        return data

    def _save_m2m(self):
        super()._save_m2m()
        # The hidden list of the other kind of rule is emptied, so nothing is left over after a switch.
        (self.instance.device_types if self.for_vms else self.instance.clusters).clear()


class IPRuleFilterForm(NetBoxModelFilterSetForm):
    model = IPRule
    fieldsets = (
        FieldSet('q', 'filter_id', 'tag'),
        FieldSet('enabled', 'object_type', 'vlan_id', 'region_id', 'site_id', name=_('Rule')),
    )
    enabled = forms.NullBooleanField(required=False, label=_('Enabled'), widget=forms.Select(choices=(
        ('', '---------'), ('true', _('Yes')), ('false', _('No')),
    )))
    object_type = forms.MultipleChoiceField(choices=RuleObjectChoices, required=False, label=_('Applies to'))
    vlan_id = DynamicModelMultipleChoiceField(queryset=VLAN.objects.all(), required=False, label=_('VLAN'))
    region_id = DynamicModelMultipleChoiceField(queryset=Region.objects.all(), required=False, label=_('Region'))
    site_id = DynamicModelMultipleChoiceField(queryset=Site.objects.all(), required=False, label=_('Site'))


class AddIPForm(forms.Form):
    """
    The Add IP popup, for a device or VM no rule matches, or to pick another
    VLAN or type the address. Site, location and VLAN group narrow down the
    VLANs; the VLAN gives the address, unless one is typed. Site and
    role are asked only when a VM has none, and saved on it. Every change
    re-renders the popup (views.AddIPPopupView), so each list only offers
    what fits the choices above it, and the preview shows what Add IP will do.

    Built for one object, obj, and the user who adds the address, from the
    submitted values (data). Every list only holds objects the user may
    view. confirm: the values are for adding the address, so the VLAN (and
    a missing site and role) are required.

    Location is a filter, not saved: it offers the device's own location and
    the ones above it, so every VLAN on offer is one the device may use.

    A typed address with no VLAN picked sets the VLAN and VLAN group from
    the smallest prefix that holds it (vlan_from_address()). ip_from keeps
    the address that did so: when the address changes, they follow it
    again; a VLAN the user picks by hand stays.
    """
    # In the order the popup shows them: each narrows down the ones below.
    role = forms.ModelChoiceField(queryset=DeviceRole.objects.none(), required=False, label=_('Role'))
    site = forms.ModelChoiceField(queryset=Site.objects.none(), required=False, label=_('Site'))
    location = forms.ModelChoiceField(queryset=Location.objects.none(), required=False, label=_('Location'))
    vlan_group = forms.ModelChoiceField(queryset=VLANGroup.objects.none(), required=False, label=_('VLAN group'))
    vlan = forms.ModelChoiceField(queryset=VLAN.objects.none(), required=False, label=_('VLAN'))
    ip_address = forms.CharField(
        required=False, label=_('IP address'),
        help_text=_('Optional. Empty: the next free address. Typed alone, the VLAN follows from its prefix.'),
    )
    ip_from = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, obj, user, data=None, confirm=False):
        data = data or {}
        # Only the popup's own fields; the CSRF token and shown address are not form data.
        super().__init__(data={key: data.get(key) for key in self.base_fields if key in data})
        self.obj, self.confirm = obj, confirm
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-select no-ts'
        self.fields['ip_address'].widget.attrs.update({'class': 'form-control', 'placeholder': _('next free')})
        self.address = (self.data.get('ip_address') or '').strip() or None
        self.address_note = None  # why the typed address could not set the VLAN

        if obj.role_id:
            del self.fields['role']
        else:
            self.fields['role'].queryset = DeviceRole.objects.restrict(user, 'view').filter(vm_role=True)
        if obj.site_id:
            del self.fields['site']
            site = obj.site
        else:
            self.fields['site'].queryset = possible_sites(obj).restrict(user, 'view')
            site = self.pick('site', self.fields['site'].queryset)

        # Where the object will be once Add IP saves the site: the preview plans for this.
        self.target = placed(obj, site)
        # The same, at the location picked as filter: the VLANs on offer.
        self.probe = placed(obj, site)
        if is_device(obj) and obj.location_id:
            locations = Location.objects.restrict(user, 'view').filter(
                pk__in=obj.location.get_ancestors(include_self=True).values('pk'),
            )
            self.fields['location'].queryset = locations
            # The device's own location until the user picks another one or none.
            own = locations.filter(pk=obj.location_id).first()  # None when the user may not view it
            self.probe.location = self.choose('location', locations, default=own)
        else:
            # VMs have no location; a device without one has nothing to narrow down.
            del self.fields['location']

        # A VM without a site first needs one picked.
        vlans = available_vlans(self.probe).restrict(user, 'view') if site else VLAN.objects.none()
        groups = VLANGroup.objects.restrict(user, 'view').filter(pk__in=vlans.values('group')).order_by('name')
        self.fields['vlan_group'].queryset = groups
        moved = self.data.get('ip_from') and self.data['ip_from'] != self.address
        if self.address and site and (moved or not self.pick('vlan', vlans)):
            self.vlan_from_address(vlans)
        # The VLAN is only picked for the user when a rule matches once the picked site is saved (a VM
        # without one): that rule's VLAN, which Add IP will use anyway. The VLAN group is also picked
        # when one group is the narrowest fit (narrowest_group()).
        rule = IPRule.for_object(self.target) if site else None
        rule_vlan = vlans.filter(pk=rule.vlan_id).first() if rule else None
        default_group = rule_vlan.group if rule_vlan else narrowest_group(groups, self.probe)
        group = self.choose('vlan_group', groups, default=default_group)
        if group:
            vlans = vlans.filter(group=group)
        vlans = vlans.select_related('group').order_by('vid')
        self.fields['vlan'].queryset = vlans
        self.vlan = self.choose('vlan', vlans, default=rule_vlan)

    def vlan_from_address(self, vlans):
        """
        Pick the VLAN and VLAN group of the smallest prefix that holds the
        typed address, when that VLAN is one of vlans (those on offer).
        Otherwise leave them and say why in address_note.
        """
        address = parse_address(self.address)
        if address is None:
            self.address_note = _('Not an IPv4 address.')
            return
        prefixes = containing_prefixes(address)
        if not prefixes:
            self.address_note = _('No active prefix holds {address}; pick the VLAN.').format(address=address)
            return
        # The smallest prefixes that hold it (more than one with VRFs).
        smallest = [prefix for prefix in prefixes if prefix.prefix.prefixlen == prefixes[0].prefix.prefixlen]
        offered = [prefix for prefix in smallest if prefix.vlan_id and vlans.filter(pk=prefix.vlan_id).exists()]
        if len(offered) == 1:
            vlan = offered[0].vlan
            self.data.update(vlan=str(vlan.pk), vlan_group=str(vlan.group_id or ''), ip_from=self.address)
        elif offered:
            self.address_note = _('Several prefixes hold {address}; pick the VLAN.').format(address=address)
        elif any(prefix.vlan_id for prefix in smallest):
            self.address_note = _('The VLAN of prefix {prefix} is not available here.').format(prefix=smallest[0])
        else:
            self.address_note = _('Prefix {prefix} has no VLAN; pick the VLAN.').format(prefix=smallest[0])

    def choose(self, name, queryset, default):
        """
        The chosen object of field name. When nothing valid is chosen, default
        (if it is in queryset) is selected, shown as chosen in the popup, and
        returned; but when the user picked the empty choice on purpose, that
        stays: None.
        """
        if found := self.pick(name, queryset):
            return found
        if default is not None and not queryset.filter(pk=default.pk).exists():
            default = None
        if name in self.data and not self.data[name]:
            return None
        if default is not None:
            self.data[name] = str(default.pk)
        return default

    def pick(self, name, queryset):
        """The chosen object of field name when it is in queryset, else None."""
        value = self.data.get(name)
        if not value or not str(value).isdigit():
            return None
        return queryset.filter(pk=value).first()

    def missing(self):
        """Labels of what the popup still needs before Add IP can do anything."""
        names = [
            name for name in ('site', 'role')
            if name in self.fields and not self.pick(name, self.fields[name].queryset)
        ]
        if self.vlan is None:
            names.append('vlan')
        return [str(self.fields[name].label) for name in names]

    def clean(self):
        data = super().clean()
        if self.confirm:
            for name in ('site', 'role', 'vlan'):
                if name in self.fields and not data.get(name):
                    self.add_error(name, _('Required.'))
        return data

    def error_text(self):
        """The form's errors in one line, for a message: 'VLAN: Required.; Site: ...'."""
        parts = []
        for name, errors in self.errors.items():
            text = ' '.join(errors)
            parts.append(f'{self.fields[name].label}: {text}' if name in self.fields else text)
        return '; '.join(parts)


def possible_sites(vm):
    """
    The sites a VM without one may get: those its cluster's scope allows (or
    its host device's site), so NetBox doesn't refuse the pick on save.
    """
    sites = Site.objects.all()
    device = getattr(vm, 'device', None)
    if device is not None and device.site_id:
        return sites.filter(pk=device.site_id)
    cluster = vm.cluster
    if cluster is None:
        return sites
    if cluster._site_id:
        return sites.filter(pk=cluster._site_id)
    if cluster._site_group_id:
        return sites.filter(group__in=cluster._site_group.get_descendants(include_self=True))
    if cluster._region_id:
        return sites.filter(region__in=cluster._region.get_descendants(include_self=True))
    return sites


def narrowest_group(groups, obj):
    """
    The VLAN group to pick for obj (placed at the popup's site and location)
    from groups, or None. The only group on offer; otherwise the narrowest
    scope with groups decides: location (deepest first), then site, site
    group and region (deepest first). One group there is picked; several
    there are left for the user.
    """
    found = list(groups[:2])
    if len(found) < 2:
        return found[0] if found else None
    site = obj.site
    location = getattr(obj, 'location', None)
    scopes = []
    if location is not None:
        scopes += list(location.get_ancestors(ascending=True, include_self=True))
    if site is not None:
        scopes.append(site)
        if site.group_id:
            scopes += list(site.group.get_ancestors(ascending=True, include_self=True))
        if site.region_id:
            scopes += list(site.region.get_ancestors(ascending=True, include_self=True))
    for scope in scopes:
        at_scope = list(groups.filter(
            scope_type=ContentType.objects.get_for_model(scope), scope_id=scope.pk,
        )[:2])
        if at_scope:
            return at_scope[0] if len(at_scope) == 1 else None
    return None
