# Viam Training Scripts Reference

Built from the official Viam training script repositories circa April 2026.

---

## Training Script Structure

All Viam custom training scripts share a common structure and contract with the
Viam training infrastructure.

### Required Entry Points and Arguments

Every training script **must** accept these CLI arguments:

| Argument | Description |
|----------|-------------|
| `--dataset_file` | Path to JSONLines file containing the dataset |
| `--model_output_directory` | Directory where model artifacts must be written |
| `--num_epochs` | (Optional) Override for number of training epochs |

Additional optional arguments vary by script (e.g., `--labels`, `--model_type`, `--base_model`).

### Package Structure

```
my-training-script/
  model/
    __init__.py
    training.py          # Main training logic; entry point via __main__
  setup.py               # or pyproject.toml
  tests/
    test_parse_args.py
    test_file_exists.py
```

The `model/training.py` file is the primary entry point. It is invoked as:
```bash
python3 -m model.training \
  --dataset_file=/path/to/dataset.jsonl \
  --model_output_directory=/path/to/output \
  --num_epochs=200
```

### Environment Variables

When running in Viam's cloud training infrastructure, these are available:

| Variable | Description |
|----------|-------------|
| `API_KEY` | Viam API key for the organization |
| `API_KEY_ID` | Viam API key ID |

These enable programmatic access to the Viam Data Client (used in the tabular training
script to fetch additional data).

### Output Requirements

Training scripts **must** write model artifacts to `--model_output_directory`:
- The model file (`.tflite`, `.onnx`, SavedModel, etc.)
- A `labels.txt` file with one label per line
- Any additional metadata files

---

## Keras Classification Training

**Source:** `classification-tflite` repository
**Dependencies:** `tensorflow==2.16.2`, `tf-keras==2.16.*`, `keras-cv`
**Output:** `.tflite` model + `labels.txt`
**Model type:** `single_label_classification` or `multi_label_classification`

### Full Script Flow

```
1. Parse args (dataset_file, model_output_directory, num_epochs, labels, model_type)
2. Set up compute strategy (GPU if available, else CPU)
3. Parse JSONLines dataset file -> image filenames + classification annotations
4. Create tf.data.Dataset with 80/20 train/test split
5. Build EfficientNetB0 model with transfer learning (ImageNet weights, frozen base)
6. Train with Adam optimizer (lr=1e-3)
7. Save labels.txt
8. Convert to TFLite and save
```

### Argument Parsing

```python
def parse_args(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_file", dest="data_json", type=str)
    parser.add_argument("--model_output_directory", dest="model_dir", type=str)
    parser.add_argument("--num_epochs", dest="num_epochs", type=int)
    parser.add_argument("--labels", dest="labels", type=str, required=False,
        help="Space-separated list of labels, MUST be enclosed in single quotes")
    parser.add_argument("--model_type", dest="model_type", type=str)
    parsed_args = parser.parse_args(args)
    return (parsed_args.data_json, parsed_args.model_dir, parsed_args.num_epochs,
            parsed_args.labels, parsed_args.model_type)
```

### Dataset Loading (Classification)

The dataset file is JSONLines with `image_path` and `classification_annotations`:

```python
def parse_filenames_and_labels_from_json(filename, all_labels, model_type):
    image_filenames = []
    image_labels = []
    with open(filename, "rb") as f:
        for line in f:
            json_line = json.loads(line)
            image_filenames.append(json_line["image_path"])
            annotations = json_line["classification_annotations"]
            labels = ["UNKNOWN"]
            for annotation in annotations:
                if model_type == multi_label:
                    if annotation["annotation_label"] in all_labels:
                        labels.append(annotation["annotation_label"])
                if model_type == single_label:
                    if annotation["annotation_label"] in all_labels:
                        labels = [annotation["annotation_label"]]
            image_labels.append(labels)
    return image_filenames, image_labels
```

**Key points:**
- Single-label: last matching label wins (arbitrary selection if multiple valid labels)
- Multi-label: all matching labels are included
- `UNKNOWN` label is always appended to the label list as a fallback

### Model Architecture

