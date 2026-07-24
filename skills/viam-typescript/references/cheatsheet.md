# Viam TypeScript SDK Cheatsheet

Quick reference for common patterns. See `ts-sdk-reference.md` for full API details.

---

## Installation

```bash
# Browser (Vite, webpack, etc.)
npm install @viamrobotics/sdk

# Node.js
npm install @viamrobotics/sdk @connectrpc/connect-node node-datachannel
```

---

## Import Paths

```typescript
// Everything from one import
import * as VIAM from '@viamrobotics/sdk';

// Or pick what you need
import {
  createRobotClient,
  RobotClient,
  MachineConnectionEvent,
  // Components
  ArmClient,
  BaseClient,
  BoardClient,
  CameraClient,
  EncoderClient,
  GantryClient,
  GripperClient,
  MotorClient,
  MovementSensorClient,
  PowerSensorClient,
  SensorClient,
  ServoClient,
  GenericComponentClient,
  // Services
  VisionClient,
  MotionClient,
  NavigationClient,
  SlamClient,
  MLModelClient,
  DataManagerClient,
  GenericServiceClient,
  // Streaming
  StreamClient,
  // App/Cloud
  createViamClient,
  // Types
  Pose,
  PoseInFrame,
  Vector3,
  Struct,
  WorldState,
  Transform,
  GeoPoint,
  // Utilities
  doCommandFromClient,
  // Errors
  ConnectError,
  Code,
  ConnectionClosedError,
} from '@viamrobotics/sdk';
```

---

## Connection Boilerplate

### Browser (WebRTC -- most common)

```typescript
import * as VIAM from '@viamrobotics/sdk';

async function main() {
  const machine = await VIAM.createRobotClient({
    host: 'my-robot-main.abc123.viam.cloud',
    credentials: {
      type: 'api-key',
      authEntity: 'YOUR_API_KEY_ID',
      payload: 'YOUR_API_KEY',
    },
    signalingAddress: 'https://app.viam.com:443',
  });

  // List resources
  const resources = await machine.resourceNames();
  console.log('Resources:', resources);

  // Use components
  const sensor = new VIAM.SensorClient(machine, 'my_sensor');
  const readings = await sensor.getReadings();
  console.log('Readings:', readings);

  // Disconnect when done
  await machine.disconnect();
}

main().catch(console.error);
```

### Browser with Connection State Tracking

```typescript
import * as VIAM from '@viamrobotics/sdk';

const statusEl = document.getElementById('status')!;

function updateStatus(event: unknown) {
  const { eventType } = event as { eventType: VIAM.MachineConnectionEvent };
  switch (eventType) {
    case VIAM.MachineConnectionEvent.CONNECTING:
      statusEl.textContent = 'Connecting...';
      break;
    case VIAM.MachineConnectionEvent.CONNECTED:
      statusEl.textContent = 'Connected';
      break;
    case VIAM.MachineConnectionEvent.DISCONNECTED:
      statusEl.textContent = 'Disconnected';
      break;
    case VIAM.MachineConnectionEvent.RECONNECTING:
      statusEl.textContent = 'Reconnecting...';
      break;
    case VIAM.MachineConnectionEvent.RECONNECTION_FAILED:
      statusEl.textContent = 'Reconnection failed';
      break;
  }
}

const machine = await VIAM.createRobotClient({
  host: HOST,
  credentials: { type: 'api-key', authEntity: API_KEY_ID, payload: API_KEY },
  signalingAddress: 'https://app.viam.com:443',
  reconnectMaxAttempts: 10,
});
machine.on('connectionstatechange', updateStatus);
```

### Node.js

```typescript
const VIAM = require('@viamrobotics/sdk');
const wrtc = require('node-datachannel/polyfill');
const connectNode = require('@connectrpc/connect-node');

// Required polyfills (MUST be before any SDK calls)
globalThis.VIAM = {
  GRPC_TRANSPORT_FACTORY: (opts: any) =>
    connectNode.createGrpcTransport({ httpVersion: '2', ...opts }),
};
for (const key in wrtc) {
  (global as any)[key] = (wrtc as any)[key];
}

async function main() {
  const client = await VIAM.createRobotClient({
    host: process.env.HOST!,
    credentials: {
      type: 'api-key',
      authEntity: process.env.API_KEY_ID!,
      payload: process.env.API_KEY!,
    },
    signalingAddress: 'https://app.viam.com:443',
    iceServers: [{ urls: 'stun:global.stun.twilio.com:3478' }],
  });

  console.log(await client.resourceNames());
}

main().catch(console.error);
```

