# Viam TypeScript SDK Reference

> Built from `@viamrobotics/sdk` v0.68.x source (April 2026). The SDK evolves
> rapidly. When in doubt, check `https://ts.viam.dev` or the user's installed
> version via their `package.json`.

---

## 1. SDK Architecture

### Transport Stack

```
Browser App
    |
    v
@viamrobotics/sdk  (@connectrpc/connect-web)
    |
    +-- WebRTC (default for cloud-connected machines)
    |     via signaling server at app.viam.com:443
    |     P2P data channel for gRPC-web frames
    |     Media tracks for camera streaming
    |
    +-- gRPC-web direct (local connections only)
          requires host URL containing "local"
          no WebRTC overhead, no media streaming
```

**Key dependencies:**
- `@bufbuild/protobuf` -- protobuf message construction
- `@connectrpc/connect` + `@connectrpc/connect-web` -- gRPC-web transport
- `exponential-backoff` -- reconnection logic

**Node.js additional dependencies:**
- `@connectrpc/connect-node` -- gRPC H2 transport (replaces connect-web)
- `node-datachannel` -- WebRTC polyfill for Node

### Connection Modes

| Mode | When Used | Media Streaming | Requirements |
|------|-----------|-----------------|--------------|
| WebRTC (cloud) | `signalingAddress` provided | Yes (camera tracks) | Internet access to app.viam.com |
| gRPC-web direct | Host contains "local" | No | Local network access, no TLS required |

**WebRTC is the default.** When `createRobotClient` receives a `DialWebRTCConf` (has `signalingAddress`), it connects via WebRTC. If WebRTC fails and `noReconnect` is set, it falls back to direct gRPC.

### Package Exports

```
@viamrobotics/sdk
  main entry: dist/main.es.js  (ESM)
  CJS entry:  dist/main.umd.js
  types:      dist/main.d.ts
```

All public API is re-exported from `src/main.ts`.

---

## 2. RobotClient

### Creating a Connection

The primary way to connect:

```typescript
import { createRobotClient } from '@viamrobotics/sdk';

const machine = await createRobotClient({
  host: 'my-robot-main.abc123xyz.viam.cloud',
  credentials: {
    type: 'api-key',
    authEntity: '<API_KEY_ID>',
    payload: '<API_KEY>',
  },
  signalingAddress: 'https://app.viam.com:443',
});
```

`createRobotClient` returns a `Promise<RobotClient>`. It calls `new RobotClient().dial(conf)` internally.

### DialConf Types

```typescript
type DialConf = DialDirectConf | DialWebRTCConf;
```

**DialWebRTCConf** (cloud connection -- most common):
```typescript
interface DialWebRTCConf {
  host: string;                        // Machine FQDN
  credentials?: Credential | AccessToken;
  signalingAddress: string;            // 'https://app.viam.com:443'
  iceServers?: ICEServer[];            // Optional STUN/TURN
  disableSessions?: boolean;
  noReconnect?: boolean;               // Default: false (reconnect enabled)
  reconnectMaxAttempts?: number;       // Default: 10
  reconnectMaxWait?: number;           // Max backoff delay (ms)
  reconnectAbortSignal?: { abort: boolean }; // External abort control
  shouldRetryOnError?: () => boolean;  // Override retry logic
  dialTimeoutMs?: number;             // Default: 10000 (10s)
  extraHeaders?: Record<string, string>;
  priority?: number;
  forceRelay?: boolean;               // TURN-only (testing)
  forceP2P?: boolean;                 // No TURN (testing)
  turnUri?: string;                   // Filter TURN server
  turnScheme?: 'turn' | 'turns';
  turnTransport?: 'tcp' | 'udp';
  turnPort?: number;
}
```

**DialDirectConf** (local/direct gRPC):
```typescript
interface DialDirectConf {
  host: string;                        // Must contain "local"
  credentials?: Credential | AccessToken;
  disableSessions?: boolean;
  noReconnect?: boolean;
  reconnectMaxAttempts?: number;
  reconnectMaxWait?: number;
  reconnectAbortSignal?: { abort: boolean };
  shouldRetryOnError?: () => boolean;
  dialTimeoutMs?: number;
  extraHeaders?: Record<string, string>;
}
```

