from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views.generic import View

from core.signals import clear_events
from dcim.models import Device
from netbox.views import generic
from utilities.views import ConditionalLoginRequiredMixin, register_model_view
from virtualization.models import VirtualMachine

from . import filtersets, forms, tables
from .assign import assign, permissions_for
from .models import SuggestionRule


class AssignView(ConditionalLoginRequiredMixin, View):
    """
    The Assign button on a device or VM page: create the suggested address
    (or addresses, one per family), make it primary and go back to the page.
    """
    model = None

    def post(self, request, pk):
        obj = get_object_or_404(self.model.objects.restrict(request.user, 'view'), pk=pk)
        if not request.user.has_perms(permissions_for(obj)):
            raise PermissionDenied
        try:
            created = assign(obj, request.user)
        except (PermissionDenied, ValidationError) as error:
            # Nothing was written, so drop the events queued for the rolled-back objects.
            clear_events.send(sender=self)
            reason = '; '.join(getattr(error, 'messages', [])) or _('permission denied')
            messages.error(request, _('No address was assigned: {reason}').format(reason=reason))
            return redirect(obj.get_absolute_url())

        if not created:
            messages.warning(request, _('Nothing was assigned: it already has a primary IP, or no address is free.'))
        for ip in created:
            text = _('{address} is now the primary IP of {object}, on {interface}.').format(
                address=ip.address, object=obj, interface=ip.assigned_object,
            )
            shown = request.POST.get(f'address{ip.family}')
            if shown and shown != str(ip.address):
                text += ' ' + _('{shown} was taken in the meantime.').format(shown=shown)
            messages.success(request, text)
        return redirect(obj.get_absolute_url())


class DeviceAssignView(AssignView):
    model = Device


class VirtualMachineAssignView(AssignView):
    model = VirtualMachine


@register_model_view(SuggestionRule, 'list', path='', detail=False)
class SuggestionRuleListView(generic.ObjectListView):
    queryset = SuggestionRule.objects.prefetch_related('roles', 'device_types', 'vlans')
    filterset = filtersets.SuggestionRuleFilterSet
    filterset_form = forms.SuggestionRuleFilterForm
    table = tables.SuggestionRuleTable


@register_model_view(SuggestionRule)
class SuggestionRuleView(generic.ObjectView):
    queryset = SuggestionRule.objects.all()


@register_model_view(SuggestionRule, 'add', detail=False)
@register_model_view(SuggestionRule, 'edit')
class SuggestionRuleEditView(generic.ObjectEditView):
    queryset = SuggestionRule.objects.all()
    form = forms.SuggestionRuleForm


@register_model_view(SuggestionRule, 'delete')
class SuggestionRuleDeleteView(generic.ObjectDeleteView):
    queryset = SuggestionRule.objects.all()


@register_model_view(SuggestionRule, 'bulk_delete', path='delete', detail=False)
class SuggestionRuleBulkDeleteView(generic.BulkDeleteView):
    queryset = SuggestionRule.objects.all()
    filterset = filtersets.SuggestionRuleFilterSet
    table = tables.SuggestionRuleTable