### Viam Application (cookie-based auth)

```typescript
import * as VIAM from '@viamrobotics/sdk';
import Cookie from 'js-cookie';

// Credentials come from URL + cookie set by app.viam.com
const machineKey = window.location.pathname.split('/')[2];
const { apiKey, hostname } = JSON.parse(Cookie.get(machineKey)!);

const machine = await VIAM.createRobotClient({
  host: hostname,
  credentials: {
    type: 'api-key',
    payload: apiKey.key,
    authEntity: apiKey.id,
  },
  signalingAddress: 'https://app.viam.com:443',
});
```

---

## Component/Service Method Signatures

### Quick Reference Table

| Component | Key Methods |
|-----------|-------------|
| `ArmClient` | `getEndPosition()`, `moveToPosition(pose)`, `moveToJointPositions(joints[])`, `getJointPositions()`, `stop()`, `isMoving()` |
| `BaseClient` | `moveStraight(mm, mm/s)`, `spin(deg, deg/s)`, `setPower(lin, ang)`, `setVelocity(lin, ang)`, `stop()`, `isMoving()` |
| `BoardClient` | `getGPIO(pin)`, `setGPIO(pin, high)`, `getPWM(pin)`, `setPWM(pin, pct)`, `readAnalogReader(name)`, `writeAnalog(pin, val)`, `streamTicks(pins, queue)` |
| `CameraClient` | `getImages()`, `getPointCloud()`, `getProperties()` |
| `EncoderClient` | `getPosition(type?)`, `resetPosition()`, `getProperties()` |
| `GripperClient` | `open()`, `grab()`, `stop()`, `isMoving()`, `isHoldingSomething()` |
| `MotorClient` | `setPower(pwr)`, `goFor(rpm, revs)`, `goTo(rpm, pos)`, `setRPM(rpm)`, `stop()`, `getPosition()`, `isPowered()` |
| `MovementSensorClient` | `getLinearVelocity()`, `getAngularVelocity()`, `getCompassHeading()`, `getOrientation()`, `getPosition()`, `getReadings()` |
| `SensorClient` | `getReadings()` |
| `ServoClient` | `move(angleDeg)`, `getPosition()`, `stop()`, `isMoving()` |

| Service | Key Methods |
|---------|-------------|
| `VisionClient` | `getDetectionsFromCamera(cam)`, `getClassificationsFromCamera(cam, count)`, `captureAllFromCamera(cam, opts)`, `getObjectPointClouds(cam)` |
| `MotionClient` | `move(dest, component, ws?, constraints?)`, `moveOnMap(dest, comp, slam)`, `moveOnGlobe(dest, comp, ms)`, `stopPlan(comp)`, `getPlan(comp)` |
| `NavigationClient` | `getMode()`, `setMode(mode)`, `getLocation()`, `getWayPoints()`, `addWayPoint(geo)`, `removeWayPoint(id)` |
| `SlamClient` | `getPosition()`, `getPointCloudMap()`, `getProperties()` |
| `MLModelClient` | `infer(tensors)`, `metadata()` |
| `StreamClient` | `getStream(name)`, `add(name)`, `remove(name)`, `getOptions(name)`, `setOptions(name, w, h)` |

---

## Camera Streaming in Browser

### Method 1: WebRTC MediaStream (live video, lowest latency)

```typescript
import { createRobotClient, StreamClient } from '@viamrobotics/sdk';

const machine = await createRobotClient({ /* ... */ });
const streamClient = new StreamClient(machine);

// Get MediaStream and display in <video>
const mediaStream = await streamClient.getStream('my_camera');
const videoEl = document.querySelector<HTMLVideoElement>('#camera-feed')!;
videoEl.srcObject = mediaStream;
videoEl.autoplay = true;
videoEl.muted = true;

// Cleanup
await streamClient.remove('my_camera');
```

### Method 2: React Component (WebRTC)

```tsx
import { useEffect, useRef, useState } from 'react';
import { StreamClient, type RobotClient } from '@viamrobotics/sdk';

function CameraView({ machine, cameraName }: { machine: RobotClient; cameraName: string }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [stream, setStream] = useState<MediaStream>();

  useEffect(() => {
    const streamClient = new StreamClient(machine);
    streamClient.getStream(cameraName)
      .then(setStream)
      .catch(console.error);
    return () => { streamClient.remove(cameraName).catch(console.error); };
  }, [machine, cameraName]);

  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream;
    }
  }, [stream]);

  return <video ref={videoRef} autoPlay muted />;
}
```

