from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.generic import View

from core.signals import clear_events
from dcim.models import Device
from netbox.views import generic
from utilities.views import ConditionalLoginRequiredMixin, register_model_view
from virtualization.models import VirtualMachine

from . import filtersets, forms, tables
from .assign import assign, permissions_for, urls_for
from .models import IPRule
from .plan import plan_for, view_flags


class AddIPView(ConditionalLoginRequiredMixin, View):
    """
    The Add IP button on a device or VM page, or its popup (always when no
    rule matches, or to pick another VLAN or type the address): add the
    address and go back to the page.
    """
    model = None

    def post(self, request, pk):
        obj = get_object_or_404(self.model.objects.restrict(request.user, 'view'), pk=pk)
        if not request.user.has_perms(permissions_for(obj)):
            raise PermissionDenied
        choice = None
        if IPRule.for_object(obj) is None or request.POST.get('popup'):
            # No rule, or sent from the popup: the popup's answers decide (forms.AddIPForm).
            form = forms.AddIPForm(obj, request.user, data=request.POST, confirm=True)
            if not form.is_valid():
                messages.error(request, _('No address was added: {reason}').format(reason=form.error_text()))
                return redirect(obj.get_absolute_url())
            choice = form.cleaned_data
        try:
            ip = assign(obj, request.user, choice)
        except (PermissionDenied, ValidationError, IntegrityError, ObjectDoesNotExist) as error:
            # Nothing was written, so drop the events queued for the rolled-back objects.
            clear_events.send(sender=self)
            messages.error(request, _('No address was added: {reason}').format(reason=failure_reason(error)))
            return redirect(obj.get_absolute_url())

        if ip is None:
            # A site or role from the popup may have been rolled back.
            clear_events.send(sender=self)
            messages.warning(request, _('Nothing was added: it already has a primary IPv4, or no address is free.'))
            return redirect(obj.get_absolute_url())
        text = _('Added {address} to {object} on {interface}.').format(
            address=ip.address, object=obj, interface=ip.assigned_object,
        )
        shown = request.POST.get('address')
        if shown and shown != str(ip.address):
            text += ' ' + _('{shown} was taken in the meantime.').format(shown=shown)
        if getattr(ip, 'primary_held', False):
            text += ' ' + _('Making it the primary IP is waiting for approval; until then, Add IP adds another address.')
            messages.warning(request, text)
        else:
            messages.success(request, text)
        return redirect(obj.get_absolute_url())


def failure_reason(error):
    """Why Add IP failed, in words for the user."""
    if isinstance(error, ValidationError):
        return '; '.join(error.messages)
    if isinstance(error, IntegrityError):
        # Such as an address with the same VRF made at the same moment outside NetBox's lock (a plain API call).
        return _('the address was taken in the meantime, try again')
    if isinstance(error, ObjectDoesNotExist):
        return _('the object was deleted in the meantime')
    return _('permission denied')


class DeviceAddIPView(AddIPView):
    model = Device


class VirtualMachineAddIPView(AddIPView):
    model = VirtualMachine


class AddIPPopupView(ConditionalLoginRequiredMixin, View):
    """
    The Add IP popup for a device or VM, as content for NetBox's htmx
    modal: for one no rule matches, or to pick another VLAN or type the
    address. It loads again with the chosen values on every change, and
    shows what Add IP would do with them. Writes nothing.
    """
    model = None

    def get(self, request, pk):
        obj = get_object_or_404(self.model.objects.restrict(request.user, 'view'), pk=pk)
        if not request.user.has_perms(permissions_for(obj)):
            raise PermissionDenied
        form = forms.AddIPForm(obj, request.user, data=request.GET)
        # Plan like Add IP will: with the site saved, at the object's own location. Nothing to plan once
        # the object has a primary IPv4 (the popup was opened from an old page).
        plan = None
        if form.vlan and not obj.primary_ip4_id:
            plan = plan_for(form.target, vlan=form.vlan, address=form.address)
        add_url, popup_url = urls_for(obj)
        return render(request, 'netbox_nextip/add_ip_popup.html', {
            'object': obj,
            'form': form,
            'rule': IPRule.for_object(obj),
            'plan': plan,
            'waiting': form.missing(),
            'add_url': add_url,
            'popup_url': popup_url,
            **view_flags(plan, request.user),
        })


class DeviceAddIPPopupView(AddIPPopupView):
    model = Device


class VirtualMachineAddIPPopupView(AddIPPopupView):
    model = VirtualMachine


@register_model_view(IPRule, 'list', path='', detail=False)
class IPRuleListView(generic.ObjectListView):
    queryset = IPRule.objects.select_related('vlan', 'region', 'site_group', 'site', 'location').prefetch_related(
        'device_types', 'roles', 'clusters',
    )
    filterset = filtersets.IPRuleFilterSet
    filterset_form = forms.IPRuleFilterForm
    table = tables.IPRuleTable


@register_model_view(IPRule)
class IPRuleView(generic.ObjectView):
    queryset = IPRule.objects.all()


@register_model_view(IPRule, 'add', detail=False)
@register_model_view(IPRule, 'edit')
class IPRuleEditView(generic.ObjectEditView):
    queryset = IPRule.objects.all()
    form = forms.IPRuleForm


@register_model_view(IPRule, 'delete')
class IPRuleDeleteView(generic.ObjectDeleteView):
    queryset = IPRule.objects.all()


@register_model_view(IPRule, 'bulk_delete', path='delete', detail=False)
class IPRuleBulkDeleteView(generic.BulkDeleteView):
    queryset = IPRule.objects.all()
    filterset = filtersets.IPRuleFilterSet
    table = tables.IPRuleTable