```python
def build_and_compile_classification(labels, model_type, input_shape):
    # Transfer learning with EfficientNetB0
    base_model = keras.applications.EfficientNetB0(
        input_shape=input_shape, include_top=False, weights="imagenet"
    )
    base_model.trainable = False  # Freeze base model

    model = keras.Sequential([
        preprocessing_layers,        # Resizing to 256x256
        data_augmentation,           # RandomFlip, RandomRotation(0.1), RandomZoom(0.1)
        base_model,
        keras.layers.GlobalAveragePooling2D(),
        keras.layers.Dense(num_classes, activation=activation, name="output"),
    ])

    # Single-label: softmax + categorical_crossentropy
    # Multi-label:  sigmoid + binary_crossentropy
    model.compile(loss=loss, optimizer=Adam(lr=1e-3), metrics=[metrics])
    return model
```

**Constants:**
- `IMG_SIZE = (256, 256)`
- `BATCH_SIZE = 16`
- `SHUFFLE_BUFFER_SIZE = 32`
- `EPOCHS = 200` (default, overridable)
- Input dtype: `uint8`

### Single-Label vs Multi-Label

| Aspect | Single-Label | Multi-Label |
|--------|-------------|-------------|
| Final activation | `softmax` | `sigmoid` |
| Loss | `categorical_crossentropy` | `binary_crossentropy` |
| Label encoding | `one_hot` | `multi_hot` |
| Metrics | CategoricalAccuracy, Precision, Recall | BinaryAccuracy, Precision, Recall |

### TFLite Conversion

```python
def save_tflite_classification(model, model_dir, model_name, target_shape):
    # Wrap with batch_size=1 for static graph
    input = keras.Input(target_shape, batch_size=1, dtype=tf.uint8)
    output = model(input, training=False)
    wrapped_model = keras.Model(inputs=input, outputs=output)

    converter = tf.lite.TFLiteConverter.from_keras_model(wrapped_model)
    converter.target_spec.supported_ops = [
        tf.lite.OpsSet.TFLITE_BUILTINS,
        tf.lite.OpsSet.SELECT_TF_OPS,
    ]
    tflite_model = converter.convert()

    with open(os.path.join(model_dir, f"{model_name}.tflite"), "wb") as f:
        f.write(tflite_model)
```

**Important:** Both `TFLITE_BUILTINS` and `SELECT_TF_OPS` are enabled, meaning the model
uses the TFLite runtime with TensorFlow fallback ops. The `tflite_cpu` module supports this.

### Label File Output

```python
def save_labels(labels, model_dir):
    with open(os.path.join(model_dir, "labels.txt"), "w") as f:
        for label in labels[:-1]:
            f.write(label + "\n")
        f.write(labels[-1])  # No trailing newline on last label
```

Labels include the `UNKNOWN` label at the end: `LABELS + ["UNKNOWN"]`.

---

## Keras Detection Training

**Source:** `detection-tflite` repository
**Dependencies:** `tensorflow==2.16.2`, `tf-keras==2.16.*`, `keras-cv`, `tflite-support`
**Output:** `.tflite` model + `labels.txt`

### Full Script Flow

```
1. Parse args (dataset_file, model_output_directory, num_epochs, labels)
2. Set up compute strategy (GPU/CPU)
3. Parse JSONLines dataset -> filenames + bounding boxes + labels
4. Create tf.data.Dataset with 80/10/10 train/val/test split
5. Apply augmentations (RandomFlip, JitteredResize) preserving bbox relationships
6. Build RetinaNet with EfficientNetV2B0 backbone (frozen, transfer learning)
7. Train with SGD (lr=0.01, momentum=0.9, clipnorm=10.0)
8. Save labels.txt
9. Convert to TFLite with quantization and save
```

### Dataset Loading (Detection)

```python
def parse_filenames_and_bboxes_from_json(filename, all_labels):
    for line in f:
        json_line = json.loads(line)
        image_filenames.append(json_line["image_path"])
        annotations = json_line["bounding_box_annotations"]
        for annotation in annotations:
            if annotation["annotation_label"] in all_labels:
                labels.append(annotation["annotation_label"])
                coords.append([
                    annotation["y_min_normalized"],
                    annotation["x_min_normalized"],
                    annotation["y_max_normalized"],
                    annotation["x_max_normalized"],
                ])  # rel_yxyx format
```

