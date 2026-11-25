# Error Handling Architecture

## Multi-Context Usage

This document remains the canonical typed error-handling reference. It is
indexed by root `CONTEXT-MAP.md` under the architecture context so the Matt
Pocock skills can find it without moving or replacing the reference docs. Read
`docs/contexts/architecture/CONTEXT.md` first for routing, then use this file as
the source of truth for exception, validation, and reporting patterns.

## Overview

This document defines a layered Dart/Flutter error-handling architecture. The system is designed to:
- **Distinguish** between programming errors (bugs) and runtime failures (exceptions)
- **Avoid** covering up programmer mistakes with try-catch blocks
- **Separate** genuine errors from user corrections (validation)
- **Triage** app-controlled failures by whether the app or feature is still usable
- **Treat user/device/environment conditions** such as offline network, DNS
  failure, permission denial, and store reachability as normal product states,
  not reportable defects
- **Report only programming/product defects**; expected external runtime
  conditions must be modeled as state, fallback, or user feedback
- **Maintain** privacy by sanitizing all PII before error reporting
- **Integrate** seamlessly with our 4-layer architecture and Riverpod 3.0

**Status**: Approved
**Date**: 2025-11-05
**Based on**: Research synthesis from Sentry, VGV, Andrea Bizzotto, Riverpod 3.0, Flutter/Dart official docs

---

## Philosophy

### The Core Distinction: Error vs Exception

Dart makes a critical distinction between programming mistakes and runtime failures:

**Error** (subclasses of `dart:core/Error`):
- **Purpose**: Indicates a program failure that the programmer should have avoided
- **Examples**: `ArgumentError`, `StateError`, `TypeError`, `AssertionError`, `RangeError`
- **Philosophy**: "Errors are not meant to be routinely caught. If they occur, the program is erroneous."
- **Action**: Let these crash the app—they reveal bugs that need fixing

**Exception** (subclasses of `dart:core/Exception`):
- **Purpose**: Conveys information about a runtime failure that can be addressed programmatically
- **Examples**: `FileSystemException`, `SocketException`, `FormatException`, `TimeoutException`
- **Philosophy**: Exceptions contain useful data for recovery
- **Action**: Catch these when you can recover or provide user feedback

**Official Reference**: https://dart.dev/language/error-handling

**Critical Rule**: We catch `Exception` types (runtime failures) only at the
boundary that owns recovery. We DO NOT catch `Error` types (programming
mistakes).

---

### Throw vs Sealed Outcome

Not every failed operation should throw. Classify before choosing a shape:

| Outcome | Shape | Who sees it |
|---|---|---|
| Programming mistake (`Error`, broken invariant) | Uncaught throw | Crash / global handler / Sentry so we can fix the bug |
| Expected product outcome (target changed, entry missing, ordinary local persist/availability failure, unsupported future schema, validation reject) | Sealed result or typed recovery state | User-visible Save/`AsyncError`, snackbar, keep-draft, Update Required — **not** Sentry |
| App/product defect we will fix (e.g. upgrade validation defect) | Typed exception or recovery state owned by one recovery owner | That owner reports once (PII-safe), then surfaces recovery |

**"Report to the user" is not Sentry.** For Journal Save and similar writes, the
feature-owned `AsyncNotifier<void>` maps a sealed reject or remaining typed
`AppException` to `AsyncError`; widgets `ref.listen` for snackbar / keep sheet
open. That is the user report channel.

**Throw for programming errors.** Prefer sealed outcomes for expected recovery.
Do not invent Presentation try/catch/rethrow so ordinary local-folder writes
look like exception control flow.

**iCloud is a local folder** for error-policy purposes (coordinated ubiquity
path). It is not an external cloud service like RevenueCat, Sentry, or PostHog.
Ordinary journal persist failures on iCloud paths follow the same sealed-result
rules as other local storage.

---

### App Defects vs User Environment Conditions

Not every failed operation is a defect. Before surfacing a typed exception from
a startup gate, feature gate, purchase flow, or maintenance operation, classify
the cause.

**User/device/environment condition**:
- The user's network is offline, DNS fails, a cloud provider is unavailable on
  the device, billing/store services are unreachable, or the OS denies access.
- This is not a programming error and not our infrastructure failure.
- Do not report to Sentry. Show user feedback, use cached state, or enter a
  degraded state.

**Programming/product defect**:
- Our code passed invalid state, lost data, corrupted data, selected an
  impossible flow, mishandled a schema migration, or could not recover from a
  condition it should handle.
- Report to Sentry with sanitized context so we can fix the app.

**Sentry decision bar: "Will I fix it?"**
- Before calling `ErrorReportingService.recordError(...)`, ask whether the event
  points to an app, product, schema, or retry/recovery defect we will actually
  fix.
- If the answer is no, do not send it to Sentry. Model it as state, fallback,
  retry, user feedback, or a low-volume breadcrumb instead.

**Blocking failure**:
- Continuing would lose data, corrupt data, or leave the requested feature
  unusable.
- Surface an error, recovery, or maintenance state.
- Report to Sentry only when the evidence points to a programming/product
  defect we can fix in code. Do not report user/device/environment conditions
  merely because they block the current request.

**Non-blocking condition**:
- The app can continue from existing data, a fallback location, cached metadata,
  or an explicit degraded state.
