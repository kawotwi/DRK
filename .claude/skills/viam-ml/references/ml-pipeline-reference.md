# Viam ML Pipeline Reference

Built from RDK source, training script repos, and ML runtime modules circa April 2026.

---

## End-to-End Pipeline Overview

```
Robot (components)
  |
  v
Data Capture (collectors on methods at configured Hz)
  |
  v
Local Storage (~/.viam/capture/)
  |
  v
Data Sync (background, configurable interval)
  |
  v
Viam Cloud Storage
  |
  v
Dataset (filtered, annotated subset of cloud data)
  |
  v
Training Script (Keras / Ultralytics / TensorFlow / custom)
  |
  v
Model Artifact (.tflite, .onnx, SavedModel, etc.)
  |
  v
Model Registry (uploaded to Viam registry)
  |
  v
Model Deployment (deployed to robot via packages)
  |
  v
ML Model Service (Infer / Metadata)
  |
  v
Vision Service (detections / classifications from ML model)
  |
  v
Application Logic
```

---

## Data Capture

### Service Interface

```go
// Package: go.viam.com/rdk/services/datamanager
type Service interface {
    resource.Resource
    Sync(ctx context.Context, extra map[string]interface{}) error
    UploadBinaryDataToDatasets(ctx context.Context, binaryData []byte, datasetIDs, tags []string,
        mimeType datasyncpb.MimeType, extra map[string]interface{}) error
    UploadImageToDatasets(ctx context.Context, image image.Image, datasetIDs, tags []string,
        mimeType datasyncpb.MimeType, extra map[string]interface{}) error
}
```

### Data Capture Configuration

Data capture is configured as an **associated config** on individual components, not on the
data manager service itself. Each component can have multiple capture methods.

```go
// DataCaptureConfig initializes a collector for a component or remote.
type DataCaptureConfig struct {
    Name               resource.Name          `json:"name"`
    Method             string                 `json:"method"`
    CaptureFrequencyHz float32                `json:"capture_frequency_hz"`
    CaptureQueueSize   int                    `json:"capture_queue_size"`
    CaptureBufferSize  int                    `json:"capture_buffer_size"`
    AdditionalParams   map[string]interface{} `json:"additional_params"`
    Disabled           bool                   `json:"disabled"`
    Tags               []string               `json:"tags,omitempty"`
    CaptureDirectory   string                 `json:"capture_directory"`
}
```

**JSON config example** (on a camera component):

```json
{
  "name": "my_camera",
  "type": "camera",
  "model": "webcam",
  "attributes": { ... },
  "service_configs": [
    {
      "type": "data_manager",
      "attributes": {
        "capture_methods": [
          {
            "method": "GetImages",
            "capture_frequency_hz": 0.5,
            "additional_params": {},
            "disabled": false,
            "tags": ["training-data"]
          }
        ]
      }
    }
  ]
}
```

**Common capture methods by component type:**

| Component | Method | Data Type |
|-----------|--------|-----------|
| Camera | `GetImages` | Images (binary) |
| Camera | `ReadImage` | Single image (binary) |
| Camera | `NextPointCloud` | Point cloud (binary) |
| Sensor | `Readings` | Tabular (key-value) |
| MovementSensor | `LinearVelocity`, `AngularVelocity`, `Position`, `CompassHeading`, etc. | Tabular |
| Motor | `IsPowered`, `Position` | Tabular |
| Arm | `EndPosition`, `JointPositions` | Tabular |
| Vision | `GetClassifications`, `GetDetections` | Tabular |

### Data Manager Service Configuration

The data manager service controls sync behavior and disk management:

```json
{
  "name": "data_manager-1",
  "type": "data_manager",
  "attributes": {
    "capture_dir": "~/.viam/capture",
    "tags": [],
    "capture_disabled": false,
    "sync_disabled": false,
    "sync_interval_mins": 0.1,
    "additional_sync_paths": [],
    "file_last_modified_millis": 10000,
    "maximum_num_sync_threads": 4,
    "maximum_capture_file_size_bytes": 262144,
    "delete_every_nth_when_disk_full": 5,
    "disk_usage_deletion_threshold": 0.9,
    "capture_dir_deletion_threshold": 0.5,
    "selective_syncer_name": ""
  }
}
```

**Key defaults:**