### Credential Types

```typescript
interface Credential {
  authEntity: string;    // API key ID or machine address
  type: 'api-key' | 'robot-secret';
  payload: string;       // The secret value
}

interface AccessToken {
  type: 'access-token';
  payload: string;       // Bearer token
}

type Credentials = Credential | AccessToken;
```

### RobotClient Methods

```typescript
class RobotClient extends EventDispatcher implements Robot {
  // Connection lifecycle
  dial(conf: DialConf): Promise<RobotClient>;
  connect(opts?: ConnectOptions): Promise<void>;
  disconnect(): Promise<void>;
  isConnected(): boolean;

  // Service accessors (lazy-initialized)
  get armService(): Client<ArmService>;
  get baseService(): Client<BaseService>;
  get boardService(): Client<BoardService>;
  get encoderService(): Client<EncoderService>;
  get gantryService(): Client<GantryService>;
  get genericService(): Client<GenericService>;
  get gripperService(): Client<GripperService>;
  get mlModelService(): Client<MLModelService>;
  get movementSensorService(): Client<MovementSensorService>;
  get powerSensorService(): Client<PowerSensorService>;
  get inputControllerService(): Client<InputControllerService>;
  get motorService(): Client<MotorService>;
  get navigationService(): Client<NavigationService>;
  get discoveryService(): Client<DiscoveryService>;
  get motionService(): Client<MotionService>;
  get visionService(): Client<VisionService>;
  get servoService(): Client<ServoService>;
  get slamService(): Client<SLAMService>;
  get worldStateStoreService(): Client<WorldStateStoreService>;

  // Custom service client creation
  createServiceClient<T extends ServiceType>(svcType: T): Client<T>;

  // Robot-level operations
  resourceNames(): Promise<ResourceName[]>;
  resourceRPCSubtypes(): Promise<ResourceRPCSubtype[]>;
  getSessions(): Promise<Session[]>;
  getOperations(): Promise<Operation[]>;
  cancelOperation(id: string): Promise<void>;
  blockForOperation(id: string): Promise<void>;
  stopAll(): Promise<void>;
  getCloudMetadata(): Promise<CloudMetadata>;
  getMachineStatus(): Promise<MachineStatus>;
  getVersion(): Promise<GetVersionResponse>;
  restartModule(moduleId?: string, moduleName?: string): Promise<void>;

  // Frame system
  frameSystemConfig(transforms: Transform[]): Promise<FrameSystemConfig[]>;
  transformPose(source: PoseInFrame, destination: string, supplementalTransforms: Transform[]): Promise<PoseInFrame>;
  transformPCD(pointCloudPCD: Uint8Array, source: string, destination: string): Promise<Uint8Array>;
  getPose(componentName: string, destinationFrame: string, supplementalTransforms: Transform[]): Promise<PoseInFrame>;
  getModelsFromModules(): Promise<ModuleModel[]>;

  // WebRTC internals
  get peerConnection(): RTCPeerConnection | undefined;
  get sessionId(): string;
}
```

### Connection Events

```typescript
enum MachineConnectionEvent {
  CONNECTING       = 'connecting',
  CONNECTED        = 'connected',
  DISCONNECTING    = 'disconnecting',
  DISCONNECTED     = 'disconnected',
  DIALING          = 'dialing',
  RECONNECTING     = 'reconnecting',
  RECONNECTION_FAILED = 'reconnection_failed',
}

// Listen to specific event
machine.on(MachineConnectionEvent.CONNECTED, (args) => { ... });

// Listen to all connection state changes
machine.on('connectionstatechange', (event) => {
  const { eventType } = event as { eventType: MachineConnectionEvent };
});
```

**Important:** Direct gRPC connections do NOT emit disconnect events automatically.
WebRTC connections DO emit disconnect events. All connections emit events during
manual `connect()` and `disconnect()` calls.

### Reconnection Behavior

