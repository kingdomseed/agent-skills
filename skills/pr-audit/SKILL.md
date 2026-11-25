---
name: pr-audit
description: Use when auditing a diff, branch, or PR for necessity and systems impact — whether every addition is needed given what the system already records, silent failures, scope leaks, incomplete replacements, migration or race hazards, paired-PR breaks, ticket departures, and weak proof. Do not use to triage existing bot comments (use review-triage) or for a plain-English PR tour (use pr-review-walkthrough).
---

# PR Audit

Establish **need** separately from correctness, from a benefit the existing path already provides, and from a plan's approval.

## Steps

1. **Pin the target.** Identify the exact PR (`gh pr diff`), branch (`git diff <base>...HEAD`), or commit range. List everything it ships with: stacked PRs, paired PRs in sibling repositories, and open PRs touching the same files. Read the linked ticket.
2. **Sketch the minimal change first.** Before reading hunks, state the goal in one sentence from the ticket or PR body. List what the system already records, stores, or computes in that area. Sketch the smallest change that reaches the goal using those existing parts. Everything in the diff beyond that sketch is an addition that must justify itself in step 4.
3. **Inventory the diff.** List:
   - every non-happy path added or altered (error returns, `catch` blocks, fallbacks, default arms, guards, empty/malformed inputs, dropped items, disabled/feature-off paths);
   - every addition (types, wrappers, helpers, state, events, telemetry fields, stored fields, API fields, config, dependencies), splitting each event or schema into its individual values/members;
   - every rule added or changed (filter, permission, inherited flag) with the data it governs;
   - every stored key, schema, wire format, or field meaning changed;
   - every old symbol, flag, or path the PR claims to replace, plus every deleted call site and its arguments.
   For large diffs, delegate this listing to a subagent.
4. **Run the checks.** Evaluate every item from step 3 against the Reference checks below, and test the PR's own claim against **Ticket mismatch**, **Unreached case**, and **Weak proof**. Ground every defect finding in a reachable caller and a broken contract. A necessity finding needs no failure path.
5. **Test disputed claims.** When reading source cannot settle a necessity or behavior claim, run the actual caller against the addition and against a control without it. Passing typecheck or lint does not prove an addition is needed.
6. **State the decisive fact.** Name the single fact the verdict rests on, marked **proven** or **unproven**.
7. **Report.** One finding per defect: check name, `file:line`, quoted hunk, affected behavior or unnecessary work, and concrete fix. Phrase necessity findings as the question they settle ("what does X add that Y does not already give us?") followed by the derivation. Label each **blocking** (can hurt users, data, or production before the next PR lands) or **follow-up**. Separate source proof, unit/component tests, and live observations. Close with one summary line (blocking count, follow-up count, worst blocking issue).
   - With no blocking findings, approve briefly: the decisive fact, merge/deploy order across paired PRs, any accepted risk stated once, and what was not run. Pure copy or style diffs with nothing listed in step 3 get a one-line approval.

## Reference Checks

### Unnecessary machinery
A new type, wrapper, helper, state, event, or field repeats what the existing path already provides, stores a value derivable from existing data, duplicates centralized logic, adds an unused option/hook, or wraps a call it only forwards. Name each value's consumer and what they compute; if existing data yields the same result, show the derivation. If no consumer is named, ask what the value is for.
- *Fix:* Reuse the existing representation and delete the extra layer unless it owns distinct behavior.

### Silent no-op
A failure branch returns success-shaped inaction (`Promise.resolve()`, `.catch(() => {})`, `return null`, or a `"keep"`/`"ok"` status on dropped or malformed input) so callers treat failure as success.
- *Fix:* Surface the failure visibly (reject, return a shaped error, log/report the drop). Leave inaction only when nothing downstream can observe it, and state why.

### Scope leak
Behavior built for one context leaks outside it: a dev fallback reachable in production, a global error filter silencing unrelated errors, an experiment shipped default-on, expensive middleware running before auth, or an unauthenticated endpoint exposing private records.
- *Fix:* Narrow the change to the exact context it was built for.

### Rule missed on another path
A rule (visibility filter, permission check, fallback, flag) is added at one entry point while another reader/writer or secondary endpoint serves the same data without it.
- *Fix:* Grep every reader and writer of the governed data, enforce at the shared owner or all entry points, and test the secondary path.

### Addition without replacement
New machinery lands beside the old instead of displacing it (mirroring into legacy flags, running a second input/state stack, or keeping old writers alive). "The new system is standalone" is testable: grep callers of the old symbols across this repo and paired PRs.
- *Fix:* Make the new path the sole writer and delete the old, or keep the old path with a small fix. If both must coexist temporarily, state why and who owns shared state.