| Parameter | Default | Notes |
|-----------|---------|-------|
| `capture_dir` | `~/.viam/capture` | Local storage before sync |
| `sync_interval_mins` | `0.1` (6 seconds) | Minimum effective interval |
| `maximum_capture_file_size_bytes` | `262144` (256 KB) | Per capture file |
| `disk_usage_deletion_threshold` | `0.9` (90%) | Start deleting old files |
| `capture_dir_deletion_threshold` | `0.5` (50%) | Capture dir must be this % of disk |
| `delete_every_nth_when_disk_full` | `5` | Delete every 5th file when threshold hit |

### Dynamic Capture Control

A `CaptureControlSensor` can dynamically adjust capture at runtime:

```go
type CaptureConfigReading struct {
    ResourceName       string   `json:"resource_name"`
    Method             string   `json:"method"`
    CaptureFrequencyHz *float32 `json:"capture_frequency_hz,omitempty"`
    Tags               []string `json:"tags"`
}
```

### Selective Sync

The `selective_syncer_name` field references a sensor whose `ShouldSync` reading controls
whether data syncs. Use `CreateShouldSyncReading(bool)` in a modular sensor to produce the
expected reading format.

---

## Dataset Management

Datasets are managed through the Viam app UI or CLI. A dataset is a filtered, annotated
collection of captured data used for training.

**CLI commands (brief -- see viam-modules-fleet for details):**

```bash
# List datasets
viam dataset list --org-id=<ORG_ID>

# Create a dataset
viam dataset create --org-id=<ORG_ID> --name=<NAME>

# Export a dataset (downloads data for local use)
viam dataset export --destination=<PATH> --dataset-id=<DATASET_ID>

# Add/remove data from datasets via data commands
viam data database configure --org-id=<ORG_ID>
```

### Dataset File Format (JSONLines)

Training scripts receive data as a **JSONLines file** (one JSON object per line).

**Image classification dataset line:**
```json
{
  "image_path": "/path/to/image.jpg",
  "classification_annotations": [
    {"annotation_label": "cat"},
    {"annotation_label": "animal"}
  ]
}
```

**Object detection dataset line:**
```json
{
  "image_path": "/path/to/image.jpg",
  "bounding_box_annotations": [
    {
      "annotation_label": "cat",
      "x_min_normalized": 0.1,
      "y_min_normalized": 0.2,
      "x_max_normalized": 0.5,
      "y_max_normalized": 0.8
    }
  ]
}
```

Bounding box coordinates are **normalized** (0.0 to 1.0 relative to image dimensions).

---

## ML Model Service Interface

### Go Interface

```go
// Package: go.viam.com/rdk/services/mlmodel
// API: rdk:service:mlmodel

type Service interface {
    resource.Resource

    // Infer takes input tensors, runs inference, returns output tensors.
    Infer(ctx context.Context, tensors ml.Tensors) (ml.Tensors, error)

    // Metadata returns model metadata: name, type, input/output tensor info.
    Metadata(ctx context.Context) (MLMetadata, error)
}
```

### Tensor Types

```go
// Package: go.viam.com/rdk/ml
// Tensors maps tensor names to dense tensor data.
type Tensors map[string]*tensor.Dense  // gorgonia.org/tensor
```

**Supported tensor data types:**
`int8`, `uint8`, `int16`, `uint16`, `int32`, `uint32`, `int64`, `uint64`, `float32`, `float64`

### MLMetadata

```go
type MLMetadata struct {
    ModelName        string       // e.g. "my_detector"
    ModelType        string       // e.g. "object_detector", "text_classifier"
    ModelDescription string
    Inputs           []TensorInfo
    Outputs          []TensorInfo
}

type TensorInfo struct {
    Name            string                 // e.g. "image", "bounding_boxes"
    Description     string
    DataType        string                 // e.g. "uint8", "float32"
    Shape           []int                  // e.g. [1, 384, 384, 3]
    AssociatedFiles []File                 // e.g. label files
    Extra           map[string]interface{}
}

type File struct {
    Name        string    // e.g. "labels.txt"
    Description string
    LabelType   LabelType // TENSOR_VALUE or TENSOR_AXIS
}
```

**LabelType values:**

| Value | Meaning |
|-------|---------|
| `TENSOR_VALUE` | Labels are the actual value in the tensor (e.g., `[0, 1, 2, 1]`) |
| `TENSOR_AXIS` | Labels are positional within the tensor axis (e.g., `[[.8,.1,.1], ...]`) |

### Using the ML Model Service (Go)