- Enabled by default (set `noReconnect: true` to disable)
- Uses exponential backoff via `exponential-backoff` library
- Controlled by `reconnectMaxAttempts` (default 10) and `reconnectMaxWait`
- Non-retryable errors: auth failures, invalid arguments, not found, permission denied
- Custom retry logic via `shouldRetryOnError` callback
- External abort via `reconnectAbortSignal: { abort: boolean }`

---

## 3. ViamClient (App API)

For accessing Viam cloud services (data, app management, ML training) without
connecting to a specific machine:

```typescript
import { createViamClient, type ViamClientOptions } from '@viamrobotics/sdk';

const client = await createViamClient({
  credentials: {
    type: 'api-key',
    authEntity: '<API_KEY_ID>',
    payload: '<API_KEY>',
  },
});

// Access sub-clients
client.dataClient;          // DataClient
client.appClient;           // AppClient
client.mlTrainingClient;    // MlTrainingClient
client.provisioningClient;  // ProvisioningClient
client.billingClient;       // BillingClient

// Connect to a machine through the ViamClient
const machine = await client.connectToMachine({ host: 'my-robot.abc.viam.cloud' });
// or by machine ID:
const machine = await client.connectToMachine({ id: 'machine-uuid' });
```

---

## 4. Component Client Interfaces

All component clients follow the pattern:
```typescript
const component = new ComponentClient(machine, 'component_name');
```

Every component implements `Resource`:
```typescript
interface Resource {
  readonly name: string;
  doCommand(command: Struct | Record<string, JsonValue>): Promise<JsonValue>;
  getStatus(): Promise<JsonValue>;
}
```

### Arm
```typescript
const arm = new ArmClient(machine, 'my_arm');

arm.getEndPosition(extra?: Struct): Promise<Pose>;
arm.moveToPosition(pose: Pose, extra?: Struct): Promise<void>;
arm.moveToJointPositions(joints: number[], extra?: Struct): Promise<void>;
arm.getJointPositions(extra?: Struct): Promise<ArmJointPositions>;
arm.getGeometries(extra?: Struct): Promise<Geometry[]>;
arm.get3DModels(extra?: Struct): Promise<Record<string, Mesh>>;
arm.getKinematics(extra?: Struct): Promise<GetKinematicsResult>;
arm.stop(extra?: Struct): Promise<void>;
arm.isMoving(): Promise<boolean>;
```

### Base
```typescript
const base = new BaseClient(machine, 'my_base');

base.moveStraight(distanceMm: number, mmPerSec: number, extra?: Struct): Promise<void>;
base.spin(angleDeg: number, degsPerSec: number, extra?: Struct): Promise<void>;
base.setPower(linear: Vector3, angular: Vector3, extra?: Struct): Promise<void>;
base.setVelocity(linear: Vector3, angular: Vector3, extra?: Struct): Promise<void>;
base.stop(extra?: Struct): Promise<void>;
base.isMoving(): Promise<boolean>;
base.getProperties(extra?: Struct): Promise<BaseProperties>;
base.getGeometries(extra?: Struct): Promise<Geometry[]>;
```

### Board
```typescript
const board = new BoardClient(machine, 'my_board');

board.getGPIO(pin: string, extra?: Struct): Promise<boolean>;
board.setGPIO(pin: string, high: boolean, extra?: Struct): Promise<void>;
board.getPWM(pin: string, extra?: Struct): Promise<number>;
board.setPWM(pin: string, dutyCyclePct: number, extra?: Struct): Promise<void>;
board.getPWMFrequency(pin: string, extra?: Struct): Promise<number>;
board.setPWMFrequency(pin: string, frequencyHz: number, extra?: Struct): Promise<void>;
board.readAnalogReader(analogReader: string, extra?: Struct): Promise<AnalogValue>;
board.writeAnalog(pin: string, value: number, extra?: Struct): Promise<void>;
board.getDigitalInterruptValue(name: string, extra?: Struct): Promise<number>;
board.streamTicks(interrupts: string[], queue: Tick[], extra?: Struct): Promise<void>;
board.setPowerMode(powerMode: PowerMode, duration: Duration, extra?: Struct): Promise<void>;
```

