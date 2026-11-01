"""
The Add IP button: create (or reuse) the rule's interface, put the rule's
VLAN on it, create the next free address there and make it the primary IP.

It plans again under NetBox's available-ips lock, so the address is free at
that moment even if the page was open for a while. Everything is written
like a user would (full_clean(), save(), change log) and checked against
the user's object permissions; one failure rolls it all back.

With netbox-change-approval installed, the interface, the address and the
primary IP change of one click are one approval request (approval_batch()).
"""
from contextlib import nullcontext
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import router, transaction
from django.urls import reverse
from django.utils.translation import gettext as _
from django_pg_utils import advisory_lock

from dcim.choices import InterfaceModeChoices
from dcim.models import Interface
from ipam.models import IPAddress
from netbox.constants import ADVISORY_LOCK_KEYS
from virtualization.models import VMInterface

from . import naming
from .plan import is_device, plan_for

try:
    # Optional: the change approval plugin groups requests that share a batch ID into one approval.
    from netbox_change_approval.context import batch_scope, current_batch
except ImportError:
    batch_scope = current_batch = None


def permissions_for(obj):
    """The model permissions Add IP needs on a device or VM."""
    meta = obj._meta
    interface = 'dcim.add_interface' if is_device(obj) else 'virtualization.add_vminterface'
    return ['ipam.add_ipaddress', interface, f'{meta.app_label}.change_{meta.model_name}']


def urls_for(obj):
    """The Add IP and popup URLs of a device or VM, as (add_url, popup_url)."""
    model = obj._meta.model_name
    return (
        reverse(f'plugins:netbox_nextip:add_ip_{model}', args=[obj.pk]),
        reverse(f'plugins:netbox_nextip:add_ip_popup_{model}', args=[obj.pk]),
    )


def assign(obj, user, choice=None):
    """
    Add the planned address to the device or VM obj, as user. Returns the new
    IPAddress, or None when there is nothing to add. Raises PermissionDenied
    or ValidationError, and writes nothing, when a write is not allowed.

    choice: the Add IP popup's answers (forms.AddIPForm): 'vlan', an
    optional typed 'ip_address', and 'site' and 'role' when the object has
    none. Site and role are saved first, so a rule may match after all.
    """
    choice = choice or {}
    using = router.db_for_write(IPAddress)
    with approval_batch(), advisory_lock(ADVISORY_LOCK_KEYS['available-ips']), transaction.atomic(using=using):
        # Load the object again under the lock: a second click (or another
        # user) that waited for the lock must see the primary IP the first
        # one set, or it would add a second address.
        obj.refresh_from_db()
        changed_obj = fill_in(obj, choice)
        plan = plan_for(obj, vlan=choice.get('vlan'), address=choice.get('ip_address') or None)
        if plan is not None and plan.problem_text:
            # A typed address that is taken or not in the VLAN: say why instead of adding another one.
            raise ValidationError(plan.problem_text)
        if plan is None or not plan.address:
            if changed_obj:
                # Don't keep a half-done popup: roll back the site and role too.
                transaction.set_rollback(True, using=using)
            return None
        # The popup only offers VLANs the object may use; check again on the object as it is saved.
        if not plan.rule.pk and not plan.rule.vlan_available(obj):
            raise ValidationError(
                _('VLAN {vlan} is not available to {object}.').format(vlan=plan.rule.vlan, object=obj),
            )
        message = changelog_message(plan.rule)
        interface, action = prepare_interface(obj, plan, message)
        ip = IPAddress(
            address=plan.address,
            vrf=plan.suggestion.vrf,
            tenant=plan.suggestion.tenant,
            status=plan.rule.ip_status,
            role=plan.rule.ip_role,
            dns_name=naming.dns_name(plan.rule, obj, interface.name),
            assigned_object=interface,
        )
        ip._changelog_message = message
        ip.full_clean()
        ip.save()
        if plan.rule.make_primary:
            # Reload first: creating the interface raised the object's interface counter in the
            # database, and saving the stale copy would write the old count back (and a change
            # approval plugin would see it as a change).
            obj.refresh_from_db()
            obj.snapshot()
            obj.primary_ip4 = ip
            obj._changelog_message = message
            obj.save()
            # Another plugin (such as a change approval one) may hold the change back. Then the address
            # exists but is not primary yet, and the view says so.
            ip.primary_held = not type(obj).objects.filter(pk=obj.pk, primary_ip4=ip).exists()
        check_permissions(user, obj, ip, interface, action, changed_obj or plan.rule.make_primary)
    return ip


def approval_batch():
    """
    With netbox-change-approval: every write of one Add IP that needs
    approval (interface, address, primary IP, popup site and role) gets the
    same batch ID, so approvers see, approve or reject them as one request,
    and are notified once. Without it, or inside a batch already open (such
    as a bulk action), nothing changes. A change set the user has open still
    takes them all in, as it does with any change.
    """
    if batch_scope is None or current_batch.get() is not None:
        return nullcontext()
    return batch_scope(uuid4())


def fill_in(obj, choice):
    """Save the popup's site and role on obj when it has none. True when obj changed."""
    fields = {
        field: choice[field] for field in ('site', 'role')
        if choice.get(field) and not getattr(obj, f'{field}_id')
    }
    if not fields:
        return False
    obj.snapshot()
    for field, value in fields.items():
        setattr(obj, field, value)
    obj._changelog_message = _('Next IP: set in Add IP')
    obj.full_clean()
    obj.save()
    return True


def changelog_message(rule):
    """What the change log says about the objects Add IP writes."""
    if rule.pk:
        return _('Next IP: rule {rule}').format(rule=rule.name)
    return _('Next IP: VLAN {vlan} picked in Add IP (no rule)').format(vlan=rule.vlan)


def prepare_interface(obj, plan, message):
    """
    (interface, action): the planned interface with the rule's VLAN as its
    untagged VLAN, and 'add' when it was created, 'change' when it was
    changed, None when it was fine as it was.
    """
    rule = plan.rule
    interface = plan.interface
    if interface is None:
        action = 'add'
        if rule.for_devices:
            interface = Interface(device=obj, type=rule.interface_type, mgmt_only=rule.mgmt_only)
        else:
            interface = VMInterface(virtual_machine=obj)
        interface.name = plan.interface_name
    elif interface.untagged_vlan_id == rule.vlan_id:
        return interface, None
    else:
        action = 'change'
        interface.snapshot()
    interface._changelog_message = message
    interface.mode = interface.mode or InterfaceModeChoices.MODE_ACCESS
    interface.untagged_vlan = rule.vlan
    interface.full_clean()
    interface.save()
    return interface, action


def check_permissions(user, obj, ip, interface, interface_action, changed_obj):
    """Like NetBox's own views: the objects as written must be in the user's object permissions."""
    checks = [(IPAddress, 'add', ip.pk)]
    if interface_action:
        checks.append((type(interface), interface_action, interface.pk))
    if changed_obj:
        checks.append((type(obj), 'change', obj.pk))
    for model, action, pk in checks:
        if not model.objects.restrict(user, action).filter(pk=pk).exists():
            raise PermissionDenied
