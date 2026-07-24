---
name: viam-machine-config
description: >-
  Push or update a Viam machine's robot config (modules, components, services)
  from a local JSON file. Use when the user wants to set/replace what's on a
  Viam machine — e.g. "update the machine config", "deploy this cell config to
  machine X", "put these components on the machine". Works where the `viam` CLI
  can't: it writes the config via the Viam app API. Pairs with local-viam-server
  (create the machine + run viam-server). For `viam` CLI, module lifecycle, and
  config-schema topics see viam-modules-fleet.
---

# viam-machine-config

Push a robot config JSON to a Viam machine.

## The problem this solves

The `viam` CLI can read config history but has no command to **set** a
machine's config. The Viam app API does (`UpdateRobotPart`).
`update_config.py` loads a local config JSON — the same
`{modules, components, services, ...}` shape as the app's raw config editor —
and writes it to the machine's main part. A connected `viam-server` applies it
on its next config-watch tick (no restart needed).

## Prerequisites

- `viam` CLI installed and logged in (`viam login`).
- Viam Python SDK installed (`pip install viam-sdk`).

## How to run it

The script lives next to this file: `update_config.py`.

```
python3 update_config.py --machine <machine-id> --config <path-to-config.json>
```

By machine name instead of id:

```
python3 update_config.py --machine <name> --org "<org>" --location <location> \
    --config <path-to-config.json>
```

It resolves the main part, mints a machine-scoped API key (unless you pass
`--api-key` / `--api-key-id`), and writes the config. It prints a
modules/components/services count on success.

## Options

| Flag | Purpose |
|---|---|
| `--machine` | Machine id, or machine name (with `--org`/`--location`) (required). |
| `--config` | Path to the robot config JSON file (required). |
| `--org`, `--location` | Used to resolve a machine *name* to its id. |
| `--api-key`, `--api-key-id` | Use a specific API key instead of minting one. |

## Notes & gotchas

- **Replaces, not merges.** `update_robot_part` overwrites the part's config
  with what you push — include the *entire* desired config (all modules,
  components, services), not a delta.
- **Registry vs local modules.** A `modules` entry is either
  `{"type":"registry","module_id":"ns:mod","version":"x.y.z","name":"..."}` or
  `{"type":"local","name":"...","executable_path":"/abs/path"}`. A local module
  only resolves if its binary exists on the machine running viam-server.
- **No restart needed.** viam-server watches for config changes and
  reconfigures in place; watch its log for `Reconfiguring robot` /
  `Successfully constructed resource`.
- **Don't push secrets.** The robot config is the user-facing config; it does
  not contain the cloud bootstrap secret (that lives in viam-server's local
  `-config` file).

## Related skills

| Topic | Skill |
|-------|-------|
| Create the machine and bring viam-server online in the first place | `local-viam-server` |
| `viam` CLI, module lifecycle, registry, robot-config schema reference | `viam-modules-fleet` |
| Writing the modules referenced in the config you push | `viam-python`, `viam-go-platform`, `viam-go-motion-vision`, `viam-cpp` |
