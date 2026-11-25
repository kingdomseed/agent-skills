# Bloc translation of the canonical error policy

Read references/error-handling.md first. This file translates its Riverpod
presentation examples into Bloc terms. It does not replace the canonical rules.

## Direct translation

| Canonical idea | Bloc form |
|---|---|
| Query provider exposes loading, data, and failure | Bloc event or repository subscription emits typed loading, success, and failure state |
| Mutation controller owns user-visible save state | Feature Bloc owns in-progress, committed, and rejected state |
| Sealed mutation result plus exhaustive switch | Bloc event handler awaits the owner, switches on the sealed result, and emits the matching state |
| ref.listen shows a snackbar or dialog | BlocListener handles the side effect |
| Provider lifecycle owns cancellation | Bloc event transformer and Bloc.close own cancellation and disposal |
| ProviderContainer test | blocTest with a fake or mocked repository |
| Global provider error observer | BlocObserver.onError plus Flutter's global handlers |

## Preferred write flow

1. Emit in-progress state.
2. Await the one mutation owner.
3. Switch exhaustively on its sealed committed or rejected result.
4. Emit success or a typed user-recovery state.
5. Let BlocListener show the message or recovery action.

Do not throw a rejection so a catch block can turn it back into state.

## Exceptions

- Let programming Error objects escape to BlocObserver and global handlers.
- Never catch StateError, ArgumentError, RangeError, TypeError, or Object.
- Let the data boundary catch precise infrastructure exceptions and transform
  them into an app-owned typed exception or sealed result.
- Catch a precise app-owned Exception in a Bloc only when that Bloc is the one
  recovery owner and the lower boundary still uses exceptions.
- Emit expected network, permission, availability, validation, and save
  outcomes as typed state. Do not call addError or Sentry for them.
- Let app defects escape so the global reporting owner can record them once.

The generic Bloc pattern catch (error, stackTrace) is broader than this
project's policy. Do not copy it.

## Async ownership

- Use sequential, droppable, or restartable event transformers to state the
  feature's concurrency rule.
- Cancel subscriptions and timers in close.
- Check the emitter's completion state after awaits when a transformer can
  cancel the handler.
- Keep one owner for each request ID, pending operation, timer, stream, and
  retry path.
- Treat repeated race and lifecycle findings as an ownership problem before
  adding guards.

## Tests

Use blocTest for each event:

- committed result emits in-progress then success;
- each sealed rejection emits its typed recovery state;
- each precise runtime exception maps only at its recovery owner;
- programming Error objects remain unhandled;
- expected external conditions do not reach Sentry or BlocObserver.onError;
- event transformers prove double-tap, restart, and cancellation behavior;
- BlocListener widget tests prove user feedback.