### Camera
```typescript
const camera = new CameraClient(machine, 'my_camera');

camera.getImages(filterSourceNames?: string[], extra?: Struct): Promise<{
  images: NamedImage[];
  metadata: ResponseMetadata;
}>;
camera.getPointCloud(extra?: Struct): Promise<Uint8Array>;
camera.getProperties(): Promise<Properties>;
camera.getGeometries(extra?: Struct): Promise<Geometry[]>;
```

**Camera does NOT have a `getImage()` method returning a single frame.** Use
`getImages()` which returns an array of `NamedImage` objects. For live streaming,
use `StreamClient` (see Streaming APIs below).

### Encoder
```typescript
const encoder = new EncoderClient(machine, 'my_encoder');

encoder.resetPosition(extra?: Struct): Promise<void>;
encoder.getProperties(extra?: Struct): Promise<EncoderProperties>;
encoder.getPosition(positionType?: EncoderPositionType, extra?: Struct): Promise<readonly [number, EncoderPositionType]>;
```

### Gantry
```typescript
const gantry = new GantryClient(machine, 'my_gantry');

gantry.getPosition(extra?: Struct): Promise<number[]>;
gantry.moveToPosition(positionsMm: number[], speedsMmPerSec: number[], extra?: Struct): Promise<void>;
gantry.getLengths(extra?: Struct): Promise<number[]>;
gantry.home(extra?: Struct): Promise<boolean>;
gantry.stop(extra?: Struct): Promise<void>;
gantry.isMoving(): Promise<boolean>;
gantry.getGeometries(extra?: Struct): Promise<Geometry[]>;
```

### Gripper
```typescript
const gripper = new GripperClient(machine, 'my_gripper');

gripper.open(extra?: Struct): Promise<void>;
gripper.grab(extra?: Struct): Promise<void>;
gripper.stop(extra?: Struct): Promise<void>;
gripper.isMoving(): Promise<boolean>;
gripper.isHoldingSomething(extra?: Struct): Promise<boolean>;
gripper.getGeometries(extra?: Struct): Promise<Geometry[]>;
```

### Motor
```typescript
const motor = new MotorClient(machine, 'my_motor');

motor.setPower(power: number, extra?: Struct): Promise<void>;          // -1 to 1
motor.goFor(rpm: number, revolutions: number, extra?: Struct): Promise<void>;
motor.goTo(rpm: number, positionRevolutions: number, extra?: Struct): Promise<void>;
motor.setRPM(rpm: number, extra?: Struct): Promise<void>;
motor.resetZeroPosition(offset: number, extra?: Struct): Promise<void>;
motor.stop(extra?: Struct): Promise<void>;
motor.getProperties(extra?: Struct): Promise<Properties>;
motor.getPosition(extra?: Struct): Promise<number>;
motor.isPowered(extra?: Struct): Promise<readonly [boolean, number]>;
motor.isMoving(): Promise<boolean>;
```

### MovementSensor
```typescript
const ms = new MovementSensorClient(machine, 'my_movement_sensor');

ms.getLinearVelocity(extra?: Struct): Promise<Vector3>;
ms.getAngularVelocity(extra?: Struct): Promise<Vector3>;
ms.getCompassHeading(extra?: Struct): Promise<number>;
ms.getOrientation(extra?: Struct): Promise<Orientation>;
ms.getPosition(extra?: Struct): Promise<MovementSensorPosition>;
ms.getProperties(extra?: Struct): Promise<MovementSensorProperties>;
ms.getAccuracy(extra?: Struct): Promise<MovementSensorAccuracy>;
ms.getLinearAcceleration(extra?: Struct): Promise<Vector3>;
ms.getReadings(extra?: Struct): Promise<Record<string, JsonValue>>;
```

### PowerSensor
```typescript
const ps = new PowerSensorClient(machine, 'my_power_sensor');

ps.getVoltage(extra?: Struct): Promise<readonly [number, boolean]>;
ps.getCurrent(extra?: Struct): Promise<readonly [number, boolean]>;
ps.getPower(extra?: Struct): Promise<number>;
ps.getReadings(extra?: Struct): Promise<Record<string, JsonValue>>;
```

