# DRK
Viam hello robot hackathon!
Replanned from right now. Two structural changes: the clock (3.5 hours left, so one integration thread instead of parallel epics) and the YOLO backbone (which changes what perception can and can't give you).

**YOLO reality check, 60 seconds.** YOLO's COCO vocabulary is superb at `person` — that's your MVP1 tracking signal, use it with confidence ~0.5+ and 2–3-frame debounce. But it does **not** know "small color-coded squares" or your drawer box. Don't burn the afternoon trying to make YOLO see the pieces. Two options: run Viam's `color_detector` *alongside* YOLO for the pieces (5-minute config, rock solid under fixed lighting), or swap your pieces for COCO-known objects (cup, scissors, sports ball, cell phone) and let YOLO do everything. If your pieces are already color-coded squares: color detector. Decide in the first 10 minutes, not at 2:30. Also: keep YOLO polling in its own 2–3 Hz loop writing to the world dict — never an inference call inside a motion sequence.

**1:00–1:15 — Triage stand-up (all three).** Mark each item done/broken/not-started: arm moves from code · gripper cycles · YOLO person detection returns boxes · tracking nudge works · pick/place one piece · Claude command parsing · any gestures. Everything below assumes the morning got you through plumbing and partial MVP1; if tracking isn't working yet, it becomes the whole 1:15 sprint and drawers die now (see de-scope).

**1:15–2:15 — Sprint: lock MVP1 + MVP2.**
- A: pick/place 3-for-3 on all three pieces from taped slots to taped zones. Nothing else.
- B: MVP1 acceptance — person centered for 30s on projector, smooth. Tune YOLO confidence + deadband under *venue* lighting now. Then stand up the color detector for pieces and verify in the transform-camera view.
- C: command → Claude → task pipeline wrapping A's pick/place, with the three core gestures attached (ack-nod before, success-nod/droop after, `think` during API latency). Typed input; add mic only if this finishes early.
- **2:15 gate:** voice/typed "move red to zone 2" works gesture-wrapped, 3-for-3. This is your guaranteed demo. Do not pass this gate on hope.

**2:15–3:15 — Sprint: one drawer beat + scene scan.**
- Scope cut from the original MVP3: **one drawer, not three; starting open if the pull isn't working within 30 minutes.** A captures the drawer sequence (taped-down box, wire-loop handle, teleoperated demonstration replay — keep the "taught by demonstration" line only if it actually works by 3:00).
- B: the "analyze scene" beat — during C's scan gesture, log every color-detected piece + YOLO detections into the world dict; C makes the robot narrate or act on it ("red is already placed, fetching blue").
- C: choreograph the full arc as one state flow: film mode → "help me set up" → scan → retrieve/place → nod → resume filming.
- **3:15 gate:** full arc runs end-to-end at least once, ugly is fine.

**3:15–3:45 — Tune only.** Confidence thresholds, deadband, gesture speeds, grasp heights. No new features — at T-minus-75 every new feature costs a working one.

**3:45–4:30 — Three clean rehearsals, record the third, reset props to tape, assign narrator/subject/driver.**

**De-scope ladder from 1pm (invoke at gates, top-down):** drawer pull → drawer open-at-start → whole drawer epic (box becomes scenery; MVP1+2+4 is still a complete "cameraman + stagehand with a personality" story) → voice → typed → BC beat → verbal mention. Never cut: gestures, the 2:15 gate, rehearsal time.

The single biggest 1pm risk is spending 90 minutes on the drawer while MVP2 is at 2-for-3. The gate order exists to prevent exactly that — a flawless sorter with a personality beats a drawer that opens once.

## Claude Code skills

This repo bundles [viam-devrel/agent-skills](https://github.com/viam-devrel/agent-skills) as a local Claude Code plugin marketplace (`.claude-plugin/`, `skills/`, `plugins/`). Most relevant to this project: `viam-python` (SDK/async patterns), `viam-ml` (YOLO training + deployment), `viam-modules-fleet` (CLI/fleet/robot config), `local-viam-server` and `viam-machine-config` (create/configure a machine via the app API). The Go, C++, and TypeScript skills are included too but off-stack for this build.

Setup, from the repo root:

```
/plugin marketplace add .
/plugin install viam-skills@viam-agent-skills
```

Or install only what's needed:

```
/plugin install viam-python@viam-agent-skills
/plugin install viam-ml@viam-agent-skills
/plugin install viam-modules-fleet@viam-agent-skills
```

Skills trigger automatically off file/context signals (e.g. touching code that imports the Viam Python SDK activates `viam-python`); invoke one manually with the `Skill` tool or by name.
