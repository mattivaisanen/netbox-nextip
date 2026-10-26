from django.core.exceptions import ObjectDoesNotExist
from django.db import router, transaction
from django.utils.translation import gettext as _
from django_pg_utils import advisory_lock
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ipam.api.serializers import IPAddressSerializer
from ipam.models import IPAddress
from netbox.api.viewsets import NetBoxModelViewSet
from netbox.api.viewsets.mixins import ObjectValidationMixin, discard_events_on_rollback
from netbox.constants import ADVISORY_LOCK_KEYS

from ..allocation import suggest
from ..filtersets import SuggestionRuleFilterSet
from ..models import SuggestionRule
from ..new_address import becomes_primary, dns_name, make_primary
from ..settings import get_setting
from .serializers import InterfaceQuerySerializer, SuggestionRuleSerializer, SuggestionSerializer

#: Request keys that pick the interface and VLAN; the rest of a POST goes to the new IP address.
QUERY_KEYS = ('interface', 'vminterface', 'vlan', 'family')


class NextIPView(ObjectValidationMixin, APIView):
    """
    GET ?interface=<id> (or vminterface): the next free address per VLAN and
    family of the interface. vlan=<id> and family=4|6 narrow it down.

    POST {"interface": <id>, ...}: create the next free address and assign it
    to the interface. Other keys (description, dns_name, role, tenant,
    status, tags, custom_fields) go to the new IP address. Taken under the
    same lock as NetBox's available-ips, so two requests never get the same
    address.
    """
    permission_classes = [IsAuthenticated]
    queryset = IPAddress.objects.all()

    def get_view_name(self):
        return 'Next IP'

    def query(self, request, data):
        """The interface the request is about, and its suggestions."""
        serializer = InterfaceQuerySerializer(data=data, user=request.user)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        interface = values['object']
        vlan = values.get('vlan')
        return interface, suggest(interface, family=values.get('family'), vlans={vlan.pk} if vlan else None)

    def get(self, request):
        _interface, suggestions = self.query(request, request.query_params)
        return Response(SuggestionSerializer(suggestions, many=True, context={'request': request}).data)

    def post(self, request):
        if not request.user.has_perm('ipam.add_ipaddress'):
            raise PermissionDenied(_('Assigning an address needs permission to add IP addresses.'))
        self.queryset = self.queryset.restrict(request.user, 'add')
        query = {key: request.data[key] for key in QUERY_KEYS if key in request.data}
        extra = {key: value for key, value in request.data.items() if key not in QUERY_KEYS}

        with advisory_lock(ADVISORY_LOCK_KEYS['available-ips']):
            interface, suggestions = self.query(request, query)
            found = next((s for s in suggestions if s.address), None)
            if found is None:
                problems = sorted({s.problem for s in suggestions}) or ['no-vlan']
                return Response(
                    {'detail': _('No free address for this interface.'), 'problems': problems},
                    status=status.HTTP_409_CONFLICT,
                )
            serializer = IPAddressSerializer(data={
                'status': get_setting('ip_status'),
                'tenant': found.tenant.pk if found.tenant else None,
                'dns_name': dns_name(interface, found),
                **extra,
                'address': found.address,
                'vrf': found.vrf.pk if found.vrf else None,
                'assigned_object_type': interface._meta.label_lower,
                'assigned_object_id': interface.pk,
            }, context={'request': request})
            serializer.is_valid(raise_exception=True)
            primary = becomes_primary(interface, found.family)

            using = router.db_for_write(IPAddress)
            try:
                with transaction.atomic(using=using), discard_events_on_rollback(self, using=using):
                    created = serializer.save()
                    self._validate_objects(created)
                    if primary:
                        make_primary(created)
            except ObjectDoesNotExist:
                raise PermissionDenied()

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class SuggestionRuleViewSet(NetBoxModelViewSet):
    queryset = SuggestionRule.objects.prefetch_related('roles', 'device_types', 'vlans', 'tags')
    serializer_class = SuggestionRuleSerializer
    filterset_class = SuggestionRuleFilterSet