**Bounding box format:** `rel_yxyx` (y_min, x_min, y_max, x_max, all normalized 0-1)

### Model Architecture

```python
model = keras_cv.models.RetinaNet(
    num_classes=num_classes,
    bounding_box_format="rel_yxyx",
    backbone=keras_cv.models.EfficientNetV2Backbone.from_preset(
        "efficientnetv2_b0_imagenet",
        load_weights=True,
        include_rescaling=True,   # Rescales [0,255] -> [0,1]
        input_shape=TARGET_SHAPE,  # (384, 384, 3)
    ),
    prediction_decoder=CombinedNMS(
        from_logits=True,
        num_classes=num_classes,
        src_bounding_box_format="rel_yxyx",
    ),
)
model.backbone.trainable = False

model.compile(
    classification_loss="focal",
    box_loss="smoothl1",
    optimizer=SGD(lr=0.01, momentum=0.9, global_clipnorm=10.0),
)
```

**Constants:**
- `TARGET_SHAPE = (384, 384, 3)` (must be multiple of 128 for EfficientNet)
- `BATCH_SIZE = 16`
- `SHUFFLE_BUFFER_SIZE = 64`
- `EPOCHS = 200` (default)
- `SRC_BBOX = TGT_BBOX = "rel_yxyx"`

### CombinedNMS (Custom Prediction Decoder)

The detection training uses a custom `CombinedNMS` layer for post-processing:

```python
class CombinedNMS(keras.layers.Layer):
    def __init__(self, from_logits, num_classes, src_bounding_box_format,
                 iou_threshold=0.35, confidence_threshold=0,
                 max_detections_per_class=32, max_total_detections=32):
        self.bounding_box_format = "rel_yxyx"  # RDK-expected format
```

**Output keys:** `boxes`, `classes`, `confidence`, `num_detections`
- Boxes are converted to `rel_yxyx` format (the format RDK expects)
- Classes are float-cast label indices
- Confidence values are sigmoid-activated logits

### Data Augmentation (Detection)

Augmentations must preserve bounding box relationships:

```python
random_flip = keras_cv.layers.RandomFlip(mode="horizontal", bounding_box_format=tgt_bbox_format)
jittered_resize = keras_cv.layers.JitteredResize(
    target_size=(384, 384),
    crop_size=None,
    scale_factor=(0.85, 1.3),
    bounding_box_format=tgt_bbox_format,
)
```

### TFLite Conversion (Detection)

```python
def save_tflite_detection(model, model_dir, model_name, target_shape):
    input = keras.Input(target_shape, batch_size=1, dtype=tf.uint8)
    preprocessing = preprocessing_layers_detection(target_shape=target_shape)
    predictions = model(preprocessing(input), training=False)
    output = model.decode_predictions(predictions, tf.ones((1,) + target_shape))
    wrapped_model = keras.Model(inputs=input, outputs=output)

    converter = tf.lite.TFLiteConverter.from_keras_model(wrapped_model)
    converter.target_spec.supported_ops = TFLITE_OPS
    converter.optimizations = [tf.lite.Optimize.DEFAULT]  # Quantization
    tflite_model = converter.convert()
```

**Key difference from classification:** Detection models enable `DEFAULT` quantization
optimization, which reduces model size and improves inference speed on edge devices.

---

## Ultralytics YOLO Training

**Source:** `yolo-training` repository
**Dependencies:** `ultralytics>=8.3.104`, `onnx`, `onnxruntime`, `onnxslim`, `scikit-learn`, `pyyaml`
**Output:** `.onnx` model + `labels.txt`
**Package manager:** `uv` (not pip/setuptools)

### Full Script Flow

```
1. Parse args (dataset_file, model_output_directory, num_epochs, labels, base_model)
2. Detect device (MPS on Apple Silicon, CUDA if available, else CPU)
3. Parse JSONLines dataset -> filenames + bboxes (converted to YOLO xywh format)
4. Auto-discover labels if none provided
5. Create 80/20 train/val split
6. Set up YOLO directory structure (images/train, images/val, labels/train, labels/val)
7. Generate dataset.yaml config
8. Copy images and create per-image label .txt files
9. Train YOLOv8 model
10. Export to ONNX
11. Copy ONNX model + create labels.txt in output directory
```

### Argument Parsing

