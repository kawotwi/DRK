# Viam Modules & Fleet -- Quick Reference Cheatsheet

Companion to `SKILL.md`. Load when answering questions about CLI commands, meta.json fields,
or robot config snippets. Based on RDK source analysis, April 2026.

## Table of Contents
1. [CLI Command Quick Reference](#cli-command-quick-reference)
2. [meta.json Minimal Template](#metajson-minimal-template)
3. [meta.json Full Template](#metajson-full-template)
4. [Robot Config Snippet Templates](#robot-config-snippet-templates)
5. [Module Packaging Commands](#module-packaging-commands)
6. [Platform Matrix](#platform-matrix)
7. [Identifier Format Reference](#identifier-format-reference)
8. [Common Error Messages and Fixes](#common-error-messages-and-fixes)

---

## CLI Command Quick Reference

### Authentication
| Command | Description |
|---------|-------------|
| `viam login` | Browser-based OAuth login |
| `viam login api-key --key-id=X --key=Y` | API key login (CI/CD) |
| `viam logout` | End current session |
| `viam whoami` | Show current identity |

### Module Lifecycle
| Command | Description |
|---------|-------------|
| `viam module generate` | Interactive module scaffolding (Python/Go) |
| `viam module create --name=X` | Register module on app.viam.com, create meta.json |
| `viam module update` | Push meta.json changes to registry |
| `viam module update-models` | Auto-detect models from binary, update meta.json |
| `viam module build local` | Run build.build from meta.json locally |
| `viam module build start --version=X` | Trigger cloud build |
| `viam module build list` | Check cloud build status |
| `viam module build logs --id=X` | View cloud build logs |
| `viam module upload --version=X --platform=Y --upload=Z` | Upload module to registry |
| `viam module download` | Download a module package |
| `viam module reload-local` | Build locally, deploy to machine, hot-reload |
| `viam module reload` | Cloud build, deploy to machine, hot-reload |
| `viam module restart` | Restart running module on a machine |

### Machines
| Command | Description |
|---------|-------------|
| `viam machines list` | List machines in org/location |
| `viam machines create --name=X --location=Y` | Create a new machine |
| `viam machines delete --machine=X` | Delete a machine |
| `viam machines status --machine=X` | Show machine status |
| `viam machines logs --machine=X` | View machine logs |
| `viam machines part list --machine=X` | List parts on a machine |
| `viam machines part status --part=X` | Show part status |
| `viam machines part logs --part=X [-f]` | View/tail part logs |
| `viam machines part shell --part=X` | SSH-like shell into machine |
| `viam machines part cp --part=X src dst` | Copy files to/from machine |
| `viam machines part restart --part=X` | Restart a machine part |
| `viam machines part add-resource --part=X --name=N --model-name=M` | Add resource to part |
| `viam machines part fragments add --part=X` | Add a fragment to a part |
| `viam machines part history --part=X` | View config change history |

### Resources
| Command | Description |
|---------|-------------|
| `viam resource enable --part=X --resource-name=Y` | Enable a resource |
| `viam resource disable --part=X --resource-name=Y` | Disable a resource |
| `viam resource update --part=X --resource-name=Y --config='{}'` | Update resource config |

### Organizations & Locations
| Command | Description |
|---------|-------------|
| `viam organizations list` | List your organizations |
| `viam organizations api-key create --org-id=X` | Create org API key |
| `viam locations list` | List locations |
| `viam locations api-key create --location-id=X` | Create location API key |

### Data
| Command | Description |
|---------|-------------|
| `viam data export binary filter --destination=D` | Download binary data |
| `viam data export tabular --destination=D --part-id=X ...` | Download tabular data |
| `viam data delete binary --org-ids=X --start=S --end=E` | Delete binary data |

### Datasets
| Command | Description |
|---------|-------------|
| `viam dataset create --org-id=X --name=N` | Create dataset |
| `viam dataset export --destination=D --dataset-id=X` | Download dataset |
| `viam dataset list --org-id=X` | List datasets |

### Packages
| Command | Description |
|---------|-------------|
| `viam packages export --type=T` | Download a package |
| `viam packages upload --path=P --org-id=X --name=N --version=V --type=T` | Upload package |

### Defaults & Profiles
| Command | Description |
|---------|-------------|
| `viam defaults set-org --org-id=X` | Set default org |
| `viam defaults set-location --location-id=X` | Set default location |
| `viam profiles add --profile-name=N --key-id=K --key=V` | Add auth profile |
| `viam --profile myprofile <command>` | Use a specific profile |

---

## meta.json Minimal Template

```json
{
  "$schema": "https://dl.viam.dev/module.schema.json",
  "module_id": "NAMESPACE:MODULE-NAME",
  "visibility": "private",
  "description": "Short description",
  "models": [
    {
      "api": "rdk:component:sensor",
      "model": "NAMESPACE:MODULE-NAME:MODEL-NAME"
    }
  ],
  "entrypoint": "run.sh"
}
```

---

## meta.json Full Template

```json
{
  "$schema": "https://dl.viam.dev/module.schema.json",
  "module_id": "acme:weather-sensors",
  "visibility": "public",
  "url": "https://github.com/acme/weather-sensors",
  "description": "Temperature and humidity sensors for DHT22",
  "models": [
    {
      "api": "rdk:component:sensor",
      "model": "acme:weather-sensors:temperature",
      "short_description": "DHT22 temperature readings"
    },
    {
      "api": "rdk:component:sensor",
      "model": "acme:weather-sensors:humidity"
    }
  ],
  "entrypoint": "dist/main",
  "first_run": "setup.sh",
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

## Robot Config Snippet Templates

### Registry Module + Component
```json
{
  "modules": [{
    "name": "acme_weather-sensors",
    "type": "registry",
    "module_id": "acme:weather-sensors"
  }],
  "components": [{
    "name": "temp-1",
    "api": "rdk:component:sensor",
    "model": "acme:weather-sensors:temperature",
    "attributes": {"pin": "4"}
  }]
}
```

### Local Module + Component
```json
{
  "modules": [{
    "name": "my-module",
    "type": "local",
    "executable_path": "/path/to/run.sh"
  }],
  "components": [{
    "name": "my-sensor",
    "api": "rdk:component:sensor",
    "model": "myorg:my-module:my-sensor",
    "attributes": {}
  }]
}
```

### Data Capture Setup
```json
{
  "services": [{
    "name": "data-mgr",
    "api": "rdk:service:data_manager",
    "model": "rdk:builtin:builtin",
    "attributes": {"sync_interval_mins": 5}
  }],
  "components": [{
    "name": "cam",
    "api": "rdk:component:camera",
    "model": "rdk:builtin:webcam",
    "attributes": {"video_path": "video0"},
    "service_configs": [{
      "type": "data_manager",
      "attributes": {
        "capture_methods": [{
          "method": "ReadImage",
          "capture_frequency_hz": 1,
          "additional_params": {"mime_type": "image/jpeg"}
        }]
      }
    }]
  }]
}
```

### Vision Service with ML Model
```json
{
  "services": [
    {
      "name": "mlmodel-1",
      "api": "rdk:service:mlmodel",
      "model": "rdk:builtin:tflite_cpu",
      "attributes": {
        "model_path": "${packages.my-model}/model.tflite",
        "label_path": "${packages.my-model}/labels.txt"
      }
    },
    {
      "name": "vision-1",
      "api": "rdk:service:vision",
      "model": "rdk:builtin:mlmodel",
      "attributes": {
        "mlmodel_name": "mlmodel-1"
      }
    }
  ]
}
```

---

## Module Packaging Commands

### Local Build + Manual Upload
```bash
# Build locally
viam module build local

# Upload for a single platform
viam module upload --version 0.1.0 --platform linux/amd64 --upload ./module.tar.gz
```

### Cloud Build + Auto Upload
```bash
# Start a cloud build (builds for all platforms in meta.json build.arch)
viam module build start --version 0.1.0

# Monitor the build
viam module build logs --id <build-id> --wait

# List recent builds
viam module build list --count 5
```

### Development Loop (reload)
```bash
# Build locally and deploy to a machine
viam module reload-local --part-id <UUID>

# Same but add a resource to the machine config
viam module reload-local --part-id <UUID> --model-name acme:weather:temp

# Skip build, just redeploy existing tarball
viam module reload-local --part-id <UUID> --no-build

# For local dev (module on same machine as viam-server)
viam module reload-local --part-id <UUID> --local
```

---

## Platform Matrix

| Platform | OS | Arch | Typical Use |
|----------|-----|------|-------------|
| `any` | Any | Any | Pure Python modules |
| `any/amd64` | Any | x86_64 | Docker-based modules |
| `any/arm64` | Any | ARM64 | Docker-based ARM modules |
| `linux/amd64` | Linux | x86_64 | Standard compiled modules |
| `linux/arm64` | Linux | ARM64 | Raspberry Pi 4, Jetson |
| `linux/arm32v7` | Linux | ARMv7 | Raspberry Pi 3 |
| `linux/arm32v6` | Linux | ARMv6 | Raspberry Pi Zero |
| `linux/any` | Linux | Any | Python modules requiring Linux OS support |
| `darwin/any` | macOS | Any | Python modules requiring macOS support |
| `darwin/amd64` | macOS | Intel | Intel Macs |
| `darwin/arm64` | macOS | Apple Silicon | M1/M2/M3 Macs |

---

## Identifier Format Reference

| Identifier | Format | Example |
|-----------|--------|---------|
| Module ID | `namespace:name` or `org-id:name` | `acme:weather-sensors` |
| API triple | `namespace:type:subtype` | `rdk:component:sensor` |
| Model triple | `namespace:family:name` | `acme:weather-sensors:temperature` |
| Org ID | UUID | `a1b2c3d4-e5f6-...` |
| Part ID | UUID | `f7g8h9i0-j1k2-...` |
| Machine ID | UUID | `m1n2o3p4-q5r6-...` |
| Location ID | UUID | `l1m2n3o4-p5q6-...` |

---

## Common Error Messages and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `your meta.json cannot have an empty build step` | `build.build` is empty or `build` section missing | Add a `"build"` section to meta.json with at least the `"build"` field |
| `meta.json must have a url field set in order to start a cloud build` | Missing `url` in meta.json | Set `"url"` to your public git repo URL |
| `nothing to upload -- please provide a path to your module` | Missing `--upload` flag or positional arg | Add `--upload ./module.tar.gz` or pass the path as a positional arg |
| `unable to find the meta.json` | No meta.json in current dir, no `--module` flag | Run from the directory with meta.json, or pass `--module /path/to/meta.json` |
| `module name cannot be changed once set` | Trying to rename via `module create` | Module names are immutable. Create a new module with the new name. |
| `a different module's meta.json already exists in the current directory` | `module create` in a dir with existing meta.json | Delete existing meta.json or `cd` to a clean directory |
| `error validating API string` | Malformed API in meta.json models | Use format `namespace:type:subtype` (e.g., `rdk:component:sensor`) |
| `API with unknown type 'X', expected one of service, component` | Wrong type in API triple | Use `component` or `service` as the middle segment |
| `provided model name was not found in the meta.json` | `--model-name` in reload doesn't match any model in meta.json | Check the `models` array in meta.json |
| `cloud build is not currently supported for Windows Python modules` | Windows + Python + cloud build | Use `viam module build local` and `viam module upload` instead |
| `no binary specified: use --binary or set entrypoint in meta.json` | `update-models` can't find the binary | Set `entrypoint` in meta.json or pass `--binary` flag |
| `resource name X already exists in part config` | Duplicate resource name during reload | Use a different `--resource-name` or remove the existing resource |
| `timed out waiting for shell service to start` | Shell service not responding after config | Check that the machine is online and the shell service is properly configured |
| `update failed and could not re-fetch part config` | Concurrent config modification | Retry the command; the CLI uses optimistic concurrency control |
| `version of the module to upload (semver2.0)` | Invalid version format | Use semantic versioning: `X.Y.Z` (e.g., `0.1.0`, `1.2.3`) |
