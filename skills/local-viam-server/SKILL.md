---
name: local-viam-server
description: >-
  Create a new Viam cloud machine (or reuse an existing one) and bring up a
  local viam-server connected to it. Use when the user wants to spin up a Viam
  machine and run a server against it locally — e.g. "make a new machine named
  X and run a viam-server for it", "stand up a local server for machine Y".
  Handles the machine part secret that the `viam` CLI does not expose, and
  picks a free port so the server can coexist with others on the same box.
  Pairs with viam-machine-config (push robot config to the machine). For
  `viam` CLI, module lifecycle, and fleet topics see viam-modules-fleet.
---

# local-viam-server

Create a Viam cloud machine and run a local `viam-server` connected to it.

## The problem this solves

`viam machines create` makes a machine, but `viam-server` needs a **cloud
config** containing the machine part **secret** — and no `viam` CLI command
exposes that secret (`part list`, `part status`, `part history` all omit it).
`machine_up.py` fetches it via the Viam **app API** (Python SDK) and writes the
config for you.

## Prerequisites

- `viam` CLI installed and logged in (`viam login`).
- Viam Python SDK installed (`pip install viam-sdk`) — `machine_up.py` imports
  `viam.app.viam_client`.
- A `viam-server` binary (the script auto-finds `/opt/viam/bin/viam-server` or
  one on `PATH`; pass `--viam-server <path>` otherwise).

## How to run it

The script lives next to this file: `machine_up.py`.

**Step 1 — create the machine + write the config.** Do *not* pass `--run`; you
launch viam-server yourself in step 2 so the session tracks the process.

```
python3 machine_up.py --name <machine-name> --location <location-name-or-id> [--org "<org>"]
```

To reuse a machine that already exists instead of creating one:

```
python3 machine_up.py --name <machine-name> --existing <machine-id>
```

The script prints the machine id, main part id, fqdn, chosen bind port, and the
config path (`~/viam-local-machines/<name>/viam-server.json`). It mints a
fresh machine-scoped API key unless you pass `--api-key` / `--api-key-id`.

**Step 2 — launch viam-server as a background process** so it stays up and the
session can monitor it:

```
viam-server -config ~/viam-local-machines/<name>/viam-server.json
```

Run that in the background (e.g. the harness's background-process mechanism, or
`nohup ... &`). Then confirm it connected by checking the log for a line like:

```
serving  {"url":"https://<machine>-main.<loc>.local.viam.cloud:<port>"}
```

If you would rather the script launch viam-server itself (detached, not
session-tracked), add `--run` to step 1 and skip step 2.

## Options

| Flag | Purpose |
|---|---|
| `--name` | Machine name (required). |
| `--location` | Location name or id — required when creating a new machine. |
| `--org` | Organization, to disambiguate same-named locations. |
| `--existing <id>` | Reuse an existing machine; skips creation. |
| `--api-key`, `--api-key-id` | Use a specific API key instead of minting one. |
| `--bind-port <n>` | viam-server web/gRPC port (default: first free port from 8080). |
| `--workdir <dir>` | Where the config is written (default `~/viam-local-machines/<name>`). |
| `--run` | Launch viam-server (detached) after writing the config. |
| `--viam-server <path>` | Explicit viam-server binary path. |

## Notes & gotchas

- **Port:** viam-server defaults to `:8080`. On a box already running a
  viam-server that port is taken — the script scans 8080–8099 for a free port
  and writes `network.bind_address` into the config. Override with
  `--bind-port`.
- **Secrets:** the generated `viam-server.json` contains the machine part
  secret; the script `chmod 600`s it. Keep it out of version control.
- **API keys:** minted keys have full write access to the machine. Name them so
  they're easy to find and revoke later (`viam machine api-key` /  the Viam app).
- **Stopping:** `kill` the viam-server pid. The cloud machine itself persists
  until `viam machines delete`.

## Related skills

| Topic | Skill |
|-------|-------|
| Push a robot config (modules, components, services) to the machine | `viam-machine-config` |
| `viam` CLI, module lifecycle, registry, fleet management | `viam-modules-fleet` |
| Writing the modules you deploy onto the machine | `viam-python`, `viam-go-platform`, `viam-go-motion-vision`, `viam-cpp` |