### Sensor
```typescript
const sensor = new SensorClient(machine, 'my_sensor');

sensor.getReadings(extra?: Struct): Promise<Record<string, JsonValue>>;
```

### Servo
```typescript
const servo = new ServoClient(machine, 'my_servo');

servo.move(angleDeg: number, extra?: Struct): Promise<void>;
servo.getPosition(extra?: Struct): Promise<number>;
servo.stop(extra?: Struct): Promise<void>;
servo.isMoving(): Promise<boolean>;
```

### Generic Component
```typescript
const generic = new GenericComponentClient(machine, 'my_component');

generic.doCommand(command: Struct | Record<string, JsonValue>): Promise<JsonValue>;
generic.getStatus(): Promise<JsonValue>;
generic.getGeometries(extra?: Struct): Promise<Geometry[]>;
```

### Additional Components

The SDK also exports these component clients (less commonly used in web UIs):

- **`AudioInClient`** / **`AudioOutClient`** -- audio capture and playback
- **`ButtonClient`** -- physical button state
- **`SwitchClient`** -- toggle switch state
- **`PoseTrackerClient`** -- pose tracking for tracked bodies
- **`InputControllerClient`** -- gamepad/joystick input events

All follow the same `new XClient(machine, 'name')` pattern and implement `Resource`.

---

## 5. Service Client Interfaces

### Vision
```typescript
const vision = new VisionClient(machine, 'my_vision');

vision.getDetectionsFromCamera(cameraName: string, extra?: Struct): Promise<Detection[]>;
vision.getDetections(image: Uint8Array, width: number, height: number, mimeType: MimeType, extra?: Struct): Promise<Detection[]>;
vision.getClassificationsFromCamera(cameraName: string, count: number, extra?: Struct): Promise<Classification[]>;
vision.getClassifications(image: Uint8Array, width: number, height: number, mimeType: MimeType, count: number, extra?: Struct): Promise<Classification[]>;
vision.getObjectPointClouds(cameraName: string, extra?: Struct): Promise<PointCloudObject[]>;
vision.getProperties(extra?: Struct): Promise<Properties>;
vision.captureAllFromCamera(cameraName: string, opts: CaptureAllOptions, extra?: Struct): Promise<CaptureAllResponse>;
```

`CaptureAllOptions`:
```typescript
interface CaptureAllOptions {
  returnImage?: boolean;
  returnClassifications?: boolean;
  returnDetections?: boolean;
  returnObjectPointClouds?: boolean;
}
```

### Motion
```typescript
const motion = new MotionClient(machine, 'builtin');

motion.move(destination: PoseInFrame, componentName: string, worldState?: WorldState, constraints?: Constraints, extra?: Struct): Promise<boolean>;
motion.moveOnMap(destination: Pose, componentName: string, slamServiceName: string, motionConfiguration?: MotionConfiguration, obstacles?: Geometry[], extra?: Struct): Promise<string>;
motion.moveOnGlobe(destination: GeoPoint, componentName: string, movementSensorName: string, heading?: number, obstaclesList?: GeoGeometry[], motionConfiguration?: MotionConfiguration, boundingRegion?: GeoGeometry[], extra?: Struct): Promise<string>;
motion.stopPlan(componentName: string, extra?: Struct): Promise<null>;
motion.getPlan(componentName: string, lastPlanOnly?: boolean, executionId?: string, extra?: Struct): Promise<GetPlanResponse>;
motion.listPlanStatuses(onlyActivePlans?: boolean, extra?: Struct): Promise<ListPlanStatusesResponse>;
motion.getPose(componentName: string, destinationFrame: string, supplementalTransforms: Transform[], extra?: Struct): Promise<PoseInFrame>;  // deprecated, use RobotClient.getPose
```