```python
parser.add_argument("--dataset_file", dest="data_json", type=str)
parser.add_argument("--model_output_directory", dest="model_dir", type=str)
parser.add_argument("--num_epochs", dest="num_epochs", type=int, default=200)
parser.add_argument("--labels", dest="labels", type=str, required=False)
parser.add_argument("--base_model", dest="base_model", type=str, default="yolov8n.pt")
```

**Extra argument:** `--base_model` allows selecting different YOLO pretrained weights
(default: `yolov8n.pt` = YOLOv8 nano).

### Bounding Box Format Conversion

The YOLO script converts from Viam's normalized `[y_min, x_min, y_max, x_max]` to YOLO
`[x_center, y_center, width, height]` format:

```python
x_min = annotation["x_min_normalized"]
y_min = annotation["y_min_normalized"]
x_max = annotation["x_max_normalized"]
y_max = annotation["y_max_normalized"]

width = x_max - x_min
height = y_max - y_min
x_center = x_min + width / 2
y_center = y_min + height / 2

coords.append([x_center, y_center, width, height])
```

### YOLO Dataset Structure

The script creates a standard YOLO dataset directory layout:

```
(cwd)/
  dataset.yaml
  images/
    train/
      image1.jpg
      image2.jpg
    val/
      image3.jpg
  labels/
    train/
      image1.txt    # class_idx x_center y_center width height
      image2.txt
    val/
      image3.txt
```

### YOLO YAML Config

```python
config = {
    "path": os.getcwd(),
    "train": "images/train",
    "val": "images/val",
    "names": {0: "cat", 1: "dog", ...},
}
```

### Training and Export

```python
model = YOLO("yolov8n.pt")  # Load pretrained model
results = model.train(
    task="detect",
    data="dataset.yaml",
    epochs=num_epochs,
    imgsz=640,
    device=device,        # "cpu", "mps", or CUDA device index
    patience=patience,    # Early stopping patience (half of num_epochs)
)
export_path = model.export(format="onnx", device=device)
```

**Device selection:**
- Apple Silicon (macOS arm64): MPS with patience=30
- CUDA available: GPU device
- Fallback: CPU

### Label Auto-Discovery

If `--labels` is not provided, the YOLO script discovers labels from the dataset:

```python
if LABELS is None:
    unique_labels = set()
    for label_list in bbox_labels:
        unique_labels.update(label_list)
    LABELS = sorted(list(unique_labels))
```

### Key Differences from Keras

| Aspect | Keras (classification/detection) | Ultralytics (YOLO) |
|--------|--------------------------------|-------------------|
| Output format | `.tflite` | `.onnx` |
| Input size | 256x256 (cls) / 384x384 (det) | 640x640 |
| Package manager | pip/setuptools | uv |
| Base model | EfficientNetB0 / EfficientNetV2B0 | YOLOv8n |
| Framework | TensorFlow/Keras | PyTorch/Ultralytics |
| Label discovery | Must be provided | Auto-discovered from data |
| Bbox format | `rel_yxyx` | YOLO `xywh` (center) |
| Early stopping | Not built-in | `patience` parameter |
| Data augmentation | Manual (keras_cv layers) | Built into Ultralytics |

---

## TensorFlow Tabular Training

**Source:** `tabular-data-tensorflow` repository
**Dependencies:** `keras==2.14.0`, `viam-sdk==0.25.2`, `protobuf==4.25.3`
**Output:** SavedModel format

### Full Script Flow

```
1. Parse args (dataset_file [ignored], model_output_directory, num_epochs)
2. Set up compute strategy (GPU/CPU)
3. Connect to Viam cloud using API_KEY/API_KEY_ID environment variables
4. Query tabular data from Viam Data Client by component names
5. Synchronize data by truncated timestamps
6. Create 80/20 train/test split
7. Build regression model (Dense layers + normalization)
8. Train with Adam optimizer (lr=0.001)
9. Save as TensorFlow SavedModel
```

### Data Loading (Tabular -- via Viam API)

Unlike image training scripts, the tabular script fetches data from Viam's cloud API:

