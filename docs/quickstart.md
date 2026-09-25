# Quickstart

This guide gets a working Titan bot running from scratch.

---

## Requirements

- Python 3.10 or later
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

---

## Installation

Install Titan directly from the official GitHub repository:

```bash
pip install git+https://github.com/WaheedFox/Titan.git
```

---

## Your First Bot

```python
from titan import Titan

bot = Titan("YOUR_TOKEN")

@bot.on("message")
async def echo(ctx):
    await ctx.reply(ctx.text or "...")

bot.run()
```

Run the file. Send any message to your bot. It replies.

`ctx` is the object your handler receives for every update. It carries the incoming data and the actions available to respond.

→ To understand how `ctx` fits into the bigger picture: [concepts/mental_model.md](concepts/mental_model.md)

---

## Handling Commands

Use `@bot.command` to handle a specific `/command`.

```python
from titan import Titan

bot = Titan("YOUR_TOKEN")

@bot.command("start")
async def start(ctx):
    await ctx.reply("Hello! Send me a message.")

@bot.command("help")
async def help(ctx):
    await ctx.reply("I respond to /start and /help.")

bot.run()
```

Each command maps to exactly one handler. Registering the same command twice raises an error.

---

## Inline Keyboards

Use `InlineKeyboard` to attach buttons to a message.

```python
from titan import Titan, InlineKeyboard

bot = Titan("YOUR_TOKEN")

@bot.command("start")
async def start(ctx):
    keyboard = (
        InlineKeyboard()
        .row()
        .button("Yes", callback_data="answer_yes")
        .button("No", callback_data="answer_no")
    )
    await ctx.reply("Are you ready?", reply_markup=keyboard)

bot.run()
```

`.row()` starts a new row of buttons. `.button()` adds a button to the current row.

→ For the full keyboard API: [reference/keyboard.md](reference/keyboard.md)

---

## Handling Button Presses

Use `@bot.callback` to handle a specific button press by its `callback_data`.

```python
from titan import Titan, InlineKeyboard

bot = Titan("YOUR_TOKEN")

@bot.command("start")
async def start(ctx):
    keyboard = (
        InlineKeyboard()
        .row()
        .button("Yes", callback_data="answer_yes")
        .button("No", callback_data="answer_no")
    )
    await ctx.reply("Are you ready?", reply_markup=keyboard)

@bot.callback("answer_yes")
async def on_yes(ctx):
    await ctx.answer_callback()
    await ctx.edit("Great, let's go.")

@bot.callback("answer_no")
async def on_no(ctx):
    await ctx.answer_callback()
    await ctx.edit("No problem.")

bot.run()
```

`ctx.answer_callback()` dismisses the loading indicator on the button. `ctx.edit()` replaces the message text in place.

---

## Running the Bot

```python
# Synchronous — recommended for most cases
bot.run()

# Async — when you manage your own event loop
import asyncio
asyncio.run(bot.run_async())
```

Both execute the same internal logic.

---

## What's Next

| I want to... | Go to |
|---|---|
| Understand how Titan is structured | [concepts/mental_model.md](concepts/mental_model.md) |
| Learn how `ctx` works in depth | [concepts/ctx.md](concepts/ctx.md) |
| Add logic that runs before every handler | [concepts/middleware.md](concepts/middleware.md) |
| Split handlers across multiple files | [reference/api.md](reference/api.md) — Router section |
| See the full API | [reference/api.md](reference/api.md) |