### Navigation
```typescript
const nav = new NavigationClient(machine, 'my_navigation');

nav.getMode(extra?: Struct): Promise<Mode>;
nav.setMode(mode: Mode, extra?: Struct): Promise<void>;   // 0=UNSPECIFIED, 1=MANUAL, 2=WAYPOINT, 3=EXPLORE
nav.getLocation(extra?: Struct): Promise<NavigationPosition>;
nav.getWayPoints(extra?: Struct): Promise<Waypoint[]>;
nav.addWayPoint(location: GeoPoint, extra?: Struct): Promise<void>;
nav.removeWayPoint(id: string, extra?: Struct): Promise<void>;
nav.getObstacles(extra?: Struct): Promise<GeoGeometry[]>;
nav.getPaths(extra?: Struct): Promise<Path[]>;
nav.getProperties(): Promise<NavigationProperties>;
```

### SLAM
```typescript
const slam = new SlamClient(machine, 'my_slam');

slam.getPosition(): Promise<SlamPosition>;
slam.getPointCloudMap(returnEditedMap?: boolean): Promise<Uint8Array>;
slam.getInternalState(): Promise<Uint8Array>;
slam.getProperties(): Promise<SlamProperties>;
```

### MLModel
```typescript
const ml = new MLModelClient(machine, 'my_model');

ml.metadata(extra?: Struct): Promise<MetadataResponse>;
ml.infer(inputTensors: FlatTensors, extra?: Struct): Promise<InferResponse>;
```

### DataManager
```typescript
const dm = new DataManagerClient(machine, 'my_data_manager');

dm.sync(extra?: Struct): Promise<void>;
dm.uploadBinaryDataToDatasets(binaryData: Uint8Array, tags: string[], datasetIds: string[], mimeType: MimeType, extra?: Struct): Promise<void>;
```

### Generic Service
```typescript
const generic = new GenericServiceClient(machine, 'my_service');

generic.doCommand(command: Struct | Record<string, JsonValue>): Promise<JsonValue>;
generic.getStatus(): Promise<JsonValue>;
```

---

## 6. Streaming APIs

### WebRTC Media Streaming (Camera in Browser)

Camera live streams use WebRTC media tracks, NOT repeated `getImages()` calls.
This only works with WebRTC connections (not direct gRPC).

**StreamClient** manages WebRTC media streams:

```typescript
import { StreamClient } from '@viamrobotics/sdk';

const streamClient = new StreamClient(machine);

// Get a MediaStream for a camera
const mediaStream = await streamClient.getStream('my_camera');

// Attach to <video> element
const videoEl = document.querySelector('video');
videoEl.srcObject = mediaStream;

// Control stream resolution
const resolutions = await streamClient.getOptions('my_camera');
await streamClient.setOptions('my_camera', 640, 480);
await streamClient.resetOptions('my_camera');

// Remove stream when done
await streamClient.remove('my_camera');
```

**StreamClient interface:**
```typescript
class StreamClient extends EventDispatcher {
  constructor(client: RobotClient, options?: Options);

  add(name: string): Promise<void>;
  remove(name: string): Promise<void>;
  getStream(name: string): Promise<MediaStream>;  // add + wait for track (5s timeout)
  getOptions(resourceName: string): Promise<Resolution[]>;
  setOptions(name: string, width: number, height: number): Promise<void>;
  resetOptions(name: string): Promise<void>;
}
```

**Important:** `getStream()` has a 5-second timeout. If the WebRTC track is not
received within 5 seconds, it throws an error.

### Image Polling (Alternative to Streaming)

For scenarios where you need processed images (with detections, etc.), poll
`camera.getImages()` or `vision.captureAllFromCamera()`:

```typescript
// Using camera.getImages()
const { images } = await camera.getImages();
const [mainImage] = images;
const base64 = btoa(
  Array.from(mainImage.image)
    .map((byte) => String.fromCharCode(byte))
    .join('')
);
img.src = `data:image/jpeg;base64,${base64}`;

// Using vision.captureAllFromCamera() for image + detections in one call
const result = await vision.captureAllFromCamera('my_camera', {
  returnImage: true,
  returnDetections: true,
});
```

### Stream Events

