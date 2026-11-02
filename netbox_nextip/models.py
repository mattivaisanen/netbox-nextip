from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from dcim.choices import InterfaceTypeChoices
from ipam.choices import IPAddressRoleChoices, IPAddressStatusChoices
from ipam.models import VLAN
from netbox.models import NetBoxModel

from . import naming
from .choices import AddressOrderChoices, RuleObjectChoices

SCOPE_ERROR = _(
    'Give a region, use a VLAN from a VLAN group that has a scope or, for virtual machines, give clusters, '
    'so the rule never applies everywhere by accident.'
)


class IPRule(NetBoxModel):
    """
    Which devices (or VMs) get an address, from which VLAN, on which new
    interface and how the address is picked. for_object() returns the rule
    of a device or VM; see the ordering there.
    """
    name = models.CharField(verbose_name=_('name'), max_length=100, unique=True)
    priority = models.PositiveIntegerField(
        verbose_name=_('priority'), default=100,
        help_text=_('Lowest first. With equal priority, the rule with the narrowest scope wins.'),
    )
    enabled = models.BooleanField(verbose_name=_('enabled'), default=True)
    description = models.CharField(verbose_name=_('description'), max_length=200, blank=True)

    # Who the rule is for. Every filled-in field must match.
    object_type = models.CharField(
        verbose_name=_('applies to'), max_length=20,
        choices=RuleObjectChoices, default=RuleObjectChoices.DEVICE,
    )
    device_types = models.ManyToManyField(
        to='dcim.DeviceType', verbose_name=_('device types'), related_name='+', blank=True,
        help_text=_('Devices of one of these types. Empty: any type.'),
    )
    roles = models.ManyToManyField(
        to='dcim.DeviceRole', verbose_name=_('roles'), related_name='+', blank=True,
        help_text=_('Devices or virtual machines with one of these roles. Empty: any role.'),
    )
    clusters = models.ManyToManyField(
        to='virtualization.Cluster', verbose_name=_('clusters'), related_name='+', blank=True,
        help_text=_('Virtual machines in one of these clusters. Empty: any cluster.'),
    )
    region = models.ForeignKey(
        to='dcim.Region', verbose_name=_('region'), on_delete=models.PROTECT, related_name='+',
        blank=True, null=True, help_text=_('Sites in this region or one below it.'),
    )
    site_group = models.ForeignKey(
        to='dcim.SiteGroup', verbose_name=_('site group'), on_delete=models.PROTECT, related_name='+',
        blank=True, null=True, help_text=_('Sites in this group or one below it.'),
    )
    site = models.ForeignKey(
        to='dcim.Site', verbose_name=_('site'), on_delete=models.PROTECT, related_name='+',
        blank=True, null=True,
    )
    location = models.ForeignKey(
        to='dcim.Location', verbose_name=_('location'), on_delete=models.PROTECT, related_name='+',
        blank=True, null=True, help_text=_('Devices in this location or one below it.'),
    )

    # Where the address comes from and goes.
    vlan = models.ForeignKey(
        to='ipam.VLAN', verbose_name=_('VLAN'), on_delete=models.PROTECT, related_name='+',
        help_text=_(
            'The address comes from this VLAN. A device the VLAN is not available to (by its site or VLAN '
            'group scope) never matches the rule.'
        ),
    )
    interface_name = models.CharField(
        verbose_name=_('interface name'), max_length=64, default='Vlan{vid}',
        help_text=_(
            'Name of the new interface. Fields: {vid}, {vlan} (VLAN name) and {n}, the lowest number from 0 '
            'that gives a name not in use yet. Without {n}, an existing interface with this name and no other '
            'VLAN is used instead of creating one.'
        ),
    )
    interface_type = models.CharField(
        verbose_name=_('interface type'), max_length=50,
        choices=InterfaceTypeChoices, default=InterfaceTypeChoices.TYPE_VIRTUAL,
        help_text=_('Devices only. VM interfaces have no type.'),
    )
    mgmt_only = models.BooleanField(
        verbose_name=_('management only'), default=False,
        help_text=_('Devices only: mark the new interface management-only.'),
    )

    # How the address is picked and what it gets.
    order = models.CharField(
        verbose_name=_('order'), max_length=20,
        choices=AddressOrderChoices, default=AddressOrderChoices.AFTER_LAST,
    )
    fill_gaps = models.BooleanField(
        verbose_name=_('fill gaps'), default=False,
        help_text=_('Also use free addresses between used ones.'),
    )
    skip_first = models.PositiveSmallIntegerField(
        verbose_name=_('skip first'), default=0,
        help_text=_('More addresses at the start of a prefix never handed out, after the network address and '
                    'the gateway. Not used for IP ranges.'),
    )
    skip_last = models.PositiveSmallIntegerField(
        verbose_name=_('skip last'), default=0,
        help_text=_('More addresses at the end of a prefix never handed out, before the broadcast address. '
                    'Not used for IP ranges.'),
    )
    ip_status = models.CharField(
        verbose_name=_('IP status'), max_length=50,
        choices=IPAddressStatusChoices, default=IPAddressStatusChoices.STATUS_ACTIVE,
    )
    ip_role = models.CharField(
        verbose_name=_('IP role'), max_length=50, choices=IPAddressRoleChoices, blank=True,
    )
    dns_name = models.CharField(
        verbose_name=_('DNS name'), max_length=255, blank=True,
        help_text=_('Template, such as {device}.example.com. Fields: {device}, {interface}, {vid}, {vlan}, '
                    '{site}. Empty: none.'),
    )
    make_primary = models.BooleanField(
        verbose_name=_('make primary'), default=True,
        help_text=_('The new address becomes the primary IPv4 of the device or VM.'),
    )

    class Meta:
        ordering = ('priority', 'name')
        verbose_name = _('IP rule')
        verbose_name_plural = _('IP rules')

    def __str__(self):
        return self.name

    @property
    def for_devices(self):
        return self.object_type == RuleObjectChoices.DEVICE

    def clean(self):
        super().clean()
        errors = {}
        if not self.for_devices and self.location_id:
            errors['location'] = _('Virtual machines have no location.')
        elif self.location_id and self.site_id and self.location.site_id != self.site_id:
            # Such a rule could never match.
            errors['location'] = _('The location is not in the rule\'s site.')
        if self.for_devices and not self.has_scope(has_clusters=False):
            # VM rules may be scoped by clusters, which are saved after clean(): related_errors() checks those.
            errors['region'] = SCOPE_ERROR
        for field, check in (('interface_name', naming.check_interface_name), ('dns_name', naming.check_dns_name)):
            if error := check(getattr(self, field)):
                errors[field] = error
        if errors:
            raise ValidationError(errors)

    @staticmethod
    def related_errors(object_type, region, vlan, device_types, clusters):
        """
        Errors about the many-to-many fields, which model validation can't
        see on a new rule. Used by the form and the API serializer.
        """
        errors = {}
        if object_type == RuleObjectChoices.DEVICE and clusters:
            errors['clusters'] = _('Clusters are for virtual machine rules.')
        if object_type == RuleObjectChoices.VIRTUAL_MACHINE:
            if device_types:
                errors['device_types'] = _('Device types are for device rules.')
            rule = IPRule(object_type=object_type, region=region, vlan=vlan)
            if not rule.has_scope(has_clusters=bool(clusters)):
                errors['region'] = SCOPE_ERROR
        return errors

    def has_scope(self, has_clusters):
        """
        False when the rule could apply everywhere. A rule needs a region, a
        VLAN from a VLAN group with a scope, or (VM rules) clusters.
        """
        return bool(self.region_id or self.vlan_group_scoped or (has_clusters and not self.for_devices))

    @property
    def scope_lost(self):
        """True for a saved rule that has no scope any more (see matches()). Shown on the rule page."""
        return not self.has_scope(has_clusters=self.clusters.exists())

    @property
    def vlan_group_scoped(self):
        """True when the rule's VLAN is in a VLAN group with a scope (region, site, cluster...)."""
        vlan = self.vlan if self.vlan_id else None
        return bool(vlan and vlan.group_id and vlan.group.scope_type_id)

    def scope_depth(self):
        """
        Sort key part: narrower scopes first. Location before site, site group
        and region, deeper in the tree before higher up, and a rule with device
        types or clusters before one without, then one with roles before one
        without. A rule with none of the place
        fields counts with the scope of its VLAN's group, so a rule whose VLAN
        group is scoped to one location is not taken for the broadest one.
        """
        def depth(node):
            return -node.level if node else 0

        location, site, site_group, region, cluster = self.location, self.site, self.site_group, self.region, None
        if not (location or site or site_group or region) and self.vlan_group_scoped:
            scope = self.vlan.group.scope
            kind = self.vlan.group.scope_type.model
            location = scope if kind == 'location' else None
            site = scope if kind == 'site' else None
            site_group = scope if kind == 'sitegroup' else None
            region = scope if kind == 'region' else None
            cluster = scope if kind in ('cluster', 'clustergroup') else None
        return (
            location is None, depth(location), site is None,
            site_group is None, depth(site_group), region is None, depth(region),
            not (self.device_types.all() or self.clusters.all() or cluster),
            not self.roles.all(),
        )

    def matches(self, obj):
        """True when this rule is for the device or VM obj."""
        if obj._meta.model_name != self.object_type:
            return False
        if not self.has_scope(has_clusters=bool(self.clusters.all())):
            # The scope was lost after the rule was saved (its VLAN group lost its scope, or the VLAN
            # left the group): never apply it everywhere.
            return False
        roles = {r.pk for r in self.roles.all()}
        if roles and obj.role_id not in roles:
            return False
        if self.for_devices:
            types = {t.pk for t in self.device_types.all()}
            if types and obj.device_type_id not in types:
                return False
            if self.location_id and not _within(obj.location, self.location):
                return False
        else:
            clusters = {c.pk for c in self.clusters.all()}
            if clusters and obj.cluster_id not in clusters:
                return False
        site = obj.site
        if self.site_id and (site is None or site.pk != self.site_id):
            return False
        if self.region_id and not _within(site and site.region, self.region):
            return False
        if self.site_group_id and not _within(site and site.group, self.site_group):
            return False
        return self.vlan_available(obj)

    def vlan_available(self, obj):
        """True when NetBox lets obj use the rule's VLAN (by site or VLAN group scope)."""
        if self.for_devices:
            vlans = VLAN.objects.get_for_device(obj)
        else:
            vlans = VLAN.objects.get_for_virtualmachine(obj)
        return vlans.filter(pk=self.vlan_id).exists()

    @classmethod
    def for_object(cls, obj):
        """The rule for a device or VM, or None."""
        rules = cls.objects.filter(enabled=True, object_type=obj._meta.model_name).select_related(
            'vlan__group__scope_type', 'region', 'site_group', 'site', 'location',
        ).prefetch_related('device_types', 'roles', 'clusters')
        rules = sorted(rules, key=lambda rule: (rule.priority, rule.scope_depth(), rule.name))
        return next((rule for rule in rules if rule.matches(obj)), None)


def _within(node, ancestor):
    """True when the region, site group or location node is ancestor or below it."""
    return node is not None and node.get_ancestors(include_self=True).filter(pk=ancestor.pk).exists()
