# Viam RDK Go SDK — Quick Reference Cheatsheet

Companion to `SKILL.md`. Load when you need specific types, unit conventions, or interface
signatures. Based on viamrobotics/rdk source analysis, April 2026.

## Table of Contents
1. [Unit Conventions](#unit-conventions)
2. [Key Packages](#key-packages)
3. [Interface Hierarchy](#interface-hierarchy)
4. [WorldState Structure](#worldstate-structure)
5. [Spatial Math Quick Reference](#spatial-math-quick-reference)
6. [PlanRequest Fields](#planrequest-fields)
7. [Constraint Patterns](#constraint-patterns)
8. [Common Error Patterns & Fixes](#common-error-patterns--fixes)
9. [Vision Pipeline Types](#vision-pipeline-types)
10. [Frame System Key Methods](#frame-system-key-methods)
11. [Point Cloud Storage Implementations](#point-cloud-storage-implementations)

---

## Unit Conventions

| Quantity | Go (internal) | Protobuf wire | Notes |
|----------|--------------|---------------|-------|
| Position / translation | **mm** | mm | r3.Vector, Pose.Point() |
| Revolute joint angle | **radians** | degrees | `Frame.InputFromProtobuf` converts |
| Prismatic joint position | **mm** | mm | |
| Orientation (internal) | quaternion | OrientationVector degrees | OX, OY, OZ, Theta |
| Orientation (external API) | OrientationVector radians | OrientationVector degrees | |
| Point cloud coordinates | **mm** | mm | |
| Collision buffer | **mm** | mm | default 1e-8 mm |
| Linear velocity | m/s | m/s | |
| Angular velocity | deg/s | deg/s | |

**Trap:** `[]referenceframe.Input` you construct manually must be **radians**. Protobuf
input/output goes through `Frame.InputFromProtobuf` / `Frame.ProtobufFromInput`.

---

## Key Packages

| Package | Import path pattern | Key types |
|---------|---------------------|-----------|
| Arm | `go.viam.com/rdk/components/arm` | `Arm` |
| Camera | `go.viam.com/rdk/components/camera` | `Camera`, `Properties`, `NamedImage` |
| Vision service | `go.viam.com/rdk/services/vision` | `Service` |
| Motion service | `go.viam.com/rdk/services/motion` | `Service`, `MoveReq`; `FromRobot` deprecated — use `FromProvider` |
| Motion planning | `go.viam.com/rdk/motionplan` | `Plan`, `Trajectory`, `Constraints` |
| Arm planning | `go.viam.com/rdk/motionplan/armplanning` | `PlanRequest`, `PlanMotion` |
| IK | `go.viam.com/rdk/motionplan/ik` | `Solver`, `NloptIK`, `CombinedIK` |
| Reference frame | `go.viam.com/rdk/referenceframe` | `Frame`, `FrameSystem`, `WorldState`, `PoseInFrame`, `Model`, `Input` |
| Frame system svc | `go.viam.com/rdk/robot/framesystem` | `Service`, `InputEnabled` |
| Spatial math | `go.viam.com/rdk/spatialmath` | `Pose`, `Orientation`, `Geometry`, `DualQuaternion` |
| Point cloud | `go.viam.com/rdk/pointcloud` | `PointCloud`, `BasicOctree`, `KDTree` |

---

## Interface Hierarchy

### Arm
```
Arm
├── resource.Resource       (Name, Reconfigure, Close)
├── resource.Shaped         (Geometries at any config — used by planner)
├── resource.Actuator       (IsMoving, Stop)
└── framesystem.InputEnabled
    ├── Kinematics(ctx) (referenceframe.Model, error)
    ├── CurrentInputs(ctx) ([]referenceframe.Input, error)
    └── GoToInputs(ctx, ...[]referenceframe.Input) error   ← trajectory execution
```

### Camera
```
Camera
├── resource.Resource
├── resource.Shaped
├── Images(ctx, filterSourceNames, extra) ([]NamedImage, ResponseMetadata, error)
├── NextPointCloud(ctx, extra) (pointcloud.PointCloud, error)
└── Properties(ctx) (Properties, error)
```

### Motion Service
```
motion.Service
├── Move(ctx, MoveReq) (bool, error)                      ← arm manipulation
├── MoveOnMap(ctx, MoveOnMapReq) (ExecutionID, error)     ← 2D nav
├── MoveOnGlobe(ctx, MoveOnGlobeReq) (ExecutionID, error) ← GPS nav
├── GetPose(ctx, ...) (*PoseInFrame, error)
├── StopPlan / ListPlanStatuses / PlanHistory
└── DoCommand  →  "plan" / "execute" keys
```

### Frame
```
referenceframe.Frame
├── Name() string
├── Transform([]Input) (spatialmath.Pose, error)      ← pose from this frame to parent
├── Geometries([]Input) (*GeometriesInFrame, error)
├── DoF() []Limit                                      ← joint limits
└── Interpolate([]Input, []Input, float64) ([]Input, error)
```

---

## WorldState Structure

```go
// Build with:
ws, err := referenceframe.NewWorldState(
    []*referenceframe.GeometriesInFrame{obstacleGIF},   // things to avoid
    []*referenceframe.LinkInFrame{detectedObjectLink},  // supplemental frame transforms
)

// GeometriesInFrame: geometries tagged to a frame
gif := referenceframe.NewGeometriesInFrame("world", []spatialmath.Geometry{boxGeom})

// LinkInFrame: a temporary frame attached to an existing frame
link := referenceframe.NewLinkInFrame(
    "my_camera",      // parent frame name
    poseRelToCamera,  // spatialmath.Pose
    "detected_obj",   // new frame name
    optionalGeom,     // can be nil
)
```

**Planner calls `ws.ObstaclesInWorldFrame(fs, inputs)` internally** — you don't need to.

---

## Spatial Math Quick Reference

### Pose operations
```go
// Compose: apply b first, then a  (NOT commutative)
c := spatialmath.Compose(a, b)

// Relative transform: "what is b relative to a?"
rel := spatialmath.PoseBetween(a, b)

// Inverse
inv := spatialmath.PoseInverse(p)

// Difference for distance measurement (not composition)
delta := spatialmath.PoseDelta(a, b)
```

### Constructors
```go
spatialmath.NewPoseFromPoint(r3.Vector{X: 100, Y: 0, Z: 250})  // mm
spatialmath.NewPose(point, orientation)
spatialmath.NewPoseFromOrientation(o)
spatialmath.NewPoseFromDH(a, d, alpha)                          // Denavit-Hartenberg
spatialmath.NewPoseFromProtobuf(proto)
```

### Orientation representations (all interconvertible)
```go
type Orientation interface {
    OrientationVectorRadians() *OrientationVector  // canonical external format: OX,OY,OZ,Theta
    OrientationVectorDegrees() *OrientationVectorDegrees
    AxisAngles() *R4AA
    Quaternion() quat.Number                       // internal representation
    EulerAngles() *EulerAngles
    RotationMatrix() *RotationMatrix
}
```

### Geometry types
| Type | Constructor | Notes |
|------|------------|-------|
| Box | `spatialmath.NewBox(pose, dims, label)` | dims in mm |
| Sphere | `spatialmath.NewSphere(pose, radius, label)` | radius in mm |
| Capsule | `spatialmath.NewCapsule(pose, radius, length, label)` | |
| Point | `spatialmath.NewPoint(point, label)` | |
| Mesh | from proto / URDF | convertible to octree via `pointcloud.NewFromMesh` |

```go
// Collision check
collides, distLowerBound, err := geomA.CollidesWith(geomB, bufferMM)
dist, err := geomA.DistanceFrom(geomB)  // negative = penetration depth
```

---

## PlanRequest Fields

```go
armplanning.PlanRequest{
    FrameSystem:    fs,          // *referenceframe.FrameSystem — full robot topology
    Goals:          []*PlanState // ordered waypoints; pose (needs IK) or configuration
    StartState:     *PlanState   // must include Configuration; poses optional
    WorldState:     ws,          // *referenceframe.WorldState — obstacles + temp frames
    Constraints:    c,           // *motionplan.Constraints — optional
    PlannerOptions: opts,        // *PlannerOptions — timeouts, threads, etc.
}
```

### PlannerOptions highlights
| Option | Default | Notes |
|--------|---------|-------|
| `Timeout` | 300 | seconds; controls cBiRRT wall time |
| `MaxSolutions` | 100 | IK solution pool size (seeds goal tree) |
| `ReturnPartialPlan` | false | return best partial plan on timeout |
| `MeshesAsOctrees` | false | convert mesh obstacles → octrees |

Note: `NumThreads` is a module-level default (`min(runtime.NumCPU()/2, 10)`), not a
`PlannerOptions` field.

---

## Constraint Patterns

```go
c := motionplan.NewEmptyConstraints()

// Straight-line end-effector motion
c.AddLinearConstraint(motionplan.LinearConstraint{
    LineToleranceMm:          2.0,
    OrientationToleranceDegs: 5.0,
})

// Proportional deviation (tolerates curves proportional to travel distance)
c.AddPseudolinearConstraint(motionplan.PseudolinearConstraint{
    LineToleranceFactor:          1.0,  // max radius = total travel distance
    OrientationToleranceFactor:   0.1,
})

// Hold orientation (e.g., keep cup level)
c.AddOrientationConstraint(motionplan.OrientationConstraint{
    OrientationToleranceDegs: 5.0,
})

// Allow specific frame pair to collide (grasping)
c.AddCollisionSpecification(motionplan.CollisionSpecification{
    Allows: []motionplan.CollisionSpecificationAllowedFrameCollisions{
        {Frame1: "my_gripper", Frame2: "target_object"},
    },
})
```

---

## Common Error Patterns & Fixes

| Error symptom | Likely cause | Fix |
|---------------|-------------|-----|
| "frame not found: my_camera" | Camera not in frame system | Register in robot config or add via supplemental transforms |
| IK solver returns no solutions | Pose unreachable or joint limits | Check pose is in workspace; try relaxing orientation constraint |
| Arm collides with obstacle immediately | Start state is in collision | Check obstacle geometry overlaps start pose; clear or shrink |
| Plan succeeds but motion is jerky | Single `GoToInputs` per step | Pass multiple inputs to `GoToInputs` for blending |
| `CollidesWith` returns true unexpectedly | Collision buffer | Lower `bufferMM` or check geometry center/offset |
| "desired joint positions out of bounds" | Input in degrees instead of radians | Verify units; use `Frame.InputFromProtobuf` for proto-sourced values |
| Timeout with no plan | Path fully blocked or start=goal collision | Add `ReturnPartialPlan: true`; inspect WorldState |

---

## Vision Pipeline Types

```go
// 2D detection
type objectdetection.Detection interface {
    BoundingBox() *image.Rectangle
    Score() float64
    Label() string
}

// 3D segmented object (vision/object.go)
type vision.Object struct {
    pointcloud.PointCloud       // embedded
    Geometry spatialmath.Geometry
}

// Camera intrinsics (for 2D→3D projection)
type transform.PinholeCameraIntrinsics struct {
    Width, Height int
    Fx, Fy        float64  // focal lengths in pixels
    Ppx, Ppy      float64  // principal point
}
```

### 2D → 3D projection (manual, without depth)
Use `camera.ExtrinsicParams` + `PinholeCameraIntrinsics`:
- `PointToPixel(worldPt)` — world point → pixel (inverse extrinsic + project)
- For pixel → world you need depth; use `NextPointCloud` or a depth camera.

---

## Frame System Key Methods

```go
// Transform any Transformable between frames
result, err := fs.Transform(inputs, objectInFrame, destinationFrameName)

// Walk frame chain to world
chain, err := fs.TracebackFrame(queryFrame)

// Merge arm kinematics into robot frame system
fs.MergeFrameSystem(armKinematicsFS, attachToFrame)

// Live service (uses current joint state)
fsSvc.TransformPose(ctx, poseInFrame, dstFrameName, supplementalTransforms)
fsSvc.TransformPointCloud(ctx, pcd, srcFrameName, dstFrameName)
fsSvc.CurrentInputs(ctx)  // → FrameSystemInputs (all component joint states)
```

---

## Point Cloud Storage Implementations

| Type | Best for | Implements Geometry? |
|------|----------|----------------------|
| `BasicPointCloud` | Small clouds, general use | No |
| `BasicOctree` | Obstacle representation, collision | **Yes** — use as WorldState obstacle |
| `KDTree` | Nearest-neighbor queries, registration | No |
| `VoxelGrid` | Voxel segmentation | No |

`BasicOctree` key parameters:
- Max recursion depth: 250
- Supports confidence threshold for probabilistic occupancy
- `Transform(pose)` returns a repositioned octree (doesn't copy points — new root pose)
