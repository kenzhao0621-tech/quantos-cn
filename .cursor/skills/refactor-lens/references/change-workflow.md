# Change Workflow

Use this reference when planning or executing a concrete change in risky legacy code.

## Table of Contents

- Change algorithm
- Effect sketch template
- Characterization tests
- Pinch points and interception points
- Understanding without rewriting
- Safety checklist
- Done criteria

## Change Algorithm

1. Identify change points.
   - Search for user-visible words, route names, commands, API fields, error strings, feature flags, and call sites.
   - Inspect tests and recent git history around candidate files.
   - Prefer the smallest code location that owns the behavior.
2. Find test points.
   - Start near the change point.
   - Move outward only when dependencies make the closer test too expensive.
   - Prefer a test that fails for the intended behavior change and passes for unrelated behavior.
3. Break dependencies.
   - Break only the dependency that blocks the test.
   - Keep the production path equivalent before the behavior change.
   - Run compiler/type checks immediately after mechanical changes.
4. Write tests.
   - Use characterization tests for current behavior.
   - Use focused new tests for the requested behavior.
   - Add regression tests at the lowest useful level; add an integration test when the contract crosses module boundaries.
5. Make the change and refactor.
   - Make the behavior change after tests exist.
   - Refactor only inside the newly protected area unless broader cleanup is necessary.

## Effect Sketch Template

Use this template in notes, PR descriptions, or implementation plans:

```text
Requested behavior:
Entry point(s):
Likely change point(s):
Observed output / side effect:
Relevant collaborators:
Hard dependencies:
Existing tests:
New test point(s):
Seam:
Enabling point:
Validation:
Residual risk:
```

## Characterization Tests

Use characterization tests when preserving existing behavior matters and the intended behavior is not fully known.

Procedure:

1. Put the code under a test harness through its current public or stable internal entry point.
2. Exercise one concrete input or state.
3. Let the first failure reveal the actual output or side effect.
4. Change the assertion to preserve that observed behavior if it is part of the contract.
5. Add more examples for edge cases, branches, errors, empty inputs, and state transitions.

Rules:

- Name tests after the observed behavior, not after guesses about intent.
- Keep fixtures small enough that failures identify the broken behavior.
- Do not freeze obviously incidental data such as timestamps, random IDs, nondeterministic ordering, or generated object addresses.
- If characterization exposes a bug, separate the preservation test from the intentional behavior-change test.

## Pinch Points and Interception Points

Use a pinch point when many changes or effects pass through one location. Examples include command handlers, request routers, serializers, adapters, schedulers, domain services, and transaction boundaries.

Good pinch points:

- observe the behavior users care about
- avoid excessive setup
- cover multiple downstream paths
- are stable enough not to make every refactor painful

Avoid pinch points that are so broad they require the whole application, live services, or fragile timing unless no lower surface exists.

Use an interception point when adding or redirecting behavior around an existing flow. It should be explicit, named, and easy to remove or keep as a permanent boundary.

## Understanding Without Rewriting

Use these techniques before editing hard-to-understand code:

- notes/sketching: draw data flow, call flow, and state transitions
- listing markup: annotate branches, side effects, and invariants in a temporary note or review comment
- scratch refactoring: make local exploratory edits to understand shape, then discard them before production edits
- delete unused code only when proven by search, compiler, tests, or product evidence

Do not ship exploratory edits just because they made the code easier to read. Convert them into small, validated refactorings after tests exist.

## Safety Checklist

Before editing:

- Identify the behavior being preserved.
- Identify the exact behavior being changed.
- Know the test or check that will fail if the change is wrong.
- Keep the first dependency break behavior-preserving.

During editing:

- Make one goal per edit.
- Preserve signatures unless the contract is intentionally changing.
- Lean on compiler, type checker, and IDE refactors.
- Prefer adding parameters or adapters over reading global state in tests.
- Keep test-only seams out of production control flow unless they are clean boundaries.

After editing:

- Run the narrow tests.
- Run the broader validation path relevant to the changed module.
- Inspect diff for incidental formatting, unrelated cleanup, and public contract drift.
- Document residual risk if a behavior could not be characterized.

## Done Criteria

A legacy-code change is done when:

- the requested behavior is implemented
- current behavior around the change is characterized or otherwise validated
- dependencies broken for testing are clear and maintainable
- tests fail for the old bug or missing feature when possible
- validation commands were run and results are known
- any remaining risk is explicit