- Do not report as an error. Record a low-volume breadcrumb only when the
  condition helps diagnose performance or recovery behavior.

Example:

```dart
@riverpod
Future<void> appStartupGate(Ref ref) async {
  final repository = await ref.watch(campaignRepositoryProvider.future);

  try {
    await repository.refreshFromStorage();
  } on StorageLocationException catch (error, stackTrace) {
    final hasUsableLocalState = await repository.hasUsableLocalState();
    if (hasUsableLocalState) {
      await ErrorReportingService.addBreadcrumb(
        'Storage refresh skipped; existing local state is usable',
        category: 'startup.storage',
        data: {'code': error.code},
      );
      return;
    }

    // A missing or unreachable user-selected storage location is not
    // reportable. If this boundary catches a separate typed app defect, such
    // as app-generated data corruption or a failed schema migration, report
    // that specific defect before throwing.
    Error.throwWithStackTrace(error, stackTrace);
  }
}
```

Use this pattern for storage startup, file-backed table materialization, cloud
sync readiness, purchase restore, and other places where a failed operation may
be real but not reportable. "Blocking" means the UI needs a recovery state; it
does not automatically mean the event belongs in Sentry.

---

### Reporting Ownership

`ErrorReportingService.recordError(...)` belongs only to the component that owns
the failure's recovery state. Lower layers classify, add breadcrumbs when useful,
and throw typed exceptions when an owner above will retry, absorb, or surface the
failure. Do not report the same recoverable failure at both the wrapper and the
inner operation boundary.

Typed exceptions are a transport mechanism, not a reporting instruction. A data
layer may classify `FileSystemException` (and similar) into `StorageException`
at the filesystem edge so callers do not treat a failed write as success. Once
that failure reaches the component that owns recovery state, expected
user/device/environment conditions must stop being exception-shaped in the
normal path. Convert them to state such as dirty, pending sync, degraded
storage, retry scheduled, sealed mutation reject, or user recovery UI. Do not
rethrow them toward global handlers merely because the operation failed.

**Journal targeted mutations (one owner):** The sole Journal mutation owner
(session / mutation port) absorbs ordinary Tier-1 or local persist failure into
a sealed result such as
`JournalMutationRejected(JournalMutationPersistFailed(...))` (or equivalent).
It must not rethrow that ordinary failure into Presentation. Feature Save
controllers `switch` committed vs rejected and map reject to `AsyncError`.
Programming `Error`s remain uncaught. See Decision 42 and address-catalog #17.

Strict caller-handling paths are the narrow exception outside that owned
mutation contract. Prefer an explicit failure **result** over a typed throw
whenever a follow-up would lose data or mutate the wrong file. That is control
flow for the caller, not Sentry telemetry. Keep it local, typed, and tested; do
not use it to recreate wrapper-level reporting noise or compensating
try/catch/rethrow theater.

---

### Repeated Async Findings Are Architecture Findings

If Greptile or code review repeatedly reports async lifecycle, stale-cache,
disposed-state, stream restart, timer, or cancellation findings in the same
slice, do not treat the third round as another local error-handling task. Stop
and run the ownership review defined in `ARCHITECTURE_GUIDE.md` and
`DECISIONS.md` Decision 39.

Error handling is not an ownership mechanism:

- Do not add broader catches to keep a stream alive.
- Do not catch `Object` or `Error` to convert architecture bugs into recoverable
  failures.
- Do not stack disposed guards, retry branches, or best-effort persistence
  fallbacks when two layers are still trying to own the same lifecycle or
  freshness state.
- Do assign one owner for the stream, platform handle, cache, dirty marker,
  retry/timer, and invalidation path, then make typed exception handling local
  to the boundary that owns the recoverable runtime condition.

---

## What We Catch vs What We Don't

### ❌ NEVER Catch (Programming Errors)

These indicate bugs in our code. Catching them hides problems that need fixing:

| Error Type | Meaning | Action |
|------------|---------|--------|
| `ArgumentError` | Wrong arguments passed to function | Fix calling code |
| `StateError` | Invalid state for operation | Fix initialization/state management |
| `TypeError` | Type mismatch | Fix type declarations |
| `AssertionError` | Failed assertion | Fix logic that allowed invalid state |
| `RangeError` | Index out of bounds | Fix array access logic |
| `NoSuchMethodError` | Calling non-existent method | Fix code/add null check |

**Pattern**: Let these bubble up to global error handlers where they'll be reported to Sentry so we can fix the code.

### ✅ SHOULD Catch (Recoverable Runtime Exceptions)

These are runtime conditions outside normal control flow. Catch them only where
the app can transform them into typed state, user feedback, fallback behavior,
or recovery UI.

| Exception Type | Meaning | Transform To | Report? |
|----------------|---------|--------------|---------|
| `FileSystemException` | File not found, permission denied, disk full | `StorageException` or recovery state | Only if app bug/data loss evidence |
| `SocketException` | User/device network unavailable | Offline/degraded state | No |
| `HttpException` | External service unavailable | Service unavailable state | No, unless our request is malformed |
| `FormatException` | Invalid JSON or corrupt data | `DataCorruptionException` | Only if app-generated data/schema bug |
| `TimeoutException` | Operation too slow | Timeout/retry state | No, unless caused by app-owned deadlock/loop |

