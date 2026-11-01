"""
What the Add IP button of a device or VM would do: which rule, which
interface and which address. Shown on the device page and done by
assign.py. Reads only.

The interface: a device or VM with exactly one interface gets the address
there, when it can take the rule's VLAN without losing its own (see
takes_vlan()). Otherwise a new interface named by the rule's template (or
the existing one with that name).
"""
import copy
from dataclasses import dataclass

from dcim.choices import InterfaceModeChoices
from ipam.models import VLAN, IPRange, Prefix

from . import naming
from .allocation import TYPED_PROBLEMS, Suggestion, check_address, suggest
from .models import IPRule

# Why the interface can't be used.
NO_NAME = 'no-name'                # every {n} name is in use
INTERFACE_IN_USE = 'in-use'        # the named interface is in another VLAN, a trunk, disabled or a LAG member
BAD_TEMPLATE = 'bad-template'      # the rule's name templates fail today's checks (saved before them)


@dataclass
class Plan:
    rule: IPRule
    interface_name: str | None
    interface: object | None = None     # the existing interface to use, or None: create one
    suggestion: Suggestion | None = None
    problem: str | None = None      # NO_NAME, INTERFACE_IN_USE or the suggestion's problem

    @property
    def address(self):
        return None if self.problem else self.suggestion.address

    @property
    def problem_text(self):
        """Why a typed address can't be used, in words; None for other problems."""
        return TYPED_PROBLEMS.get(self.problem)


def plan_for(obj, vlan=None, address=None):
    """
    The Plan for a device or VM, or None when it has a primary IPv4 or no
    rule matches. With vlan (picked in the Add IP popup), the matching rule
    is used when it has that VLAN, otherwise the default rule for that VLAN
    (default_rule()). With address (typed in the popup), that address is
    checked and used instead of the next free one.
    """
    if obj.primary_ip4_id:
        return None
    rule = IPRule.for_object(obj)
    if vlan is not None and (rule is None or rule.vlan_id != vlan.pk):
        rule = default_rule(obj, vlan)
    if rule is None:
        return None
    interfaces = {interface.name: interface for interface in obj.interfaces.all()}
    suggestion = check_address(rule.vlan, address) if address else suggest(rule)
    if naming.check_interface_name(rule.interface_name) or naming.check_dns_name(rule.dns_name):
        # A rule saved before the template checks got stricter: say so rather than make a junk name.
        return Plan(rule, None, suggestion=suggestion, problem=BAD_TEMPLATE)
    if len(interfaces) == 1:
        only = next(iter(interfaces.values()))
        if takes_vlan(only, rule.vlan_id):
            return Plan(rule, only.name, interface=only, suggestion=suggestion, problem=suggestion.problem)
    name = naming.interface_name(rule, interfaces)
    plan = Plan(rule, name, interface=interfaces.get(name), suggestion=suggestion)
    if name is None:
        plan.problem = NO_NAME
    elif plan.interface and not takes_vlan(plan.interface, rule.vlan_id):
        plan.problem = INTERFACE_IN_USE
    else:
        plan.problem = plan.suggestion.problem
    return plan


def takes_vlan(interface, vlan_id):
    """
    True when the interface may get vlan_id as its untagged VLAN: it has it
    already, or it is not an 802.1Q trunk and has no untagged VLAN yet. A
    trunk (tagged, tagged all, Q-in-Q) is never changed, because setting its
    untagged VLAN would change the native VLAN of an uplink. A disabled
    interface or a LAG member is never used.
    """
    if not interface.enabled or getattr(interface, 'lag_id', None):
        return False
    if interface.untagged_vlan_id == vlan_id:
        return True
    return interface.untagged_vlan_id is None and interface.mode in ('', None, InterfaceModeChoices.MODE_ACCESS)


def default_rule(obj, vlan):
    """
    An unsaved rule with every default, for the Add IP popup of a device no
    rule matches: the address after the last used one in the VLAN, on the
    only interface or a new Vlan<vid> interface, made primary.
    """
    return IPRule(name='', object_type=obj._meta.model_name, vlan=vlan)


def placed(obj, site=None, location=None):
    """
    A copy of obj (not saved) with the given site and location, to ask which
    VLANs it could use there. Unchanged fields stay as they are; obj itself
    is not touched (Django copies the instance state and its cache).
    """
    probe = copy.copy(obj)
    if site is not None:
        probe.site = site
    if location is not None and hasattr(probe, 'location'):
        probe.location = location
    return probe


def view_flags(plan, user):
    """
    Template flags: may the user see the plan's VLAN and the prefix or range
    the address comes from? Object permissions count, not only model ones.
    """
    if plan is None:
        return {'can_view_vlan': False, 'can_view_prefix': False}
    suggestion = plan.suggestion
    source = suggestion and (suggestion.range or suggestion.prefix)
    source_model = IPRange if suggestion and suggestion.range else Prefix
    return {
        'can_view_vlan': VLAN.objects.restrict(user, 'view').filter(pk=plan.rule.vlan_id).exists(),
        'can_view_prefix': bool(source) and source_model.objects.restrict(user, 'view').filter(pk=source.pk).exists(),
    }


def is_device(obj):
    """True for a device, False for a virtual machine."""
    return obj._meta.model_name == 'device'


def available_vlans(obj):
    """The VLANs NetBox lets the device or VM use (by site, location, cluster and VLAN group scope)."""
    if is_device(obj):
        return VLAN.objects.get_for_device(obj)
    return VLAN.objects.get_for_virtualmachine(obj)
