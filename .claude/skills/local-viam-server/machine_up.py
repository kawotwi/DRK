#!/usr/bin/env python3
"""
machine_up.py — create (or reuse) a Viam cloud machine and write the
viam-server cloud config needed to run a local server against it.

Why this exists
---------------
The `viam` CLI can create a machine (`viam machines create`) but does
NOT expose the machine *part secret* — and viam-server's `cloud` config
block needs that secret to authenticate. `viam machines part {list,
status,history}` all omit it by design.

This script bridges the gap: it uses the Viam **app API** (via the
Python SDK) to fetch the part secret, then writes a minimal
viam-server config:

    {"cloud": {"app_address": "https://app.viam.com:443",
               "id": "<part-id>", "secret": "<part-secret>"}}

Auth
----
Needs a Viam API key with access to the machine. Either:
  * pass --api-key / --api-key-id explicitly, or
  * omit them and the script mints a fresh machine-scoped key via
    `viam machines api-key create` (requires a prior `viam login`).

Usage
-----
    # create a new machine + write config
    machine_up.py --name my-machine --location <loc-name-or-id> [--org "Org"]

    # reuse an existing machine
    machine_up.py --name my-machine --existing <machine-id>

    # also launch viam-server (detached) once the config is written
    machine_up.py --name my-machine --location <loc> --run

Output: prints the machine id, part id, fqdn, and config path. With
--run, also starts viam-server and prints its pid + log path.
"""
import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time


# Lines the `viam` CLI prints to stderr/stdout that are just noise.
_NOISE = ("Update Check", "out of date", "viam update", "Warning: CLI Update")


def viam(args):
    """Run a `viam` CLI subcommand; return stdout with update-check noise stripped."""
    proc = subprocess.run(["viam"] + list(args), capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"`viam {' '.join(args)}` failed:\n{proc.stderr or proc.stdout}")
    keep = [ln for ln in proc.stdout.splitlines()
            if not any(n in ln for n in _NOISE)]
    return "\n".join(keep)


def create_machine(name, location, org):
    """Create a machine via the CLI; return its id."""
    args = ["machines", "create", "--name", name, "--location", location]
    if org:
        args += ["--organization", org]
    out = viam(args)
    # "created new machine with id <uuid>"
    for ln in out.splitlines():
        if "machine with id" in ln:
            return ln.strip().split()[-1]
    sys.exit(f"could not parse machine id from create output:\n{out}")


def main_part_id(machine_id):
    """Return the main part id for a machine."""
    out = viam(["machines", "part", "list", "--machine", machine_id])
    for ln in out.splitlines():
        ln = ln.strip()
        if ln.startswith("ID:"):
            return ln.split("ID:", 1)[1].strip()
    sys.exit(f"no parts found for machine {machine_id}")


def mint_api_key(machine_id):
    """Mint a fresh machine-scoped API key; return (key, key_id)."""
    out = viam(["machines", "api-key", "create", "--machine-id", machine_id,
                "--name", f"machine-up-{int(time.time())}"])
    key = key_id = None
    for ln in out.splitlines():
        if "Key ID:" in ln:
            key_id = ln.split("Key ID:", 1)[1].strip()
        elif "Key Value:" in ln:
            key = ln.split("Key Value:", 1)[1].strip()
    if not (key and key_id):
        sys.exit(f"could not parse minted API key from:\n{out}")
    return key, key_id


async def fetch_main_part(api_key, api_key_id, machine_id, part_id):
    """Fetch the machine's main RobotPart via the Viam app API."""
    from viam.app.viam_client import ViamClient
    from viam.rpc.dial import DialOptions

    opts = DialOptions.with_api_key(api_key, api_key_id)
    client = await ViamClient.create_from_dial_options(opts)
    try:
        parts = await client.app_client.get_robot_parts(machine_id)
        if not parts:
            sys.exit(f"machine {machine_id} has no parts")
        for p in parts:
            if p.id == part_id:
                return p
        for p in parts:
            if getattr(p, "main_part", False):
                return p
        return parts[0]
    finally:
        client.close()