**Pattern**: Catch at data layer boundaries, transform to domain exceptions,
and surface typed recovery state. Report to Sentry only when evidence indicates
a programming/product defect. Offline network, DNS failure, store reachability,
OS permissions, and third-party service availability are user/device/environment
conditions, not reportable app defects.

### 🔵 NOT Errors (User Corrections)

These are valid states that don't require exceptions:

| Scenario | Pattern | User Sees |
|----------|---------|-----------|
| Empty input | Return validation result | Inline validation message |
| Invalid format | Return validation result | "Email format invalid" |
| Empty results | Return null or empty list | "No campaigns found" |
| Business rule violation | Return result type | "Chaos Factor must be 3-6" |

**Pattern**: Use validation result types or return null—never throw exceptions for expected user behavior.

**Reference**: https://codewithandrea.com/articles/flutter-exception-handling-try-catch-result-type/

---

## Exception Hierarchy

### Base Exception Class

```dart
abstract class AppException implements Exception {
  const AppException(
    this.code,
    this.message, {
    this.cause,
  });

  final String code;
  final String message;
  final Object? cause;

  @override
  String toString() => '$code: $message';
}
```

> **Why `abstract` instead of `sealed`?** With 30+ exception subclasses across multiple files, `sealed` is not viable — Dart requires all subclasses of a sealed class to be in the same library. We use `abstract class` to allow subclasses in separate files per feature. If exhaustive pattern matching is needed for a specific subset (e.g., storage exceptions only), consider making leaf exception groups sealed while keeping the base abstract.

### Runtime Exception Types

**Purpose**: Represent recoverable runtime conditions in typed form so the app
can show the right state or recovery path.

**Characteristics**:
- User-friendly messages (not technical jargon)
- Error codes for local diagnostics and user support
- Typed classes for distinct recovery and reporting behavior
- Sealed leaf groups only when all variants live in one library and exhaustive
  handling is useful

**Types**:
- `StorageException` - File system/storage failures
- `NetworkException` - User/device network unavailable state; do not report
- `DataCorruptionException` - Invalid/corrupt data
- `OperationTimeoutException` - Operations taking too long

**Reference**: See `lib/src/exceptions/app_exception.dart`

**When to Create New Exception Types**:
1. Represents a distinct recoverable runtime condition
2. Requires different user messaging
3. Needs specific error recovery logic
4. Needs distinct recovery or fallback behavior

**When NOT to Create Exception Types**:
- For programming errors (use assertions instead)
- For user input validation (use result types)
- For empty results (return null)
- For business rule violations from user input (use result types)

---

## Layer-by-Layer Error Handling

### Data Layer (Repositories)

**Responsibility**: Transform recoverable runtime failures into domain
exceptions or typed recovery state.

**Pattern**:
```dart
class CampaignRepositoryImpl implements CampaignRepository {
  @override
  Future<Campaign?> getCampaign(String id) async {
    try {
      final json = await _storageService.readFile('campaigns/$id.json');
      return Campaign.fromJson(jsonDecode(json));
    } on FileSystemException catch (e, stack) {
      await ErrorReportingService.addBreadcrumb(
        'CampaignRepository read failed; surfacing storage recovery state',
        category: 'storage.campaign',
        data: {
          'operation': 'read',
          'os_error_code': e.osError?.errorCode,
        },
      );
      Error.throwWithStackTrace(StorageException('read campaign'), stack);
    } on FormatException catch (e, stack) {
      await ErrorReportingService.addBreadcrumb(
        'CampaignRepository parse failed; surfacing data recovery state',
        category: 'storage.campaign',
        data: {'operation': 'parse'},
      );
      Error.throwWithStackTrace(DataCorruptionException('Campaign'), stack);
    }
    // Let ArgumentError, StateError, etc. crash - those are bugs
  }
}
```

> **Why `Error.throwWithStackTrace` instead of `throw`?** Using `throw StorageException(...)` inside a catch block creates a *new* stack trace pointing to the throw site in the repository, not to the original `FileSystemException` origin. `Error.throwWithStackTrace(exception, stack)` preserves the original stack trace, so Sentry reports show the full causal chain back to the actual failure point. This makes production debugging significantly easier.

**Rules**:
- ✅ Catch ONLY specific recoverable runtime exception types (`on FileSystemException`, `on SocketException`, `on FormatException`, `on TimeoutException`)
- ✅ Transform to domain exceptions
- ✅ Add low-volume breadcrumbs when context helps recovery diagnosis
- ✅ Report to Sentry only when the failure indicates a programming/product
  defect, not an expected external condition
- ✅ Preserve stack traces
- ❌ NEVER catch `Error` types
- ❌ NEVER catch without specific type (`catch (e)`)
- ❌ NEVER catch to handle user input validation
- ✅ For iCloud in‑place access, surface coordinated read/write failures as
  typed storage exceptions (do not return null when the file exists).

**See**: `lib/src/features/*/data/AGENTS.md` for layer-specific guidance

---

### Domain Layer

**Responsibility**: Define exception types, throw them, never catch.

**Pattern**:
- Define custom exception types in `lib/src/exceptions/`
- Throw exceptions for invariant violations
- No try-catch blocks in domain layer

**Rules**:
- ✅ Define typed exceptions
- ✅ Throw when external dependencies fail
- ✅ Use assertions for programmer contract violations
- ❌ NEVER catch exceptions in domain layer
- ❌ NEVER throw exceptions for user input validation

