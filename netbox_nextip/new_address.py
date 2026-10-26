"""
What a new address gets besides the address itself: a DNS name from the
dns_name setting, and whether it becomes the primary IP of its device or VM
(primary_ip setting). Used by the Assign link, the API and bulk assign.
"""
from django.core.exceptions import ImproperlyConfigured
from django.utils.text import slugify

from .settings import get_setting


def dns_name(interface, suggestion):
    """
    The dns_name template filled in, or '' when there is none (or the device
    has no name). Each part becomes a DNS label, so 'Gi1/0/1' becomes 'gi1-0-1'.
    """
    template = get_setting('dns_name')
    parent = interface.parent_object
    if not template or not parent.name:
        return ''
    site = getattr(parent, 'site', None)
    return template.format(
        # A device named as an FQDN keeps its dots: 'sw1.lab' -> 'sw1.lab'.
        device='.'.join(_label(part) for part in parent.name.split('.')),
        interface=_label(interface.name),
        vlan=_label(suggestion.vlan.name),
        vid=suggestion.vlan.vid,
        site=site.slug if site else '',
    ).lower()


def check_dns_name():
    """Fail at startup, not on every interface page, when dns_name has an unknown field."""
    try:
        get_setting('dns_name').format(device='', interface='', vlan='', vid=0, site='')
    except (KeyError, IndexError, ValueError) as error:
        raise ImproperlyConfigured(f"netbox_nextip: bad dns_name template: {error!r}")


def _label(text):
    """text as a DNS label: 'Gi1/0/1.100' -> 'gi1-0-1-100'."""
    for char in '/._':
        text = text.replace(char, '-')
    return slugify(text)


def becomes_primary(interface, family):
    """
    True when primary_ip is on and the device or VM has no primary IP of
    this family. Asks the database, so a bulk assign that already gave
    another interface of the device the primary IP sees it.
    """
    if not get_setting('primary_ip'):
        return False
    parent = interface.parent_object
    return type(parent).objects.filter(pk=parent.pk, **{f'primary_ip{family}__isnull': True}).exists()


def make_primary(ip, preview=False):
    """
    Make ip the primary IP of its device or VM for its family. A preview
    writes only the column (no change log or events), for a transaction
    that is rolled back.
    """
    parent = ip.assigned_object.parent_object
    field = f'primary_ip{ip.family}'
    if preview:
        type(parent).objects.filter(pk=parent.pk).update(**{field: ip})
        return
    parent.snapshot()
    setattr(parent, field, ip)
    parent.save()