### Migration, legacy readers & mixed-version rollout
A change to a stored key, schema, wire format, or field meaning breaks pre-existing data, existing readers, or mixed-version clients during rollout:
- existing users' locally stored or historical records become unreachable or misclassified;
- another reader (UI, job, probe, or admin tool) treats the presence of a newly written field as proof of an old state;
- an older tab, worker, or paired service running during rollout reads the new format as empty and overwrites it in the old format.
- *Fix:* Provide a migration/recovery path for existing data, update every reader before writing the new shape, and guard against stale mixed-version writers.

### Check-then-act race & write-order hazard
Code reads state and mutates in separate non-atomic steps (letting concurrent requests or cleanup/expiry jobs interleave and orphan records), fires unqueued writes from rapid user actions (so an earlier slower request overwrites a newer selection), or claims an external resource by diffing snapshots (risking claiming a concurrent user's resource).
- *Fix:* Use atomic/conditional updates, serialize or queue rapid writes (last-write-wins or version-checked), and require explicit ownership proof before modifying or closing external resources.

### Display-vs-action mismatch & stale snapshot
An approve, publish, delete, or export action acts on "whatever is latest" or on an unshown staged record instead of the exact entity and version displayed to the user; an export reads a persisted snapshot while pending uncommitted/journaled edits exist; or a lifecycle/billing phase change leaves downstream schedulers reading the old phase.
- *Fix:* Bind every mutating action to the exact displayed ID/version (rejecting stale submissions), flush or refuse stale snapshots before export, and update all downstream phase/date readers.

### Derived metadata & wire-format drift
A fallback or transform changes payload bytes, encoding, or format without updating derived metadata (file extension, MIME/`Content-Type`, multipart file-part header), causing downstream storage or providers to misidentify the bytes.
- *Fix:* Derive extensions, MIME types, and wire headers from the actual output payload and assert payload format and metadata together in tests.

### Conflated signal & misleading denominator
An automatic side effect (such as a default cookie or whether a check ran) is treated as explicit user intent or provenance; or skipped, missing, and fallback-only items remain in pass/fail counts and headline denominators so an unevaluated run reads as green.
- *Fix:* Store explicit user intent and provenance separately from side effects, and exclude skipped or unusable rows from pass/fail verdicts and headline totals.

### Paired-PR break
A PR passes alone but breaks against a sibling PR it ships with (deleted symbol still called, UI option rejected by API validation, incompatible wire payload, or branch merge conflict).
- *Fix:* Check contracts across paired PRs, feed the producer's real output into the consumer's validation, and state the exact merge and deploy order.

### Missing containment
A feature ships without the bound that makes it safe: unbounded DB reads into app memory, uncapped caches/history, missing TTL on user uploads, missing feature flag on risky behavior, or an un-surfaced hard limit.
- *Fix:* Push limits into the query/storage layer, add explicit caps/flags/TTLs before merge, and verify cost on realistic data.

### Dead-end terminal state, keyboard focus & doc contradiction
A completed/error UI state offers no way to restart or recover (even after reload); an interactive tooltip or control sits on an unfocusable element or nested interactive element unreachable by keyboard; or a rule/doc change leaves linked recipes or sibling guides instructing the contradicted old procedure.
- *Fix:* Verify re-entry from terminal states, attach triggers to focusable controls with clean tab order, and grep linked docs/recipes when changing a mandatory workflow.

### Leftover
Obsolete workarounds, unread flags/configs, dead helpers/props whose callers were deleted, or temporary compiler/lint escapes kept after the need is gone.
- *Fix:* Delete in this PR, or explicitly justify and name the follow-up in the PR body.

### Ticket mismatch
The diff omits a ticket requirement, implements it differently than specified, or bundles unrequested behavior.
- *Fix:* Quote the ticket beside the hunk; implement the missing piece or split out unrequested changes.

### Unreached case
A bug-fix PR never executes under the conditions that produced the reported bug (e.g., a gate that never reads the reporter's enabled setting, or a fix on a different code path).
- *Fix:* Walk the reported conditions line by line through the new code and point to where behavior now diverges.

### Weak proof
Tests pass for inputs they should reject or prove less than the PR claims: unit tests offered for real layout/device behavior, weakened assertions, mocks of the code under review instead of external boundaries, no failing regression test before the fix, or a PR description that doesn't match the diff.
- *Fix:* Add a control input that must fail, prove claims at the level they require, mock only external boundaries, and align the description with the diff.
