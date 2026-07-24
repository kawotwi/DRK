# Viam ML Cheatsheet

Quick-reference tables, config snippets, and templates.

---

## Supported Model Formats per Runtime

| Runtime Module | Model Format | Platforms | GPU Required |
|---------------|-------------|-----------|-------------|
| `viam:mlmodel-tflite:tflite_cpu` | `.tflite` | linux/amd64, linux/arm64, darwin/arm64, windows/amd64 | No |
| `viam:mlmodelservice:triton` | SavedModel, ONNX, TorchScript, TensorRT | linux (NVIDIA GPU) | Yes |

---

## Config Snippets

### TFLite Deployment (most common)

```json
{
  "services": [
    {
      "name": "my_classifier",
      "type": "mlmodel",
      "model": "viam:mlmodel-tflite:tflite_cpu",
      "attributes": {
        "model_path": "${packages.my_model}/classification_model.tflite",
        "label_path": "${packages.my_model}/labels.txt",
        "num_threads": 2
      }
    }
  ],
  "packages": [
    {
      "package": "<org-id>/my_model",
      "version": "latest",
      "name": "my_model",
      "type": "ml_model"
    }
  ]
}
```

### Triton Deployment

```json
{
  "name": "my_detector_triton",
  "type": "mlmodel",
  "model": "viam:mlmodelservice:triton",
  "attributes": {
    "model_name": "my_detection_model",
    "model_path": "${packages.ml_model.MyModel}",
    "tensor_name_remappings": {
      "outputs": {
        "output_0": "location",
        "output_1": "score",
        "output_2": "category",
        "output_3": "n_detections"
      }
    }
  }
}
```

### Vision Service wrapping ML Model

```json
{
  "name": "my_vision",
  "type": "vision",
  "model": "mlmodel",
  "attributes": {
    "mlmodel_name": "my_classifier"
  }
}
```

### Data Capture on a Camera

```json
{
  "name": "my_camera",
  "type": "camera",
  "model": "webcam",
  "attributes": { "video_path": "video0" },
  "service_configs": [
    {
      "type": "data_manager",
      "attributes": {
        "capture_methods": [
          {
            "method": "GetImages",
            "capture_frequency_hz": 0.5,
            "disabled": false,
            "tags": ["training-data"]
          }
        ]
      }
    }
  ]
}
```

### Data Capture on a Sensor

```json
{
  "name": "my_sensor",
  "type": "sensor",
  "model": "my_sensor_model",
  "service_configs": [
    {
      "type": "data_manager",
      "attributes": {
        "capture_methods": [
          {
            "method": "Readings",
            "capture_frequency_hz": 1.0,
            "disabled": false
          }
        ]
      }
    }
  ]
}
```

### Data Manager Service

```json
{
  "name": "data_manager-1",
  "type": "data_manager",
  "attributes": {
    "sync_interval_mins": 0.1,
    "capture_dir": "",
    "tags": [],
    "sync_disabled": false,
    "capture_disabled": false
  }
}
```

---

## Training Script Templates

### Minimal Keras Classification Script

```python
import argparse
import json
import os
import sys

os.environ["TF_USE_LEGACY_KERAS"] = "1"
import tensorflow as tf
import tf_keras as keras

def parse_args(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_file", dest="data_json", type=str)
    parser.add_argument("--model_output_directory", dest="model_dir", type=str)
    parser.add_argument("--num_epochs", dest="num_epochs", type=int, default=50)
    parser.add_argument("--labels", dest="labels", type=str, required=False)
    return parser.parse_args(args)

def load_dataset(data_json, labels):
    filenames, image_labels = [], []
    with open(data_json, "rb") as f:
        for line in f:
            row = json.loads(line)
            filenames.append(row["image_path"])
            for ann in row["classification_annotations"]:
                if ann["annotation_label"] in labels:
                    image_labels.append(ann["annotation_label"])
                    break
            else:
                image_labels.append("UNKNOWN")
    return filenames, image_labels

if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    LABELS = args.labels.strip("'").split() if args.labels else ["class_a", "class_b"]
    ALL_LABELS = LABELS + ["UNKNOWN"]

    filenames, labels_list = load_dataset(args.data_json, LABELS)

    # Build model
    base = keras.applications.EfficientNetB0(
        input_shape=(256, 256, 3), include_top=False, weights="imagenet")
    base.trainable = False
    model = keras.Sequential([
        keras.layers.Resizing(256, 256),
        base,
        keras.layers.GlobalAveragePooling2D(),
        keras.layers.Dense(len(ALL_LABELS), activation="softmax"),
    ])
    model.compile(loss="categorical_crossentropy", optimizer="adam")

    # TODO: create tf.data.Dataset, train, convert to TFLite
    # model.fit(train_dataset, epochs=args.num_epochs)

    # Save labels
    with open(os.path.join(args.model_dir, "labels.txt"), "w") as f:
        f.write("\n".join(ALL_LABELS))
```

