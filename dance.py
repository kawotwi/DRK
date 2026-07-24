"""robot20 celebration dance — continuous, self-healing, smooth.

Pairs with "Celebration" (Kool & The Gang). Joint-space only, elevated over the
base, never reaches table level. Runs on StableRobot (heals dropped WebRTC
streams) AND heals xArm servo faults (clear_error + retry) so a mid-routine
motor trip no longer stops the dance. Loops continuously until time budget /
Ctrl-C, then a finally-block ALWAYS returns the arm home.

Creds: VIAM_ADDRESS, VIAM_API_KEY, VIAM_API_KEY_ID (from .env or environment,
       same as robot.py).
Opt:   DANCE_SECONDS (default 180) — total run time before it homes and stops.

Run:  .venv/bin/python dance.py
Stop: Ctrl-C — the finally-block still returns the arm home.
"""
import asyncio, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from drk_robot import StableRobot
from viam.proto.component.arm import JointPositions


def jp(vals):
    return JointPositions(values=[float(v) for v in vals])


READY = [0.0, -40.0, -55.0, 0.0, 95.0, 0.0]

# Flowing pose loop (no dead stops). Ordered so each pose transitions naturally
# into the next -> smooth, continuous motion. `clap` = gripper accents at that pose.
#   (label, joints, claps)
ROUTINE = [
    ("sway right",  [ 30, -42, -55,   0,  95,  40], 0),
    ("wave right",  [ 45, -38, -58,   0,  95,   0], 2),
    ("sway right",  [ 30, -42, -55,   0,  95,  40], 0),
    ("center",      READY,                          0),
    ("bob up",      [  0, -50, -48,   0,  92,   0], 0),
    ("bob down",    [  0, -30, -66,   0,  98,   0], 2),
    ("bob up",      [  0, -50, -48,   0,  92,   0], 0),
    ("center",      READY,                          0),
    ("sway left",   [-30, -42, -55,   0,  95, -40], 0),
    ("wave left",   [-45, -38, -58,   0,  95,   0], 2),
    ("sway left",   [-30, -42, -55,   0,  95, -40], 0),
    ("center",      READY,                          0),
    ("twirl a",     [ 22, -42, -55,  40,  95,  80], 0),
    ("twirl b",     [-22, -42, -55, -40,  95, -80], 0),
    ("flourish",    [  0, -52, -46,   0, 112,  55], 3),
]


async def clear_fault(robot, arm):
    try:
        await robot.call(lambda: arm.do_command({"clear_error": True}), label="clear_error")
    except Exception:
        pass


async def safe_move(robot, arm, joints, retries=3):
    """Move with full resilience: clear_error + retry on ANY failure, and NEVER
    raise — a failed pose is logged and skipped so the continuous loop never dies."""
    for attempt in range(1, retries + 1):
        try:
            await robot.call(lambda: arm.move_to_joint_positions(jp(joints)),
                             label="move", retries=2)
            return True
        except Exception as e:
            print(f"     move failed ({type(e).__name__}: {str(e)[:70]}) "
                  f"-> clear + retry {attempt}/{retries}")
            await clear_fault(robot, arm)
            await asyncio.sleep(0.4)
    print("     pose skipped after retries (loop continues)")
    return False


async def clap(robot, grip, n):
    for _ in range(n):
        try:
            await robot.call(lambda: grip.grab(), label="clap")
            await robot.call(lambda: grip.open(), label="clap")
        except Exception:
            break


async def preflight(robot, arm):
    js = []
    for _ in range(3):
        j = await robot.call(lambda: arm.get_joint_positions(), label="preflight")
        js.append([round(v, 2) for v in j.values])
        await asyncio.sleep(0.6)
    driven = any(s != js[0] for s in js)
    print(f"preflight: {js[0]}  externally driven: {driven}")
    return js[0], (not driven)


async def main():
    budget = float(os.environ.get("DANCE_SECONDS", "180"))
    async with StableRobot.from_env() as robot:
        arm = await robot.arm("arm-1")
        grip = await robot.gripper("gripper-1")

        await clear_fault(robot, arm)                 # start clean
        start, clear = await preflight(robot, arm)
        if not clear:
            print("ABORT: someone else is driving the arm.")
            return

        t0 = time.time()
        cycle = 0
        try:
            print(f"\n--- CONTINUOUS DANCE ({budget:.0f}s) ---")
            while time.time() - t0 < budget:
                cycle += 1
                print(f"\n=== cycle {cycle} (t+{time.time()-t0:.0f}s) ===")
                for label, joints, claps in ROUTINE:
                    if time.time() - t0 >= budget:
                        break
                    print(f"  {label}" + (f"  +{claps}claps" if claps else ""))
                    try:
                        await safe_move(robot, arm, joints)
                        if claps:
                            await clap(robot, grip, claps)
                    except Exception as e:
                        # last-resort guard: nothing a single pose does can stop the loop
                        print(f"     !! pose error swallowed ({type(e).__name__}: {str(e)[:60]})")
                        await clear_fault(robot, arm)
            print(f"\ntime budget reached after {cycle} cycles.")
        finally:
            print("\n--- returning HOME (guaranteed) ---")
            await clear_fault(robot, arm)
            await safe_move(robot, arm, start)
            try:
                await robot.call(lambda: grip.open(), label="home-open")
            except Exception:
                pass
            print("home done.")


if __name__ == "__main__":
    asyncio.run(main())