```python
async def connect() -> ViamClient:
    dial_options = DialOptions.with_api_key(
        os.environ.get("API_KEY"), os.environ.get("API_KEY_ID")
    )
    return await ViamClient.create_from_dial_options(dial_options, "app.viam.com")

async def get_data_from_filter(data_client, my_filter, reading_name):
    data = {}
    last = None
    while True:
        tabular_data, _, last = await data_client.tabular_data_by_filter(
            my_filter, last=last
        )
        if not tabular_data:
            break
        for datum in tabular_data:
            # Truncate time for synchronization
            truncated_time = datetime.datetime(
                time_received.year, time_received.month, time_received.day,
                time_received.hour, time_received.minute, time_received.second,
            )
            data[truncated_time] = datum.data["readings"][reading_name]
    return data
```

**Key concept:** Multiple sensor readings are synchronized by truncating timestamps to
the second. This means capture frequency should be about 1 Hz for reliable joins.

### Model Architecture (Tabular)

```python
def build_and_compile_model(batch_size, input_names):
    inputs = [
        keras.layers.Input(shape=(1,), batch_size=batch_size, name=name)
        for name in input_names
    ]
    merged = keras.layers.Concatenate(axis=1)(inputs)
    layers = keras.models.Sequential([
        keras.layers.Normalization(axis=-1),
        keras.layers.Dense(64, activation="relu"),
        keras.layers.Dense(64, activation="relu"),
    ])(merged)
    output = keras.layers.Dense(1)(layers)

    model = keras.models.Model(inputs=inputs, outputs=output)
    model.compile(loss="mean_absolute_error", optimizer=Adam(0.001))
    return model
```

### SavedModel Export

```python
def save_model(model, model_dir):
    tf.saved_model.save(model, model_dir)
```

This produces a directory structure:
```
model_output_directory/
  saved_model.pb
  variables/
    variables.data-00000-of-00001
    variables.index
```

### Key Differences from Image Scripts

| Aspect | Image (Keras) | Tabular (TF) |
|--------|---------------|---------------|
| Data source | JSONLines file | Viam Data Client API |
| `dataset_file` usage | Primary input | Ignored |
| Output format | `.tflite` | SavedModel |
| Model type | Classification/Detection | Regression |
| Requires API keys | No | Yes (env vars) |
| Input shape | `[1, H, W, 3]` | `[batch, 1]` per feature |

---

## Registration and CLI Submission

### Submitting a Custom Training Script

**From the registry (recommended for published scripts):**

```bash
viam train submit custom from-registry \
  --dataset-id=<DATASET-ID> \
  --org-id=<ORG-ID> \
  --model-name=my-model \
  --model-type=object_detection \
  --script-name=yolo-onnx-training \
  --args=num_epochs=100,labels="'green_square blue_star'"
```

**With local upload:**

```bash
viam train submit custom with-upload \
  --dataset-id=<DATASET-ID> \
  --model-org-id=<ORG-ID> \
  --model-name=classification \
  --model-type=single_label_classification \
  --framework=tflite \
  --path=<PATH-TO-TAR> \
  --script-name=classification_script \
  --args=num_epochs=3,labels="'green_square blue_star'"
```

**Label quoting:** Labels must be enclosed in single quotes inside double quotes:
`labels="'green_square blue_star'"`.

### Model Types

| Model Type | Description |
|-----------|-------------|
| `single_label_classification` | One label per image |
| `multi_label_classification` | Multiple labels per image |
| `object_detection` | Bounding box detection |

### Publishing a Training Script

For the YOLO script (using uv):
```bash
# Update version in pyproject.toml, then:
version=<version> make publish
```

For Keras scripts (using GitHub Actions):
- Merging to `main` auto-publishes to the Viam registry
- Framework is fixed per repository (e.g., `tflite` for classification-tflite)

---

## Model Export Formats Summary

| Training Script | Framework | Export Format | Deployment Runtime |
|----------------|-----------|---------------|-------------------|
| classification-tflite | Keras + TF | `.tflite` | `viam:mlmodel-tflite:tflite_cpu` |
| detection-tflite | Keras + keras_cv | `.tflite` (quantized) | `viam:mlmodel-tflite:tflite_cpu` |
| yolo-training | Ultralytics + PyTorch | `.onnx` | Triton or custom ONNX module |
| tabular-data-tensorflow | TensorFlow | SavedModel | Triton |
