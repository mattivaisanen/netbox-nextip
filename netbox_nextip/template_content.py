from ipam.models import IPAddress
from netbox.plugins import PluginTemplateExtension

from .assign import permissions_for, urls_for
from .plan import is_device, plan_for, view_flags


class DeviceNextIP(PluginTemplateExtension):
    """
    The "Next IP" card on a device or VM without a primary IPv4: its rule,
    VLAN, the address and interface Add IP would create, and the button
    (views.AddIPView). When no rule matches, the button opens the Add IP
    popup instead (views.AddIPPopupView), for users who may add addresses.
    """
    models = ('dcim.device', 'virtualization.virtualmachine')

    def right_page(self):
        obj = self.context['object']
        if obj.primary_ip4_id:
            return ''
        plan = self.plan(obj)
        can_add = self.context['request'].user.has_perms(permissions_for(obj))
        if plan is None and not can_add:
            return ''
        add_url, popup_url = urls_for(obj)
        return self.render('netbox_nextip/inc/device_panel.html', extra_context={
            'plan': plan,
            'add_url': add_url,
            'popup_url': popup_url,
            'can_add': can_add,
            **view_flags(plan, self.context['request'].user),
        })

    def buttons(self):
        """
        "Add IP address" in the button bar, next to Add Components, while no
        interface of the device or VM has an IP address yet.
        """
        obj = self.context['object']
        if obj.primary_ip4_id or not self.context['request'].user.has_perms(permissions_for(obj)):
            return ''
        if IPAddress.objects.filter(**{f'{interface_field(obj)}__in': obj.interfaces.all()}).exists():
            return ''
        add_url, popup_url = urls_for(obj)
        return self.render('netbox_nextip/inc/add_ip_button.html', extra_context={
            'plan': self.plan(obj),
            'add_url': add_url,
            'popup_url': popup_url,
        })

    def plan(self, obj):
        """
        plan_for(obj), worked out once per page: the card and the button
        both need it, and it reads every used address of the VLAN.
        """
        plans = self.context['request'].__dict__.setdefault('_nextip_plans', {})
        key = (obj._meta.label_lower, obj.pk)
        if key not in plans:
            plans[key] = plan_for(obj)
        return plans[key]


def interface_field(obj):
    """The IPAddress relation to the interfaces of a device or a VM."""
    return 'interface' if is_device(obj) else 'vminterface'


template_extensions = [DeviceNextIP]
