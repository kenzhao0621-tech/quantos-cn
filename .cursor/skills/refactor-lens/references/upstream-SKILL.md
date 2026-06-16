---
name: refactor-legacy-code
description: Apply legacy-code refactoring and maintenance workflows for large codebases where behavior must be preserved while changing risky, poorly tested, tightly coupled, or hard-to-understand code. Use when asked to refactor, modernize, stabilize, maintain, add features to, test, untangle, break dependencies in, or plan safe changes for legacy systems, large repositories, monster methods/classes, hard-to-test code, API-heavy code, library/global/static dependencies, or repeated cross-cutting changes.
license: MIT
---

# Refactor Legacy Code

## Overview

Use this skill to make production changes in legacy code without turning the work into a rewrite. Treat legacy code as code whose behavior is not protected by fast, useful tests; the goal is to deliver the requested change while increasing local control through characterization tests, seams, and small refactorings.

This skill packages widely used legacy-code refactoring practices into an executable agent workflow. Do not reproduce copyrighted source material; apply the ideas to the current codebase.

## Core Loop

Use this loop for each risky change:

1. Identify change points: find the smallest places where the requested behavior can be changed.
2. Find test points: locate the closest observable behavior that can detect breakage.
3. Break dependencies only as needed to make the test possible.
4. Write characterization or focused tests around current behavior.
5. Make the change, then refactor inside the tested area.

Prefer code edits that create a tested foothold in the active area over broad cleanup. Leave unrelated design cleanup for later unless it directly lowers the risk of the requested change.

## Workflow

### 1. Frame the Change

Classify the request as bug fix, feature, migration, cleanup, performance, or architectural maintenance. Then inspect the repository before proposing edits.

Capture:

- user-visible behavior being changed or preserved
- candidate files/functions/classes/modules
- existing tests, build commands, and known validation path
- side effects: database, network, filesystem, time, random, threads, process state, global/static state
- unknowns that affect correctness

If the goal is ambiguous, ask one narrow question only when a wrong assumption would change the public contract or data behavior.

### 2. Build an Effect Sketch

Before editing, sketch how the change can propagate:

- entry points that receive the triggering input
- internal calls that decide the outcome
- outputs and side effects that users or systems observe
- collaborators that block fast tests
- natural test points near the change

For broad changes, find a pinch point: a method, module boundary, adapter, handler, command, or API endpoint that sees many relevant paths. Test there when testing every downstream class would be expensive.

### 3. Choose a Seam

Choose the least invasive seam that lets tests sense behavior or separate hard dependencies.

Default order:

1. Object seam: constructor parameter, method parameter, interface, subclass override, strategy, adapter, fake collaborator.
2. Wrapper or sprout: add new tested behavior beside existing behavior when direct tests are too costly.
3. Link or build seam: substitute a dependency through classpath, module path, linker, dynamic loader, package resolution, or test build wiring.
4. Preprocessor/text seam: use only for stacks where this is already normal, such as C/C++ conditional compilation.

Every seam must have an enabling point: the test or build must be able to choose the alternate behavior without editing the production line under test.

### 4. Characterize Current Behavior

When expected behavior is unclear, write characterization tests against actual current behavior before changing it. Start with a narrow input, let the system reveal the observed output, then lock that output if it is part of behavior that must not regress.

Do not turn characterization into product redesign. If a current behavior looks wrong but the task is behavior-preserving, record it as an open question or issue instead of silently changing it.

### 5. Edit in Small Steps

Keep each edit single-purpose:

- dependency break
- characterization test
- production behavior change
- cleanup/refactor inside tested code
- broader validation

Use automated refactoring tools when reliable. After each meaningful step, run the narrowest useful test or compiler/type check before continuing.

### 6. Scale the Work

In large repositories, build tested islands around active work rather than chasing full coverage first.

Prioritize areas with:

- repeated changes across the same code
- high defect risk or unclear ownership
- slow feedback loops
- large classes/methods that keep growing
- unstable external dependencies
- behavior copied across many call sites

Record the maintenance map as you work: hot spots, test footholds, useful seams, risky dependencies, and deferred cleanup.

## Situation Playbook

- No time, change is urgent: use Sprout Method/Class or Wrap Method/Class to put new behavior under test without fully untangling old code.
- Cannot instantiate a class: break constructor, global, static, or library dependencies just enough to create a test harness.
- Cannot run a method in a test: extract/override the hard call, parameterize the collaborator, or move the logic into a method object.
- Need many changes in one area: find an interception or pinch point and test behavior there first.
- Do not know what tests to write: characterize actual behavior with representative inputs before changing it.
- Monster method blocks tests: use automated extraction where available; otherwise use scratch refactoring to understand it, then make one preserving extraction at a time.
- Class is too big: add new behavior beside it first, then extract responsibilities after tests protect the split.
- Application is mostly API calls: put a thin boundary around external calls and test domain decisions on the inside.
- Library dependency blocks tests: wrap only the parts the code actually uses; avoid modeling the entire library.
- Same change appears everywhere: stop duplicating edits, find the concept or boundary that should own the rule, then migrate call sites incrementally.

## Guardrails

- Do not default to rewrites. Require explicit user approval for replacing a subsystem wholesale.
- Do not make broad style, naming, or folder changes before behavior is protected.
- Do not add abstractions unless they create a test seam, reduce a real repeated change, or match an existing local pattern.
- Preserve public signatures and data contracts unless the task requires changing them.
- Prefer fast local tests, but use higher-level tests when they are the only trustworthy characterization surface.
- Treat mocks as tools for sensing and separation, not as the goal.
- Make test/production substitutions obvious in build files and test setup.
- When tests cannot cover the first incision, rely on compiler/type checks, hyperaware single-goal edits, and explicit residual-risk notes.

## References

Load only the reference needed for the current task:

- `references/change-workflow.md`: detailed change loop, effect sketches, characterization tests, large-repo triage, and safety checklist.
- `references/dependency-breaking.md`: seam selection and dependency-breaking technique table.

## Output Contract

When planning, return:

- change points
- test points
- chosen seam and enabling point
- dependency-breaking step, if any
- implementation steps
- validation commands
- residual risks

When implementing, do the work end to end unless the user asked only for a plan. Keep changes scoped to the requested behavior and the local tests needed to protect it.
