# Viam CLI Reference

Comprehensive reference for the `viam` CLI tool, extracted from RDK source (`cli/app.go` and
related files), April 2026. The CLI is built with `urfave/cli/v3`.

---

## Table of Contents
1. [Global Options](#global-options)
2. [Authentication](#authentication)
3. [Module Commands](#module-commands)
4. [Machine Commands](#machine-commands)
5. [Organization Commands](#organization-commands)
6. [Location Commands](#location-commands)
7. [Data Commands](#data-commands)
8. [Dataset Commands](#dataset-commands)
9. [Data Pipeline Commands](#data-pipeline-commands)
10. [Package Commands](#package-commands)
11. [Training Commands](#training-commands)
12. [Resource Commands](#resource-commands)
13. [Profile Commands](#profile-commands)
14. [Defaults Commands](#defaults-commands)
15. [Other Commands](#other-commands)

---

## Global Options

Every `viam` command accepts these flags before the subcommand:

| Flag | Aliases | Description |
|------|---------|-------------|
| `--base-url` | (hidden) | Base URL of app (internal use) |
| `--config`, `-c` | | Load configuration from FILE |
| `--debug`, `--vvv` | | Enable debug logging |
| `--quiet`, `-q` | | Suppress warnings |
| `--profile` | | Specify a particular profile for the current command |
| `--disable-profiles` | `--disable-profile` | Disable usage of profiles, falling back to default behavior |

---

## Authentication

### `viam login`

Login to app.viam.com via browser-based OAuth flow.

```
viam login [--disable-browser-open]
```

| Flag | Aliases | Description |
|------|---------|-------------|
| `--disable-browser-open` | `--no-browser` | Prevent opening the default browser during login |

Aliases: `viam auth` (backward compatibility)

### `viam login api-key`

Authenticate with an API key (for CI/CD, scripts, headless environments).

```
viam login api-key --key-id=<key-id> --key=<key>
```

| Flag | Required | Description |
|------|----------|-------------|
| `--key-id` | Yes | ID of the key to authenticate with |
| `--key` | Yes | Key value to authenticate with |

### `viam login print-access-token`

Print the access token associated with current credentials. Useful for passing tokens to other tools.

```
viam login print-access-token
```

### `viam logout`

Logout from current session.

```
viam logout
```

### `viam whoami`

Get currently logged-in user information.

```
viam whoami
```

---

## Module Commands

All under `viam module`. This is the core lifecycle command group.

### `viam module generate`

Generate a new modular resource via interactive prompts.

```
viam module generate [options]
```

| Flag | Description |
|------|-------------|
| `--name` | Module name (e.g., "sensors") |
| `--language` | Language: `python`, `go` |
| `--visibility` | `private`, `public`, `public_unlisted` |
| `--public-namespace` | Org namespace or org ID |
| `--resource-subtype` | Resource subtype (e.g., arm, camera, motion) |
| `--model-name` | Name for the resource implementation (e.g., "moisture") |
| `--register` | Register module with Viam after generation |
| `--dry-run` | (hidden) Skip regular checks, for testing |

Supported languages: `python`, `go`. Minimum versions: Python 3.10, Go 1.23.

When run without flags, launches an interactive TUI wizard.

### `viam module create`

Create and register a module on app.viam.com. Writes a `meta.json` in the current directory.

```
viam module create --name=<name> [options]
```

| Flag | Required | Description |
|------|----------|-------------|
| `--name` | Yes | Module name (cannot be changed once set) |
| `--public-namespace` | No | Public namespace (alternative to org-id) |
| `--org-id` | No | Organization ID that will host the module |
| `--local-only` | No | Create meta.json locally without registering on backend |

### `viam module update`

Update a module's metadata on app.viam.com from `meta.json`.

```
viam module update [--module=<path-to-meta.json>]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--module` | `./meta.json` | Path to meta.json |

This reads the local `meta.json` and pushes changes to the registry. If the module was created
with an org ID and the org now has a public namespace, the `meta.json` is updated to use the namespace.

### `viam module update-models`

Auto-detect models provided by a module binary and update `meta.json`.

```
viam module update-models [--module=<path>] [--binary=<path>]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--module` | `./meta.json` | Path to meta.json |
| `--binary` | (entrypoint from meta.json) | Module binary to inspect (must work on current OS/arch) |

This runs the module binary to discover its models, then updates the `models` array in meta.json.
It also checks for companion markdown files (e.g., `namespace_family_modelname.md`) and sets
`markdown_link` fields accordingly.

### `viam module upload`

Upload a new version of your module to the registry.

```
viam module upload --version=<semver> --platform=<platform> --upload=<path> [options]
```

| Flag | Required | Description |
|------|----------|-------------|
| `--version` | Yes | Semver version (e.g., "0.1.0"). Leading "v" is stripped. |
| `--platform` | Yes | Target platform (see below) |
| `--upload` | No* | Path to the file or directory to upload |
| `--module` | No | Path to meta.json (default: `./meta.json`) |
| `--public-namespace` | No | Public namespace (alternative to org-id) |
| `--org-id` | No | Organization ID hosting the module |
| `--name` | No | Module name (used if you lack a meta.json) |
| `--tags` | No | Platform constraint tags (e.g., `distro:debian`) |
| `--force` | No | Skip validation (may produce non-functional versions) |

*`--upload` can also be the first positional argument.

**Supported platforms:**

| Value | Description |
|-------|-------------|
| `any` | Most Python modules |
| `any/amd64` | Most Docker-based modules |
| `any/arm64` | Docker-based ARM modules |
| `linux/any` | Python modules requiring OS support |
| `darwin/any` | macOS Python modules |
| `linux/amd64` | Standard Linux x86_64 |
| `linux/arm64` | Standard Linux ARM64 |
| `linux/arm32v7` | Linux ARMv7 (32-bit) |
| `linux/arm32v6` | Linux ARMv6 (32-bit) |
| `darwin/amd64` | Intel Macs |
| `darwin/arm64` | Apple Silicon Macs |

The upload process:
1. Loads meta.json to get module ID
2. Calls `updateModule` to sync metadata
3. Creates tarball from the upload path (if not already a tarball)
4. Validates the tarball (checks entrypoint exists, no bad symlinks) unless `--force`
5. Streams the upload to the registry

### `viam module build`

Build your module for different architectures using cloud runners.

#### `viam module build local`

Run your meta.json build command locally.

```
viam module build local [--module=<path>]
```

Executes the `build.build` command from meta.json in a shell. If `build.setup` is defined,
it runs first. Uses `bash -c` on Unix, `cmd.exe /C` on Windows.

#### `viam module build start`

Start a remote (cloud) build.

```
viam module build start --version=<semver> [options]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--version` | (required) | Semver version |
| `--module` | `./meta.json` | Path to meta.json |
| `--ref` | `main` | Git ref to clone (branch or commit hash) |
| `--token` | | Checkout token for private repos |
| `--workdir` | `.` | Subdirectory of repo containing meta.json |
| `--platforms` | (from meta.json `build.arch`) | Platforms to build (e.g., `linux/amd64,linux/arm64`) |

**Requirements:** The `url` field in meta.json must be set to a public git repo URL.

#### `viam module build list`

Check status of cloud builds.

```
viam module build list [--module=<path>] [--count=<n>] [--id=<build-id>]
```

Build statuses: `Unknown`, `Building`, `Failed`, `Done`.

#### `viam module build logs`

Get logs from a cloud build.

```
viam module build logs --id=<build-id> [options]
```

| Flag | Description |
|------|-------------|
| `--build-id` / `--id` | (required) Build ID |
| `--platform` | Filter to specific platform logs |
| `--wait` | Wait for build to finish before outputting |
| `--group-logs` | Write `::group::` commands for GitHub Actions |

### `viam module reload-local`

Build a module locally and deploy it to a target machine. Rebuild and restart if already running.

```
viam module reload-local [options]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--part-id` | (from /etc/viam.json) | Part ID of target machine |
| `--module` | `meta.json` | Path to meta.json |
| `--name` | | Module name (alternative to meta.json) |
| `--id` | | Module ID (alternative to meta.json) |
| `--no-build` | false | Skip the build step |
| `--local` | false | Run entrypoint directly (for localhost) |
| `--no-progress` | false | Hide file transfer progress |
| `--home` | `~` | Remote user's home directory |
| `--cloud-config` | `/etc/viam.json` | Path to viam.json for part ID lookup |
| `--model-name` | (none) | Model triple to add as a resource |
| `--resource-name` | (auto-generated) | Name for the newly added resource |
| `--workdir` | `.` | Subdirectory containing meta.json |

This is the primary development workflow command. It:
1. Runs `build.build` from meta.json (unless `--no-build`)
2. Packages the output tarball
3. Transfers it to the target machine via shell service
4. Configures the module in the machine's config
5. Restarts the module if already configured

### `viam module reload`

Build a module in the cloud and run it on a target machine.

```
viam module reload [options]
```

Similar to `reload-local` but uses cloud build instead of local build. The machine downloads
the package directly from the registry.

| Flag | Default | Description |
|------|---------|-------------|
| `--part-id` | (from /etc/viam.json) | Part ID of target machine |
| `--module` | `meta.json` | Relative path to meta.json from workdir |
| `--cloud-config` | `/etc/viam.json` | Path to viam.json |
| `--model-name` | (none) | Model triple to add as a resource |
| `--resource-name` | (auto-generated) | Name for the newly added resource |
| `--workdir` | `.` | Subdirectory containing meta.json |
| `--path` | `.` | Path to root of the module's git repo |

### `viam module restart`

Restart a currently-running module on a machine.

```
viam module restart [options]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--part-id` | (from /etc/viam.json) | Part ID |
| `--module` | `meta.json` | Path to meta.json |
| `--name` | | Module name |
| `--id` | | Module ID (e.g., `viam:wifi-sensor`) |
| `--cloud-config` | `/etc/viam.json` | viam.json path for part ID lookup |

### `viam module download`

Download a module package from the registry.

```
viam module download [options]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--destination` | `.` | Output directory |
| `--id` | (from meta.json) | Module ID (org-id:name or namespace:name) |
| `--version` | `latest` | Version to download |
| `--platform` | (current platform) | Target platform |

---

## Machine Commands

All under `viam machines` (aliases: `machine`, `robots`, `robot`).

### `viam machines create`

```
viam machines create --name=<name> --location=<location> [--organization=<org>]
```

### `viam machines delete`

```
viam machines delete --machine=<machine> [--location=<loc>] [--organization=<org>]
```

### `viam machines update`

Move a machine between locations and/or rename it.

```
viam machines update --machine=<machine> [--new-location=<loc>] [--new-name=<name>]
```

### `viam machines list`

```
viam machines list [--organization=<org>] [--location=<loc>] [--all]
```

`--all` lists all machines in the organization, overriding location filter.

### `viam machines status`

```
viam machines status --machine=<machine> [--organization=<org>] [--location=<loc>]
```

### `viam machines logs`

```
viam machines logs --machine=<machine> [options]
```

| Flag | Description |
|------|-------------|
| `--output` | Path to output file |
| `--format` | File format: `text` or `json` |
| `--keyword` | Filter logs by keyword |
| `--levels` | Filter by levels (info, warn, error) |
| `--start` | RFC3339 timestamp (default: 12h ago) |
| `--end` | RFC3339 timestamp |
| `--count` | Number of logs to fetch |

### `viam machines api-key create`

```
viam machines api-key create --machine-id=<id> [--name=<name>] [--org-id=<org>]
```

### Machine Part Commands

Under `viam machines part`.

#### `viam machines part list`

```
viam machines part list --machine=<machine> [--organization=<org>] [--location=<loc>]
```

#### `viam machines part create`

```
viam machines part create --part-name=<name> --machine=<machine>
```

#### `viam machines part delete`

```
viam machines part delete --part=<part-id-or-name>
```

#### `viam machines part status`

```
viam machines part status --part=<part>
```

#### `viam machines part logs`

```
viam machines part logs --part=<part> [--errors] [--tail/-f] [--start] [--end] [--count]
```

#### `viam machines part history`

```
viam machines part history --part=<part> [--filter-by-email=<email>]
```

#### `viam machines part restart`

```
viam machines part restart --part=<part>
```

#### `viam machines part add-resource`

```
viam machines part add-resource --part=<part> --name=<name> --model-name=<model> [--api=<api>] [--resource-subtype=<subtype>]
```

#### `viam machines part remove-resource`

```
viam machines part remove-resource --part=<part> --name=<name>
```

#### `viam machines part run`

```
viam machines part run --part=<part> --method=<method> [--data=<json>] [--stream=<duration>] [--component=<name>]
```

#### `viam machines part shell`

Start an interactive shell on a machine part. Requires shell service.

```
viam machines part shell --part=<part>
```

#### `viam machines part cp`

Copy files to/from a machine part. Uses `machine:` prefix to identify machine paths.

```
viam machines part cp --part=<part> [-r] [-p] <source>... <target>
```

#### `viam machines part fragments add/remove`

```
viam machines part fragments add --part=<part> [--fragment=<name-or-id>]
viam machines part fragments remove --part=<part> [--fragment=<name-or-id>]
```

#### `viam machines part add-job`

Add a scheduled job to a machine part.

```
viam machines part add-job --part=<part> [--config=<json-or-file>]
```

Config JSON fields: `name` (required), `schedule` (required: "continuous", Go duration, or cron),
`resource` (required), `method` (required), `command` (optional), `log_configuration` (optional).

#### `viam machines part add-trigger / delete-trigger`

```
viam machines part add-trigger --part=<part> [--config=<json-or-file>]
viam machines part delete-trigger --part=<part> [--name=<trigger-name>]
```

---

## Organization Commands

Under `viam organizations` (aliases: `organization`, `org`).

### `viam organizations list`

List all organizations for the current user.

```
viam organizations list
```

### `viam organizations api-key create`

```
viam organizations api-key create --org-id=<id> [--name=<key-name>]
```

### `viam organizations support-email set/get`

```
viam organizations support-email set --org-id=<id> --support-email=<email>
viam organizations support-email get --org-id=<id>
```

### `viam organizations logo set/get`

```
viam organizations logo set --org-id=<id> --logo-path=<path.png>
viam organizations logo get --org-id=<id>
```

### `viam organizations billing-service`

Subcommands: `get-config`, `enable`, `disable`, `update`.

### `viam organizations auth-service`

Manage OAuth applications. Subcommands: `enable`, `disable`, `oauth-app create/read/update/delete/list`.

---

## Location Commands

Under `viam locations` (aliases: `location`).

### `viam locations list`

```
viam locations list [--organization=<org>]
```

### `viam locations api-key create`

```
viam locations api-key create --location-id=<id> [--name=<key-name>] [--org-id=<org>]
```

---

## Data Commands

Under `viam data`.

### `viam data export binary filter`

```
viam data export binary filter --destination=<dir> [filter flags]
```

| Flag | Description |
|------|-------------|
| `--destination` | (required) Output directory |
| `--parallel` | Parallel download requests (default: 100) |
| `--timeout` | Seconds to wait for large files (default: 30) |
| `--tags` | Tags filter ("tagged", "untagged", or tag list) |

Plus all common filter flags: `--org-ids`, `--location-ids`, `--machine-id`, `--part-id`,
`--machine-name`, `--part-name`, `--component-type`, `--component-name`, `--method`,
`--mime-types`, `--start`, `--end`, `--bbox-labels`.

### `viam data export binary ids`

```
viam data export binary ids --destination=<dir> --binary-data-ids=<ids>
```

### `viam data export tabular`

```
viam data export tabular --destination=<dir> --part-id=<id> --resource-name=<name> --resource-subtype=<type> --method=<method> [--start=<ts>] [--end=<ts>]
```

### `viam data delete binary`

```
viam data delete binary --org-ids=<ids> --start=<ts> --end=<ts> [filter flags]
```

### `viam data delete tabular`

```
viam data delete tabular --org-id=<id> --delete-older-than-days=<n>
```

### `viam data database configure/hostname`

```
viam data database configure --org-id=<id> --password=<pw>
viam data database hostname --org-id=<id>
```

### `viam data tag ids add/remove`

```
viam data tag ids add --tags=<tags> --binary-data-ids=<ids>
viam data tag ids remove --tags=<tags> --binary-data-ids=<ids>
```

### `viam data tag filter add/remove`

```
viam data tag filter add --tags=<tags> [filter flags]
viam data tag filter remove --tags=<tags> [filter flags]
```

### `viam data index create/delete/list`

```
viam data index create --org-id=<id> --collection-type=<type> --index-path=<file> [--pipeline-name=<name>]
viam data index delete --org-id=<id> --collection-type=<type> --index-name=<name>
viam data index list --org-id=<id> --collection-type=<type>
```

Collection types: `hot-storage`, `pipeline-sink`.

---

## Dataset Commands

Under `viam dataset`.

### `viam dataset create`

```
viam dataset create --org-id=<id> --name=<name>
```

### `viam dataset rename`

```
viam dataset rename --dataset-id=<id> --name=<new-name>
```

### `viam dataset list`

```
viam dataset list [--dataset-ids=<ids> | --org-id=<id>]
```

### `viam dataset delete`

```
viam dataset delete --dataset-id=<id>
```

### `viam dataset export`

```
viam dataset export --destination=<dir> --dataset-id=<id> [--only-jsonlines] [--parallel=100] [--timeout=30]
```

### `viam dataset merge`

```
viam dataset merge --org-id=<id> --name=<name> --dataset-ids=<id1,id2,...>
```

### `viam dataset data add/remove ids/filter`

```
viam dataset data add ids --dataset-id=<id> --binary-data-ids=<ids>
viam dataset data add filter --dataset-id=<id> [filter flags]
viam dataset data remove ids --dataset-id=<id> --binary-data-ids=<ids>
viam dataset data remove filter --dataset-id=<id> [filter flags]
```

---

## Data Pipeline Commands

Under `viam datapipelines`.

```
viam datapipelines list --org-id=<id>
viam datapipelines describe --id=<pipeline-id>
viam datapipelines create --org-id=<id> --name=<name> --schedule=<cron> --enable-backfill [--mql=<query> | --mql-path=<file>]
viam datapipelines rename --id=<pipeline-id> --name=<new-name>
viam datapipelines delete --id=<pipeline-id>
viam datapipelines enable --id=<pipeline-id>
viam datapipelines disable --id=<pipeline-id>
```

---

## Package Commands

Under `viam packages`.

### `viam packages export`

```
viam packages export --type=<type> [--destination=<dir>] [--org-id=<id>] [--name=<name>] [--version=<ver>]
```

Package types: `unspecified`, `archive`, `ml_model`, `module`, `slam_map`.

If `--org-id` and `--name` are omitted, reads from `meta.json` in the current directory.

### `viam packages upload`

```
viam packages upload --path=<file> --org-id=<id> --name=<name> --version=<ver> --type=<type> [--model-framework=<fw>] [--model-type=<type>]
```

---

## Training Commands

Under `viam train`.

### `viam train submit managed`

Submit a training job with a Viam-managed training script.

### `viam train submit custom from-registry`

Submit a custom training job using an existing registry script.

### `viam train submit custom with-upload`

Submit a custom training job while uploading a training script.

### `viam train get/logs/cancel/list`

```
viam train get --job-id=<id>
viam train logs --job-id=<id>
viam train cancel --job-id=<id>
viam train list --org-id=<id> [--job-status=<status>]
```

---

## Resource Commands

Under `viam resource`.

### `viam resource enable/disable`

```
viam resource enable --part=<part> --resource-name=<name> [--resource-name=<name2>...]
viam resource disable --part=<part> --resource-name=<name> [--resource-name=<name2>...]
```

### `viam resource update`

```
viam resource update --part=<part> --resource-name=<name> --config=<json-or-file>
```

---

## Profile Commands

Under `viam profiles`. Profiles allow multiple authentication contexts.

```
viam profiles add --profile-name=<name> --key-id=<id> --key=<key>
viam profiles update --profile-name=<name> --key-id=<id> --key=<key>
viam profiles list
viam profiles remove --profile-name=<name>
```

Use `--profile <name>` on any command to select a profile.

---

## Defaults Commands

Under `viam defaults`. Set default org/location so you don't have to pass them every time.

```
viam defaults set-org --org-id=<id>
viam defaults clear-org
viam defaults set-location --location-id=<id>
viam defaults clear-location
```

---

## Other Commands

### `viam version`

Print version info.

### `viam update`

Update the CLI to the latest version.

### `viam parse-ftdc`

Parse an FTDC file and open a REPL.

```
viam parse-ftdc --path=<file>
```

### `viam xacro convert`

Convert xacro files to URDF (uses Docker).

```
viam xacro convert --input-file=<file> --output-file=<file> [options]
```

### `viam traces`

Work with viam-server trace data. Subcommands: `import-local`, `import-remote`, `print-local`,
`print-remote`, `get-remote`.