def find_free_port(start=8080, end=8100):
    """Return the first free TCP port in [start, end). viam-server's web
    server defaults to :8080 — on a box already running a viam-server
    that port is taken, so a new server must bind elsewhere."""
    import socket
    for port in range(start, end):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("0.0.0.0", port))
            return port
        except OSError:
            continue
        finally:
            s.close()
    sys.exit(f"no free port found in [{start}, {end})")


def resolve_viam_server(explicit):
    """Locate the viam-server binary."""
    if explicit:
        return explicit
    found = shutil.which("viam-server")
    if found:
        return found
    for cand in ("/opt/viam/bin/viam-server", "/usr/local/bin/viam-server"):
        if os.path.exists(cand):
            return cand
    sys.exit("viam-server binary not found; pass --viam-server <path>")


def main():
    ap = argparse.ArgumentParser(description="Create/reuse a Viam machine and write its viam-server config.")
    ap.add_argument("--name", required=True, help="machine name")
    ap.add_argument("--location", help="location name or id (required when creating)")
    ap.add_argument("--org", help="organization (disambiguates same-named locations)")
    ap.add_argument("--existing", metavar="MACHINE_ID",
                    help="reuse an existing machine instead of creating one")
    ap.add_argument("--api-key", help="Viam API key (else a fresh one is minted)")
    ap.add_argument("--api-key-id", help="Viam API key id")
    ap.add_argument("--workdir", help="where to write the config (default ~/viam-local-machines/<name>)")
    ap.add_argument("--bind-port", type=int,
                    help="viam-server web/gRPC port (default: first free port from 8080)")
    ap.add_argument("--run", action="store_true", help="launch viam-server (detached) after writing the config")
    ap.add_argument("--viam-server", help="path to the viam-server binary")
    args = ap.parse_args()

    # 1. machine
    if args.existing:
        machine_id = args.existing
        print(f"machine:   {args.name} ({machine_id}) [existing]")
    else:
        if not args.location:
            sys.exit("--location is required when creating a machine")
        machine_id = create_machine(args.name, args.location, args.org)
        print(f"machine:   {args.name} ({machine_id}) [created]")

    # 2. main part
    part_id = main_part_id(machine_id)
    print(f"main part: {part_id}")

    # 3. API key
    api_key, api_key_id = args.api_key, args.api_key_id
    if not (api_key and api_key_id):
        api_key, api_key_id = mint_api_key(machine_id)
        print(f"api key:   {api_key_id} [minted]")

    # 4. fetch the part secret via the app API
    part = asyncio.run(fetch_main_part(api_key, api_key_id, machine_id, part_id))
    secret = getattr(part, "secret", "") or ""
    fqdn = getattr(part, "fqdn", "") or ""
    if not secret:
        sys.exit("the machine part has no secret (unexpected — check API-key permissions)")

    # 5. write the viam-server cloud config. The `network.bind_address`
    #    moves viam-server's web/gRPC port off the default :8080 so it
    #    can coexist with any viam-server already running on this box.
    port = args.bind_port or find_free_port()
    workdir = args.workdir or os.path.expanduser(f"~/viam-local-machines/{args.name}")
    os.makedirs(workdir, exist_ok=True)
    config_path = os.path.join(workdir, "viam-server.json")
    config = {
        "cloud": {
            "app_address": "https://app.viam.com:443",
            "id": part.id,
            "secret": secret,
        },
        "network": {
            "bind_address": f":{port}",
        },
    }
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    os.chmod(config_path, 0o600)  # the file holds a machine secret
    print(f"fqdn:      {fqdn}")
    print(f"bind:      :{port}")
    print(f"config:    {config_path}")

    # 6. optionally launch viam-server
    server = resolve_viam_server(args.viam_server)
    if args.run:
        log_path = os.path.join(workdir, "viam-server.log")
        log = open(log_path, "a")
        proc = subprocess.Popen([server, "-config", config_path],
                                stdout=log, stderr=subprocess.STDOUT)
        print(f"viam-server: started pid {proc.pid}, logs -> {log_path}")
        print("  stop with:  kill", proc.pid)
    else:
        print(f"to start:  {server} -config {config_path}")


if __name__ == "__main__":
    main()