```go
import (
    "go.viam.com/rdk/ml"
    "go.viam.com/rdk/services/mlmodel"
    "gorgonia.org/tensor"
)

myMLModel, err := mlmodel.FromProvider(machine, "my_mlmodel")

// Infer
inputTensors := ml.Tensors{
    "image": tensor.New(
        tensor.Of(tensor.Uint8),
        tensor.WithShape(1, 384, 384, 3),
        tensor.WithBacking(imageBytes),  // []uint8 of length 1*384*384*3
    ),
}
outputTensors, err := myMLModel.Infer(ctx, inputTensors)

// Metadata
metadata, err := myMLModel.Metadata(ctx)
```

---

## Model Deployment: Runtime Configurations

### TFLite (`viam:mlmodel-tflite:tflite_cpu`)

**Module ID:** `viam:tflite_cpu`
**Platforms:** linux/amd64, linux/arm64, darwin/arm64, windows/amd64
**Model format:** `.tflite` files

**Config attributes:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `model_path` | Yes | Absolute path to `.tflite` file |
| `label_path` | No | Absolute path to `.txt` labels file |
| `num_threads` | No | CPU threads for inference (default: 1) |

**Configuration example:**

```json
{
  "name": "fruit_classifier",
  "type": "mlmodel",
  "model": "viam:mlmodel-tflite:tflite_cpu",
  "attributes": {
    "model_path": "${packages.my_fruit_model}/my_fruit_model.tflite",
    "label_path": "${packages.my_fruit_model}/labels.txt",
    "num_threads": 1
  }
}
```

**With registry model deployment (packages auto-configured):**

```json
{
  "packages": [
    {
      "package": "39c34811-9999-4fff-bd91-26a0e4e90644/my_fruit_model",
      "version": "YYYY-MM-DDThh-mm-ss",
      "name": "my_fruit_model",
      "type": "ml_model"
    }
  ]
}
```

**Model requirements (TFLite):**
- Single input tensor: UInt8 (0-255) or Float32 (-1 to 1) image
- For detectors: at least 3 output tensors (bounding boxes, class labels, confidence scores)
- Bounding box output: `[x x y y]` order, values 0-1 (proportional)
- Compatible architectures: EfficientDet, MobileNet, SSD MobileNet V1

**Implementation notes (from source):**
- Model file is read into memory at configuration time (not memory-mapped) to avoid file-change issues during inference
- A zero-input inference is run at configuration time to populate output tensor metadata
- Inference is single-threaded per interpreter (mutex-locked); concurrent calls serialize
- Tensor data is returned as views aliasing interpreter buffers (zero-copy until caller releases)

### Triton Server (`viam:mlmodelservice:triton`)

**Module ID:** `viam:mlmodelservice-triton-jetpack`
**Requirements:** NVIDIA GPU + NVIDIA Container Runtime (Jetson Orin or CUDA-capable GPU)
**Supported frameworks:** TensorFlow, PyTorch, TensorRT, ONNX (via Triton backends)

**Config attributes:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `model_name` | Yes | Model name to load from repository |
| `model_repository_path` | Semi | Container-side path to model repository (under `~/.viam`) |
| `model_path` | Semi | Directory containing model; supports `${packages.ml_model.X}` |
| `model_version` | No | Model version (default: newest = `-1`) |
| `backend_directory` | No | Override Triton backend directory |
| `tensor_name_remappings` | No | Rename input/output tensor names for vision service compatibility |
| `model_config` | No | Triton model config overrides (instance groups, dynamic batching) |

Exactly one of `model_repository_path` or `model_path` is required.

**Minimal configuration:**

```json
{
  "name": "mlmodel-effdet-triton",
  "type": "mlmodel",
  "model": "viam:mlmodelservice:triton",
  "attributes": {
    "model_name": "efficientdet-lite4-detection",
    "model_path": "${packages.ml_model.FaceDetector}"
  }
}
```

**With tensor name remappings (common for detection models):**

```json
{
  "attributes": {
    "model_name": "coco",
    "model_path": "${packages.ml_model.TF2-EfficientDetD0-COCO}",
    "tensor_name_remappings": {
      "outputs": {
        "output_0": "location",
        "output_1": "score",
        "output_2": "category",
        "output_3": "n_detections"
      },
      "inputs": {
        "images": "image"
      }
    }
  }
}
```

**Triton model repository structure:**