The `StreamClient` emits `'track'` events whenever a WebRTC track is received.
The `RobotClient` also emits `'track'` events. StreamClient listens to the
RobotClient's track events and re-emits them.

On reconnection (`MachineConnectionEvent.CONNECTED`), the StreamClient
automatically re-adds all previously added streams.

---

## 7. Type System

### Common Types (from `@viamrobotics/sdk`)

```typescript
// Spatial types
type Pose = { x: number; y: number; z: number; oX: number; oY: number; oZ: number; theta: number };
type PoseInFrame = { referenceFrame: string; pose?: Pose };
type Vector3 = { x: number; y: number; z: number };
type Orientation = { oX: number; oY: number; oZ: number; theta: number };

// Geometry types
type Geometry = { center?: Pose; sphere?: Sphere; box?: RectangularPrism; capsule?: Capsule; label: string };
type GeometriesInFrame = { referenceFrame: string; geometries: Geometry[] };
type Sphere = { radiusMm: number };
type RectangularPrism = { dimsMm: Vector3 };
type Capsule = { radiusMm: number; lengthMm: number };

// Geo types
type GeoPoint = { latitude: number; longitude: number };
type GeoGeometry = { location?: GeoPoint; geometries: Geometry[] };

// Resource identity
type ResourceName = { namespace: string; type: string; subtype: string; name: string };

// World state (for motion planning)
type WorldState = { obstacles: GeometriesInFrame[]; transforms: Transform[] };
type Transform = { referenceFrame: string; poseInObserverFrame?: PoseInFrame; physicalObject?: Geometry };

// Protobuf helpers
type Struct      -- from @bufbuild/protobuf
type JsonValue   -- from @bufbuild/protobuf
type PlainMessage<T>  -- strips protobuf methods, gives plain object shape
```

### Type Construction

Types are exported both as TypeScript types and as constructors:
```typescript
import { Pose, PoseInFrame, Vector3, Struct } from '@viamrobotics/sdk';

// As constructor
const pose = new Pose({ x: 100, y: 0, z: 200, oX: 0, oY: 0, oZ: 1, theta: 0 });
const pif = new PoseInFrame({ referenceFrame: 'world', pose });

// As plain object (also works where PlainMessage<T> is expected)
const poseObj: Pose = { x: 100, y: 0, z: 200, oX: 0, oY: 0, oZ: 1, theta: 0 };
```

### Struct Usage

For `doCommand` and `extra` parameters:

```typescript
import { Struct } from '@viamrobotics/sdk';

// From JSON (recommended for doCommand)
const cmd = Struct.fromJson({ myCommand: { key: 'value' } });
const result = await component.doCommand(cmd);

// Plain object also accepted by doCommand (auto-converted)
const result = await component.doCommand({ myCommand: { key: 'value' } });
```

---

## 8. Node.js Support

### Requirements
- Node.js >= 20
- Additional packages: `@connectrpc/connect-node`, `node-datachannel`

### Setup (Required Polyfills)

```typescript
// Must be at the top of your entry point
const wrtc = require('node-datachannel/polyfill');
for (const key in wrtc) {
  (global as any)[key] = (wrtc as any)[key];
}

const connectNode = require('@connectrpc/connect-node');
globalThis.VIAM = {
  GRPC_TRANSPORT_FACTORY: (opts: any) =>
    connectNode.createGrpcTransport({ httpVersion: '2', ...opts }),
};
```

### Known Limitations

- **No MediaStream API**: Camera streaming via `StreamClient.getStream()` does
  NOT work in Node.js because there is no browser `MediaStream` API. Use
  `camera.getImages()` or `camera.getPointCloud()` instead for frame capture.
- **Polyfill instability**: The `node-datachannel` polyfill may have
  compatibility issues with certain WebRTC features.
- **No DOM**: Obviously no DOM APIs -- cannot render to `<video>` or `<canvas>`.
- **CJS/ESM**: The SDK exports both ESM and UMD. Node.js examples use `require()`.

### Node.js Connection Pattern

