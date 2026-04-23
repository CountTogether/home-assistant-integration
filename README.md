# CountTogether – Home Assistant Integration

Connect [CountTogether](https://counttogether.app) to Home Assistant. The integration automatically creates sensor entities for each of your counters and exposes actions to control them directly from Home Assistant.

## Features

- UI-based setup via config flow (no YAML required)
- Automatic discovery of all counters in your account
- Real-time updates via WebSocket, with polling as a fallback
- One device per counter, with entities depending on the counter type:

  | Counter type | Entities |
  |--------------|----------|
  | UpDown   | `sensor.<name>_value` |
  | FromDate | `sensor.<name>_value` (elapsed days) + `sensor.<name>_start_date` |
  | ToDate   | `sensor.<name>_value` (remaining days) + `sensor.<name>_end_date` |

- Actions (services) with device/entity targets and automatic counter-type filtering:

  | Service | Description | Counter type |
  |---------|-------------|--------------|
  | `counttogether.increment`      | Increase a counter    | UpDown   |
  | `counttogether.decrement`      | Decrease a counter    | UpDown   |
  | `counttogether.set_value`      | Set the counter value | UpDown   |
  | `counttogether.set_start_date` | Change the start date | FromDate |
  | `counttogether.set_end_date`   | Change the end date   | ToDate   |

## Installation via HACS

1. Open HACS and go to Integrations.
2. In the overflow menu, select "Custom repositories".
3. Add `https://github.com/CountTogether-Repos/home-assistant-integration` with the category "Integration".
4. Install CountTogether and restart Home Assistant.

## Manual installation

```bash
cp -r custom_components/counttogether <ha_config>/custom_components/
```

Then restart Home Assistant.

## Configuration

1. Go to Settings → Devices & services → Add integration → CountTogether.
2. Enter your API token (CountTogether app → Profile → API).
3. The timezone is taken from your Home Assistant settings automatically.

## Using the actions

The services use Home Assistant's standard `target` concept. You pick a device (one counter per device) or a counter entity as the target.

Increment a counter by 1:

```yaml
action: counttogether.increment
target:
  device_id: 4a1b2c3d4e5f6789abcdef0123456789
data:
  amount: 1
```

Or by entity:

```yaml
action: counttogether.increment
target:
  entity_id: sensor.my_counter_value
data:
  amount: 2
```

Change the start date of a FromDate counter:

```yaml
action: counttogether.set_start_date
target:
  device_id: 4a1b2c3d4e5f6789abcdef0123456789
data:
  start_date: "2026-01-01"
```

Counter-type filtering is enforced automatically: `increment`, `decrement` and `set_value` only work with UpDown counters, `set_start_date` only with FromDate, `set_end_date` only with ToDate.

## Requirements

- Home Assistant 2026.4.0 or newer
- An active CountTogether account with an API token

