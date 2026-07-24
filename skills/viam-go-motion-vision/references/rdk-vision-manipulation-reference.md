# Viam RDK Internals: Vision-Guided Manipulation Reference

A deep reference on how the Viam RDK's arm, camera, motion planning, frame system, point cloud, and spatial math subsystems interoperate to enable vision-guided robotic manipulation.

Based on source analysis of [viamrobotics/rdk](https://github.com/viamrobotics/rdk) (April 2026).

---

## 1. Architectural Overview

Vision-guided manipulation in Viam flows through a layered architecture:

```
┌──────────────────────────────────────────────────────────────────┐
│  Client Code (Go SDK / Python SDK / MCP / Behavior Tree)        │
├──────────────────────────────────────────────────────────────────┤
│  Motion Service (services/motion)                               │
│    → Builds kinematic chain, calls planner, executes trajectory  │
├───────────────┬──────────────────────────────────────────────────┤
│  Frame System │  Motion Planner (motionplan/armplanning)         │
│  Service      │    → cBiRRT + IK solver, constraint checking    │
│  (robot/      │    → collision detection against WorldState      │
│  framesystem) │    → path smoothing, multi-waypoint sequencing   │
├───────────────┴──────────────────────────────────────────────────┤
│  Component Layer                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐                   │
│  │   Arm    │  │  Camera  │  │ Vision Svc   │                   │
│  │ (IK,FK,  │  │ (images, │  │ (detections, │                   │
│  │  joints) │  │  PCD)    │  │  segments)   │                   │
│  └──────────┘  └──────────┘  └──────────────┘                   │
├──────────────────────────────────────────────────────────────────┤
│  Foundation Libraries                                            │
│  ┌──────────────┐ ┌────────────┐ ┌──────────────┐               │
│  │ spatialmath  │ │ pointcloud │ │referenceframe│               │
│  │ (Pose, Geom, │ │ (Octree,   │ │(Frame, Model,│               │
│  │  Orientation)│ │  KDTree)   │ │ WorldState)  │               │
│  └──────────────┘ └────────────┘ └──────────────┘               │
└──────────────────────────────────────────────────────────────────┘
```

The key insight: the motion service is the orchestration layer. It does not move arms directly. It constructs a `PlanRequest` containing the frame system topology, start state, goal poses, world state (obstacles + transforms), and constraints, then delegates to the `armplanning.PlanMotion` function. The resulting `Trajectory` is executed by calling `GoToInputs` on each `InputEnabled` component.

---

## 2. Arm Component (`components/arm`)

### 2.1 Interface

```go
// components/arm/arm.go
type Arm interface {
    resource.Resource
    resource.Shaped
    resource.Actuator
    framesystem.InputEnabled

    EndPosition(ctx context.Context, extra map[string]interface{}) (spatialmath.Pose, error)
    MoveToPosition(ctx context.Context, pose spatialmath.Pose, extra map[string]interface{}) error
    MoveToJointPositions(ctx context.Context, positions []referenceframe.Input, extra map[string]interface{}) error
    MoveThroughJointPositions(ctx context.Context, positions [][]referenceframe.Input, options *MoveOptions, extra map[string]any) error
    JointPositions(ctx context.Context, extra map[string]interface{}) ([]referenceframe.Input, error)
    Get3DModels(ctx context.Context, extra map[string]interface{}) (map[string]*commonpb.Mesh, error)
}
```

Key composition interfaces:

- **`resource.Shaped`** — returns collision geometries for the arm at any configuration, used by the motion planner for self-collision and obstacle avoidance.
- **`framesystem.InputEnabled`** — the critical integration point with motion planning. Provides:
  - `Kinematics(ctx) (referenceframe.Model, error)` — returns the kinematic model (a `Frame` implementing `Transform`, `DoF`, `Geometries`)
  - `CurrentInputs(ctx) ([]referenceframe.Input, error)` — current joint positions in radians/mm
  - `GoToInputs(ctx, ...[]referenceframe.Input) error` — moves the arm to one or more sets of joint positions (supports trajectory blending when multiple inputs are provided)
- **`resource.Actuator`** — provides `IsMoving()` and `Stop()`.

### 2.2 Input Units

All `referenceframe.Input` values are in **radians** (revolute joints) or **millimeters** (prismatic joints). Protobuf conversions to/from degrees are handled by `Frame.InputFromProtobuf` and `Frame.ProtobufFromInput`.

Joint positions are validated against the kinematic model's `DoF()` limits. The `CheckDesiredJointPositions` function enforces that desired positions either bring joints back in-bounds or don't move them further out-of-bounds.

### 2.3 Kinematic Models

Arms report their kinematics via the `Kinematics()` method, which returns a `referenceframe.Model`. Two formats are supported:

- **SVA (JSON)** — Viam's native format, parsed via `UnmarshalModelJSON`. Defines joints, links, and geometries as a tree.
- **URDF (XML)** — Standard robotics format, parsed via `UnmarshalModelXML`. Supports mesh geometries embedded in the proto response.

The `SimpleModel` struct wraps an internal `FrameSystem` representing the arm's kinematic tree. It supports serial chains and branching topologies (e.g., multi-finger grippers). A `primaryOutputFrame` determines which frame tip `Transform()` returns the pose of.

### 2.4 MoveToPosition vs. Motion Service Move

`MoveToPosition` on the arm component calls `armplanning.MoveArm`, which:
1. Gets current joint inputs via `CurrentInputs`
2. Gets the kinematic model via `Kinematics`
3. Creates a temporary single-frame `FrameSystem`
4. Calls `PlanFrameMotion` → `PlanMotion` to solve
5. Executes via `MoveThroughJointPositions`

This is a simpler path than the motion service's `Move`, which operates on the full robot frame system and supports world state obstacles, multi-component coordination, and supplemental transforms.

---

## 3. Camera Component (`components/camera`)

### 3.1 Interface

```go
// components/camera/camera.go
type Camera interface {
    resource.Resource
    resource.Shaped

    Images(ctx context.Context, filterSourceNames []string,
           extra map[string]interface{}) ([]NamedImage, resource.ResponseMetadata, error)
    NextPointCloud(ctx context.Context,
                   extra map[string]interface{}) (pointcloud.PointCloud, error)
    Properties(ctx context.Context) (Properties, error)
}
```

### 3.2 Properties and Calibration

`Properties` carries the camera's intrinsic/extrinsic calibration and capabilities:

```go
type Properties struct {
    SupportsPCD      bool
    ImageType        ImageType
    IntrinsicParams  *transform.PinholeCameraIntrinsics
    DistortionParams transform.Distorter
    ExtrinsicParams  *ExtrinsicParams
    MimeTypes        []string
    FrameRate        float32
}
```

**`ExtrinsicParams`** (`Translation` + `Orientation`) define the camera's pose relative to a reference frame. The `PointToPixel` method uses these to project 3D world points into 2D pixel coordinates — it applies the inverse extrinsic transform to move a point from the reference frame into camera-local coordinates, then projects via intrinsics.

### 3.3 Transform Pipeline (`components/camera/transformpipeline`)

The transform pipeline enables declarative image processing chains configured in JSON:

```json
{
  "type": "transform",
  "attributes": {
    "source": "my_camera",
    "pipeline": [
      { "type": "resize", "attributes": { "width": 640, "height": 480 } },
      { "type": "detections", "attributes": { "detector_name": "my_yolo" } }
    ]
  }
}
```

Available transforms: `rotate`, `resize`, `crop`, `detections`, `classifications`.

The `detections` transform is the bridge between camera and vision service — it fetches an image from the source camera, runs it through a vision service detector, and overlays bounding boxes. The `detectorSource.Read()` method:
1. Gets image from source camera
2. Calls `vision.Service.Detections(ctx, img, extra)`
3. Applies confidence and label filters
4. Overlays bounding boxes on the image

### 3.4 Point Clouds

Cameras with depth sensing support `NextPointCloud()`, returning a `pointcloud.PointCloud`. This is the primary pathway for getting 3D scene data into the motion planning pipeline — point clouds can be converted to octrees for use as obstacles in `WorldState`.

---

## 4. Vision Service (`services/vision`)

### 4.1 Interface

```go
// services/vision/vision.go
type Service interface {
    resource.Resource
    DetectionsFromCamera(ctx, cameraName string, extra) ([]objectdetection.Detection, error)
    Detections(ctx, img image.Image, extra) ([]objectdetection.Detection, error)
    ClassificationsFromCamera(ctx, cameraName string, n int, extra) (classification.Classifications, error)
    Classifications(ctx, img image.Image, n int, extra) (classification.Classifications, error)
    GetObjectPointClouds(ctx, cameraName string, extra) ([]*vision.Object, error)
    GetProperties(ctx, extra) (*Properties, error)
    CaptureAllFromCamera(ctx, cameraName string, opts, extra) (viscapture.VisCapture, error)
}
```

### 4.2 Role in Vision-Guided Manipulation

The vision service provides two key outputs for manipulation:

1. **2D Detections** — bounding boxes with labels and confidence scores. These must be projected into 3D via camera intrinsics/extrinsics and the frame system to become spatial targets.

2. **3D Object Point Clouds** via `GetObjectPointClouds` — returns segmented `vision.Object` instances with associated point clouds. These can be directly used to construct obstacle geometries or grasp targets in the `WorldState`.

### 4.3 Obstacle Detectors in Motion Configuration

The motion service's `MotionConfiguration` supports dynamic obstacle detection through `ObstacleDetectorName` pairs:

```go
type ObstacleDetectorName struct {
    VisionServiceName string
    CameraName        string
}
```

This is used by `MoveOnMap` and `MoveOnGlobe` for continuous obstacle polling during navigation. The motion service periodically queries the vision service for new obstacles and re-plans if needed.

---

## 5. Frame System (`referenceframe/` + `robot/framesystem/`)

### 5.1 Core Concepts

The frame system is a tree of `Frame` nodes rooted at `"world"`. Each frame defines a transform from itself to its parent, parameterized by zero or more `Input` values (joint positions).

```go
// referenceframe/frame.go
type Frame interface {
    Name() string
    Transform([]Input) (spatial.Pose, error)     // pose FROM this frame TO parent
    Geometries([]Input) (*GeometriesInFrame, error)
    DoF() []Limit                                 // degrees of freedom / joint limits
    Interpolate([]Input, []Input, float64) ([]Input, error)
    // ... protobuf conversion, JSON marshaling
}
```

`Input` is simply a `float64` alias — the semantic meaning (radians vs. mm) depends on the frame type.

### 5.2 FrameSystem

```go
// referenceframe/frame_system.go
type FrameSystem struct {
    name            string
    world           Frame
    frames          map[string]Frame
    parents         map[string]string
    flattenedModels map[string]*SimpleModel    // component → original multi-DoF model
    componentSchemas map[string]*LinearInputsSchema
    mimicFrames     map[string]*mimicInfo
}
```

Key methods:

- **`Transform(inputs, object Transformable, dst string)`** — transforms any `Transformable` (pose, geometry set) from its parent frame into the destination frame. This is the fundamental operation for converting between coordinate frames.
- **`AddFrame(frame, parent Frame)`** — attaches a frame to the tree.
- **`TracebackFrame(query Frame) ([]Frame, error)`** — walks from a frame back to world, returning the chain.
- **`MergeFrameSystem(systemToMerge, attachTo Frame)`** — attaches another frame system (e.g., an arm's internal kinematics) to a point in this system.

### 5.3 FrameSystem Service

The `framesystem.Service` wraps a live `FrameSystem` with robot state:

```go
type RobotFrameSystem interface {
    FrameSystemConfig(ctx) (*Config, error)
    GetPose(ctx, componentName, destinationFrame string, supplementalTransforms, extra) (*PoseInFrame, error)
    TransformPose(ctx, pose *PoseInFrame, dst string, supplementalTransforms) (*PoseInFrame, error)
    TransformPointCloud(ctx, srcpc pointcloud.PointCloud, srcName, dstName string) (pointcloud.PointCloud, error)
    CurrentInputs(ctx) (FrameSystemInputs, error)
}
```

`TransformPointCloud` is essential for vision-guided manipulation — it takes a point cloud captured in a camera's frame and transforms it into the world frame (or any other frame) for use in obstacle representation or grasp planning.

### 5.4 Transformable Types

The `Transformable` interface (`referenceframe/transformable.go`) is implemented by:

- **`PoseInFrame`** — a pose tagged with its parent frame name. Optionally carries a `GoalCloud` for fuzzy goal specification.
- **`GeometriesInFrame`** — a set of collision geometries tagged with their parent frame.
- **`LinkInFrame`** — a frame with an associated pose offset from its parent (used for supplemental transforms in `WorldState`).

### 5.5 WorldState

`WorldState` packages the environment representation for motion planning:

```go
type WorldState struct {
    obstacleNames map[string]bool
    obstacles     []*GeometriesInFrame    // obstacles in their parent frames
    transforms    []*LinkInFrame          // supplemental frame system transforms
}
```

`ObstaclesInWorldFrame(fs, inputs)` converts all obstacles into world-frame coordinates by running each `GeometriesInFrame` through `FrameSystem.Transform`. This is called during motion planning to build the collision environment.

Obstacles are `spatialmath.Geometry` instances — boxes, spheres, capsules, points, meshes, or octrees (point clouds). Transforms in the `WorldState` allow attaching temporary frames to the frame system (e.g., a detected object's pose relative to a camera).

---

## 6. Spatial Math (`spatialmath/`)

### 6.1 Pose

```go
// spatialmath/pose.go
type Pose interface {
    Point() r3.Vector       // position in mm
    Orientation() Orientation
}
```

Internally represented as dual quaternions (`DualQuaternion`). Key operations:

- **`Compose(a, b Pose) Pose`** — function composition: C(x) = A(B(x)). Non-commutative.
- **`PoseBetween(a, b Pose) Pose`** — returns c such that Compose(a, c) = b.
- **`PoseInverse(p Pose) Pose`** — the inverse transform.
- **`PoseDelta(a, b Pose) Pose`** — difference for distance measurement (uses axis-angle, not composition).

Constructors: `NewPose(point, orientation)`, `NewPoseFromPoint(point)`, `NewPoseFromOrientation(o)`, `NewPoseFromDH(a, d, alpha)` (Denavit-Hartenberg), `NewPoseFromProtobuf(proto)`.

### 6.2 Orientation

```go
type Orientation interface {
    OrientationVectorRadians() *OrientationVector
    OrientationVectorDegrees() *OrientationVectorDegrees
    AxisAngles() *R4AA
    Quaternion() quat.Number
    EulerAngles() *EulerAngles
    RotationMatrix() *RotationMatrix
}
```

Viam's canonical external format is **OrientationVector** (OX, OY, OZ, Theta) — a unit vector defining the rotation axis and a rotation angle. Internally, quaternions are used for composition. Multiple representations are supported: quaternion, axis-angle (R4AA), Euler angles, rotation matrix.

### 6.3 Geometry

```go
type Geometry interface {
    Pose() Pose
    Transform(Pose) Geometry
    CollidesWith(other Geometry, buffer float64) (bool, float64, error)
    DistanceFrom(Geometry) (float64, error)
    EncompassedBy(Geometry) (bool, error)
    ToPoints(density float64) []r3.Vector
    Label() string
    SetLabel(string)
}
```

Geometry types: `box`, `sphere`, `capsule`, `point`, `Mesh`.

The `CollidesWith` method returns a collision flag and a lower-bound distance estimate. `DistanceFrom` returns signed distance (negative = penetration depth). The collision buffer parameter (`defaultCollisionBufferMM = 1e-8`) specifies minimum separation.

Meshes can be converted to octrees via `pointcloud.NewFromMesh(mesh)` for efficient collision detection. This conversion is triggered by the `MeshesAsOctrees` planner option.

### 6.4 BVH (Bounding Volume Hierarchy)

The `spatialmath/bvh.go` implements a BVH for efficient collision queries between sets of geometries. This is used internally by the motion planner's constraint checker to accelerate collision detection when many geometries are involved.

---

## 7. Point Cloud (`pointcloud/`)

### 7.1 Interface

```go
type PointCloud interface {
    Size() int
    MetaData() MetaData
    Set(p r3.Vector, d Data) error
    At(x, y, z float64) (Data, bool)
    Iterate(numBatches, myBatch int, fn func(p r3.Vector, d Data) bool)
    FinalizeAfterReading() (PointCloud, error)
    CreateNewRecentered(offset spatialmath.Pose) PointCloud
}
```

### 7.2 Storage Implementations

- **`BasicPointCloud`** — simple dictionary-based storage. Good for small clouds.
- **`BasicOctree`** — recursive spatial partitioning into octants. Implements both `PointCloud` and `spatialmath.Geometry` interfaces, making it usable as a collision object in motion planning. Max recursion depth is 250 (enough to model extreme precision). Supports confidence thresholds for probabilistic occupancy.
- **`KDTree`** — k-d tree for efficient nearest-neighbor queries. Useful for point cloud registration and matching.
- **`VoxelGrid`** — regular grid discretization. Used for voxel-based segmentation.

### 7.3 File I/O

PCD (Point Cloud Data) format is the primary serialization format, supporting both ASCII and binary encodings. `ReadPCD` and `WritePCD` handle conversions. PCD files can specify the storage type (`octree`, etc.).

### 7.4 Operations

- **Merging** (`pointcloud/merging.go`): `MergePointClouds` combines multiple clouds, optionally applying pose transforms. `MergePointCloudsWithColor` preserves color data.
- **Plane detection** (`pointcloud/plane.go`): RANSAC-based plane fitting for surface detection.
- **Voxel segmentation** (`pointcloud/voxel_segmentation.go`): segments a point cloud into connected components using voxel-based adjacency.
- **Centroid computation**: `CloudCentroid(pc)` returns the mean position.

### 7.5 Octree as Collision Geometry

`BasicOctree` implements `spatialmath.Geometry`, providing:
- `Pose()` — center of the octree
- `Transform(pose)` — returns a repositioned octree
- `CollidesWith(geom, buffer)` — collision detection against any other geometry type
- `DistanceFrom(geom)` — signed distance computation

This dual nature is critical for vision-guided manipulation: a camera's point cloud output can be directly used as obstacle geometry in the motion planner's `WorldState`.

---

## 8. Motion Planning (`motionplan/` + `motionplan/armplanning/`)

### 8.1 Plan Request

```go
// motionplan/armplanning/api.go
type PlanRequest struct {
    FrameSystem    *referenceframe.FrameSystem
    Goals          []*PlanState          // ordered waypoints (pose or configuration)
    StartState     *PlanState            // must have configuration; may have poses
    WorldState     *referenceframe.WorldState
    Constraints    *motionplan.Constraints
    PlannerOptions *PlannerOptions
}
```

Each `PlanState` can be a `FrameSystemPoses` (Cartesian goal, requiring IK) or a `Configuration` (direct joint goal). Multi-waypoint plans are supported — the planner hits each goal in sequence.

### 8.2 Plan Output

```go
// motionplan/plan.go
type Plan interface {
    Path() Path             // sequence of FrameSystemPoses (Cartesian)
    Trajectory() Trajectory // sequence of FrameSystemInputs (joint space)
}

type Trajectory []referenceframe.FrameSystemInputs
type Path []referenceframe.FrameSystemPoses
```

A `Trajectory` maps frame names to input vectors at each step. The motion service executes a trajectory by iterating steps and calling `GoToInputs` on each `InputEnabled` component.

### 8.3 Planner Architecture

The `planManager` orchestrates multi-waypoint planning:

1. **Validate** the `PlanRequest` (frame existence, goal consistency, input bounds)
2. For each goal waypoint:
   - If the goal is a **configuration** → `planToDirectJoints` (interpolation)
   - If the goal is a **pose** → `generateWaypoints` (may split into sub-goals for complex paths), then `planSingleGoal`
3. `planSingleGoal` invokes the **cBiRRT** planner (Constrained Bidirectional RRT, Berenson et al. 2009)
4. Post-process: **path smoothing** to reduce unnecessary joint motion

### 8.4 cBiRRT Planner

The `cBiRRTMotionPlanner` (`motionplan/armplanning/cBiRRT.go`) implements constrained bidirectional rapidly-exploring random tree search:

- Two trees grow simultaneously from start and goal configurations
- Extension steps are constrained (checked against all active constraints)
- Uses `NloptIK` (gradient descent via NLopt) for fast single-attempt IK solves during tree extension
- Max 5000 planning iterations, max 5000 extension iterations per step
- Duplicate solution filtering (similarity score threshold of 0.05)

Smart seeding (`smart_seed.go`) generates initial IK solutions to seed the goal tree, improving planner success rate for difficult poses.

### 8.5 Constraints

```go
type Constraints struct {
    LinearConstraint       []LinearConstraint
    PseudolinearConstraint []PseudolinearConstraint
    OrientationConstraint  []OrientationConstraint
    CollisionSpecification []CollisionSpecification
}
```

- **`LinearConstraint`** — enforces straight-line end-effector motion with tolerance in mm and orientation tolerance in degrees.
- **`PseudolinearConstraint`** — proportional deviation: tolerance scales with start-to-goal distance. A `LineToleranceFactor` of 1.0 means the end-effector stays within a radius equal to the total travel distance.
- **`OrientationConstraint`** — bounds orientation deviation during motion.
- **`CollisionSpecification`** — allows specific frame pairs to collide (e.g., gripper fingers with a grasped object). Supports component-level specification (all sub-geometries of a named component).

### 8.6 Collision Detection Pipeline

The `ConstraintChecker` (`motionplan/constraint_checker.go`) evaluates three types of collision constraints at each planning step:

1. **Obstacle collisions** — moving robot geometries vs. world obstacles from `WorldState`
2. **Robot-to-robot collisions** — moving component geometries vs. stationary component geometries
3. **Self-collisions** — moving geometries against each other

Geometries are computed by calling `Frame.Geometries(inputs)` at each candidate configuration, transforming them to world frame, then checking pairwise collisions via `spatialmath.Geometry.CollidesWith`.

### 8.7 IK Solver (`motionplan/ik/`)

The `ik.Solver` interface provides gradient-descent inverse kinematics:

```go
type Solver interface {
    Solve(ctx, solutions chan<- *Solution, totalAttempts *atomic.Int32,
          seeds [][]float64, limits [][]referenceframe.Limit,
          minFunc CostFunc, rseed int) (int, []SeedSolveMetaData, error)
}
```

The primary implementation is `NloptIK`, which uses the NLopt numerical optimization library. It minimizes a `CostFunc` that typically combines position error and orientation error. Solutions below `defaultGoalThreshold` (1e-6) are considered exact.

The `CombinedIK` solver runs multiple solvers concurrently with different random seeds for better coverage of the solution space.

### 8.8 Planner Options

```go
type PlannerOptions struct {
    MaxSolutions    int
    Timeout         float64           // seconds
    SmoothIter      int
    NumThreads      int
    ReturnPartialPlan bool
    MeshesAsOctrees bool              // convert mesh obstacles to octrees
    // ... more options
}
```

`ReturnPartialPlan` is important for long-horizon tasks — if the planner times out, it returns the best partial plan found so far along with metadata indicating which waypoint it reached.

---

## 9. Motion Service (`services/motion`)

### 9.1 Interface

```go
type Service interface {
    resource.Resource
    Move(ctx context.Context, req MoveReq) (bool, error)
    MoveOnMap(ctx context.Context, req MoveOnMapReq) (ExecutionID, error)
    MoveOnGlobe(ctx context.Context, req MoveOnGlobeReq) (ExecutionID, error)
    GetPose(ctx, componentName, destinationFrame string, supplementalTransforms, extra) (*PoseInFrame, error)
    StopPlan(ctx, req StopPlanReq) error
    ListPlanStatuses(ctx, req ListPlanStatusesReq) ([]PlanStatusWithID, error)
    PlanHistory(ctx, req PlanHistoryReq) ([]PlanWithStatus, error)
}
```

### 9.2 Move Flow (Arm Manipulation)

The builtin motion service's `Move` method (`services/motion/builtin/builtin.go`) orchestrates:

1. **Lock** — acquires read lock, cancels other operations with the same label
2. **Build frame system** — calls `framesystem.NewFromService` with any supplemental transforms from `WorldState`
3. **Collect current inputs** — `fsService.CurrentInputs(ctx)` gathers joint positions from all `InputEnabled` components
4. **Resolve goal frame** — transforms goal poses from their specified frames to world frame coordinates (workaround for multi-component coordination — see RSDK-8847)
5. **Build PlanRequest** — assembles frame system, waypoints, start state, world state, constraints
6. **Plan** — calls `armplanning.PlanMotion(ctx, logger, planRequest)`
7. **Execute** — iterates the trajectory, batching `GoToInputs` calls where possible for trajectory blending

### 9.3 MoveReq

```go
type MoveReq struct {
    ComponentName string                        // what to move
    Destination   *referenceframe.PoseInFrame   // where (pose + reference frame)
    WorldState    *referenceframe.WorldState     // obstacles + supplemental transforms
    Constraints   *motionplan.Constraints        // motion constraints
    Extra         map[string]interface{}         // planner options, waypoints
}
```

### 9.4 Execution

The `execute` method batches trajectory steps for efficiency:
- Groups consecutive steps that move the same set of components
- Validates starting position (within epsilon tolerance) before execution
- On error, stops the actuator before returning
- Supports multi-input `GoToInputs` for trajectory blending (hardware-level interpolation)

### 9.5 DoCommand: Plan/Execute Split

The motion service exposes `DoPlan` and `DoExecute` commands via `DoCommand`, enabling a plan-then-execute workflow:

```go
// Plan without executing
resp, _ := motionSvc.DoCommand(ctx, map[string]interface{}{
    "plan": moveRequestJSON,
})
trajectory := resp["plan"]

// Execute a previously planned trajectory
resp, _ = motionSvc.DoCommand(ctx, map[string]interface{}{
    "execute": trajectory,
    "executeCheckStart": true,  // verify arm is at start position
})
```

This is valuable for vision-guided manipulation where you want to inspect/validate a plan before executing.

### 9.6 Teleop Support

The motion service includes a teleop pipeline (`services/motion/builtin/teleop.go`) for low-latency incremental moves. It uses a pre-built frame system and caller-provided inputs to avoid per-call overhead, making it suitable for real-time teleoperation control loops.

---

## 10. Putting It Together: Vision-Guided Manipulation Pipeline

### 10.1 Perceive → Plan → Act

A typical vision-guided manipulation sequence:

```
1. PERCEIVE
   Camera.Images()           → RGB image
   Camera.NextPointCloud()   → 3D point cloud (depth camera)
   Vision.Detections(img)    → 2D bounding boxes with labels
   Vision.GetObjectPointClouds(cam) → segmented 3D objects

2. LOCALIZE TARGET
   FrameSystem.TransformPose(detectionPose, "camera", "world")
   FrameSystem.TransformPointCloud(objectPCD, "camera", "world")

3. BUILD WORLD STATE
   WorldState{
     obstacles: [detected_objects_as_geometries],
     transforms: [camera_to_world_link],
   }

4. PLAN
   Motion.Move(MoveReq{
     ComponentName: "my_arm",
     Destination:   PoseInFrame{parent: "world", pose: graspPose},
     WorldState:    worldState,
     Constraints:   linearConstraint,
   })

5. ACT (handled internally by motion service)
   arm.GoToInputs(trajectory_step_1)
   arm.GoToInputs(trajectory_step_2)
   ...
```

### 10.2 Key Integration Points

**Camera → Frame System:** The camera's frame is registered in the frame system at configuration time. Its extrinsics define where it sits relative to the robot. Point clouds and detections are in the camera's frame and must be transformed to world (or arm base) frame via `FrameSystem.Transform`.

**Vision → WorldState:** Detected objects can be added to the `WorldState` as obstacles (things to avoid) or removed to create clearance (things to grasp). `GeometriesInFrame` wraps the geometry with its parent frame name.

**WorldState → Motion Planner:** The planner calls `WorldState.ObstaclesInWorldFrame(fs, inputs)` to get all obstacles in world coordinates. These are checked against the robot's geometries (from `Frame.Geometries(inputs)`) at every candidate configuration during planning.

**Motion Planner → Arm:** The trajectory output maps frame names to input sequences. The motion service looks up each component by name, asserts it implements `InputEnabled`, and calls `GoToInputs`. Multiple input sets can be passed for trajectory blending.

### 10.3 Supplemental Transforms for Detected Objects

When a vision system detects an object and provides its pose relative to the camera, you can inject this into the frame system via `WorldState.Transforms`:

```go
// Object detected at cameraPose in camera frame
objectLink := referenceframe.NewLinkInFrame(
    "my_camera",           // parent frame
    cameraPose,            // pose relative to camera
    "detected_object",     // name for this frame
    objectGeometry,        // collision geometry (box, mesh, etc.)
)

worldState, _ := referenceframe.NewWorldState(
    []*referenceframe.GeometriesInFrame{obstacles},
    []*referenceframe.LinkInFrame{objectLink},
)
```

This adds a temporary "detected_object" frame to the frame system for the duration of the planning call. The motion planner can then plan relative to it.

### 10.4 Point Clouds as Obstacles

For scene-level obstacle avoidance using depth cameras:

```go
// Get point cloud from depth camera
pcd, _ := camera.NextPointCloud(ctx, nil)

// Transform to world frame (Robot embeds framesystem.RobotFrameSystem)
worldPCD, _ := robot.TransformPointCloud(ctx, pcd, "my_camera", "world")

// Convert to octree geometry for efficient collision checking
octree, _ := pointcloud.ToBasicOctree(worldPCD, 0) // 0 = no confidence threshold

// Add to world state
obstacleGIF := referenceframe.NewGeometriesInFrame("world", []spatialmath.Geometry{octree})
worldState, _ := referenceframe.NewWorldState([]*referenceframe.GeometriesInFrame{obstacleGIF}, nil)
```

The `MeshesAsOctrees` planner option automatically converts any mesh geometries in the world state to octrees for more efficient collision detection.

### 10.5 Constraints for Manipulation

Common constraint patterns for manipulation:

```go
// Keep end-effector level while moving (e.g., carrying a cup)
constraints := motionplan.NewEmptyConstraints()
constraints.AddOrientationConstraint(motionplan.OrientationConstraint{
    OrientationToleranceDegs: 5.0,
})

// Move in a straight line to the grasp point
constraints.AddLinearConstraint(motionplan.LinearConstraint{
    LineToleranceMm:          2.0,
    OrientationToleranceDegs: 5.0,
})

// Allow gripper to collide with target object (for grasping)
constraints.AddCollisionSpecification(motionplan.CollisionSpecification{
    Allows: []motionplan.CollisionSpecificationAllowedFrameCollisions{
        {Frame1: "my_gripper", Frame2: "target_object"},
    },
})
```

---

## 11. Key Go Packages Summary

| Package | Purpose | Key Types |
|---------|---------|-----------|
| `components/arm` | Arm component API | `Arm` interface |
| `components/camera` | Camera component API | `Camera`, `Properties`, `NamedImage` |
| `components/camera/transformpipeline` | Image transform chains | `Transformation`, `detectorSource` |
| `services/motion` | Motion orchestration | `Service`, `MoveReq`, `PlanWithStatus` |
| `services/motion/builtin` | Builtin motion implementation | `builtIn` (plan + execute) |
| `services/vision` | Vision processing API | `Service` (detect, classify, segment) |
| `motionplan` | Plan types, constraints, collision | `Plan`, `Trajectory`, `Constraints`, `ConstraintChecker` |
| `motionplan/armplanning` | Planning algorithms | `PlanRequest`, `PlanMotion`, `cBiRRTMotionPlanner` |
| `motionplan/ik` | Inverse kinematics | `Solver`, `NloptIK`, `CombinedIK` |
| `referenceframe` | Coordinate frames, kinematics | `Frame`, `FrameSystem`, `WorldState`, `Model`, `PoseInFrame` |
| `robot/framesystem` | Live frame system service | `Service`, `InputEnabled` |
| `spatialmath` | Poses, orientations, geometry | `Pose`, `Orientation`, `Geometry`, `DualQuaternion` |
| `pointcloud` | 3D point cloud data | `PointCloud`, `BasicOctree`, `KDTree` |

---

## 12. Unit Conventions

| Quantity | Internal Unit | Protobuf Unit |
|----------|---------------|---------------|
| Position (translation) | millimeters (mm) | millimeters (mm) |
| Joint angle (revolute) | radians | degrees |
| Joint position (prismatic) | millimeters | millimeters |
| Orientation | quaternion (internal), OV radians | OrientationVector degrees |
| Point cloud coordinates | millimeters | millimeters |
| Collision buffer | millimeters | millimeters |
| Linear velocity | meters/sec | meters/sec |
| Angular velocity | degrees/sec | degrees/sec |