**See**: `lib/src/features/*/domain/AGENTS.md` for layer-specific guidance

---

### Application Layer (Optional)

**Responsibility**: Coordinate errors from multiple repositories, add business context.

**Pattern**:
```dart
class CampaignSyncService {
  Future<void> syncCampaign(String campaignId) async {
    try {
      final campaign = await _campaignRepo.getCampaign(campaignId);
      final characters = await _characterRepo.getCharacters(campaignId);
      await _syncRepo.sync(campaign, characters);
    } on StorageException catch (e, stack) {
      await ErrorReportingService.addBreadcrumb(
        'Campaign sync blocked by storage recovery state',
        category: 'sync.campaign',
        data: {'service': 'campaign_sync', 'code': e.code},
      );
      rethrow;
    }
  }
}
```

**Rules**:
- ✅ Prefer returning a sealed workflow / mutation result over catch-and-rethrow
  pass-through when Application owns the outcome
- ✅ Add business context with breadcrumbs or typed recovery state when useful
- ✅ Coordinate errors from multiple repositories
- ⚠️ `rethrow` only when there is not yet an owner that can return a sealed
  result and the intentional path is still exception-shaped; preserve stack
  traces with `Error.throwWithStackTrace` when transforming
- ❌ Do not use Application try/catch to implement compensating two-phase
  rollbacks (rename-then-undo, optimistic-mutate-then-rollback) when one owner
  can return committed vs rejected
- ❌ Don't report external conditions already handled in data layer unless the
  new evidence points to a programming/product defect

**See**: `lib/src/features/*/application/AGENTS.md` for layer-specific guidance

---

### Presentation Layer (Controllers & UI)

**Responsibility**: Display errors to users via AsyncValue patterns.

**Read Path — Query Providers (no controller, no try-catch)**:
```dart
// Failures become AsyncValue.error after the provider's retry policy settles.
Duration? noRetry(int retryCount, Object error) => null;

@Riverpod(retry: noRetry)
Future<Campaign> campaign(Ref ref, {required String campaignId}) async {
  final repo = ref.watch(campaignRepositoryProvider);
  return repo.getCampaign(campaignId);
}
```

Riverpod 3 has automatic provider retry. If a provider and the root
`ProviderScope` both leave `retry` unset, ordinary `Exception`s are retried by
Riverpod's default policy before the UI sees `AsyncValue.error`. Startup,
storage, recovery, and user-correctable providers must define an explicit retry
policy so the app does not delay recovery or create repeated error-reporting
noise.

During a scheduled retry, Riverpod can represent the provider as `AsyncLoading`
with the previous error attached and `AsyncValue.retrying == true`. The public
getter is `retrying`. It can be true while `isLoading` is false during the
backoff delay. Code that awaits `provider.future` stays pending through retrying
`AsyncLoading` states and completes with data or a terminal error. It does not
expose every retry failure to awaiters. Do not build storage recovery on the
assumption that `.when(error:)` or `provider.future` will see every intermediate
storage failure.

There is no public `AsyncValue.retryCount` getter in the resolved Riverpod
version. Capture retry counts inside explicit retry-policy callbacks or
observer-side state when needed.

Default startup/storage retry policy:
- Do not retry user-correctable storage states such as
  `StorageLocationException` or `ICloudContainerUnavailableException`.
- Do not retry expected degraded/fallback states that should become typed state
  or recovery UI.
- Use short, bounded retry only for genuinely transient infrastructure failures
  where retrying cannot hide required user action.

**Write Path — Prefer sealed results; `AsyncValue.guard` is optional sugar**:

Riverpod's `AsyncValue.guard` is try/catch that returns `AsyncValue` (success →
`AsyncData`, matching throw → `AsyncError`, non-matching throw → rethrow). Use
it only when a lower boundary still throws typed `AppException` you have not
sealed yet. When the owner already returns a sealed mutation result, `switch`
on that result — do not require guard.

```dart
@riverpod
class JournalEntrySaveController extends _$JournalEntrySaveController {
  @override
  FutureOr<void> build() {}

  // Preferred when the mutation owner returns a sealed result:
  Future<void> save(JournalMutationTarget target, JournalMutation mutation) async {
    state = const AsyncLoading();
    final outcome = await ref.read(journalMutationProvider).mutate(target, mutation);
    if (!ref.mounted) return;

    switch (outcome) {
      case JournalMutationCommitted():
        state = const AsyncData(null);
      case JournalMutationRejected(:final rejection):
        // User report channel — snackbar / keep draft via ref.listen
        state = AsyncError(rejection, StackTrace.current);
    }
  }
}
```

Optional guard when a remaining path still throws `AppException`:

```dart
Future<void> updateCampaign(Campaign campaign) async {
  state = const AsyncLoading();
  final result = await AsyncValue.guard(
    () async {
      final repo = ref.read(campaignRepositoryProvider);
      await repo.updateCampaign(campaign);
    },
    (error) => error is AppException,
  );
  if (!ref.mounted) return;
  state = result;
  if (!result.hasError) {
    ref.invalidate(campaignProvider);
  }
}
```

Always pass a typed predicate to `AsyncValue.guard`, normally
`(error) => error is AppException`. Without a predicate, Riverpod catches
programming `Error` objects too. Store the result locally, check `ref.mounted`,
then assign state; assigning the awaited result first makes the mounted check
too late.