```
~/.viam/triton/repository/
  my_model/
    config.pbtxt          (optional but recommended)
    1/                    (version number, any positive integer)
      model.savedmodel/   (for TensorFlow)
        saved_model.pb
        variables/
          variables.data-00000-of-00001
          variables.index
```

**For ONNX models:**
```
my_model/
  1/
    model.onnx
```

**For PyTorch (TorchScript):**
```
my_model/
  1/
    model.pt
```

### ONNX Runtime

ONNX models are typically served via Triton (above) or through a custom module.
YOLO training scripts export to ONNX format by default.

**Model format:** `.onnx` file + `labels.txt`

### PyTorch

PyTorch models are served through Triton using the PyTorch backend.
Models must be exported as TorchScript (`.pt`) format for Triton serving.

### TensorFlow (SavedModel)

TensorFlow SavedModel format is served through Triton.
The tabular-data-tensorflow training script exports in SavedModel format directly.

---

## Vision Service and ML Model Integration

The vision service consumes ML model service outputs to provide detection and classification.

### Configuring Vision with ML Model

```json
{
  "name": "my_detector",
  "type": "vision",
  "model": "mlmodel",
  "attributes": {
    "mlmodel_name": "fruit_classifier"
  }
}
```

The vision service's `mlmodel` model type wraps any ML model service and exposes it as
detections or classifications depending on the model type.

### How Detection Output Tensors Are Interpreted

The RDK's `ml` package (`go.viam.com/rdk/ml`) automatically interprets model output tensors.

**Expected detection tensor names:** `location`, `category`, `score`
- If tensor names don't match, the RDK uses heuristics to guess:
  - 3D tensor -> `location`
  - Integer-typed 2D tensor -> `category`
  - Float-typed 2D tensor -> `score`
  - 1D tensor -> `n_detections`

**Bounding box coordinate interpretation:**
- If all four values for the first detection sum to less than 4.0, coordinates are treated as proportional (0-1)
- Otherwise, coordinates are treated as absolute pixel values and normalized by image dimensions

**Box order:** The default expected order is `[x, y, x, y]` (xmin, ymin, xmax, ymax).
Triton models may need `tensor_name_remappings` to match these expectations.

### How Classification Output Tensors Are Interpreted

**Expected tensor name:** `probability`
- If not found and model has exactly one output tensor, that tensor is used
- Output values are checked: if any value is outside [0,1], softmax is applied
- For binary classifiers (single output), sigmoid is applied if value is outside [-1,1]

### Label Files

Label files (`labels.txt`) are simple text files with one label per line.
The line number (0-indexed) corresponds to the tensor index for that class.

Example `labels.txt`:
```
cat
dog
bird
UNKNOWN
```

---

## Framework-Specific Details

### Input Tensor Formats

**Image models (TFLite, detection, classification):**
- Shape: `[batch, height, width, channels]` (NHWC format)
- Common shapes: `[1, 256, 256, 3]`, `[1, 384, 384, 3]`
- dtype: `uint8` (0-255) or `float32` (-1 to 1)
- Channels: RGB (3 channels)

**Tabular models:**
- Shape: `[batch, 1]` per input feature
- Each input has its own named tensor

### Output Tensor Formats

**Classification:**
- Single tensor named `probability` (or similar)
- Shape: `[1, num_classes]`
- Values: probabilities (0-1) or logits (softmax applied by RDK)

**Detection:**
- `location` tensor: shape `[1, max_detections, 4]` (bounding box coordinates)
- `category` tensor: shape `[1, max_detections]` (class indices)
- `score` tensor: shape `[1, max_detections]` (confidence scores)
- Optional `n_detections` tensor: shape `[1]` (actual number of valid detections)

**Detection output for Keras/Viam-trained models (from CombinedNMS):**
- Bounding boxes in `rel_yxyx` format (y_min, x_min, y_max, x_max, normalized)
- Output keys: `boxes`, `classes`, `confidence`, `num_detections`

### Preprocessing Patterns

**Classification (Keras):**
```python
preprocessing = keras.Sequential([
    keras.layers.Resizing(256, 256, crop_to_aspect_ratio=False),
])
```

**Detection (Keras):**
```python
preprocessing = keras.Sequential([
    keras_cv.layers.Resizing(384, 384, crop_to_aspect_ratio=False, pad_to_aspect_ratio=True),
])
```

**YOLO (Ultralytics):**
- Input size: 640x640 (default `imgsz=640`)
- Preprocessing handled internally by Ultralytics
