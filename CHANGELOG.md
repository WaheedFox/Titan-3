# Changelog

All notable changes to titan-framework are documented here.

---

## [Unreleased]

_No unreleased changes._

## [1.0.0b1] - 2026-08-11

Titan B1 (`1.0.0b1`) is the first public baseline. Earlier alpha versions are
historical pre-releases, not earlier public baselines.

### Packaging

- The distribution package is named `titan-framework`.
- The Python import path remains `titan`, so existing
  `from titan import ...` code is unchanged.
- The source distribution contains only the package source and the files
  required to build and identify the release.
- Tests, documentation, examples, ecosystem material, and development-only
  project files are excluded from release artifacts.

### Fixed

- `AliasMap.register()` now fails fast with `TitanError` when an alias
  conflicts with an existing `Context` attribute.
- Middleware return values now produce a runtime warning because they are
  ignored by the framework contract.
- Startup `get_me()` failures now produce a warning instead of being silently
  swallowed.
- Documentation and examples use `AliasMap` and `fetch_permissions()`.

### Added

- **Titan Atlas** (`titan.atlas`) — a deterministic architectural knowledge
  layer with `search()`, `explain()`, `rules()`, and `decisions()`.
- **Performance Profiler** (`titan.profiler`) for measuring update handling
  time in a controlled environment.
- **Message Links Protocol** for stable, addressable identities for sent
  messages.
- **Runtime Contract Validator** for validating handler registrations when
  they are declared.

### Runtime Semantics

- Per-chat update dispatch advances the polling offset when an update is
  accepted for processing, so a handler waiting for an `ask()` response does
  not block polling.

## [1.0.0a2] - 2026-07-18

Alpha patch release. No new features or architectural changes.

### Fixed

- Corrected the aliases documentation in the Arabic and English READMEs.
- Corrected the permissions API documentation and moderation example.

## [1.0.0a1] - 2026-07-01

First public alpha pre-release, preceding the Titan B1 public baseline. The
public API is stable and contract-frozen.

### Public API

- `Titan` — core bot class.
- `Router` — code organization tool for splitting handlers across files.
- `InlineKeyboard` / `InlineButton` — inline keyboard builders.
- `TitanError` / `TelegramError` — error types.

### Bot Methods

- `bot.on(event)` — raw event handler.
- `bot.command(name)` — command handler.
- `bot.callback(data)` — inline button handler.
- `bot.middleware` — pre-handler middleware.
- `bot.include(router)` — merge a router into the bot.
- `bot.run()` / `bot.run_async()` — entry points.
- `bot.telegram` — direct Telegram API adapter.

### Known Sharp Edges

- Including a router can leave earlier event handlers registered if a later
  command conflicts.
- An empty `callback_data` registers successfully but is never matched.
- The README documents additional safeguards that are intentionally not
  enforced automatically.