When an Application or Journal mutation returns an expected sealed result, do
not throw a rejection just to make `AsyncValue.guard` catch it. The mutation
controller maps committed to success and rejected to typed recovery state. The
widget still observes only the controller and the controller method still
returns `Future<void>`.

Fast local commands may be simple `void build()` mutation controllers that call
a repository and invalidate reads when the operation is effectively synchronous
from the user's perspective and failure is not meaningfully recoverable at that
UI surface. Do not add controller state for fast local writes just to follow a
pattern.

**UI Error Display — watching both paths**:
```dart
@override
Widget build(BuildContext context, WidgetRef ref) {
  // READ: Watch the query provider directly for data display
  final campaignAsync = ref.watch(campaignProvider(campaignId: id));

  // WRITE: Listen for mutation side effects (snackbar on error)
  ref.listen<AsyncValue<void>>(campaignControllerProvider, (prev, next) {
    next.whenOrNull(
      error: (error, _) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.toString())),
        );
      },
    );
  });

  return campaignAsync.when(
    data: (campaign) => CampaignDetails(campaign),
    loading: () => const CircularProgressIndicator(),
    error: (error, stack) => ErrorDisplay(message: error.toString()),
  );
}
```

**Rules**:
- ✅ **Read path**: Use `FutureProvider`/`StreamProvider` for data fetching. Failures become `AsyncValue.error` after explicit retry policy is applied.
- ✅ **Write path (preferred)**: When the owner returns a sealed mutation result, `switch` to `AsyncData` / `AsyncError`. That is the user report channel.
- ✅ **Write path (optional)**: Use predicate-limited `AsyncValue.guard()` only when a lower boundary still throws typed `AppException` and the UI needs loading/error state.
- ✅ **Fast local write path**: Use narrow mutation methods without extra state when failure is not meaningfully actionable at that UI surface.
- ✅ Check `ref.mounted` after every `await` in a mutation controller, before updating state
- ✅ Display read errors via `AsyncValue.when()` in the widget build
- ✅ Display mutation errors via `ref.listen()` for side effects (snackbar, dialog)
- ✅ Use Riverpod 3 `AsyncValue.value` for nullable data access only when
  last-known/current data is an explicit contract; use exhaustive
  `AsyncData`/`AsyncLoading`/`AsyncError` matching when readiness matters
- ❌ Do not use controllers as broad exception-translation layers.
- ❌ NEVER Presentation try/catch/rethrow compensating rollbacks (optimistic
  mutate then undo; nested rename undo). Fix ownership / sealed results instead.
- ❌ NEVER throw a sealed rejection so `AsyncValue.guard` can catch it.
- ❌ NEVER catch programming errors in UI
- ❌ NEVER create a controller just to fetch and display data
- ❌ NEVER use `.value!` as an async-readiness assertion
- ❌ NEVER use `valueOrNull` or compatibility shims for old Riverpod APIs in new
  or touched error-handling code

**UI Error Display Principles**:
- **Least Interruption**: Errors should not disrupt user workflow unnecessarily
- **Accessible Interruption**: Users must be informed of failures with clear explanations
- **Actionable Feedback**: When applicable, offer users a way to resolve the issue (e.g., retry, change input)
- **Implementation Flexibility**: Use appropriate UI patterns based on severity and context
  - Modal dialogs for critical failures requiring immediate attention
  - Persistent notifications (snackbars without auto-dismiss) for recoverable errors
  - Inline messages for validation feedback

**Pattern**: Use Riverpod's `AsyncValue.when()` or `ref.listen()` to display errors, choosing the presentation method that best serves the user's needs while respecting accessibility.

**API Currency**: Do not add compatibility shims to preserve old error-handling
or Riverpod call-site shapes. Migrate touched code to the current API directly.
For `AsyncValue`, that means `value`, `requireValue` behind an explicit gate, or
exhaustive pattern matching; not `valueOrNull`.

**Anti-pattern example**: A monolithic `SettingsController` that owns
settings data, storage/cloud processing flags, stream subscription behavior, and
broad invalidation cascades — plus manual typed catches and manual
`AsyncValue.data(...)` updates — is a split candidate, not a controller example to copy.

**Reference**: https://riverpod.dev/docs/concepts/async_value

**See**: `lib/src/features/*/presentation/AGENTS.md` for layer-specific guidance

---

## Validation Patterns (Not Exceptions)

### The Principle

User input validation and business rule violations are **not exceptions**—they're expected scenarios that users need to correct.

**Anti-Pattern**:
```dart
// ❌ WRONG - Don't throw for validation
void setChaosFactor(int value) {
  if (value < 3 || value > 6) {
    throw InvalidChaosFactorException(value); // BAD
  }
}
```

**Correct Pattern**:
```dart
// ✅ RIGHT - Return result type
sealed class SetChaosFactorResult {}
class ChaosFactorUpdated extends SetChaosFactorResult {}
class ChaosFactorOutOfRange extends SetChaosFactorResult {
  final int min = 3;
  final int max = 6;
}

SetChaosFactorResult setChaosFactor(int value) {
  if (value < 3 || value > 6) {
    return ChaosFactorOutOfRange();
  }
  state = state.copyWith(chaosFactor: value);
  return ChaosFactorUpdated();
}
```

### Validation Result Types