### Minimal Ultralytics YOLO Script

```python
import argparse
import json
import os
import shutil
import sys

from ultralytics import YOLO
import yaml

def parse_args(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_file", dest="data_json", type=str)
    parser.add_argument("--model_output_directory", dest="model_dir", type=str)
    parser.add_argument("--num_epochs", dest="num_epochs", type=int, default=100)
    parser.add_argument("--labels", dest="labels", type=str, required=False)
    return parser.parse_args(args)

if __name__ == "__main__":
    args = parse_args(sys.argv[1:])

    # 1. Parse JSONLines -> YOLO format
    # 2. Create images/train, images/val, labels/train, labels/val dirs
    # 3. Write dataset.yaml
    # 4. Train
    model = YOLO("yolov8n.pt")
    results = model.train(data="dataset.yaml", epochs=args.num_epochs, imgsz=640)

    # 5. Export to ONNX
    export_path = model.export(format="onnx")
    os.makedirs(args.model_dir, exist_ok=True)
    shutil.copy2(export_path, os.path.join(args.model_dir, "model.onnx"))

    # 6. Save labels
    with open(os.path.join(args.model_dir, "labels.txt"), "w") as f:
        for label in LABELS:
            f.write(f"{label}\n")
```

---

## CLI Commands for ML Operations

```bash
# --- Data ---
viam data export --destination=./data --dataset-id=<ID>
viam data delete --org-id=<ORG> --dataset-id=<ID>
viam data database configure --org-id=<ORG>

# --- Datasets ---
viam dataset list --org-id=<ORG>
viam dataset create --org-id=<ORG> --name="my_dataset"
viam dataset export --destination=./data --dataset-id=<ID>

# --- Training ---
# Submit from registry
viam train submit custom from-registry \
  --dataset-id=<ID> --org-id=<ORG> \
  --model-name=my_model --model-type=object_detection \
  --script-name=yolo-onnx-training \
  --args=num_epochs=100,labels="'cat dog'"

# Submit with local upload
viam train submit custom with-upload \
  --dataset-id=<ID> --model-org-id=<ORG> \
  --model-name=my_model --model-type=single_label_classification \
  --framework=tflite --path=./model.tar.gz \
  --script-name=my_script

# Check training job status
viam train list --org-id=<ORG>
viam train get --job-id=<JOB_ID>

# --- Models ---
# Upload a model to registry
viam ml-model upload --org-id=<ORG> --name=my_model \
  --framework=tflite --path=./model_dir
```

For full CLI reference, see the `viam-modules-fleet` skill.

---

## Common Error Patterns and Fixes

### Data Capture

| Error / Symptom | Cause | Fix |
|----------------|-------|-----|
| No data appearing in cloud | `sync_disabled: true` | Set `sync_disabled: false` |
| No data appearing in cloud | `capture_disabled: true` on component | Set `disabled: false` |
| Data syncing but empty | `capture_frequency_hz: 0` | Set to a positive value (e.g., `0.5`) |
| Disk filling up | Sync not keeping up, or large capture rate | Increase `sync_interval_mins`, decrease capture frequency, or adjust deletion thresholds |
| `changing the capture directory is prohibited` | Running with `-untrusted-env` flag | Use default `~/.viam/capture` directory |

### Training Scripts

