"""DRK demo orchestrator — command-driven: pick-up -> tracking -> dance.

Flow:
  pick-up   pick the object up from its taught spot
  tracking  keep the primary person centered in the wrist cam (Enter to stop)
  dance     put the object down, then run the celebration dance
  home      return the arm to the safe READY pose
  quit      home and exit

Everything runs through ONE StableRobot connection (only one process may drive
the arm at a time), reusing the project's existing code:
  - StableRobot (drk_robot.py)  — resilient connection + retry
  - PersonTracker (cameraman.py) — sticky single-person lock
  - safe_move/clear_fault/clap/ROUTINE (dance.py) — self-healing motion + dance

Creds: VIAM_ADDRESS/VIAM_API_KEY/VIAM_API_KEY_ID (.env or environment).
Run:   .venv/bin/python demo.py
Teach: .venv/bin/python demo.py --teach   (capture pick/place joint poses)
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from drk_robot import StableRobot
from dance import safe_move, clear_fault, clap, READY, ROUTINE
from cameraman import PersonTracker, load_tuning
from robot import ARM, GRIPPER, CAMERA, VISION_YOLO
from viam.components.arm import Arm
from viam.components.camera import Camera
from viam.services.vision import VisionClient
from viam.proto.component.arm import JointPositions

# --- Taught poses (6 joint angles, deg). CALIBRATE with `--teach`. -----------
# Defaults are SAFE ELEVATED placeholders: an uncalibrated run moves gently and
# never descends toward the table (so it won't crash), but also won't truly
# grasp until you replace these with real taught poses and set CALIBRATED=True.
PICK_APPROACH  = [0.0, -40.0, -55.0, 0.0,  95.0, 0.0]   # above the object, gripper open
PICK_GRASP     = [0.0, -33.0, -62.0, 0.0,  97.0, 0.0]   # at the object, ready to close
PLACE_APPROACH = [30.0, -40.0, -55.0, 0.0, 95.0, 0.0]   # above the drop zone
PLACE_DROP     = [30.0, -33.0, -62.0, 0.0, 97.0, 0.0]   # at the drop zone
CALIBRATED = False
DANCE_SECONDS = float(os.environ.get("DEMO_DANCE_SECONDS", "40"))

state = {"holding": False}


def jl(vals):
    return JointPositions(values=[float(v) for v in vals])


async def preflight(robot, arm):
    await clear_fault(robot, arm)
    js = []
    import asyncio as _a
    for _ in range(3):
        j = await robot.call(lambda: arm.get_joint_positions(), label="preflight")
        js.append([round(v, 2) for v in j.values])
        await _a.sleep(0.5)
    driven = any(s != js[0] for s in js)
    print(f"preflight: {js[0]}  externally driven: {driven}")
    return not driven


# --- Phase: PICK-UP ----------------------------------------------------------
async def pick_up(robot, arm, grip):
    if not CALIBRATED:
        print("  [pick-up] NOTE: poses not calibrated — running the motion safely "
              "(elevated), grasp may not seat. Run --teach to calibrate.")
    print("  [pick-up] approach")
    await safe_move(robot, arm, PICK_APPROACH)
    await robot.call(lambda: grip.open(), label="grip-open")
    print("  [pick-up] descend to grasp")
    await safe_move(robot, arm, PICK_GRASP)
    print("  [pick-up] close")
    await robot.call(lambda: grip.grab(), label="grip-grab")
    try:
        holding = await robot.call(lambda: grip.is_holding_something(), label="hold?")
        print(f"  [pick-up] holding_something: {getattr(holding, 'is_holding_something', holding)}")
    except Exception:
        pass
    print("  [pick-up] lift")
    await safe_move(robot, arm, PICK_APPROACH)
    state["holding"] = True
    print("  [pick-up] done (holding).")


# --- Phase: PLACE (used by dance) -------------------------------------------
async def place_down(robot, arm, grip):
    print("  [place] approach drop zone")
    await safe_move(robot, arm, PLACE_APPROACH)
    print("  [place] descend + release")
    await safe_move(robot, arm, PLACE_DROP)
    await robot.call(lambda: grip.open(), label="grip-open")
    print("  [place] retract")
    await safe_move(robot, arm, PLACE_APPROACH)
    state["holding"] = False
    print("  [place] done (empty).")


# --- Phase: TRACKING ---------------------------------------------------------
async def track(robot, arm, cam, vision, stop: asyncio.Event):
    # Pan-only follow using the project's live-tuned config (tracker_tuning.json).
    # For the full two-axis / tilt behavior, run cameraman.py directly.
    cfg = load_tuning()
    props = await robot.call(lambda: cam.get_properties(), label="cam-props")
    ip = props.intrinsic_parameters
    width = ip.width_px or 1280
    height = ip.height_px or 720
    half = width / 2.0
    tracker = PersonTracker(width, height)
    period = 1.0 / cfg["loop_hz"]
    kp, pan_sign = cfg["kp_deg"], cfg["pan_sign"]
    max_step, j1_limit = cfg["max_step_deg"], cfg["j1_limit_deg"]
    deadband = cfg["deadband_enter"]
    print(f"  [track] {width}x{height} frame, deadband ±{deadband * half:.0f}px "
          f"(Enter to stop)")
    while not stop.is_set():
        t0 = asyncio.get_event_loop().time()
        dets = await robot.call(
            lambda: vision.get_detections_from_camera(CAMERA), label="yolo")
        res = tracker.update(dets, cfg)
        if res is not None:
            cx, _aim_y = res
            offset = (cx - half) / half
            if abs(offset) > deadband:
                step = max(-max_step, min(max_step, pan_sign * kp * offset))
                j = list((await robot.call(
                    lambda: arm.get_joint_positions(), label="joints")).values)
                j[0] = max(-j1_limit, min(j1_limit, j[0] + step))
                await safe_move(robot, arm, j)
                print(f"  [track] offset {offset:+.2f} -> pan {step:+.1f}° (J1 {j[0]:+.1f}°)")
            else:
                print(f"  [track] offset {offset:+.2f} (centered)")
        else:
            print("  [track] no lock")
        elapsed = asyncio.get_event_loop().time() - t0
        await asyncio.sleep(max(0.0, period - elapsed))
    print("  [track] stopped.")


# --- Phase: DANCE (place first if holding) ----------------------------------
async def dance(robot, arm, grip):
    if state["holding"]:
        await place_down(robot, arm, grip)
    import time
    print(f"  [dance] celebrating for {DANCE_SECONDS:.0f}s")
    t0 = time.time()
    while time.time() - t0 < DANCE_SECONDS:
        for label, joints, claps in ROUTINE:
            if time.time() - t0 >= DANCE_SECONDS:
                break
            try:
                await safe_move(robot, arm, joints)
                if claps:
                    await clap(robot, grip, claps)
            except Exception as e:
                print(f"  [dance] pose error swallowed ({type(e).__name__})")
                await clear_fault(robot, arm)
    print("  [dance] done.")


# --- Teach mode --------------------------------------------------------------
async def teach(robot, arm):
    print("TEACH: jog the arm by hand / the Viam app; joints print each second.\n"
          "Copy the values into PICK_APPROACH / PICK_GRASP / PLACE_APPROACH / "
          "PLACE_DROP, then set CALIBRATED=True.  Ctrl-C to exit.\n")
    import asyncio as _a
    while True:
        j = await robot.call(lambda: arm.get_joint_positions(), label="teach")
        print("  joints:", [round(v, 2) for v in j.values])
        await _a.sleep(1.0)


# --- Orchestrator ------------------------------------------------------------
CMDS = {
    "pick-up": "pick", "pickup": "pick", "pick": "pick",
    "tracking": "track", "track": "track",
    "dance": "dance",
    "home": "home", "quit": "quit", "q": "quit", "exit": "quit",
}


async def main():
    loop = asyncio.get_event_loop()
    async with StableRobot.from_env() as robot:
        arm = await robot.arm(ARM)
        grip = await robot.gripper(GRIPPER)
        cam = Camera.from_robot(robot.machine, CAMERA)
        vision = VisionClient.from_robot(robot.machine, VISION_YOLO)

        if "--teach" in sys.argv:
            await teach(robot, arm)
            return

        if not await preflight(robot, arm):
            print("ABORT: someone else is driving the arm.")
            return

        print("\nDRK demo ready. Commands: pick-up | tracking | dance | home | quit")
        try:
            while True:
                raw = (await loop.run_in_executor(
                    None, input, "\n> ")).strip().lower()
                cmd = CMDS.get(raw)
                if cmd is None:
                    print(f"  ? unknown '{raw}' — try: pick-up | tracking | dance | home | quit")
                    continue
                if cmd == "quit":
                    break
                if cmd == "pick":
                    await pick_up(robot, arm, grip)
                elif cmd == "track":
                    stop = asyncio.Event()
                    task = asyncio.create_task(track(robot, arm, cam, vision, stop))
                    await loop.run_in_executor(None, input, "")  # Enter stops it
                    stop.set()
                    await task
                elif cmd == "dance":
                    await dance(robot, arm, grip)
                elif cmd == "home":
                    await safe_move(robot, arm, READY)
                    await robot.call(lambda: grip.open(), label="grip-open")
                    print("  home done.")
        finally:
            print("\n--- returning HOME ---")
            await clear_fault(robot, arm)
            await safe_move(robot, arm, READY)
            try:
                await robot.call(lambda: grip.open(), label="grip-open")
            except Exception:
                pass
            print("home done.")


if __name__ == "__main__":
    asyncio.run(main())