**Option 1: Simple Boolean + Message**
```dart
class ValidationResult {
  final bool isValid;
  final String? errorMessage;

  const ValidationResult.valid() : isValid = true, errorMessage = null;
  const ValidationResult.invalid(this.errorMessage) : isValid = false;
}
```

**Option 2: Sealed Classes (Type-Safe)**
```dart
sealed class CampaignNameValidation {}
class ValidCampaignName extends CampaignNameValidation {}
class EmptyCampaignName extends CampaignNameValidation {}
class CampaignNameTooLong extends CampaignNameValidation {
  final int maxLength = 100;
}
```

**Option 3: Formz Package** (Recommended for Forms)

Reference: https://pub.dev/packages/formz

Keep result types focused. Use them for validation and explicit business
outcomes. Do not introduce broad `Result<T>` wrappers across async repository
reads just to avoid exceptions; this project uses typed exceptions plus
`AsyncValue` for asynchronous recoverable runtime failures.

---

## Sentry Integration

### Breadcrumbs for Performance Diagnostics

When investigating AppHangs/jank, breadcrumbs can provide a low-overhead timeline of “slow operations that just finished” without requiring full tracing.

Guidelines:
- Prefer `ErrorReportingService.addBreadcrumb(...)` (wrapper) over raw `Sentry.addBreadcrumb(...)` so behavior is consistent and testable.
- Record only slow operations (use a threshold such as `elapsed_ms >= 2000`).
- Use structured categories (e.g. `performance.tables`) and include `elapsed_ms` plus safe counts/flags.
- Avoid per-item breadcrumbs inside loops; record one summary breadcrumb per operation.

### Global Error Handlers

**Purpose**: Catch unhandled programming errors that escape our system.

**Setup** (schematic; keep aligned with `lib/main.dart`):
```dart
void main() async {
  await SentryFlutter.init(
    (options) {
      options.dsn = const String.fromEnvironment('SENTRY_DSN');
      options.sendDefaultPii = false; // CRITICAL for privacy
      options.beforeSend = ErrorReportingService.beforeSend;
      // ... other options
    },
    appRunner: setupApp,
  );
}

void setupApp() {
  final previousHandler = FlutterError.onError;

  FlutterError.onError = (details) {
    if (ErrorReportingService.isTextPainterHitTestRaceCondition(
      details.exception,
      details.stack,
    )) {
      unawaited(
        ErrorReportingService.addBreadcrumb(
          'TextPainter hit test race condition (benign)',
          category: 'flutter.framework',
          level: SentryLevel.debug,
        ),
      );
      return;
    }

    previousHandler?.call(details) ?? FlutterError.presentError(details);
  };

  ErrorWidget.builder = (errorDetails) {
    unawaited(
      ErrorReportingService.recordError(
        errorDetails.exception,
        errorDetails.stack ?? StackTrace.current,
        reason: 'Widget rendering failure',
        fatal: true,
      ),
    );
    return ErrorFallbackWidget(errorDetails);
  };
}
```

**What Global Handlers Catch**:
- Programming errors that we didn't anticipate (`ArgumentError`, `StateError`, etc.)
- Product defects that escaped typed recovery paths
- Framework errors (build/layout/paint failures)

**Reference**: https://docs.sentry.io/platforms/flutter/

---

### Data Layer Error Handling

**Purpose**: Convert recoverable runtime conditions into typed recovery paths
without turning user/device/environment conditions into Sentry errors.

**Pattern**:
```dart
try {
  // ... operation
} on FileSystemException catch (e, stack) {
  await ErrorReportingService.addBreadcrumb(
    'CampaignRepository read failed; surfacing storage recovery state',
    category: 'storage.campaign',
    data: {
      'operation': 'read',
      'os_error_code': e.osError?.errorCode,
    },
  );
  Error.throwWithStackTrace(StorageException('read campaign'), stack);
}
```

**Rules**:
- ✅ Preserve stack traces
- ✅ Use `ErrorReportingService.addBreadcrumb(...)` for low-volume context
  when it helps understand recovery behavior
- ✅ Use `ErrorReportingService.recordError(...)` only for programming/product
  defects, not ordinary external runtime failures
- ✅ Keep call-site `properties` PII-safe; the reporting wrapper does not make arbitrary metadata safe
- ❌ DON'T log campaign IDs, character names, or user data
- ❌ DON'T report offline network, missing cloud provider, store/backend outage,
  permission denial, or other user/device/environment conditions as Sentry
  errors merely because they block a request

---

### Filtering Strategy

**Purpose**: Don't report scenarios that aren't actionable errors.

**Implementation**: use `ErrorReportingService.beforeSend` for transport-level
filtering and `ErrorReportingService.recordError(...)` for call-site reporting.

The Sentry bar is: **"Will I fix it?"** If an event does not create a concrete
engineering action for this app, it should not become a Sentry issue. Expected
user/device/environment conditions belong in recovery state, user feedback,
fallbacks, retries, or breadcrumbs. `beforeSend` filters are a backstop, not a
substitute for removing noisy call-site reporting.

**DON'T report**:
- Validation failures (not errors)
- "Not found" scenarios (valid states)
- User input corrections
- Expected connectivity/cloud-storage states when existing data or a degraded
  state remains usable
- Offline network, DNS failures, store/backend outage, device permission denial,
  billing-service unavailability, or cloud-provider unavailability
- Successful fallback and recovery paths

