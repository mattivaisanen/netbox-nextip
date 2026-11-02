# Developer guide

How the plugin works and why, for anyone changing it.

## Modules

| Module | Does |
| --- | --- |
| `models.py` | `IPRule`. `for_object()` picks the rule of a device or VM; `matches()` checks one rule; `related_errors()` validates the many-to-many fields for the form and the serializer. |
| `choices.py` | What a rule is for (devices or VMs) and the address order. |
| `plan.py` | `plan_for()`: for a device or VM with no primary IPv4, the rule, the interface (new or existing) and the address. Reads only. |
| `allocation.py` | Which address: the VLAN's prefixes and ranges, the reserved addresses of a prefix, and `free_number()`. Reads only. |
| `naming.py` | The interface name and DNS name templates. |
| `signals.py` | Disables a rule when its last device type, role or cluster is deleted (connected in `NextIPConfig.ready()`). With a request, NetBox's own `pre_delete` handler removes the entry from the rule first, so `rule_list_changed()` (m2m `post_remove`) tells a deletion from an edit by NetBox's internal `core.signals._signals_received.pre_delete`. |
| `assign.py` | `assign()`: what Add IP does. Plans again under the available-ips lock, creates or updates the interface, creates the address, sets the primary IP, then checks object permissions. |
| `template_content.py`, `templates/.../inc/device_panel.html`, `inc/plan_rows.html` | The *Next IP* card on device and VM pages (`right_page()`). |
| `templates/.../inc/add_ip_button.html` | *Add IP address* in the button bar (`buttons()`), while no interface has an IP. |
| `views.py`, `urls.py`, `templates/.../add_ip_popup.html` | `AddIPView` (the button's POST), `AddIPPopupView` (the popup) and the rule views. |
| `forms.py`, `filtersets.py`, `tables.py`, `navigation.py`, `api/` | The rule UI and REST API, in the usual NetBox shape. |

Everything a rule decides is a field on the rule, so there are no
`PLUGINS_CONFIG` settings.

## Picking the rule

`for_object()` loads the enabled rules of the object's kind, sorts them by
priority, then `scope_depth()` (location, site, site group, region, a deeper
tree node first, then rules with device types or clusters, then rules with
roles), then name, and
returns the first that `matches()`. The cheap field checks run first; the
last check asks NetBox whether the object may use the rule's VLAN
(`VLAN.objects.get_for_device()` / `get_for_virtualmachine()`), so a rule
whose VLAN is in a scoped VLAN group follows that group's scope.

Regions, site groups and locations are ltree models in NetBox 4.7;
`_within()` uses `get_ancestors(include_self=True)`, which both tree
backends have.

A rule must have a region, a VLAN from a VLAN group with a scope, or (VM
rules) clusters. Roles do not count as scope. Clusters and device types are many-to-many and not saved
when `clean()` runs on a new rule, so those checks live in
`related_errors()`, called by `IPRuleForm.clean()` and
`IPRuleSerializer.validate()`.

## Finding a free address

`free_number(first, last, taken, used, order, fill_gaps)` works on
integers. `taken` is a list of `(start, end)` intervals that may overlap or
stick out of the bounds: existing addresses as `(n, n)`, the ranges of a
prefix, and the reserved addresses of the prefix (`reserved()`: network,
gateway, broadcast). `used` are the existing addresses only. Without
`fill_gaps` the bounds are first narrowed to above the highest used address
(or below the lowest, downwards); then one walk over the sorted intervals
finds the lowest (or highest) free number. A /16 costs one query of the
existing addresses in it.

For a prefix, addresses inside its ranges are not counted as used, so a
reservation in a DHCP pool does not move "the last used address" past the
pool.

## Add IP

`assign()` holds NetBox's available-ips advisory lock, reloads the object
(`refresh_from_db()`) and plans again inside it. The reload makes a second
click wait and then see the primary IP the first one set. The address shown on the page may have been taken; the view
says so when the created address differs from the posted `address`. Writes
use `full_clean()` and `save()` (change log, events). The only interface of a
device, or an existing interface named by a template without `{n}`, is
reused when `plan.takes_vlan()` allows it: it has the rule's VLAN already,
or it has no untagged VLAN and is not a trunk. It gets mode access (if it
had none) and the VLAN. On failure (also an `IntegrityError` from an
address made outside the lock) the view sends `clear_events`, so no
webhooks fire for the rolled-back objects.

With netbox-change-approval, each write that needs approval would be its own
request: the new interface, the new address and the device's primary IP
(plus the popup's site and role). `assign.approval_batch()` opens the
plugin's `batch_scope()` around the click, so they share one `batch_id`:
one inbox item, one notification, approved or rejected together (applied in
creation order, so the address exists before it becomes primary). It is an
optional import; nothing else of that plugin is used.

The card and the button bar share one `plan_for()` per request
(`DeviceNextIP.plan()`, cached on the request).

## The popup

With no matching rule, the card's *Add IP…* button loads
`AddIPPopupView` into NetBox's own htmx modal (`#htmx-modal`, part of every
object page). The popup's form has `hx-get` back to the same view on every
`change`, so each reload rebuilds `forms.AddIPForm` from the values so far:

- Every queryset is `.restrict(user, 'view')`.
- Location choices are the device's own location and its ancestors, so
  every VLAN offered is one the device may use. VLANs are
  `available_vlans()` of `form.probe`, a copy of the object placed at the
  chosen site and location (`plan.placed()`), so NetBox's own scope rules
  decide (location, site, region, cluster groups). VLAN groups are the
  groups of those VLANs.
- The VLAN is only prefilled from a rule that matches `form.target` (a VM
  once its picked site is saved). The VLAN group is prefilled from that rule
  or by `forms.narrowest_group()`. `AddIPForm.choose()`
  keeps an empty choice the user made on purpose (the key is in the data,
  empty).
- The preview is `plan_for(form.target, vlan)`: the object with the picked
  site, at its own location, as `assign()` will see it. It is rendered with
  the same rows as the card (`inc/plan_rows.html`); VLAN and prefix rows
  need `ipam.view_vlan` / `ipam.view_prefix`.
- `hx-params` leaves the CSRF token out of the reload's query string.
- A typed address (`ip_address`) with no VLAN picked runs
  `AddIPForm.vlan_from_address()`: the smallest active prefixes that hold it
  (`allocation.containing_prefixes()`), and if exactly one has a VLAN on
  offer, that VLAN and its group go into the form data. The hidden
  `ip_from` keeps the address that did it, so a changed address picks again
  but a VLAN picked by hand is kept.
- `plan_for(obj, vlan, address)` checks a typed address with
  `allocation.check_address()` (prefix of the VLAN, `child_prefixes()`,
  `reserved()`, an `IPAddress` with `address__net_host` in the prefix's VRF,
  populated ranges) instead of `suggest()`. Its problems have texts
  (`TYPED_PROBLEMS`, `Plan.problem_text`); `assign()` raises them as a
  `ValidationError`. A popup VLAN other than the matching rule's uses
  `default_rule()`.
- The popup posts `popup=1`, so `AddIPView` uses its answers also when a
  rule matches (*Other IP…* on the card).

Selects are plain (`no-ts`): TomSelect does not always send a `change` the
form sees, and the server-built lists are short.

Submitting posts to `AddIPView`, which builds the form again with
`confirm=True` (VLAN, and a VM's missing site and role, required) and passes
`cleaned_data` to `assign()`. `assign()` saves the site and role first
(`fill_in()`), plans again (a rule that matches now wins, otherwise
`plan.default_rule()`, an unsaved `IPRule` with every default), checks the
VLAN is available to the object itself, and rolls the site and role back
when nothing can be added.

Every object written gets `_changelog_message` (`assign.changelog_message()`),
so the change log says "Next IP: rule ..." or that the VLAN was picked in
the popup.

## Migrations

`0001_ip_rules` starts the plugin fresh. It drops the rule tables of
releases before 0.3.0, if present, and creates `IPRule`. It is not named
`0001_initial`, so databases that applied the old `0001_initial` still run
it. NetBox leaves `choices`, `help_text` and `verbose_name` out of
migrations, so changing those needs no migration.

## NetBox internals used

Nothing is patched. The plugin uses, and would break if NetBox changed:

- `VLANQuerySet.get_for_device()` and `get_for_virtualmachine()`.
- `Prefix.get_child_ips()`, `Prefix.get_child_ranges()`,
  `IPRange.get_child_ips()`.
- `get_ancestors()` and `level` on regions, site groups and locations.
- The `available-ips` advisory lock key and `core.signals.clear_events`.
- `PluginTemplateExtension.right_page()`, NetBox's `#htmx-modal` and `_changelog_message`.

## Tests

`python manage.py test netbox_nextip` from a NetBox checkout. The suite is
small on purpose: `free_number()` without a database, rule precedence, and
one Add IP click.