```typescript
const VIAM = require('@viamrobotics/sdk');
// ... polyfills above ...

const client = await VIAM.createRobotClient({
  host: process.env.HOST,
  credentials: {
    type: 'api-key',
    authEntity: process.env.API_KEY_ID,
    payload: process.env.API_KEY_SECRET,
  },
  signalingAddress: 'https://app.viam.com:443',
  iceServers: [{ urls: 'stun:global.stun.twilio.com:3478' }],
});
```

---

## 9. Connection Lifecycle

### Connect
1. `createRobotClient(conf)` creates a new `RobotClient` and calls `dial(conf)`
2. `dial()` validates config, then calls `performDial()`
3. If `DialWebRTCConf`: attempts WebRTC first, falls back to direct gRPC on failure
4. If `DialDirectConf`: attempts direct gRPC only (host must contain "local")
5. On success: creates `RobotService` client, emits `CONNECTED`
6. Returns connected `RobotClient`

### Reconnect (automatic, WebRTC)
1. WebRTC `iceConnectionState` changes to `'closed'` or data channel closes
2. `onDisconnect()` fires, emits `RECONNECTING`
3. Exponential backoff retries `connect()` up to `reconnectMaxAttempts`
4. On success: emits `CONNECTED`, StreamClient re-adds all streams
5. On failure: emits `RECONNECTION_FAILED` with error and attempt count

### Disconnect
1. Call `machine.disconnect()`
2. Emits `DISCONNECTING`
3. Aborts any in-progress dial
4. Closes RTCPeerConnection and DataChannel
5. Resets session manager
6. Sets `closed = true`
7. Emits `DISCONNECTED`

### Error Handling

Non-retryable gRPC error codes (will NOT trigger reconnection):
- `Canceled`, `InvalidArgument`, `NotFound`, `AlreadyExists`
- `PermissionDenied`, `FailedPrecondition`, `OutOfRange`
- `Unimplemented`, `Unauthenticated`

Error messages containing "invalid", "configuration", or "cannot dial" are also non-retryable.

---

## 10. Viam Applications Model

Viam Applications are web apps hosted on `https://app.viam.com` that connect to
machines. They use the same SDK but with a specific deployment and auth pattern.

### Architecture

```
app.viam.com   (hosts the static web app)
     |
     v
Browser loads app HTML/JS/CSS
     |
     v
JS calls createRobotClient() with credentials from cookie/URL
     |
     v
WebRTC connection to machine via signaling at app.viam.com:443
```

### Credential Flow (from cube-sorter-webapp)

Viam Applications receive credentials via URL parameters and cookies:

```typescript
// Extract machine key from URL path
const machineKey = window.location.pathname.split('/')[2];

// Read credentials from cookie (set by app.viam.com)
const { apiKey, machineId, hostname } = JSON.parse(Cookie.get(machineKey));

const machine = await createRobotClient({
  host: hostname,
  credentials: {
    type: 'api-key',
    payload: apiKey.key,
    authEntity: apiKey.id,
  },
  signalingAddress: 'https://app.viam.com:443',
});
```

### Development Setup

For local development, use Vite with environment variables:

```typescript
// vite.config.ts -- standard Vite config
// .env file:
// VITE_HOST=my-robot.abc.viam.cloud
// VITE_API_KEY_ID=...
// VITE_API_KEY=...

const HOST = import.meta.env.VITE_HOST;
```

### App vs ViamClient

| Use Case | API |
|----------|-----|
| Connect to a specific machine | `createRobotClient()` |
| Access Viam cloud APIs (data, fleet) | `createViamClient()` |
| Build a Viam Application | `createRobotClient()` with cookie-based creds |

---

## 11. Global Configuration

The SDK reads global configuration from `globalThis.VIAM`:

```typescript
// Enable gRPC trace logging
globalThis.VIAM = {
  GRPC_TRACE_LOGGING: true,
};

// Override transport factory (required for Node.js)
globalThis.VIAM = {
  GRPC_TRANSPORT_FACTORY: (opts) =>
    connectNode.createGrpcTransport({ httpVersion: '2', ...opts }),
};
```