**DO report**:
- Programming errors (so we can fix the code)
- Product defects where app code caused data loss, corruption, an impossible
  state, or an unrecoverable flow
- Data corruption only when evidence points to an app bug or unsupported schema
  migration, not when it is user-authored invalid content

**Reference**: https://docs.sentry.io/platforms/flutter/configuration/filtering/

---

### Privacy Sanitization

**Purpose**: Remove all PII before sending to Sentry while **preserving actionable debugging context** (privacy is a feature).

**The "Redacted Report" Pattern**:

Provide **structural context** without **exposing content**:

**✅ INCLUDE (Safe Metadata)**:
- Error type: `FileSystemException`, `FormatException`
- Operation context: `read_campaign`, `parse_fate_chart`
- Resource identifiers: Hashed or truncated IDs (e.g., last 4 chars)
- Data structure issues: Field names without values ("Missing required field 'chaosFactor'")
- Validation failures: Constraints without actual values ("Value out of range [1-9]")
- Collection sizes: Counts and lengths ("Expected 9 items, got 5")
- Timestamps: When error occurred
- Layer/component: Where in architecture

**❌ REDACT (User Data)**:
- Campaign names, descriptions, content
- Character names, attributes, notes
- User-generated text (questions, journal entries)
- File paths containing usernames
- Actual data values (chaos factor numbers, dice roll results)

**Principle**: Report context that helps fix bugs (structure, types, counts) but never content that reveals user activity (names, text, actual values).

**Critical Sentry Configuration**:
- `sendDefaultPii = false` - Prevent automatic PII capture
- `attachScreenshot = false` - Screenshots may contain user content
- `attachViewHierarchy = false` - UI hierarchy may reveal sensitive state
- Implement `ErrorReportingService.beforeSend` for transport-level filtering
- Keep all `ErrorReportingService.recordError(...)` properties sanitized at the call site

**Reference**: https://docs.sentry.io/platforms/flutter/data-management/sensitive-data/

---

## Testing Error Scenarios

### Test Infrastructure Failures

**Pattern**:
```dart
test('throws StorageException on file error', () async {
  when(() => mockStorage.readFile(any()))
      .thenThrow(FileSystemException('File not found'));

  expect(
    () => repository.getCampaign('test-id'),
    throwsA(isA<StorageException>()),
  );
});

test('reports error through ErrorReportingService with context', () async {
  when(() => mockStorage.readFile(any()))
      .thenThrow(FileSystemException('Permission denied'));

  try {
    await repository.getCampaign('test-id');
  } on StorageException {
    // expected
  }

  expect(recordedErrors, hasLength(1));
  expect(recordedErrors.single.error, isA<FileSystemException>());
  expect(recordedErrors.single.reason, contains('CampaignRepository'));
});
```

### Test Validation Logic

**Pattern**:
```dart
test('returns Invalid when campaign name is empty', () {
  final result = validateCampaignName('');

  expect(result, isA<EmptyCampaignName>());
});

test('returns Valid when campaign name is acceptable', () {
  final result = validateCampaignName('My Campaign');

  expect(result, isA<ValidCampaignName>());
});
```

### Test AsyncValue Error States

**Read path — query provider enters error state on repository failure**:
```dart
test('campaign provider enters error state on repository failure', () async {
  when(() => mockRepository.getCampaign(any()))
      .thenThrow(StorageException('read'));

  final container = ProviderContainer.test(
    overrides: [
      campaignRepositoryProvider.overrideWithValue(mockRepository),
    ],
  );

  // Query provider automatically wraps the error in AsyncValue.error
  await expectLater(
    container.read(campaignProvider(campaignId: 'test-id').future),
    throwsA(isA<StorageException>()),
  );
});
```

**Write path — mutation controller state transition on failure**:
```dart
test('updateCampaign enters error state on repository failure', () async {
  when(() => mockRepository.updateCampaign(any()))
      .thenThrow(StorageException('write'));

  final container = ProviderContainer.test(
    overrides: [
      campaignRepositoryProvider.overrideWithValue(mockRepository),
    ],
  );

  final listener = Listener<AsyncValue<void>>();
  container.listen(campaignControllerProvider, listener.call,
      fireImmediately: true);

  // Verify initial idle state
  verify(() => listener(null, const AsyncData<void>(null)));

  // Trigger mutation
  await container
      .read(campaignControllerProvider.notifier)
      .updateCampaign(testCampaign);

  // Verify state transition: data → loading → error
  verifyInOrder([
    () => listener(
          const AsyncData<void>(null),
          any(that: isA<AsyncLoading<void>>()),
        ),
    () => listener(
          any(that: isA<AsyncLoading<void>>()),
          any(that: isA<AsyncError<void>>()),
        ),
  ]);
});
```

**Requirements**:
- ✅ Test all error paths (100% coverage)
- ✅ Verify errors are transformed correctly
- ✅ Verify expected external/runtime conditions do **not** call the
  `ErrorReportingService.recordError` seam
- ✅ Verify `ErrorReportingService.recordError` is called only for
  programming/product defects
- ✅ Test AsyncValue error states in controllers
- ❌ Don't test programming errors (those should never happen)

**Reference**: https://docs.flutter.dev/testing

---

## Migration Strategy

