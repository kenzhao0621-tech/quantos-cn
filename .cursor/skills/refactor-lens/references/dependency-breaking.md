# Dependency Breaking

Use this reference when code cannot be instantiated, exercised, or observed in a test because of hard dependencies.

## Table of Contents

- Seam selection
- Fast technique selector
- Technique notes
- Risk controls

## Seam Selection

Prefer seams in this order unless the codebase strongly suggests otherwise:

1. Object seam: change the collaborator selected by a constructor argument, method argument, interface, subclass, virtual dispatch, adapter, or strategy.
2. Wrapper/sprout seam: put new behavior beside or around old code when old code is too tangled for immediate tests.
3. Link seam: substitute at classpath, module, package, linker, dynamic loader, or test build configuration level.
4. Preprocessing/text seam: use compile-time substitution only when it is already idiomatic in the language or build system.

Check that the seam has an enabling point: a constructor call, test setup, dependency injection binding, factory, classpath, linker flag, or build profile where the test can select alternate behavior.

## Fast Technique Selector

| Problem | Prefer | Watch for |
| --- | --- | --- |
| New behavior needed, old method is unsafe to edit | Sprout Method | Existing method grows; schedule later cleanup if it keeps growing |
| New behavior has its own state/collaborators | Sprout Class | Avoid creating a dumping ground for unrelated behavior |
| Need behavior before/after an existing call | Wrap Method | Wrapper must preserve ordering and error behavior |
| Need to surround a collaborator or subsystem | Wrap Class | Keep wrapper interface smaller than the wrapped library |
| Constructor needs painful objects | Parameterize Constructor, Extract Interface, Adapt Parameter | Preserve production construction path |
| Method needs painful objects | Parameterize Method, Adapt Parameter | Do not leak test-only concepts into public APIs without reason |
| Static/global access blocks tests | Encapsulate Global References, Replace Global Reference with Getter, Introduce Static Setter | Static setters can leak state across tests; reset carefully |
| External library/API dominates code | Wrap Class, Extract Interface, Introduce Instance Delegator | Wrap only used behavior |
| Hard call inside method blocks test | Extract and Override Call, Extract and Override Factory Method, Extract and Override Getter | Prefer overriding existing behavior over creating strange test hooks |
| Large method has separable local logic | Break Out Method Object, Extract Method | Preserve data flow and side effects one step at a time |
| Existing subclass point can replace dependency | Subclass and Override Method | Avoid overriding methods unrelated to the test |
| Need substitute implementation at build/load time | Link Substitution | Make test-vs-production binding obvious |
| Procedural C/C++ code resists object seams | Replace Function with Function Pointer, Text Redefinition, Template Redefinition | Keep substitutions local and visible |
| Parameter object is huge or hard to create | Primitivize Parameter, Adapt Parameter | Often leaves design debt; use as a temporary bridge |
| Useful behavior lives on wrong side of inheritance | Pull Up Feature, Push Down Dependency | Verify inheritance contract before moving behavior |
| Instance field prevents test control | Supersede Instance Variable | Avoid invalid object states in production |

## Technique Notes

### Sprout Method and Sprout Class

Use when adding behavior under time pressure and the surrounding code is not safely testable. Put new behavior in a new tested method or class, then call it from the old flow with the smallest possible edit.

Use this as a foothold, not as a permanent excuse to keep growing the old method.

### Wrap Method and Wrap Class

Use when behavior must run around an existing call or collaborator. Keep the wrapper explicit and narrow. Tests should verify both the new behavior and preserved delegation.

### Parameterize Constructor and Parameterize Method

Use when hard-coded collaborators make setup impossible. Add a path that accepts a collaborator from tests while keeping the normal production path intact.

### Extract Interface and Extract Implementer

Use when code depends on a concrete class but only needs a small role. Name the interface after the role the caller needs, not after the implementation class.

### Adapt Parameter and Primitivize Parameter

Use when a parameter is too large, too nested, or too coupled to construct. Create a smaller view of the needed behavior or data. Treat this as risky when it changes public signatures or leaves low-level data passing behind.

### Extract and Override Techniques

Use when one call inside a method blocks testing. Extract that call into an overridable method, factory, or getter; tests override it to sense or separate behavior. Keep override points protected/package-private when the language allows it.

### Break Out Method Object

Use for monster methods with many locals and branches. Move the method's working state into a small object so pieces can be tested and extracted incrementally.

### Encapsulate Global/Static Dependencies

Use when code reaches directly into global state, singletons, clocks, environment variables, random sources, process state, or static services. Introduce a small accessor or provider, then substitute it in tests. Reset global substitutions after each test.

### Link Substitution

Use when source edits are too invasive but the build or runtime can bind a fake implementation. Keep the fake implementation in test scope and make the binding difference obvious in build files.

## Risk Controls

- Break one dependency at a time.
- Keep the first dependency-breaking edit behavior-preserving.
- Run the smallest compile/test check after each break.
- Prefer a seam that can become a real design boundary.
- Remove temporary seams when the code becomes directly testable.
- Do not use test-only conditionals in production logic unless the codebase already has a disciplined pattern for them.
