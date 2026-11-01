"""
Keep rules from widening by themselves. A rule's device types and clusters
are many-to-many fields: when the last one is deleted, the empty list would
mean "any type" (or "any cluster"). Such a rule is disabled first, with a
change log entry saying why.

Two ways a deletion reaches a rule:
- With a request (UI, API), NetBox's own pre_delete handler removes the
  object from each rule's list first (an m2m "post_remove"), so the
  pre_delete receiver below finds no rule any more. rule_list_changed()
  catches that case.
- Without one (scripts, shell), the list rows just go with the object:
  entry_deleting() notes the rules before, entry_deleted() checks them after.
"""
from threading import local

from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import m2m_changed, post_delete, pre_delete
from django.dispatch import receiver
from django.utils.translation import gettext as _

try:
    # NetBox internal: the objects whose pre_delete it is handling in this thread.
    from core.signals import _signals_received
except ImportError:  # a later NetBox renamed it: only the delete receivers below are left
    _signals_received = None
from dcim.models import DeviceType
from virtualization.models import Cluster

from .models import IPRule

# Rule field -> (model of its entries, word for the change log message).
LIST_FIELDS = {
    'device_types': (DeviceType, _('device type')),
    'clusters': (Cluster, _('cluster')),
}


# Rules that list an object being deleted, per thread: (field, object pk, rule pk).
_pending = local()


@receiver(pre_delete, sender=DeviceType)
@receiver(pre_delete, sender=Cluster)
def entry_deleting(sender, instance, **kwargs):
    """Note the enabled rules that list instance; entry_deleted() checks them once the rows are gone."""
    field = 'device_types' if sender is DeviceType else 'clusters'
    pending = _pending.__dict__.setdefault('rules', set())
    for pk in IPRule.objects.filter(enabled=True, **{field: instance}).values_list('pk', flat=True):
        pending.add((field, instance.pk, pk))


@receiver(post_delete, sender=DeviceType)
@receiver(post_delete, sender=Cluster)
def entry_deleted(sender, instance, **kwargs):
    """
    Disable the noted rules whose list is empty now. Checked after the delete,
    so a bulk delete of all of a rule's entries at once is caught too.
    """
    field = 'device_types' if sender is DeviceType else 'clusters'
    pending = _pending.__dict__.setdefault('rules', set())
    entries = {entry for entry in pending if entry[:2] == (field, instance.pk)}
    pending.difference_update(entries)
    noted = {rule_pk for _field, _pk, rule_pk in entries}
    for rule in IPRule.objects.filter(pk__in=noted, enabled=True):
        if not getattr(rule, field).exists():
            disable(rule, field, instance)


@receiver(m2m_changed, sender=IPRule.device_types.through)
@receiver(m2m_changed, sender=IPRule.clusters.through)
def rule_list_changed(sender, instance, action, reverse, pk_set, **kwargs):
    """A rule's list lost its last entry because that entry is being deleted (not because of an edit)."""
    if action != 'post_remove' or reverse or not isinstance(instance, IPRule) or not instance.enabled:
        return
    field = 'device_types' if sender is IPRule.device_types.through else 'clusters'
    if getattr(instance, field).exists():
        return  # other entries are left, so the rule does not widen
    model = LIST_FIELDS[field][0]
    deleting = getattr(_signals_received, 'pre_delete', None) or set()
    object_type = ContentType.objects.get_for_model(model)
    deleted = [pk for pk in pk_set or () if (object_type, pk) in deleting]
    if deleted:
        disable(instance, field, model.objects.filter(pk=deleted[0]).first() or deleted[0])


def disable(rule, field, deleted):
    """Disable rule, with a change log message naming the deleted entry."""
    if getattr(rule, '_prechange_snapshot', None) is None:
        # NetBox's delete handler took one before removing the entry; keep it so the "before" lists it.
        rule.snapshot()
    rule.enabled = False
    rule._changelog_message = _('Next IP: disabled, its only {kind} {name} was deleted').format(
        kind=LIST_FIELDS[field][1], name=deleted,
    )
    rule.save()