### Phase 1: Foundation (Week 1)
- ✅ Set up Sentry with privacy configuration
- ✅ Create exception hierarchy (`app_exception.dart`)
- ✅ Create utility/reporting files (`async_value_ui.dart`, `error_reporting_service.dart`)
- ✅ Update `main.dart` with global error handlers

### Phase 2: Data Layer (Week 2)
- ✅ Audit all repository implementations
- ✅ Add try-catch for infrastructure exceptions only
- ✅ Transform to domain exceptions
- ✅ Add `ErrorReportingService.recordError(...)` with context
- ✅ Remove any catches of `Error` types

### Phase 3: Presentation Layer (Week 3)
- ✅ Audit all controllers — split data-fetching controllers into query providers (read path) and mutation controllers returning `FutureOr<void>` (write path)
- ✅ Remove broad controller exception translation; use `AsyncValue.guard` for user-visible mutations and typed catches only for UI-specific context/recovery branching
- ✅ Add `ref.mounted` checks after every `await` in mutation controllers
- ✅ Add error display with `ref.listen()` or `AsyncValueWidget`
- ✅ Test all error states

### Phase 4: Validation Refactor (Week 4)
- ✅ Identify validation exceptions (anti-pattern)
- ✅ Replace with result types
- ✅ Update UI to handle validation results
- ✅ Remove validation exceptions from exception hierarchy

### Phase 5: Testing (Ongoing)
- ✅ Write tests for all error scenarios
- ✅ Achieve 100% coverage including error paths
- ✅ Verify Sentry integration in tests

---

## Reference Links

### Official Documentation
- **Dart Error Handling**: https://dart.dev/language/error-handling
- **Dart Futures Error Handling**: https://dart.dev/libraries/async/futures-error-handling
- **Flutter Error Handling**: https://docs.flutter.dev/testing/errors
- **Riverpod AsyncValue**: https://riverpod.dev/docs/concepts/async_value
- **Sentry Flutter SDK**: https://docs.sentry.io/platforms/flutter/
- **Sentry Privacy**: https://docs.sentry.io/platforms/flutter/data-management/sensitive-data/

### Community Resources
- **Andrea Bizzotto - Exception Handling**: https://codewithandrea.com/articles/flutter-exception-handling-try-catch-result-type/
- **Andrea Bizzotto - AsyncValue Widget**: https://codewithandrea.com/articles/async-value-widget-riverpod/
- **Formz Package**: https://pub.dev/packages/formz

### Internal Documentation
- **Architecture Guide**: `docs/architecture/ARCHITECTURE_GUIDE.md`
- **Decisions**: `docs/architecture/DECISIONS.md` (Decisions 12, 39, and 42)
- **Layer-Specific Guidance**: `lib/src/features/*/AGENTS.md`

---

## Key Takeaways

### What We Catch
✅ Recoverable runtime exceptions at data layer boundaries (FS edge classification)
✅ Transform to domain exceptions or sealed owner results with user-friendly messages
✅ Report to Sentry only for programming/product defects ("Will I fix it?")
✅ User-visible mutation failures via sealed reject → Save `AsyncError`, or optional predicate-limited `AsyncValue.guard()` for remaining throws

### What We Don't Catch
❌ Programming errors (`Error` types) - let them crash
❌ User input validation - use result types
❌ Empty results - return null or empty lists
❌ Business rule violations from user input - use result types
❌ Ordinary local / iCloud-folder journal persist failures on an owned mutation path - sealed reject at the mutation owner
❌ Non-blocking degraded storage/cloud states - model as typed state, fallback, or recovery workflow
❌ Offline network, DNS failures, store/backend outage, permissions, and other
external user/device/environment conditions - model as typed state, fallback,
breadcrumb, or user feedback

### Patterns We Use
✅ Read path: `FutureProvider`/`StreamProvider` for data fetching with explicit retry policy where failures matter
✅ Retry-aware UI: inspect `AsyncValue.retrying` when distinguishing initial loading from retry backoff
✅ Write path (preferred): sealed mutation result + `switch` → `AsyncData` / `AsyncError` in Save controllers
✅ Write path (optional): predicate-limited `AsyncValue.guard()` only when a lower boundary still throws `AppException`
✅ Fast local write path: narrow mutation methods without extra state when failure is not meaningfully actionable at that UI surface
✅ `ref.mounted` checked after every `await` in mutation controllers
✅ `AsyncValue.value` or exhaustive `AsyncValue` pattern matching for nullable/readiness-aware data access
✅ Abstract exception base class with typed subclasses per feature
✅ Extension methods for error display (`ref.listen()` for mutation side effects)
✅ Privacy-first Sentry configuration
✅ Blocking-vs-non-blocking triage before startup, storage, and cloud gates surface errors

### Patterns We Do Not Preserve
❌ Compatibility shims for old framework/package/internal APIs
❌ `valueOrNull` for `AsyncValue` access in new or touched code
❌ Compensating try/catch/rethrow theater (optimistic rollback, nested rename undo)
❌ Throwing sealed rejects so guard can catch them
❌ Broad `on Exception` catch in Presentation or Application as a default pattern

### Quality Standards
✅ 100% test coverage includes error paths
✅ All infrastructure exceptions have tests
✅ All validation logic has tests
✅ Sentry integration tested with mocks

---

**Date Last Reviewed**: June 10, 2026
**Version**: 2.1.0
**Status**: Approved — Updated for ownership escalation alignment with ARCHITECTURE_GUIDE.md
