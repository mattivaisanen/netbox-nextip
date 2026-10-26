from django.db import models
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel


class SuggestionRule(NetBoxModel):
    """
    Which devices and VMs get a suggested IP, and from which VLANs. Rules are
    tried by priority, lowest first; the first enabled rule that matches is
    used. A device or VM no rule matches gets no suggestion. See plan.py.
    """
    name = models.CharField(verbose_name=_('name'), max_length=100, unique=True)
    priority = models.PositiveIntegerField(
        verbose_name=_('priority'), default=100,
        help_text=_('Rules are tried from the lowest priority up. The first one that matches is used.'),
    )
    enabled = models.BooleanField(verbose_name=_('enabled'), default=True)
    roles = models.ManyToManyField(
        to='dcim.DeviceRole', verbose_name=_('roles'), related_name='+', blank=True,
        help_text=_('Devices and VMs with one of these roles. Empty: any role.'),
    )
    device_types = models.ManyToManyField(
        to='dcim.DeviceType', verbose_name=_('device types'), related_name='+', blank=True,
        help_text=_('Devices of one of these types. Empty: any type. A rule with types never matches a VM.'),
    )
    vlans = models.ManyToManyField(
        to='ipam.VLAN', verbose_name=_('VLANs'), related_name='+', blank=True,
        help_text=_(
            'Addresses come only from these VLANs. When no interface is in one, the VLAN available at the '
            "device's site is used. Empty: the VLAN of the device's interfaces."
        ),
    )
    interface_name = models.CharField(
        verbose_name=_('interface name'), max_length=64, default='mgmt0',
        help_text=_(
            'Where the address goes when no interface is in a VLAN: this interface, else the management-only '
            "interface, else the device's only interface. Created when there is none of those."
        ),
    )
    description = models.CharField(verbose_name=_('description'), max_length=200, blank=True)

    class Meta:
        ordering = ('priority', 'name')
        verbose_name = _('suggestion rule')
        verbose_name_plural = _('suggestion rules')

    def __str__(self):
        return self.name

    def matches(self, obj):
        """True when this rule is for the device or VM obj."""
        roles = {role.pk for role in self.roles.all()}
        types = {device_type.pk for device_type in self.device_types.all()}
        if roles and obj.role_id not in roles:
            return False
        return not types or getattr(obj, 'device_type_id', None) in types

    @classmethod
    def for_object(cls, obj):
        """The rule for a device or VM, or None."""
        rules = cls.objects.filter(enabled=True).prefetch_related('roles', 'device_types', 'vlans')
        return next((rule for rule in rules if rule.matches(obj)), None)
