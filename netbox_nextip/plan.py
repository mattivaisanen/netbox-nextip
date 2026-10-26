"""
Which address a device or VM gets, and on which interface: the suggestion
on the device page and what its Assign button creates.

The SuggestionRule for the device decides whether it gets one at all, and
from which VLANs. For each address family it has no primary IP of:

1. An interface in a VLAN (its own, or the cabled switch port's) gives the
   address: management-only interfaces first, then the rule's interface
   name, then the rest in name order. With VLANs on the rule, only those
   VLANs count, so a switch's access ports don't hand out user addresses.
2. Otherwise the address comes from the rule's VLANs, the ones available at
   the device's site (or VLAN group scope), and goes on the rule's
   interface name, else the management-only interface, else the device's
   only interface. With none of those, Assign creates the named interface.

Nothing here writes.
"""
from dataclasses import dataclass

from ipam.models import VLAN

from .allocation import first_free, suggest, suggest_for_vlan
from .models import SuggestionRule
from .settings import get_setting

NO_VLAN = 'no-vlan'  # no interface is in a VLAN, and the rule names none available here


@dataclass
class Plan:
    family: int
    rule: SuggestionRule
    interface: object = None    # an existing interface, or None: create interface_name
    interface_name: str = ''
    suggestion: object = None   # an allocation.Suggestion
    problem: str | None = None  # NO_VLAN, or the suggestion's problem

    @property
    def address(self):
        return self.suggestion.address if self.suggestion else None


def plan_for(obj):
    """
    One Plan per family in the families setting that the device or VM has no
    primary IP of. An empty list when no rule matches or nothing is missing.
    """
    rule = SuggestionRule.for_object(obj)
    if rule is None:
        return []
    interfaces = list(obj.interfaces.select_related('untagged_vlan', 'vrf'))
    plans = []
    for family in get_setting('families'):
        if not getattr(obj, f'primary_ip{family}_id'):
            plans.append(from_interfaces(rule, interfaces, family) or from_rule(obj, rule, interfaces, family))
    return plans


def from_interfaces(rule, interfaces, family):
    """The Plan from an interface's own VLAN, or None when no interface is in one."""
    allowed = {vlan.pk for vlan in rule.vlans.all()} or None
    first_problem = None
    for interface in sorted(interfaces, key=lambda i: preference(i, rule)):
        suggestions = suggest(interface, family=family, vlans=allowed)
        if not suggestions:
            continue
        plan = Plan(family, rule, interface, interface.name, suggestions[0])
        if found := first_free(suggestions):
            plan.suggestion = found[0]
            return plan
        first_problem = first_problem or plan
    if first_problem:
        first_problem.problem = first_problem.suggestion.problem
    return first_problem


def from_rule(obj, rule, interfaces, family):
    """The Plan from the rule's VLANs, on the interface the rule picks."""
    interface = pick_interface(interfaces, rule.interface_name)
    plan = Plan(family, rule, interface, interface.name if interface else rule.interface_name)
    vlans = available_vlans(obj, rule)
    if not vlans:
        plan.problem = NO_VLAN
        return plan
    vrf = interface.vrf if interface and interface.vrf_id and get_setting('match_interface_vrf') else None
    suggestions = [suggest_for_vlan(vlan, family, vrf) for vlan in vlans]
    found = first_free(suggestions)
    plan.suggestion = found[0] if found else suggestions[0]
    plan.problem = plan.suggestion.problem
    return plan


def preference(interface, rule):
    """Sort key: management-only first, then the rule's interface name, then name order."""
    return not getattr(interface, 'mgmt_only', False), interface.name != rule.interface_name


def pick_interface(interfaces, name):
    """The interface called name, else the management-only one, else the only one, else None."""
    for test in (lambda i: i.name == name, lambda i: getattr(i, 'mgmt_only', False)):
        if match := next((i for i in interfaces if test(i)), None):
            return match
    return interfaces[0] if len(interfaces) == 1 else None


def available_vlans(obj, rule):
    """The rule's VLANs that the device or VM can use (by site, VLAN group scope or global)."""
    pks = [vlan.pk for vlan in rule.vlans.all()]
    if not pks:
        return []
    if obj._meta.model_name == 'device':
        vlans = VLAN.objects.get_for_device(obj)
    else:
        vlans = VLAN.objects.get_for_virtualmachine(obj)
    return list(vlans.filter(pk__in=pks).order_by('vid'))
