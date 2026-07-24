# Viam Configuration Schema Reference

Comprehensive reference for `meta.json` (module manifest) and robot configuration JSON structure.
Extracted from RDK source (`cli/module_registry.go`, `cli/module.schema.json`, `config/config.go`,
`config/module.go`), April 2026.

---

## Table of Contents
1. [meta.json Schema](#metajson-schema)
2. [Robot Config Structure](#robot-config-structure)
3. [Module Config in Robot](#module-config-in-robot)
4. [Component Config](#component-config)
5. [Service Config](#service-config)
6. [Remote Config](#remote-config)
7. [Fragment Config](#fragment-config)
8. [Process Config](#process-config)
9. [Package Config](#package-config)
10. [Common Config Patterns](#common-config-patterns)

---

## meta.json Schema

The module manifest file. JSON Schema: `https://dl.viam.dev/module.schema.json`

### Top-level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `$schema` | string | No | Schema URL for validation. Set to `https://dl.viam.dev/module.schema.json` |
| `module_id` | string | Yes | Colon-separated `ORG:NAME`. ORG is org UUID or public namespace. Pattern: `^[^:]+:[^:]+$` |
| `visibility` | enum | Yes | `"private"`, `"public"`, or `"public_unlisted"` |
| `url` | string (URI) | No* | Path to git repo or info page. **Required for cloud build.** Must be public git repo URL. |
| `description` | string | Yes | Short description of the module |
| `models` | array | Yes | Models provided by this module (see below) |
| `entrypoint` | string | Yes | Relative path to the executable entrypoint in the tarball |
| `first_run` | string | No | Command to run on first deployment (shared with RDK via `JSONManifest`) |
| `build` | object | No* | Build instructions. **Required for cloud build and code reloading.** |
| `markdown_link` | string | No | Relative path to the markdown doc file for this module |
| `applications` | array | No | App metadata for multi-machine or single-machine Viam apps |

### `models[]` Array Items

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `api` | string | Yes | Colon-delimited triple `NAMESPACE:TYPE:SUBTYPE` (e.g., `rdk:component:sensor`). Pattern: `^[^:]+:[^:]+:[^:]+$` |
| `model` | string | Yes | Colon-delimited triple `NAMESPACE:FAMILY:NAME`. Namespace must match org's public namespace. |
| `short_description` | string | No | Short description of this model. **Note:** The JSON schema calls this field `description`, but the Go struct serializes it as `short_description`. Use `short_description` in your meta.json. |
| `markdown_link` | string | No | Relative path to markdown doc for this specific model |

**API string structure:** `<namespace>:<type>:<subtype>`
- `namespace`: Usually `rdk` for built-in types, or your org namespace for custom types
- `type`: `component` or `service`
- `subtype`: e.g., `sensor`, `camera`, `arm`, `motor`, `vision`, `mlmodel`

**Model string structure:** `<namespace>:<family>:<name>`
- `namespace`: Your org's public namespace
- `family`: Grouping name (often the module name)
- `name`: Specific implementation name

### `build` Section

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `build` | string | `"make module.tar.gz"` | Shell command to build the module tarball |
| `setup` | string | (none) | Optional one-time setup command (e.g., `"sudo apt install nlopt"`) |
| `path` | string | `"module.tar.gz"` | Location of the built tarball produced by the build command |
| `arch` | string[] | `["linux/amd64", "linux/arm64"]` | Platforms for cloud build |
| `distro` | string | `"bullseye"` | Base image distro for cloud build. Use `"bookworm"` for C++ modules. |
| `darwin_deps` | string[] | (none) | Homebrew dependencies for darwin builds |

### `applications[]` Array Items

For Viam app modules:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | App display name |
| `type` | string | App type |
| `entrypoint` | string | App entrypoint |
| `fragmentIds` | string[] | Fragment IDs |
| `allowedOrgIds` | string[] | Allowed org IDs |
| `logoPath` | string | Logo file path |
| `customizations` | object | UI customizations |

### Minimal meta.json Example

```json
{
  "$schema": "https://dl.viam.dev/module.schema.json",
  "module_id": "my-namespace:my-module",
  "visibility": "private",
  "description": "A custom sensor module",
  "models": [
    {
      "api": "rdk:component:sensor",
      "model": "my-namespace:my-module:my-sensor"
    }
  ],
  "entrypoint": "run.sh"
}
```

### Full meta.json with Build Section

```json
{
  "$schema": "https://dl.viam.dev/module.schema.json",
  "module_id": "acme:weather-sensors",
  "visibility": "public",
  "url": "https://github.com/acme-robotics/weather-sensors",
  "description": "Weather sensor implementations for temperature and humidity",
  "models": [
    {
      "api": "rdk:component:sensor",
      "model": "acme:weather-sensors:temperature",
      "short_description": "Reads temperature from DHT22"
    },
    {
      "api": "rdk:component:sensor",
      "model": "acme:weather-sensors:humidity",
      "short_description": "Reads humidity from DHT22"
    }
  ],
  "entrypoint": "dist/main",
  "build": {
    "setup": "sudo apt-get install -y libgpiod-dev",
    "build": "make module.tar.gz",
    "path": "module.tar.gz",
    "arch": ["linux/amd64", "linux/arm64"],
    "distro": "bookworm"
  },
  "markdown_link": "README.md"
}
```

---

## Robot Config Structure

The full robot configuration as defined in `config.Config`. This is what gets managed via
the Viam app (app.viam.com) and stored in the cloud.

### Top-level JSON Structure

```json
{
  "cloud": { ... },
  "modules": [ ... ],
  "remotes": [ ... ],
  "components": [ ... ],
  "services": [ ... ],
  "processes": [ ... ],
  "packages": [ ... ],
  "network": { ... },
  "auth": { ... },
  "debug": false,
  "log": [ ... ],
  "maintenance": { ... },
  "jobs": [ ... ],
  "tracing": { ... }
}
```

### `cloud` Section

Managed by the app. Contains the machine's cloud identity.

```json
{
  "cloud": {
    "id": "<machine-part-id>",
    "secret": "<part-secret>",
    "app_address": "https://app.viam.com:443"
  }
}
```

---

## Module Config in Robot

Each entry in the `modules` array configures a module that provides resources.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Arbitrary unique name for the module. Used for socket naming. Cannot be `"parent"`. |
| `executable_path` | string | Path to the executable (absolute or relative to working dir). For local modules. |
| `log_level` | string | Log level: `""` (default), `"debug"`, `"info"`, `"warn"`, `"error"` |
| `type` | string | `"local"` or `"registry"` |
| `module_id` | string | Registry module ID (e.g., `"acme:weather-sensors"`). Empty for local modules. |
| `env` | object | Additional environment variables passed to the module process |
| `tcp_mode` | boolean | Use TCP connection instead of Unix socket |
| `first_run_timeout` | duration | Timeout for first run script (default: 1 hour) |

Module version for registry modules is managed by the package manager, not as a direct field in the module config.

### Local Module Example

```json
{
  "modules": [
    {
      "name": "my-custom-sensor",
      "type": "local",
      "executable_path": "/home/user/modules/my-sensor/run.sh",
      "log_level": "info"
    }
  ]
}
```

### Registry Module Example

```json
{
  "modules": [
    {
      "name": "acme_weather-sensors",
      "type": "registry",
      "module_id": "acme:weather-sensors"
    }
  ]
}
```

### Reload Fields (used by `module reload`)

When using `viam module reload-local` or `viam module reload`, additional fields are managed:

| Field | Description |
|-------|-------------|
| `reload_enabled` | Whether reload is active |
| `reload_path` | Absolute path to the local entrypoint |
| `reload_user` | Email or key ID of who triggered the reload |
| `reload_time` | RFC3339 timestamp of the reload |

---

## Component Config

Each entry in `components` follows the `resource.Config` structure.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique name for this component |
| `api` | string | API triple: `rdk:component:<subtype>` |
| `model` | string | Model triple: `<namespace>:<family>:<name>` |
| `attributes` | object | Model-specific configuration (arbitrary JSON) |
| `depends_on` | string[] | Explicit dependencies on other resources |
| `frame` | object | Frame system config (parent, translation, orientation) |
| `log_configuration` | object | Per-resource log level (`{"level": "debug"}`) |
| `disabled` | boolean | If true, resource will not start |

### Component Example

```json
{
  "components": [
    {
      "name": "my-temp-sensor",
      "api": "rdk:component:sensor",
      "model": "acme:weather-sensors:temperature",
      "attributes": {
        "pin": "4",
        "i2c_bus": "1"
      }
    },
    {
      "name": "left-motor",
      "api": "rdk:component:motor",
      "model": "rdk:builtin:gpio",
      "attributes": {
        "board": "local-board",
        "pins": {
          "pwm": "32",
          "dir": "29",
          "en": ""
        }
      },
      "depends_on": ["local-board"]
    }
  ]
}
```

---

## Service Config

Same structure as components but under `services`. Uses `rdk:service:<subtype>` API format.

### Common Service Types

| API | Description |
|-----|-------------|
| `rdk:service:vision` | Vision service (detection, classification, segmentation) |
| `rdk:service:motion` | Motion planning |
| `rdk:service:mlmodel` | ML model inference |
| `rdk:service:slam` | SLAM mapping and localization |
| `rdk:service:navigation` | Navigation |
| `rdk:service:data_manager` | Data capture and sync |
| `rdk:service:shell` | Remote shell access |

### Data Manager Service Example

```json
{
  "services": [
    {
      "name": "data-manager",
      "api": "rdk:service:data_manager",
      "model": "rdk:builtin:builtin",
      "attributes": {
        "capture_dir": "/home/user/.viam/capture",
        "sync_interval_mins": 5,
        "additional_sync_paths": []
      }
    }
  ]
}
```

### Data Capture Configuration

Data capture is configured per-component via the `data_capture_methods` field within service config
or as part of component attributes:

```json
{
  "name": "my-camera",
  "api": "rdk:component:camera",
  "model": "rdk:builtin:webcam",
  "attributes": {
    "video_path": "video0"
  },
  "service_configs": [
    {
      "type": "data_manager",
      "attributes": {
        "capture_methods": [
          {
            "method": "ReadImage",
            "capture_frequency_hz": 0.5,
            "additional_params": {
              "mime_type": "image/jpeg"
            }
          }
        ]
      }
    }
  ]
}
```

---

## Remote Config

Connect to another machine and use its resources as if they were local.

```json
{
  "remotes": [
    {
      "name": "remote-arm",
      "address": "remote-machine.xxxx.viam.cloud:443",
      "secret": "<location-secret>",
      "frame": {
        "parent": "world",
        "translation": {"x": 0, "y": 0, "z": 0},
        "orientation": {"type": "ov_degrees", "value": {"x": 0, "y": 0, "z": 1, "th": 0}}
      }
    }
  ]
}
```

### Remote Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique name |
| `address` | string | FQDN or IP:port of the remote machine |
| `secret` | string | Location secret for authentication |
| `frame` | object | Frame system attachment for remote's world frame |
| `insecure` | boolean | Allow insecure connections |
| `managed_by` | string | Managed by identifier |

---

## Fragment Config

Fragments are reusable configuration snippets managed at the organization level. They are
applied to machine parts and merged with the part's own config.

Fragments are referenced by ID in the machine part configuration. The app manages fragment
inheritance.

### Working with Fragments via CLI

```
# Add a fragment to a part
viam machines part fragments add --part=<part-id> --fragment=<fragment-name-or-id>

# Remove a fragment from a part
viam machines part fragments remove --part=<part-id> --fragment=<fragment-name-or-id>
```

Fragments are particularly useful for fleet management: define a standard configuration
once as a fragment, then apply it to many machines.

### Fragment Behavior

- Fragment config is merged into the part config
- Part-level config takes precedence over fragment config for conflicts
- Changes to a fragment propagate to all machines using it
- A part can use multiple fragments

---

## Process Config

Processes are arbitrary programs managed by viam-server.

```json
{
  "processes": [
    {
      "name": "data-collector",
      "id": "data-collector",
      "log": true,
      "cwd": "/home/user/scripts",
      "one_shot": false
    }
  ]
}
```

---

## Package Config

Packages are versioned artifacts downloaded from the registry.

```json
{
  "packages": [
    {
      "name": "ml-model-v2",
      "package": "acme/my-ml-model",
      "type": "ml_model",
      "version": "1.0.0"
    }
  ]
}
```

### Package Types

| Type | Description |
|------|-------------|
| `module` | Module binary package |
| `ml_model` | ML model artifact |
| `slam_map` | SLAM map data |
| `archive` | Generic archive |
| `ml_training` | ML training script |

Note: `archive` and `ml_training` types are only valid for CLI package commands (`viam packages export/upload`), not in robot config `packages[]` entries. Robot config supports: `ml_model`, `module`, `slam_map`.

---

## Common Config Patterns

### Add a Registry Module + Component

The minimum to use a registry module: add the module, then add a component that uses it.

```json
{
  "modules": [
    {
      "name": "acme_weather-sensors",
      "type": "registry",
      "module_id": "acme:weather-sensors"
    }
  ],
  "components": [
    {
      "name": "temp-sensor-1",
      "api": "rdk:component:sensor",
      "model": "acme:weather-sensors:temperature",
      "attributes": {
        "pin": "4"
      }
    }
  ]
}
```

### Add a Local Module + Component

```json
{
  "modules": [
    {
      "name": "my-local-module",
      "type": "local",
      "executable_path": "/home/user/my-module/run.sh"
    }
  ],
  "components": [
    {
      "name": "my-sensor",
      "api": "rdk:component:sensor",
      "model": "my-org:my-module:my-sensor",
      "attributes": {}
    }
  ]
}
```

### Set Up Data Capture

1. Ensure the data manager service is configured
2. Add capture configuration to each component

```json
{
  "services": [
    {
      "name": "data-mgr",
      "api": "rdk:service:data_manager",
      "model": "rdk:builtin:builtin",
      "attributes": {
        "sync_interval_mins": 1,
        "capture_dir": ""
      }
    }
  ],
  "components": [
    {
      "name": "my-camera",
      "api": "rdk:component:camera",
      "model": "rdk:builtin:webcam",
      "attributes": { "video_path": "video0" },
      "service_configs": [
        {
          "type": "data_manager",
          "attributes": {
            "capture_methods": [
              {
                "method": "ReadImage",
                "capture_frequency_hz": 1,
                "additional_params": { "mime_type": "image/jpeg" }
              }
            ]
          }
        }
      ]
    }
  ]
}
```

### Multi-Part Configuration

A machine can have multiple parts. Each part runs its own `viam-server` and has its own
config. Parts communicate via the `remotes` mechanism automatically when managed through
the app.
