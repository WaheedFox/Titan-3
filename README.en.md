# Titan

A minimal async Python framework for building Telegram bots.

Titan gives you clean events, readable code, and a stable API that does not change under your feet.

> **Public baseline:** Titan B1 (`1.0.0b1`) is the first public baseline. Earlier alpha versions (`1.0.0a1` and `1.0.0a2`) are historical pre-releases, not earlier baselines.

[![CI](https://github.com/WaheedFox/Titan/actions/workflows/ci.yml/badge.svg)](https://github.com/WaheedFox/Titan/actions/workflows/ci.yml)

> 🇸🇦 [Arabic version ← README.md](README.md)

---

## Installation

Install Titan directly from the official GitHub repository:

```bash
pip install git+https://github.com/WaheedFox/Titan.git
```

---

## Quick Start

```python
from titan import Titan

bot = Titan("YOUR_TOKEN")

@bot.command("start")
async def start(ctx):
    await ctx.reply("Hello! I am ready.")

bot.run()
```

---

## Why Titan?

Titan is for developers who want Telegram bots to stay understandable as they
grow.

- **Explicit routing** — commands, events, callbacks, middleware, and routers
  each have a clear job.
- **A small mental model** — `bot` organizes the application, `ctx` represents
  the current update, and `bot.telegram` is the explicit escape hatch to the
  Telegram API.
- **Predictable async behavior** — updates are assigned to per-chat workers, so
  work in one chat does not automatically serialize unrelated chats.
- **Stable contracts** — the public API, error behavior, and important runtime
  semantics are documented instead of being left to guesswork.
- **Operational visibility** — inspect your bot, check its health, lint its
  design, and investigate update timing before a small issue becomes a
  production mystery.

### If your current framework feels slow or difficult to reason about

Sometimes the problem is not Telegram itself. It is the amount of machinery
between an update and your handler.

Titan is designed for developers who are tired of:

- unrelated chats being held up by work in one chat;
- not knowing where an update was routed;
- large abstractions hiding what a handler actually receives;
- boilerplate growing faster than the bot;
- discovering configuration and registration mistakes only at runtime;
- unclear lifecycle, offset, and restart behavior;
- changing framework behavior that is difficult to track between releases.

Titan does not make network latency, Telegram rate limits, blocking code, or
slow application logic disappear. Its goal is more useful: make the execution
model explicit, isolate unrelated chat work, and give you tools to see what your
bot is doing.

---

## The Titan community

The project is supported by a small, direct community around Waheed's bots,
Titan Library, and related projects. Each space has a different purpose:

<table>
  <tr>
    <td align="center" width="25%">
      <a href="https://t.me/WaheedUpdates">
        <img src="docs/assets/community/waheed-updates.jpg" width="112" alt="Waheed Updates profile picture">
      </a><br>
      <b><a href="https://t.me/WaheedUpdates">Waheed Updates</a></b><br>
      <sub>Official announcements for Waheed's bots, Titan Library, and other projects.</sub>
    </td>
    <td align="center" width="25%">
      <a href="https://t.me/WaheedSupport">
        <img src="docs/assets/community/waheed-support.jpg" width="112" alt="Waheed Support profile picture">
      </a><br>
      <b><a href="https://t.me/WaheedSupport">Waheed Support</a></b><br>
      <sub>The official support group. Check <code>/rules</code> and <code>/help</code> before asking.</sub>
    </td>
    <td align="center" width="25%">
      <a href="https://t.me/WaheedChat">
        <img src="docs/assets/community/waheed-chat.jpg" width="112" alt="Waheed Chat profile picture">
      </a><br>
      <b><a href="https://t.me/WaheedChat">Waheed Chat</a></b><br>
      <sub>Discussion space for Waheed's bots, Titan Library, and related projects.</sub>
    </td>
    <td align="center" width="25%">
      <a href="https://t.me/WaheedMarket">
        <img src="docs/assets/community/waheed-market.jpg" width="112" alt="Waheed Market profile picture">
      </a><br>
      <b><a href="https://t.me/WaheedMarket">Waheed Market</a></b><br>
      <sub>The marketplace for promotions, deals, and ads powered by Waheed.</sub>
    </td>
  </tr>
</table>

Use **Waheed Updates** for releases and announcements, **Waheed Support** for
help, **Waheed Chat** for discussion, and **Waheed Market** for marketplace
activity.

---

## Core Concepts

Titan exposes five ways to interact with your bot. Each has a distinct role.

| Method | Role |
|---|---|
| `bot.on(event)` | Handle raw Telegram events by name |
| `bot.command(name)` | Handle a specific `/command` |
| `bot.callback(data)` | Handle a specific inline button press |
| `bot.middleware` | Run logic before every handler |
| `bot.telegram` | Call Telegram API methods directly |

### `bot.on` — Raw Event Handler

```python
@bot.on("message")
async def on_message(ctx):
    await ctx.reply("Got your message.")

@bot.on("callback")
async def on_callback(ctx):
    await ctx.answer_callback()

@bot.on("channel")
async def on_channel(ctx):
    pass  # channel posts
```

Supported events: `message`, `callback`, `channel`, `new_member`, `left_member`.

### `bot.command` — Command Handler

```python
@bot.command("start")
async def start(ctx):
    await ctx.reply("Welcome!")

@bot.command("help")
async def help(ctx):
    await ctx.reply("Send any message to begin.")
```

### `bot.callback` — Inline Button Handler

```python
@bot.callback("confirm")
async def on_confirm(ctx):
    await ctx.answer_callback("Confirmed.")

@bot.callback("cancel")
async def on_cancel(ctx):
    await ctx.answer_callback("Cancelled.")
```

If no matching `bot.callback` exists, the update falls through to `bot.on("callback")`.

### `bot.middleware` — Pre-Handler Logic

Runs before every handler. Use it for logging, auth checks, and rate limiting.

```python
@bot.middleware
async def logger(ctx, next):
    print(f"Update from user {ctx.user_id}")
    await next()
```

- Call `await next()` to continue to the handler.
- Return without calling `next()` to stop execution.
- Middleware must not contain business logic that belongs in handlers.

### `bot.telegram` — Direct API Access

For operations outside the normal update-response cycle.

```python
await bot.telegram.send_message(chat_id=123, text="Hello from outside a handler.")
await bot.telegram.get_chat_member(chat_id=123, user_id=456)
await bot.telegram.pin_message(chat_id=123, message_id=789)
```

`bot.telegram` bypasses middleware and ctx. It is for explicit, direct API calls only.

---

## Context (`ctx`)

Every handler receives a `ctx` object. It carries the current update's data and the allowed actions.

### Data Properties

```python
ctx.user_id        # int | None — Telegram user ID
ctx.chat_id        # int | None — chat ID
ctx.text           # str | None — message text
ctx.callback_data  # str | None — callback_data from inline button
ctx.is_banned      # bool — whether user_id is in bot.banned_users

ctx.sender         # Sender object: .id, .first_name, .username, .is_bot
ctx.chat           # Chat object: .id, .type, .title, .username
ctx.message        # Message object: .id, .text
```

### Actions

```python
await ctx.reply("Hello")
await ctx.send("Hello")
await ctx.edit("Updated text")          # callback handlers only
await ctx.delete_message()
await ctx.ban_user()
await ctx.leave()
await ctx.answer_callback("Done")
await ctx.fetch_permissions()           # checks bot's delete permission in this chat
```

### Escape Hatch

```python
ctx.raw  # full raw Telegram JSON dict for this update
```

The existence of `ctx.raw` is guaranteed and part of the contract. Its *structure* follows Telegram's API and may change independently of Titan. Use it only when `ctx` does not expose what you need.

---

## Inline Keyboards

```python
from titan import Titan, InlineKeyboard

bot = Titan("YOUR_TOKEN")

@bot.command("start")
async def start(ctx):
    keyboard = (
        InlineKeyboard()
        .row()
        .button("Yes", callback_data="confirm")
        .button("No", callback_data="cancel")
    )
    await ctx.reply("Are you sure?", reply_markup=keyboard)

@bot.callback("confirm")
async def on_confirm(ctx):
    await ctx.answer_callback("Confirmed!")

@bot.callback("cancel")
async def on_cancel(ctx):
    await ctx.answer_callback("Cancelled.")

bot.run()
```

---

## Router

Router lets you split handlers across multiple files, then include them into the main bot.

```python
# admin.py
from titan import Router

router = Router()

@router.command("ban")
async def ban(ctx):
    await ctx.ban_user()
    await ctx.reply("Done.")

@router.callback("confirm_ban")
async def confirm_ban(ctx):
    await ctx.answer_callback()
```

```python
# main.py
from titan import Titan
from admin import router

bot = Titan("YOUR_TOKEN")
bot.include(router)
bot.run()
```

Router supports: `on()`, `command()`, `callback()`.

Router does **not** support: `middleware()` or nested `include()`.

---

## Aliases

`AliasMap` from `titan.extras` lets you define custom names for `ctx` methods within your own project.

```python
from titan.extras.alias import AliasMap

aliases = AliasMap()
aliases.register("say", "reply")
aliases.register("kick", "ban_user")

bot.middleware(aliases.as_middleware())

@bot.on("message")
async def handler(ctx):
    await ctx.say("Hello")  # same as ctx.reply()
    await ctx.kick()        # same as ctx.ban_user()
```

The original method names remain available. Aliases are a naming layer only — they do not change behavior.

`AliasMap` is an independent object — share it across multiple routers:

```python
router1.middleware(aliases.as_middleware())
router2.middleware(aliases.as_middleware())
```

---

## Ban System

```python
bot.banned_users  # set[int] — managed entirely by you

bot.banned_users.add(user_id)
bot.banned_users.discard(user_id)
```

When a user is in `bot.banned_users`, `ctx.is_banned` is `True` before middleware runs. Titan does not act on this automatically — your middleware decides what to do.

```python
@bot.middleware
async def guard(ctx, next):
    if ctx.is_banned:
        return
    await next()
```

---

## Running the Bot

```python
# Synchronous (recommended for most cases)
bot.run()

# Async (when you manage your own event loop)
import asyncio
asyncio.run(bot.run_async())
```

Both entrypoints execute the same internal logic.

---

## Known Sharp Edges

---

### Previously Fixed Issues

#### `bot.include()` — preflight before mutation

If a `Router` contains both event handlers and a command that conflicts with an already-registered command, `bot.include()` checks the entire router before mutating bot state, then raises `TitanError` without partially adding the router.

```python
@bot.command("start")
async def existing(ctx): ...

router = Router()

@router.on("message")
async def handler(ctx): ...  # not added when preflight fails

@router.command("start")
async def conflict(ctx): ...  # causes TitanError

bot.include(router)
# TitanError is raised — no router handlers are added
```

**How to handle it:** Fix the conflict, then retry `include()` with the corrected router.

---

#### `bot.callback("")` — never fires

Registering with an empty string `callback_data` (`""`) succeeds without error, but the handler is never invoked when an update arrives with `callback_data=""`. The internal routing logic treats `""` as absent data.

```python
@bot.callback("")        # registers successfully
async def handler(ctx):  # never called
    ...
```

**How to handle it:** Never use an empty string as `callback_data`. Always use a descriptive value such as `"noop"` or `"skip"`.

---

### Missing Safeguards (valid behavior, no protection)

These are not bugs — Titan behaves consistently in each case. The framework does not guard against the following misuse patterns:

**Calling `next()` twice in middleware**
Causes every handler to execute twice. Titan does not detect this. Rule: call `next()` exactly once per middleware function.

**Registering a command with a leading slash: `bot.command("/start")`**
Registers successfully but never matches any update. The correct form is `"start"` without the slash.

**Registering `error_handler` more than once**
Titan keeps one error-handler slot per bot. The last registration replaces the
previous one and handles subsequent unhandled exceptions. This is intentional;
no warning or exception is issued.

**`AliasMap.register()` using a name that already exists on `ctx`**
`AliasMap.register()` checks the alias name against properties and methods defined on `Context` and raises `TitanError` for those conflicts. This check does not cover every instance attribute, such as `raw`, `sender`, `chat`, `message`, `permissions`, and `is_banned`.

```python
aliases.register("text", "reply")
# TitanError — text is an attribute on Context
```

Choose names that do not conflict with `Context` attributes or instance attributes.

**Passing `async def` to `on_offset`**
`on_offset` expects a plain synchronous callable. Passing an `async def`
raises `TitanError` before polling starts, so Titan never creates and discards
an un-awaited coroutine.

```python
async def save(offset):    # wrong — async function
    ...

bot.run(on_offset=save)    # raises TitanError before polling starts
```

Use a plain function. If you need async work inside it, schedule it explicitly onto a running event loop.

---

## Philosophy

Titan is a stability-driven framework.

- Simple things are simple.
- Complex things remain possible via `bot.telegram`.
- The public API does not change without a version bump.
- No hidden behavior. No magic. No feature race.

---

## Contributing

Titan is built by people who care about clear APIs, durable decisions, and
honest documentation.

- [Contributing guide](CONTRIBUTING.md)
- [The Titan Ledger](CONTRIBUTORS.md)

---

## License

**W.A.S.L v1.0** — Waheed Accessible Source License
See [LICENSE](LICENSE) for full terms.

---

© Copyright by **Waheed**. All rights reserved.
*(Alien's Zone ~ building real robots to help humanity thrive and stay alive! ^^)*
