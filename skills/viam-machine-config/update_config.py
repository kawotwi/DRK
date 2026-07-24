#!/usr/bin/env python3
"""
update_config.py — push a robot config JSON to a Viam machine.

The `viam` CLI has no command to set a machine's config. The Viam app
API does (UpdateRobotPart). This script loads a local config JSON — the
same `{modules, components, services, ...}` shape as the app's raw
config editor — and writes it to the machine's main part. A connected
viam-server applies the new config on its next config-watch tick.

Auth
----
Needs a Viam API key with access to the machine. Either pass --api-key /
--api-key-id, or omit them and the script mints a fresh machine-scoped
key via `viam machines api-key create` (requires a prior `viam login`).

Usage
-----
    update_config.py --machine <machine-id> --config cell.json

    # machine by name instead of id
    update_config.py --machine my-machine --org "My Org" --location colorado \
        --config cell.json
"""
import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
import time


_NOISE = ("Update Check", "out of date", "viam update", "Warning: CLI Update")
_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)


def viam(args):
    """Run a `viam` CLI subcommand; return stdout with update-check noise stripped."""
    proc = subprocess.run(["viam"] + list(args), capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"`viam {' '.join(args)}` failed:\n{proc.stderr or proc.stdout}")
    return "\n".join(ln for ln in proc.stdout.splitlines()
                     if not any(n in ln for n in _NOISE))


def resolve_machine_id(machine, org, location):
    """Return a machine id. `machine` may already be an id, or a name to look up."""
    if _UUID.match(machine):
        return machine
    args = ["machines", "list"]
    if org:
        args += ["--organization", org]
    if location:
        args += ["--location", location]
    for ln in viam(args).splitlines():
        ln = ln.strip()
        if ln.startswith(machine + " ") and "(id: " in ln:
            return ln.split("(id: ", 1)[1].split(")")[0].strip()
    sys.exit(f"machine {machine!r} not found — pass the machine id, or add --org/--location")


def main_part(machine_id):
    """Return (part_id, part_name) for the machine's main part."""
    out = viam(["machines", "part", "list", "--machine", machine_id])
    part_id = part_name = None
    for ln in out.splitlines():
        ln = ln.strip()
        if ln.startswith("ID:"):
            part_id = ln.split("ID:", 1)[1].strip()
        elif ln.startswith("Name:"):
            part_name = ln.split("Name:", 1)[1].split("(")[0].strip()
    if not (part_id and part_name):
        sys.exit(f"could not resolve the main part for machine {machine_id}")
    return part_id, part_name


def mint_api_key(machine_id):
    """Mint a fresh machine-scoped API key; return (key, key_id)."""
    out = viam(["machines", "api-key", "create", "--machine-id", machine_id,
                "--name", f"update-config-{int(time.time())}"])
    key = key_id = None
    for ln in out.splitlines():
        if "Key ID:" in ln:
            key_id = ln.split("Key ID:", 1)[1].strip()
        elif "Key Value:" in ln:
            key = ln.split("Key Value:", 1)[1].strip()
    if not (key and key_id):
        sys.exit(f"could not parse minted API key from:\n{out}")
    return key, key_id


async def push_config(api_key, api_key_id, part_id, part_name, config):
    """Write `config` to the machine part via the Viam app API."""
    from viam.app.viam_client import ViamClient
    from viam.rpc.dial import DialOptions

    opts = DialOptions.with_api_key(api_key, api_key_id)
    client = await ViamClient.create_from_dial_options(opts)
    try:
        await client.app_client.update_robot_part(
            robot_part_id=part_id, name=part_name, robot_config=config,
        )
    finally:
        client.close()


def main():
    ap = argparse.ArgumentParser(description="Push a robot config JSON to a Viam machine.")
    ap.add_argument("--machine", required=True,
                    help="machine id, or machine name (with --org/--location)")
    ap.add_argument("--config", required=True, help="path to the robot config JSON file")
    ap.add_argument("--org", help="organization (for name lookup)")
    ap.add_argument("--location", help="location (for name lookup)")
    ap.add_argument("--api-key", help="Viam API key (else a fresh one is minted)")
    ap.add_argument("--api-key-id", help="Viam API key id")
    args = ap.parse_args()

    with open(os.path.expanduser(args.config)) as f:
        config = json.load(f)
    if not isinstance(config, dict):
        sys.exit("config file must contain a JSON object ({modules, components, services, ...})")

    machine_id = resolve_machine_id(args.machine, args.org, args.location)
    part_id, part_name = main_part(machine_id)
    print(f"machine:   {machine_id}")
    print(f"main part: {part_id} ({part_name})")

    api_key, api_key_id = args.api_key, args.api_key_id
    if not (api_key and api_key_id):
        api_key, api_key_id = mint_api_key(machine_id)
        print(f"api key:   {api_key_id} [minted]")

    asyncio.run(push_config(api_key, api_key_id, part_id, part_name, config))

    count = lambda k: len(config.get(k, []) or [])
    print(f"pushed:    {count('modules')} modules, "
          f"{count('components')} components, {count('services')} services")
    print("a connected viam-server applies the new config on its next watch tick.")


if __name__ == "__main__":
    main()
