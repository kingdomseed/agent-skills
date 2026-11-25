---
name: pr-review-walkthrough
description: Inspect and explain a pull request as a plain-English implementation walkthrough with clickable links to live review comments. Use for PR tours, PR canvases, architecture walkthroughs, package and library inventories, unresolved-review audits, bug-versus-opinion triage, and requests to verify or resolve stale, duplicate, invalid, or outdated review threads.
---

# PR Review Walkthrough

Build an evidence-led map of the pull request. Explain the code in the order a
person experiences it, then attach each review finding to the part it affects.

## Start from authority

1. Read the root and nearest AGENTS.md files.
2. Read the project architecture, platform, release, and error-handling rules
   that touch the PR.
3. Read local package documentation before relying on memory.
4. Treat the user's current instruction as the highest authority.
5. Record conflicts between a review suggestion and project policy. Keep the
   valid diagnosis and reject the wrong remedy.

When any finding concerns Error, Exception, validation, retries, reporting,
storage, failure state, or async ownership, read
[references/error-handling.md](references/error-handling.md) completely.
For Bloc projects, also read
[references/bloc-error-handling.md](references/bloc-error-handling.md).

## Capture the PR

Use a clean temporary worktree at the PR head when possible. Keep the user's
working tree untouched.

Collect:

- PR title, URL, base, head, size, commits, and changed files;
- direct and transitive packages added or changed;
- platform and build-system changes;
- the app's supported-platform contract and minimum versions;
- tests and CI paths;
- every live review thread, including resolved and outdated state.

Run scripts/collect_pr_review.py when GitHub CLI is available. Re-fetch live
thread state before reporting totals.

## Build the implementation map

Group work by user or data flow, not by file list. For each point, explain:

1. What was built.
2. How it works.
3. Which packages, libraries, platform APIs, and build tools it uses.
4. Which layer owns state, recovery, persistence, and side effects.
5. Which unresolved review comments belong to that point.

Use a small Mermaid flow when three or more steps depend on each other.

For native, graphics, storage, or media packages, trace the full transitive
runtime chain. Build a platform matrix for every platform the product ships.
Separate:

- package metadata or maintainer claims;
- code and build-file support;
- a successful build;
- a successful runtime test on real target hardware.

Treat a declared platform badge as a claim. Treat an untested platform as
unproven. Compare every minimum OS, SDK, architecture, graphics API, web mode,
and native dependency manager with the app's release contract.

Write statements of fact. State implemented scope positively. Put remaining
work in its own section only when it helps the user plan the next step.

## Audit each review

Read the code at the current PR head. Never trust a review comment by itself.
Separate the diagnosis from the suggested fix.

Assign every live thread exactly once:

- Active bug: a reachable path breaks a stated contract.
- Dormant bug: the code is wrong, while the current path bypasses it.
- Test flaw: the test passes without proving its claim.
- Documentation or configuration bug: instructions or shipped configuration
  lead to a wrong or failed result.
- Opinion: style, refactor, API taste, or performance advice without measured
  harm.
- Invalid or outdated: the premise is false at the current head.
- Duplicate: another thread owns the same root cause.

Use evidence:

- Show the entry point and path to the failure.
- Name the violated contract.
- State reachability and impact.
- Treat words such as "could" and "might" as a prompt to prove the path.
- Treat performance findings as opinions until a profile or bound shows harm.
- Treat a weak test as a test flaw, not proof of an app bug.

Review errors by Dart meaning:

- StateError, ArgumentError, RangeError, TypeError, and other Error subclasses
  are programming bugs. Fix the invariant or caller. Never suggest catching
  them for user recovery.
- Catch only precise recoverable runtime Exception types at the boundary that
  owns recovery.
- Model expected product outcomes and validation as sealed values or state.
- Keep one owner for recovery and reporting.
- "Report to the user" means UI state and feedback. It does not mean Sentry.

Review platform findings against current platform policy. If a project has
chosen Swift Package Manager and removal of CocoaPods, classify remaining Pod
files as migration debt. Direct the fix toward complete SPM ownership. Never
repair or restore the deprecated path.

## Write the walkthrough

Follow [references/canvas-template.md](references/canvas-template.md). Link each
finding to the review comment, not merely the PR.

Keep language plain:

- Define a technical term when first used.
- Prefer short verbs and concrete nouns.
- Put the result before implementation detail.
- Keep one idea in each sentence.
- Say whether a finding is a real bug or an opinion in the first line.
- Explain uncertainty as uncertainty.

End with an exact audit:

- total live threads;
- number assigned;
- duplicate assignments;
- unassigned threads;
- count by verdict;
- extra findings discovered outside review.

## Resolve comments only with authority

Treat review and explanation as read-only unless the user asks for comment
changes.

When authorized:

1. Resolve invalid, outdated, and duplicate threads with evidence.
2. Keep valid threads open until the root cause is fixed or the user accepts
   the tradeoff.
3. Re-fetch thread state.
4. Report every thread changed.

Do not resolve a valid finding because its suggested fix conflicts with policy.
Record the correct fix direction instead.