### Method 3: Image Polling (works with detections overlay)

```typescript
import { CameraClient, VisionClient } from '@viamrobotics/sdk';

const camera = new CameraClient(machine, 'my_camera');
const vision = new VisionClient(machine, 'my_vision');
const canvas = document.querySelector<HTMLCanvasElement>('#canvas')!;
const ctx = canvas.getContext('2d')!;

async function pollFrame() {
  const result = await vision.captureAllFromCamera('my_camera', {
    returnImage: true,
    returnDetections: true,
  });

  if (result.image) {
    const base64 = btoa(
      Array.from(result.image.image)
        .map(byte => String.fromCharCode(byte))
        .join('')
    );
    const img = new Image();
    img.onload = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

      // Draw detections
      result.detections.forEach(det => {
        const x = Number(det.xMinNormalized) * canvas.width;
        const y = Number(det.yMinNormalized) * canvas.height;
        const w = (Number(det.xMaxNormalized) - Number(det.xMinNormalized)) * canvas.width;
        const h = (Number(det.yMaxNormalized) - Number(det.yMinNormalized)) * canvas.height;
        ctx.strokeStyle = '#00ef83';
        ctx.lineWidth = 2;
        ctx.strokeRect(x, y, w, h);
        ctx.fillStyle = '#00ef83';
        ctx.fillText(`${det.className} ${(det.confidence * 100).toFixed(1)}%`, x, y - 4);
      });
    };
    img.src = `data:image/jpeg;base64,${base64}`;
  }
}

// Poll loop
setInterval(pollFrame, 500);
```

---

## doCommand Patterns

```typescript
// Using plain object (recommended)
const result = await component.doCommand({ myCommand: { key: 'value' } });

// Using Struct.fromJson
import { Struct } from '@viamrobotics/sdk';
const cmd = Struct.fromJson({ command: 'start' });
const result = await service.doCommand(cmd);

// Async generator polling pattern (from cube-sorter-webapp)
async function* pollStatus(service: GenericServiceClient, intervalMs: number) {
  while (true) {
    const response = await service.doCommand(
      Struct.fromJson({ command: 'get_status' })
    );
    yield response;
    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }
}

for await (const status of pollStatus(sorter, 1000)) {
  updateUI(status);
}
```

---

## Viam Application Config Template

### package.json

```json
{
  "name": "my-viam-app",
  "type": "module",
  "scripts": {
    "dev": "vite"
  },
  "dependencies": {
    "@viamrobotics/sdk": "^0.68.0",
    "js-cookie": "^3.0.5"
  },
  "devDependencies": {
    "typescript": "^5.2.2",
    "vite": "^5.2.0"
  }
}
```

### index.html

```html
<!doctype html>
<html>
<head>
  <title>My Viam App</title>
</head>
<body>
  <div id="app">
    <p>Status: <span id="status">Connecting...</span></p>
    <video id="camera-feed" autoplay muted></video>
    <div id="controls"></div>
  </div>
  <script type="module" src="src/main.ts"></script>
</body>
</html>
```

### src/main.ts (minimal)

```typescript
import * as VIAM from '@viamrobotics/sdk';

async function main() {
  const machine = await VIAM.createRobotClient({
    host: import.meta.env.VITE_HOST,
    credentials: {
      type: 'api-key',
      authEntity: import.meta.env.VITE_API_KEY_ID,
      payload: import.meta.env.VITE_API_KEY,
    },
    signalingAddress: 'https://app.viam.com:443',
  });

  document.getElementById('status')!.textContent = 'Connected';
  machine.on('connectionstatechange', (event: unknown) => {
    const { eventType } = event as { eventType: VIAM.MachineConnectionEvent };
    document.getElementById('status')!.textContent = eventType;
  });

  // Camera stream
  const stream = new VIAM.StreamClient(machine);
  const mediaStream = await stream.getStream('my_camera');
  (document.getElementById('camera-feed') as HTMLVideoElement).srcObject = mediaStream;

  // Sensor readings
  const sensor = new VIAM.SensorClient(machine, 'my_sensor');
  setInterval(async () => {
    const readings = await sensor.getReadings();
    console.log(readings);
  }, 1000);
}

main().catch(console.error);
```

### .env (for local development)

```
VITE_HOST=my-robot-main.abc123.viam.cloud
VITE_API_KEY_ID=your-api-key-id
VITE_API_KEY=your-api-key-secret
```

