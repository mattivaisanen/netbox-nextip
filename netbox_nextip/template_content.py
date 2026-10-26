from urllib.parse import urlencode

from django.urls import reverse

from netbox.plugins import PluginTemplateExtension

from .allocation import suggest_for_vlan
from .assign import permissions_for
from .plan import plan_for
from .settings import get_setting


class DeviceNextIP(PluginTemplateExtension):
    """
    The suggested IP at the top of a device or VM page, with an Assign
    button that creates it and makes it primary (views.AssignView). Shown
    only when a suggestion rule matches and the device lacks a primary IP.
    """
    models = ('dcim.device', 'virtualization.virtualmachine')

    def alerts(self):
        if not get_setting('device_panel'):
            return ''
        obj = self.context['object']
        plans = plan_for(obj)
        if not plans:
            return ''
        return self.render('netbox_nextip/inc/device_panel.html', extra_context={
            'plans': plans,
            'assign_url': reverse(f'plugins:netbox_nextip:assign_{obj._meta.model_name}', args=[obj.pk]),
            'assignable': any(plan.address for plan in plans),
            'can_assign': self.context['request'].user.has_perms(permissions_for(obj)),
        })


class VLANNextIP(PluginTemplateExtension):
    """
    The "Next free IP" panel on a VLAN: the next address per family. Add
    opens NetBox's IP address form with it filled in.
    """
    models = ('ipam.vlan',)

    def right_page(self):
        if not get_setting('vlan_panel'):
            return ''
        vlan = self.context['object']
        suggestions = [suggest_for_vlan(vlan, family) for family in get_setting('families')]
        for suggestion in suggestions:
            suggestion.add_url = add_url(suggestion, vlan.get_absolute_url()) if suggestion.address else None
        return self.render('netbox_nextip/inc/vlan_panel.html', extra_context={
            'suggestions': suggestions,
        })


def add_url(suggestion, return_url):
    """NetBox's IP address form, filled in with the suggestion."""
    params = {'address': suggestion.address, 'status': get_setting('ip_status'), 'return_url': return_url}
    if suggestion.vrf:
        params['vrf'] = suggestion.vrf.pk
    if suggestion.tenant:
        params['tenant'] = suggestion.tenant.pk
    return f"{reverse('ipam:ipaddress_add')}?{urlencode(params)}"


template_extensions = [DeviceNextIP, VLANNextIP]
