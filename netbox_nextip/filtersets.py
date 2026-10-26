from django.db.models import Q

from netbox.filtersets import NetBoxModelFilterSet

from .models import SuggestionRule


class SuggestionRuleFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = SuggestionRule
        fields = ('id', 'name', 'priority', 'enabled', 'interface_name')

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))
