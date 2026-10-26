# Developer guide

How the plugin works and why, for anyone changing it.

## Modules

| Module | Does |
| --- | --- |
| `models.py` | `SuggestionRule`: roles, device types, VLANs, interface name, priority. `for_object()` returns the first enabled rule that matches. |
| `plan.py` | `plan_for()`: for a device or VM, which address (per family it has no primary IP of) and on which interface, or `interface=None` for a new one. Reads only. |
| `assign.py` | `assign()`: what the Assign button does. Plans again under the available-ips lock, creates the interface if needed and the address, sets the primary IP, then checks object permissions. |
| `allocation.py` | Everything about which address: the VLANs of an interface, their prefixes and ranges, and `free_number()`, which finds the first or last free number between two bounds. Reads only. |
| `template_content.py`, `templates/.../inc/*_panel.html` | The suggestion at the top of device and VM pages (`alerts()`), and the *Next free IP* panel on VLANs. |
| `views.py`, `urls.py` | `AssignView` (the button's POST) and the rule list, edit and delete views. |
| `forms.py`, `filtersets.py`, `tables.py`, `navigation.py` | The rule UI, in the usual NetBox shape. |
| `new_address.py` | The DNS name template and the API's primary IP. |
| `api/` | `NextIPView` (`GET` suggests, `POST` creates for an interface) and the rules viewset. |
| `settings.py` | `get_setting()`; the defaults are `NextIPConfig.default_settings`. |

Rules are a model rather than a setting because they point at roles,
device types and VLANs: database objects that admins rename and add in the
UI. A model keeps the links when they are renamed, is edited without a
restart and has a change log. The address rules (ranges, skips, order) stay
in `PLUGINS_CONFIG`; they rarely change.

## Which interface

`plan.from_interfaces()` tries every interface of the device, management-only
first, then the one named in the rule, then the rest in NetBox's name order,
and stops at the first with a free address. With VLANs on the rule, only
those VLANs count, so a switch's access ports never give out user VLAN
addresses. When no interface is in a VLAN, `from_rule()` takes the rule's
VLANs that `VLAN.objects.get_for_device()` (or `get_for_virtualmachine()`)
allows, in VID order, and `pick_interface()` the interface. Assign creates
the named interface (type *virtual* on devices) only when `pick_interface()`
finds none, and never changes an interface's mode or VLAN.

## The cabled interface's VLAN

`vlan_source()` uses the interface's own VLANs. When it has none (and
`cable_peer_vlans` is on), it takes `connected_endpoints`, NetBox's traced
cable path, so patch panels in between are fine. Only one endpoint that is
an interface counts. `connected_endpoints` is cached on the instance, so
re-fetch an interface after cabling it (see `tests/utils.py`).

## Assign

`assign()` holds NetBox's available-ips advisory lock for the whole run and
plans again inside it, so the address shown on the page may have been taken;
the view says so when the created address differs from the posted
`address4` / `address6`. Writes use `full_clean()` and `save()` (change log,
events), the device gets one `snapshot()` and `save()` for all its primary
IPs, and the new objects are checked against the user's object permissions.
On failure the view sends `clear_events` so no webhooks fire for the
rolled-back objects.

## Finding a free address

`free_number(first, last, taken, order)` works on integers: `taken` is a
list of `(start, end)` intervals that may overlap or stick out of the
bounds. Existing IP addresses are `(n, n)`; for the prefix, every range in
it is its whole span. Walking the sorted intervals once finds the first gap (or, by
end descending, the last one), so a /16 or an IPv6 /64 costs one query of
the existing addresses in it and no set of all addresses.

Existing addresses come from NetBox's `Prefix.get_child_ips()` and
`IPRange.get_child_ips()`, so the VRF rules are NetBox's (a global
container prefix sees every VRF). Ranges of a prefix come from
`Prefix.get_child_ranges()` (same VRF, fully inside the prefix).

`usable_bounds()` copies NetBox's rules for which addresses of a prefix are
usable (network, broadcast, subnet-router anycast, pools, /31 and /127)
instead of calling `Prefix.usable_ip_bounds`, which is new in NetBox 4.7.

## NetBox internals used

Nothing is patched. The plugin uses, and would break if NetBox changed:

- `PathEndpoint.connected_endpoints` (the cable trace).
- `VLANQuerySet.get_for_device()` and `get_for_virtualmachine()`.
- `PluginTemplateExtension.alerts()` for the device page.
- `Prefix.get_child_ips()`, `Prefix.get_child_ranges(**filters)`,
  `IPRange.get_child_ips()`.
- `netbox.constants.ADVISORY_LOCK_KEYS['available-ips']` with
  `django_pg_utils.advisory_lock`: the same lock as NetBox's own
  available-ips endpoint, so the two never hand out the same address.
- `core.signals.clear_events`.
- `ObjectValidationMixin` and `discard_events_on_rollback` from
  `netbox.api.viewsets.mixins`, as NetBox's `AvailableObjectsView` uses
  them: the new address is checked against the user's object permissions
  inside the transaction.
- The IP address form takes `address`, `vrf`, `tenant`, `status` and
  `return_url` from the query string (the VLAN panel's *Add*).
- The migration depends on the newest `dcim`, `extras` and `ipam`
  migrations of NetBox 4.7.0.

## Tests

```bash
cd /opt/netbox/netbox
python manage.py test netbox_nextip --keepdb
```

`tests/utils.py` makes a switch with an access port in VLAN 10
(10.0.10.0/24). `test_allocation.py` covers the address rules and settings,
`test_api.py` the endpoint and the VLAN panel, `test_device.py` the
suggestion rules and Assign. Settings are changed in tests
with `plugin_settings()`, which keeps the other defaults.
