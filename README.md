# Lockable Cover

`lockable_cover` is a Home Assistant custom integration that creates a proxy `cover`
entity mirroring an existing cover, but refusing movement in the **opening** direction
while a chosen lock entity is engaged.

Closing and stopping are **always** allowed. This is a deliberate safety property: the
lock must never be able to trap a garage door in the open position.

Configuration is entirely through the UI. There is no YAML.

## Requirements

- Home Assistant 2026.9.0 or newer
- No third-party Python dependencies

## Installation with HACS

1. In HACS, open **Integrations**.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add `https://github.com/brocosoup/ha-lockable-cover` as the URL, select
   **Integration** as the category, and add it.
4. Install **Lockable Cover**.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration** and search for
   **Lockable Cover**.

### Manual installation

Copy `custom_components/lockable_cover/` into your Home Assistant `config/custom_components/`
directory and restart.

## Configuration

The setup dialog asks for four things:

| Field | Meaning |
| --- | --- |
| **Name** | Friendly name of the proxy cover entity. |
| **Source cover** | The real cover this proxy forwards commands to. |
| **Lock entity** | A `lock`, `switch`, or `input_boolean`. While engaged, opening is refused. |
| **Invert lock state** | Treat the lock as *engaged* when it reads `off`/`unlocked` instead of `on`/`locked`. |

Each source cover can only be wrapped once, and a lockable cover proxy cannot be used as
the source for another proxy.

After setup, **Configure** on the integration entry lets you change the lock entity and
the invert flag. The source cover is fixed at setup time, because changing it would change
the identity of the proxy entity. Changing options reloads the entry automatically.

## Important: the proxy is not a firewall

Commands sent **directly to the source cover** are not intercepted. This integration adds
a gated entity alongside the original; it does not restrict the original.

Point your dashboards, scripts, automations, and voice assistants at the **proxy** entity
wherever the safety behavior matters. The source cover remains fully operable by anything
that addresses it directly.

## Behavior

### Command gating

| Command | While locked |
| --- | --- |
| `cover.open_cover` | blocked |
| `cover.open_cover_tilt` | blocked |
| `cover.set_cover_position` to a position **greater** than current | blocked |
| `cover.set_cover_tilt_position` to a position **greater** than current | blocked |
| `cover.set_cover_position` to a position at or below current | allowed |
| `cover.close_cover`, `cover.close_cover_tilt` | **always allowed** |
| `cover.stop_cover`, `cover.stop_cover_tilt` | **always allowed** |
| `cover.toggle` | resolved to open or close from the current state, then gated as above |

A blocked command raises a `ServiceValidationError`, so Home Assistant shows a translated
error toast in the UI and the automation or script trace records a clear failure, rather
than silently doing nothing.

### Fail-closed lock handling

The lock is considered engaged when the lock entity's state is `on` or `locked` (reversed
by **Invert lock state**).

If the lock entity is `unavailable`, `unknown`, or missing entirely, it is treated as
**locked** and a warning is logged. A garage door is a security boundary, so an
unreadable lock denies opening rather than permitting it. Closing and stopping still work
in this state.

### Mirroring

The proxy mirrors the source cover's state, current position, current tilt position,
opening/closing/closed status, device class, and supported features. Supported features
are read from the source at runtime, so the proxy never advertises a feature the source
does not have.

The proxy becomes `unavailable` when the source cover is unavailable or missing. It is
fully push-driven — it subscribes to state changes on both the source cover and the lock
entity, and never polls.

### Extra attributes

| Attribute | Meaning |
| --- | --- |
| `locked` | Whether opening is currently blocked. |
| `lock_entity` | The entity id of the lock. |
| `source_entity` | The entity id of the source cover. |

## Worked example: a garage door

The real door is `cover.garage_door`. You want a "night lock" that prevents the door
being opened, while still allowing it to be closed at any time.

1. Create a helper toggle: **Settings → Devices & services → Helpers → Create helper →
   Toggle**, named `Garage door lock`. This gives you `input_boolean.garage_door_lock`.
2. Add the integration: **Settings → Devices & services → Add integration → Lockable
   Cover**.
   - **Name**: `Garage door (safe)`
   - **Source cover**: `cover.garage_door`
   - **Lock entity**: `input_boolean.garage_door_lock`
   - **Invert lock state**: off, because `on` means locked here.
3. You now have `cover.garage_door_safe`. Put **that** entity on your dashboard instead of
   `cover.garage_door`.

Engage the lock automatically at night:

```yaml
automation:
  - alias: Lock the garage overnight
    triggers:
      - trigger: time
        at: "23:00:00"
    actions:
      - action: input_boolean.turn_on
        target:
          entity_id: input_boolean.garage_door_lock

  - alias: Unlock the garage in the morning
    triggers:
      - trigger: time
        at: "06:30:00"
    actions:
      - action: input_boolean.turn_off
        target:
          entity_id: input_boolean.garage_door_lock
```

With the lock on:

- Pressing open on `cover.garage_door_safe` shows *"cover.garage_door_safe cannot be
  opened because input_boolean.garage_door_lock is locked."*
- Pressing close still closes the door.
- A "close the garage if it has been open 10 minutes" automation targeting the proxy keeps
  working, which is the point — the lock can never strand the door open.

```yaml
automation:
  - alias: Close the garage if left open
    triggers:
      - trigger: state
        entity_id: cover.garage_door_safe
        to: "open"
        for: "00:10:00"
    actions:
      - action: cover.close_cover
        target:
          entity_id: cover.garage_door_safe
```

## Using a real lock entity

Any `lock` domain entity works as the lock, so a physical smart lock or a `switch` can
gate the cover instead of a helper toggle. Pick the entity in the config flow; `locked`
and `on` both count as engaged.
