# Embedded, Real-Time, and Hardware-in-the-Loop Systems

A MATLAB-first, Khan-Academy-style learning track with 24 guided modules.

Each implemented module combines:

- a concise lesson and physical mental model;
- MATLAB `%%` notebook cells;
- deterministic plots;
- actual UI sliders, spinners, or dropdowns;
- two parameter sweeps;
- one deliberately broken case;
- executable numerical checks;
- a tutor protocol that asks one observation question at a time.

## Start

From a shell:

```bash
./bin/learn start
./bin/learn start P01
./bin/learn start P02
./bin/learn start P03
./bin/learn start P04
./bin/learn list
./bin/learn status
```

On Windows PowerShell:

```powershell
python .\bin\learn.py start
```

In MATLAB:

```matlab
launch_lesson("P04")
run_module_checks("P04")
```

`P01` is the reference implementation, and P02–P04 are complete compounding learning slices. Every
module marked `implemented` is runnable; remaining modules advance through their own bounded,
reviewable batches. The live manifest remains the source of truth as that frontier moves.

## Module layout

```text
modules/01-example/
├── README.md
├── lesson.m
├── p##_scenario.m (when the module owns reusable deterministic input fixtures)
├── model.m
├── experiment.m
├── interactive.m
├── lesson.md
├── walkthrough.md
├── checks.md
└── run_checks.m
```

## Learning contract

The flow is always:

> question → mental model → baseline → manipulate levers → observe plots → break an assumption → explain → check → teach back

This repository is compatible with the same tutor/build split used by `dsp-radar_learning`.