| Error / Symptom | Cause | Fix |
|----------------|-------|-----|
| `No module named 'model'` | Wrong entry point or package structure | Ensure `model/__init__.py` exists, run as `python -m model.training` |
| Labels file empty | Labels arg not quoted correctly | Use `labels="'label_a label_b'"` (single inside double quotes) |
| `Invalid model_type` | Wrong model_type string | Use `single_label` or `multi_label` (no `MODEL_TYPE_` prefix) |
| YOLO: `No images found` | Dataset directory structure wrong | Verify `images/train/` and `labels/train/` match |
| TFLite conversion fails | Unsupported ops | Both `TFLITE_BUILTINS` and `SELECT_TF_OPS` must be in `supported_ops` |
| Out of memory during training | Batch size too large | Reduce `BATCH_SIZE` (try 8 or 4) |

### Model Deployment

| Error / Symptom | Cause | Fix |
|----------------|-------|-----|
| `model_path` not found | Package not deployed | Add package to `packages` array, or use absolute local path |
| `Required parameter model_path not found` | Missing `model_path` in TFLite config | Add `model_path` attribute |
| `tensor name X is not a known input tensor` | Input tensor name mismatch | Check model's `Metadata()` for actual tensor names; use `tensor_name_remappings` for Triton |
| `expected byte size N but M provided` | Tensor shape/dtype mismatch | Verify input image dimensions match model's expected input shape |
| Wrong detection labels | No `label_path` configured | Add `label_path` pointing to `labels.txt` |
| Classification returns numbers instead of labels | No label file | Add `label_path` or ensure labels.txt is in model package |

### Vision + ML Integration

| Error / Symptom | Cause | Fix |
|----------------|-------|-----|
| `no tensor named 'probability'` | Classification model output tensor named differently | Rename output tensor or use `tensor_name_remappings` |
| `could not find output tensor named 'location'` | Detection model output names don't match expected | Use `tensor_name_remappings` to map to `location`, `category`, `score` |
| `length of output (N) expected to be length of label list (M)` | Labels file has wrong number of entries | Regenerate labels.txt matching model's output classes |
| Empty detections | Confidence threshold too high, or model outputs invalid boxes | Check raw `Infer()` output; verify model was trained on similar data |

---

## Tensor Name Expectations

### For Detection Models

The vision service expects these output tensor names:

| Expected Name | Content | Shape |
|--------------|---------|-------|
| `location` | Bounding box coordinates | `[1, N, 4]` |
| `category` | Class label indices | `[1, N]` |
| `score` | Confidence scores | `[1, N]` |
| `n_detections` | Number of valid detections (optional) | `[1]` |

If your model uses different names, configure `tensor_name_remappings` on the ML model service.

### For Classification Models

| Expected Name | Content | Shape |
|--------------|---------|-------|
| `probability` | Per-class probabilities or logits | `[1, num_classes]` |

If the model has exactly one output tensor, it is automatically used regardless of name.

---

## Package Path Syntax

Model files deployed from the registry use the `${packages.<name>}` syntax:

```
${packages.my_model}/classification_model.tflite
${packages.my_model}/labels.txt
${packages.ml_model.MyRegistryModel}
```

The `packages` array in the robot config defines the mapping:

```json
{
  "package": "<org-id>/model-name",
  "version": "YYYY-MM-DDThh-mm-ss",
  "name": "my_model",
  "type": "ml_model"
}
```

---

## Quick Architecture Decisions

| If you need... | Use... |
|---------------|--------|
| Simple image classification | Keras classification script -> TFLite -> `tflite_cpu` |
| Object detection (edge device, no GPU) | Keras detection script -> TFLite -> `tflite_cpu` |
| Object detection (NVIDIA GPU) | YOLO script -> ONNX -> Triton |
| Tabular prediction | TF tabular script -> SavedModel -> Triton |
| Multi-model inference | Triton (supports multiple models simultaneously) |
| Lowest latency on CPU | TFLite with `num_threads` matching CPU cores |
| Maximum accuracy detection | YOLO (larger model variants: yolov8s, yolov8m, yolov8l) |
