"""
The Assign button on a device or VM: create the planned addresses (one per
family), the interface when the plan needs a new one, and make each address
the primary IP.

It plans again under NetBox's available-ips lock, so the address is free at
that moment even if the page was open for a while. Everything is written
like a user would (full_clean(), save(), change log) and checked against
the user's object permissions; one failure rolls it all back.
"""
from django.core.exceptions import PermissionDenied
from django.db import router, transaction
from django_pg_utils import advisory_lock

from dcim.models import Interface
from ipam.models import IPAddress
from netbox.constants import ADVISORY_LOCK_KEYS
from virtualization.models import VMInterface

from .new_address import dns_name
from .plan import plan_for
from .settings import get_setting


def permissions_for(obj):
    """
    The permissions Assign needs on a device or VM: add IP addresses and
    change the device (its primary IP). Adding an interface is checked when
    one is added.
    """
    meta = obj._meta
    return ['ipam.add_ipaddress', f'{meta.app_label}.change_{meta.model_name}']


def assign(obj, user):
    """
    Create the planned addresses for the device or VM obj, as user. Returns
    the new IPAddress objects (none when there was nothing free). Raises
    PermissionDenied or ValidationError, and writes nothing, when one of the
    writes is not allowed.
    """
    using = router.db_for_write(IPAddress)
    with advisory_lock(ADVISORY_LOCK_KEYS['available-ips']), transaction.atomic(using=using):
        new_interface = None
        created = []
        for plan in plan_for(obj):
            if not plan.address:
                continue
            interface = plan.interface
            if interface is None:
                new_interface = new_interface or create_interface(obj, plan.interface_name)
                interface = new_interface
            created.append(create_address(interface, plan.suggestion))

        if created:
            obj.snapshot()
            for ip in created:
                setattr(obj, f'primary_ip{ip.family}', ip)
            obj.save()
        check_permissions(user, obj, created, new_interface)
    return created


def create_interface(obj, name):
    if obj._meta.model_name == 'device':
        interface = Interface(device=obj, name=name, type='virtual')
    else:
        interface = VMInterface(virtual_machine=obj, name=name)
    interface.full_clean()
    interface.save()
    return interface


def create_address(interface, suggestion):
    ip = IPAddress(
        address=suggestion.address,
        vrf=suggestion.vrf,
        tenant=suggestion.tenant,
        dns_name=dns_name(interface, suggestion),
        status=get_setting('ip_status'),
        assigned_object=interface,
    )
    ip.full_clean()
    ip.save()
    return ip


def check_permissions(user, obj, addresses, interface):
    """Like NetBox's own views: the objects as written must be in the user's object permissions."""
    checks = [(IPAddress, 'add', [ip.pk for ip in addresses])]
    if addresses:
        checks.append((type(obj), 'change', [obj.pk]))
    if interface is not None:
        checks.append((type(interface), 'add', [interface.pk]))
    for model, action, pks in checks:
        if model.objects.restrict(user, action).filter(pk__in=pks).count() != len(pks):
            raise PermissionDenied
