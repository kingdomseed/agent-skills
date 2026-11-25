# PR Walkthrough Canvas

## Bottom line

Link the PR. State its size and implemented scope in two or three sentences.
Name each app, package, service, or platform surface it changes.

## Flow

Use a small Mermaid diagram when it makes the flow easier to see.

## Verdict key

Define active bug, dormant bug, test flaw, configuration or documentation bug,
opinion, invalid or outdated, and duplicate.

## Implementation point

### What was built

Explain the user-visible or data-flow result.

### How it works

Walk from input to result. Name the owner of state and side effects.

### What it uses

List direct packages, important transitive packages, native APIs, and build
tools. Explain each package's job in one line.

### Reviews tied to this point

For every linked thread, use:

#### Short finding name

[Review comment](COMMENT_URL)

Start with the verdict. Then explain:

1. What the code does.
2. The path that reaches the problem.
3. The user, data, release, or maintenance impact.
4. Whether the review's suggested fix follows project policy.

## Readiness

Group the findings:

- Fix before the PR can serve its stated production path.
- Fix before a dormant public path becomes active.
- Repair the test.
- Measure before changing.
- Refactor when the cost earns it.
- Resolve as invalid, outdated, or duplicate.

## Platform compatibility

Include this section when the PR adds a native or graphics dependency.

| Platform | Product requirement | Dependency claim | Build proof | Runtime proof | Status |
|---|---|---|---|---|---|
| iOS | | | | | |
| iOS simulator | | | | | |
| macOS | | | | | |
| Android | | | | | |
| Android emulator | | | | | |
| Windows | | | | | |
| Linux | | | | | |
| Web JavaScript | | | | | |
| Web Wasm | | | | | |

Trace the direct package through its renderer, native plugin, binary artifact,
and build manager. Link the source for each claim. Call an unsupported product
platform a blocker. Call a supported but untested platform unproven.

## Exact thread audit

| Measure | Count |
|---|---:|
| Live review threads | |
| Assigned once | |
| Duplicate assignments | |
| Unassigned | |
| Active bugs | |
| Dormant bugs | |
| Test flaws | |
| Documentation/configuration bugs | |
| Opinions | |
| Invalid/outdated | |
| Duplicates | |
| Extra findings | |

State whether files, review threads, or PR state changed during the walkthrough.