---

## Common Gotchas and Fixes

### 1. "not connected yet" Error

**Cause:** Calling component methods before `createRobotClient` resolves.
**Fix:** Always `await` the connection before using clients.
```typescript
// WRONG
const machine = VIAM.createRobotClient({...}); // missing await!
const sensor = new VIAM.SensorClient(machine, 'sensor'); // machine is a Promise

// RIGHT
const machine = await VIAM.createRobotClient({...});
const sensor = new VIAM.SensorClient(machine, 'sensor');
```

### 2. "cannot dial directly" Error

**Cause:** Using `DialDirectConf` (no `signalingAddress`) with a cloud hostname.
**Fix:** Direct connections require a host URL containing "local".
```typescript
// Cloud connections MUST use signalingAddress
const machine = await VIAM.createRobotClient({
  host: 'my-robot.abc.viam.cloud',
  signalingAddress: 'https://app.viam.com:443', // Required!
  credentials: { ... },
});
```

### 3. Camera getImages() Returns Empty

**Cause:** Camera not yet streaming or wrong source name.
**Fix:** Check `camera.getProperties()` first. Use `filterSourceNames` if the
camera has multiple sources.

### 4. StreamClient.getStream() Times Out (5 seconds)

**Cause:** WebRTC track not received. Can happen if:
  - Connection is direct gRPC (no WebRTC = no media tracks)
  - Camera name is wrong
  - Network blocks WebRTC
**Fix:** Ensure WebRTC connection (use `signalingAddress`). Verify camera name
matches configuration. Check browser console for WebRTC errors.

### 5. Detection Coordinates Are Normalized (0-1)

**Cause:** Vision service returns normalized bounding box coordinates.
**Fix:** Multiply by image dimensions:
```typescript
const x = det.xMinNormalized * imageWidth;
const y = det.yMinNormalized * imageHeight;
```

### 6. Node.js: "globalThis.VIAM is not defined" or Transport Errors

**Cause:** Missing polyfills.
**Fix:** Must set `globalThis.VIAM.GRPC_TRANSPORT_FACTORY` and register
`node-datachannel` polyfills BEFORE any SDK calls.

### 7. Reconnection Not Working

**Cause:** `noReconnect: true` or `reconnectAbortSignal.abort` set to `true`.
**Fix:** Remove `noReconnect` flag. To cancel and restart, reset the abort signal.

### 8. stopAll() Doesn't Cancel doCommand

**Cause:** `stopAll()` stops actuators and cancels motion, but ongoing
`doCommand` calls to custom services may not be interrupted.
**Fix:** Use `AbortController` for cancellation of doCommand calls:
```typescript
const controller = new AbortController();
const result = await service.doCommand(cmd, { signal: controller.signal });
// To cancel:
controller.abort();
```

### 9. Struct.fromJson() Required for Nested Objects in doCommand

**Cause:** Plain objects with nested structures may not serialize correctly in
all contexts.
**Fix:** Use `Struct.fromJson()` for complex command payloads:
```typescript
const cmd = VIAM.Struct.fromJson({ command: 'start', params: { speed: 10 } });
```

### 10. WebRTC TURN/STUN Issues Behind Corporate Firewalls

**Cause:** Firewall blocks UDP (STUN) or restricts TURN relay.
**Fix:** Try `forceRelay: true` to use TURN only. Or specify a specific TURN server:
```typescript
const machine = await createRobotClient({
  ...config,
  forceRelay: true,
  // or specify explicit ICE servers
  iceServers: [{ urls: 'turn:turn.viam.com:443', username: '...', credential: '...' }],
});
```

---

## Unit Conventions

| Measurement | TypeScript SDK Unit |
|-------------|-------------------|
| Linear distance | millimeters (mm) |
| Linear speed | mm/sec |
| Angles (base.spin, servo.move) | degrees |
| Arm joint positions | degrees (0-360) |
| Angular speed (base) | degrees/sec |
| Motor speed | RPM |
| Motor position | revolutions |
| Power | -1.0 to 1.0 (fraction) |
| PWM duty cycle | 0.0 to 1.0 (fraction) |
| GPS coordinates | latitude/longitude (decimal degrees) |
| Pose position (x, y, z) | millimeters |
| Pose orientation (oX, oY, oZ, theta) | orientation vector + degrees |
| Timestamps | `@bufbuild/protobuf` Timestamp |
| Durations | `@bufbuild/protobuf` Duration |
