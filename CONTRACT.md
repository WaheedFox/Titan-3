# Titan Framework Contract (v1)

هذا الملف يحدد السلوك الرسمي لمكتبة Titan.

أي تغيير في السلوك الظاهر للمطور يعتبر breaking change إلا إذا تم تحديث هذا الملف.

---

# 0. Core Philosophy — Dual Entry (Hands Model)

Titan allows multiple entrypoints for the same capability.

Each entrypoint is valid, supported, and official.

### Principle

- Multiple ways to access the same behavior are allowed.
- No difference in runtime behavior between entrypoints.
- Entrypoints differ only in usage style, not in system logic.

### Example

run() and run_async() are both valid entrypoints to the same execution engine.

- run() → synchronous convenience entrypoint
- run_async() → native async entrypoint

Both execute the same internal logic.

### Alias Consistency Rule

If multiple names exist for the same operation:

- All aliases must map to the same underlying implementation
- No alias is allowed to introduce new behavior
- No alias is allowed to bypass system rules

### Design Rule

Titan prioritizes:

- Developer choice of expression
- Consistent internal behavior
- Zero duplication of logic paths

NOT:

- Multiple implementations for the same feature
- Hidden behavioral differences between entrypoints

---

# 1. Public API

يميز Titan بين ثلاث طبقات من السطح العام:

1. **Core Contractual API** — واجهات عامة يضمنها العقد الرسمي في v1.
2. **Intentionally Public Support API** — واجهات مقصودة وقابلة للاستخدام في حالات محددة، لكنها لا تحصل تلقائياً على نفس ضمانات Core Contractual API.
3. **Convenience Exports** — exports لتسهيل الوصول أو introspection، ولا تُعد جزءاً من Core contract لمجرد وجودها في `titan.__all__`.

التصنيف هنا يحدد مستوى الضمان والاستقرار، وليس طريقة التصدير فقط.
وجود symbol في `titan.__all__` يعني أن تصديره مقصود، لكنه لا يجعله Core Contractual API تلقائياً.

## 1.1 Core Contractual API

الاستيراد الرسمي المضمون في v1:

```python
from titan import Titan
from titan import Router
from titan import InlineKeyboard
from titan import InlineButton
from titan import TitanError
from titan import TelegramError
from titan import RichContent
```

هذه الأسماء هي Core Contractual API. أي تغيير في واجهتها أو سلوكها الموثق يخضع لقواعد هذا الـ CONTRACT ويُعامل كتغيير تعاقدي.

تظل الأقسام التفصيلية اللاحقة الخاصة بـ `InlineButton` و`RichContent` جزءاً من هذا القسم، وتحدد قواعد استخدامهما الحالية.

هذا القسم يحدد سطح الاستيراد الرسمي لـ Core API فقط. ضمانات عامة إضافية — مثل
`ctx.raw` و`model.raw` و`model.to_dict()` — موثَّقة في أقسامها المعنية من هذا
الـ CONTRACT.

لا يُفترض أن أي symbol آخر يصبح جزءاً من Core Contractual API لمجرد أنه قابل
للاستيراد من `titan` أو موجود في `titan.__all__`.

### InlineButton

`InlineButton` نوع بيانات عام (public type) يمثل زراً واحداً داخل لوحة المفاتيح.

```python
from titan import InlineButton
```

المسار المُفضَّل لإنشائه هو عبر `InlineKeyboard` builder:

```python
InlineKeyboard().row().button("نعم", callback_data="yes")
```

الإنشاء المباشر مسموح به ومدعوم — مفيد عند type annotation أو بناء لوحة مفاتيح برمجياً:

```python
btn: InlineButton = InlineButton(text="نعم", callback_data="yes")
```

كلا المسارين ينتجان نفس الكائن. لا فرق في السلوك.

يجب أن يحتوي الزر على إجراء مدعوم واحد بالضبط:

- `callback_data` فقط — مقبول.
- `url` فقط — مقبول.
- غياب كليهما — يرفع `TitanError` عند الإنشاء.
- وجود كليهما — يرفع `TitanError` عند الإنشاء.

ينطبق هذا التحقق على الإنشاء المباشر وعلى `InlineKeyboard.button()`،
ويحدث قبل إنشاء payload أو إرسال أي طلب إلى Telegram.

### RichContent

`RichContent` قيمة public تمثل mode واحداً من outgoing rich content:

```python
from titan import RichContent

RichContent.html(markup)
RichContent.markdown(markup)
RichContent.blocks(blocks)
```

القواعد:

- كل قيمة تختار mode واحداً صراحةً: `html` أو `markdown` أو `blocks`.
- لا يحوّل Titan HTML إلى Markdown أو العكس، ولا ينشئ parser أو canonical AST.
- لا يوجد constructor عام يقبل payload غير محدد، ولا تُقبل `dict` عادية
  كـ RichContent ضمن أفعال `ctx`.
- `RichContent.blocks()` تقبل ordered `Sequence` من `Mapping` values؛ تُستبعد
  `str` و`bytes` وmapping المفرد وone-shot iterators.
- لا يُشترط وجود `type` في block، وتبقى empty sequences وempty mappings
  صالحة من ناحية Titan shape. صلاحية Telegram النهائية مسؤولية Telegram.
- unknown fields داخل block mappings محفوظة ولا يُعاد تفسيرها.

`RichContent` تمثل المحتوى والتحقق الخاص به؛ لا تملك public serialization
method ولا ترسل أو تعدل الرسائل.

## 1.2 Intentionally Public Support API

الأسماء التالية exports مقصودة وقابلة للاستخدام العام في حالات الدعم الموثقة:

```python
from titan import HealthFinding
from titan import HealthLevel
from titan import BotSnapshot
```

- `HealthFinding` و`HealthLevel` مرتبطان بنتيجة `bot.health()`.
- `BotSnapshot` هو نوع الإرجاع الوصفي لـ `bot.inspect()`.

هذه الأسماء ليست accidental exports، لكنها أيضاً ليست جزءاً من Core Contractual
API. وجودها في `titan.__all__` يثبت قصد التصدير، ولا يرفعها تلقائياً إلى
مستوى Core contract.

Support API مدعومة للاستخدام في الحالات الموثقة أعلاه. هذا يعني أن المطور
يستطيع الاعتماد على وجودها واستخدامها ضمن تلك الحالات، لكنه لا يعني أنها
تحصل تلقائياً على نفس ضمانات الثبات الممنوحة لـ Core Contractual API.

هذا القسم ليس Contract ثانياً مخفياً. وهو لا يجمّد كل تفاصيل التنفيذ، ولا يمنع
كل تغيير مستقبلي في Support API. Support API ليست جزءاً من Core Contract،
وأي تغيير مقصود عليها يجب أن يكون متوافقاً مع قرار المشروع ووثائقه ذات الصلة،
دون أن يترتب على ذلك مستوى الضمان الممنوح لـ Core Contractual API.

## 1.3 Convenience Exports

`__version__` export مريح للوصول إلى إصدار الحزمة:

```python
from titan import __version__
```

`__version__` ليس جزءاً من Core Contractual API ولا من Intentionally Public
Support API. وجوده في `titan.__all__` يسهّل introspection والوصول إلى metadata،
لكنه لا يمنحه contractual stability guarantee.

---

# 2. Core Principle

- No hidden side effects
- Deterministic execution
- ctx is the only execution point within an update-response cycle. Operations outside the update-response cycle use bot.telegram (see §14).

---

# 3. Context (ctx)

Allowed actions:
- reply()
- send()
- edit() (callback only)
- delete_message()
- ban_user()
- leave()
- answer_callback()
- fetch_permissions() → populates ctx.permissions (ChatPermissions)

Rules:
- لا وصول مباشر لـ Telegram API
- Message / Update / Chat / Sender = data-only

### RichContent in ctx actions

`ctx.send()`, `ctx.reply()`, و`ctx.edit()` تقبل `str | RichContent` في
المعامل المسمى `text`:

- `str` تحافظ على text transport الحالي.
- `RichContent` تُرسل بحسب mode الذي اختاره constructor.
- `ctx.send(RichContent.html(...))` و
  `ctx.send(text=RichContent.html(...))` كلاهما مدعومان.
- اسم المعامل يبقى `text`؛ لا يوجد `content=` ولا `send_rich()` أو
  `reply_rich()` أو `edit_rich()`.
- `parse_mode` لا تُستخدم مع `RichContent`؛ الجمع بينهما يرفع `TitanError`
  قبل Telegram.
- `reply_markup` سطح مستقل ولا يصبح جزءاً من `RichContent`.
- `None` ليست outgoing content صالحة لهذه الأفعال.
- `ctx.edit()` تبقى callback-only.

### RichContent submission boundary

في أفعال `send` و`reply` و`edit` الأساسية، يثبت Titan owned
transport-content snapshot قبل أول network await:

- mutation قبل boundary قد تظهر في الطلب.
- بعد إنشاء snapshot لا تؤثر mutation اللاحقة في input object على الطلب الجاري.
- nested mappings/lists تصبح مستقلة عن input graph عند boundary.
- قبل network، يجب أن تكون قيم المحتوى قابلة للتمثيل داخل snapshot
  مستقل يملكه Titan. أي قيمة لا يستطيع request boundary materializeها
  لهذا الطلب تُرفض بـ `TitanError` قبل network.
- لا يعرّف هذا العقد طريقة التحويل أو protocol عاماً للقيم المخصصة؛
  دعم أي opaque object بعينه يبقى implementation detail ما لم يوثَّق
  بشكل مستقل.
- خوارزمية النسخ الداخلية ليست public contract، ولا توجد
  `RichContent.serialize()` method عامة.

### ctx.raw — Escape Hatch

- ctx.raw يكشف raw JSON الكامل القادم من Telegram على مستوى الـ update
- وجود ctx.raw مضمون وجزء من الـ contract
- ctx.raw intentionally exposes Telegram's native payload. Titan guarantees the existence of this access point, but not the structure of the payload itself, because that structure is defined by Telegram and may evolve independently of Titan.
- استخدمه فقط عند الحاجة لبيانات غير متاحة عبر ctx مباشرة
- لا تبني منطقاً دائماً يعتمد على حقول بعينها داخل ctx.raw

### model.raw — Scoped Escape Hatch

ينطبق على: Message.raw / Sender.raw / Chat.raw / RichMessage.raw

- وجود .raw على كل نموذج مضمون وجزء من الـ contract
- يكشف القاموس الخام المقطوع من الـ update لذلك النموذج تحديداً
- يختلف عن ctx.raw في النطاق: ctx.message.raw يعطيك قاموس الرسالة مباشرة بغض النظر عن بنية الـ update الخارجية
- model.raw intentionally exposes Telegram's native payload scoped to that model. Titan guarantees the existence of this access point on every model, but not the structure of the payload itself, because that structure is defined by Telegram and may evolve independently of Titan.
- لا تبني منطقاً دائماً يعتمد على حقول بعينها داخل model.raw

### model.to_dict() — Serialization Contract

ينطبق على: Message.to_dict() / Sender.to_dict() / Chat.to_dict() /
RichMessage.to_dict()

- وجود to_dict() على كل نموذج مضمون وجزء من الـ contract
- الغرض منها: serialization — تحويل النموذج إلى قاموس للتسجيل أو التخزين أو التكامل مع أنظمة خارجية
- تنفيذها اليوم يعكس .raw، لكن قد تتضمن في المستقبل حقولاً محسوبة تُضيفها Titan
- For fields originating from Telegram, the same principle applies: Titan guarantees the method exists, not the structure of what Telegram sends.

### Message.rich_message

`message.rich_message` هو `RichMessage | None` ويعرض incoming rich content
كـ data-only read model:

- Rich messages تدخل message route الحالي؛ لا يوجد event أو update route جديد.
- `Message.text` يمكن أن يكون `None` عندما لا تصل رسالة نصية.
- `RichMessage.mode` هو mode المعروف إذا كان واضحاً؛ mode غير المعروف لا
  يُحوّل إلى mode معروف.
- `RichMessage.raw` يحتفظ بالـ raw rich representation، بما فيها raw block
  mappings وunknown fields.
- `RichMessage.to_dict()` يعيد نفس representation الواردة، ولا ينشئ
  outgoing envelope أو text projection.
- `RichMessage` لا تملك methods للإرسال أو التعديل أو التحويل، ولا تُقبل
  مكان `RichContent` في أفعال outgoing بلا تحويل صريح.
- لا يضمن `RichMessage` immutable snapshot مستقلاً عن contract الحالي
  لـ `model.raw`.

---

# 4. Event System

- message
- callback
- channel
- new_member
- left_member

Semantic events must not overlap with message handler.

### Unrouted Updates

Updates that Titan does not recognise as any of its supported event types are silently dropped.

- They are not passed to any handler — including `on("message")`.
- They are not treated as errors and do not invoke the error handler.
- They do not affect polling or the update offset.

This applies equally to update types that are *unsupported* (known to Telegram but not yet routed by Titan) and *unknown* (added by Telegram after this version was built).

---

# 5. Registration Rules

### Routing Key Principle

A routing key is the value Titan uses to select exactly one handler for an incoming update.

Registration types that define a routing key:
- **command name** — selects the handler for `/command` messages
- **callback_data** — selects the handler for callback_query updates

Each routing key must be unique across the entire bot instance, regardless of whether it was registered directly on the bot or via any router.

Attempting to register a second handler for an existing routing key raises `TitanError` at registration time, not at runtime.

### Internal State Rule

`bot.commands`, `bot.handlers`, `bot.callback_handlers` are internal state exposed for inspection only.

Direct assignment (`bot.commands = {}`) or direct mutation (`bot.commands["x"] = fn`) bypasses all registration validation, duplicate detection, and source tracking. This is unsupported — behavior is undefined.

Use `@bot.command()`, `@bot.on()`, `@bot.callback()`, and `bot.include(router)` as the only supported registration paths.

### Error-handler registration

Each bot instance has exactly one error-handler slot.

- `@bot.error_handler` and `bot.error_handler(fn)` use the same slot.
- Registering another error handler replaces the previous one.
- The last registration is the handler used for subsequent unhandled exceptions.
- This replacement is intentional and does not emit a warning or raise `TitanError`.

### Fan-Out Registration

`@bot.on(event)` does not define a routing key.

It registers a handler into a fan-out list for that event type. All registered handlers for an event are called in registration order. Multiple handlers for the same event type are expected behavior, not a conflict.

### Router Instance Integrity

Each Router instance may be passed to `bot.include()` exactly once.

Passing the same Router instance twice raises `TitanError`.

This rule is independent of routing-key uniqueness. Two distinct Router instances are not restricted relative to each other — only their routing keys must remain globally unique.

---

# 6. Callback Routing

- @bot.callback(data) has priority over @bot.on("callback")
- If no @bot.callback(data) matches the incoming callback_data, the update falls through to @bot.on("callback") if registered
- Duplicate callback_data registration is governed by §5

---

# 7. Long Polling

- exponential backoff:
  1s → 2s → 4s → 8s → 16s → 30s
- reset on success — success is defined as get_updates() returning without raising an exception, including when the result list is empty. Only an exception triggers backoff.

---

# 8. Offset Handling

- external responsibility
- bot.run(offset=...) — synchronous entrypoint
- bot.run_async(offset=...) — async entrypoint (see §0)
- bot.offset available for persistence
- bot.offset reflects the highest update_id accepted by Titan for processing, not necessarily the last update whose handler has completed. Once an update is enqueued, Titan takes responsibility for executing it — the offset advances regardless of whether the handler has run yet.

### on_offset Hook

- Signature: `Callable[[int], None]`
- Must be synchronous — not a coroutine
- Passing an async function or async callable object raises `TitanError`
  before polling starts; no coroutine is created or discarded.
- Called once per update, after the update has been dispatched to its chat queue and bot.offset has been updated
- Receives the current offset value as its only argument
- Guaranteed call order per update: update dispatched → bot.offset updated → on_offset(offset)
- Note: dispatch means the update has been accepted and queued for processing; handler completion may follow asynchronously
- If a synchronous callback raises, the polling loop treats it as a polling
  error and applies its normal backoff.
- If no on_offset is provided, offset management is entirely the developer's responsibility via bot.offset

### Lifecycle Ownership and Shutdown

These rules apply to updates accepted by the `run()` / `run_async()` polling
engine:

- An update is **accepted** when Titan has either placed it on its per-chat
  dispatch queue or created the direct handler task for an update without a
  chat. Once accepted, the update is Titan's responsibility even if its handler
  has not started or completed.
- Lifecycle ownership includes every chat worker and every update-handler task
  created as a consequence of polling, for both the per-chat and direct-update
  paths. Titan owns those tasks until they finish, are cancelled, and their
  results or exceptions have been observed.
- `feed_update()` is a separate direct-processing entrypoint. The caller owns
  the coroutine used to call it; work started by that caller is not part of the
  polling lifecycle contract.
- Per-chat dispatch-start order remains FIFO. Handler completion order remains
  concurrent and is not guaranteed.

When polling stops, shutdown follows this order:

1. Titan stops accepting new updates from polling.
2. Existing per-chat queues are allowed to reach their shutdown sentinel in
   arrival order. No update accepted before the stop is silently removed from
   the queue.
3. Titan gives already accepted handler tasks a bounded opportunity to finish.
   Handler tasks that remain unfinished after that grace period are cancelled.
4. Titan waits for every lifecycle-owned worker and handler task to finish
   cleanup and observes every task result or exception.
5. Only after that cleanup does Titan close the Telegram API session.

The grace-period duration is an internal lifecycle tuning value, not a public
API or a developer-configurable promise in v1. The policy is fixed: shutdown
must be bounded and may cancel in-flight handlers; it does not guarantee that
an in-flight handler completes after shutdown begins.

Cancellation semantics:

- Cancelling `run_async()` stops polling and runs the same ownership cleanup.
- The original `asyncio.CancelledError` remains observable by the caller after
  cleanup.
- Cancellation of an in-flight handler during shutdown is expected lifecycle
  control, not an error to be sent to the user error handler.
- A pending `AskManager` interaction is not persistent across shutdown. If its
  owning handler is cancelled, the pending interaction is cancelled and
  cleaned up according to the existing `AskManager` contract.

Non-cancellation failures in lifecycle-owned handler tasks must be observed and
reported through Titan's existing error semantics exactly once. Shutdown must
never return with an unobserved lifecycle-owned task or before the API session
is safe to close.

---

# 9. Alias Layer — titan.extras only

The alias feature is NOT part of core Titan. It is provided by the standalone
`AliasMap` utility in `titan.extras`.

See §16 for the full extras contract.

Summary:
- `AliasMap` is an independent opt-in utility in `titan.extras`, not part of `Titan`
- Aliases are enabled explicitly by registering `aliases.as_middleware()`
- Vanilla `Titan` instances carry no alias machinery or alias state
- AliasMap validation, scope, and lifecycle rules apply only when its middleware is registered

### Alias Lifecycle and Scope

- Validation: target is validated against the Context class at registration time, not at runtime
- Scope: aliases are applied per ctx instance when the AliasMap middleware runs
- Aliases may target optional methods and properties on `ctx`
- Timing: aliases are applied when execution reaches the registered middleware in the chain, and that middleware then calls `await next()`
- Alias application is not a fixed phase before all middleware

---

# 10. Middleware System

### Core Principle
Middleware exists ONLY to control request flow before reaching handlers.

### Rules

- Middleware must be linear (no branching execution graphs)
- Middleware receives (ctx, next)
- next() is the ONLY way to continue execution
- Middleware must not return values.
- Use `await next()` to continue execution.
- Use `return` (without value) to stop execution.
- Any returned value from middleware is ignored and considered invalid usage.
- No side-effect APIs are introduced via middleware
- Middleware must NOT contain business logic that belongs to handlers

### Allowed usage

- Authentication / authorization checks
- Logging
- Rate limiting
- Request preprocessing (e.g. normalization)

### Forbidden usage

- Plugin systems
- Behavior injection into ctx
- Overriding handler routing logic
- Dynamic execution modification beyond next()

### Ban System

- bot.banned_users — public set[int], managed entirely by the developer
- ctx.is_banned — bool, set by bot before middleware runs
- ctx.is_banned is True only when ctx.user_id is in bot.banned_users
- middleware reads ctx.is_banned — it does not write to it

### Guaranteed Execution Order

For every incoming update, Titan guarantees this sequence:

1. Update is parsed and ctx is built
2. ctx.is_banned is set — False if no user_id, or if user_id is not in bot.banned_users
3. Middleware chain runs, wrapping the dispatch function
4. dispatch() is invoked via next() inside the middleware chain
5. The matched handler executes inside dispatch()

This order is guaranteed and externally observable. Any change to this sequence is a breaking change.

Note: When using `AliasMap` from `titan.extras` (see §16), alias application
occurs inside the middleware chain when its registered middleware is reached.
The AliasMap middleware applies aliases to `ctx` and then calls `await next()`;
it is not a fixed phase before all middleware and is not part of the core
sequence above.

### Stability Rule

Any middleware feature that introduces hidden execution paths or non-linear flow is considered a breaking change.

---

# 11. Error Handling

Errors in Titan must follow these principles:

- Explain what happened
- Explain why it happened
- Provide a fix suggestion when possible
- Never change runtime behavior

---

# 12. Stability Rule

Any change is breaking if it:
- changes output for same input
- adds undocumented behavior
- changes execution order

---

# 13. Stability Principle

Titan is not designed as a feature-driven framework.

Titan is designed as a stability-driven system.

### Core Rule

The public API is considered frozen.

New features do not automatically justify API changes or additions.

### Version Philosophy

- Updates do not imply new features
- Features are added only if they preserve full backward compatibility
- Stability is prioritized over market trends or external library behavior

### Design Intent

Titan does not participate in feature race with other frameworks.

Instead, Titan focuses on:

- Consistency
- Predictability
- Long-term developer trust

---

# 14. Adapter Layer

bot.telegram provides access to Telegram Bot API operations outside the update-response cycle, as selected by Titan.

### Architecture

- bot.telegram is a TelegramAdapter instance attached to every Titan bot
- It operates on the same session as the core (no separate connection)
- It is independent of ctx, middleware, routing, and alias

### Principle

- Adapter exists for capabilities outside the update-response cycle
- Adapter methods do not go through middleware
- Adapter does not modify core behavior

### Stability Rule

bot.telegram is a stable public entrypoint. Its presence is guaranteed. Individual method signatures follow Telegram Bot API conventions.

---

# 15. Router

### Purpose

Router is a code organization tool only. It has no runtime behavior of its own.

### API

```python
router = Router()

@router.on("message")
@router.command("start")
@router.callback("yes")

bot.include(router)
```

### Rules

- Router supports: on(), command(), callback()
- Router does NOT support: middleware(), alias(), nested include()
- bot.include(router) transfers all registrations to the bot
- include() does not modify the router itself
- Multiple routers can be included into the same bot
- Duplicate detection and instance integrity rules are governed by §5

### Forbidden

- Nested routers
- Router middleware
- Priorities or groups
- Any routing tree logic

---

# 16. titan.extras — Opt-in DX Layer

`titan.extras` provides optional developer-experience utilities that are NOT part of the core contract.
Importing `titan` alone carries zero extras machinery — no state, no hooks, no interception.

```python
from titan.extras import AliasMap, AskManager
```

## Design boundary

| Core (`titan.Titan` + `titan.ctx.Context`) | Extras (`titan.extras`) |
|---|---|
| routing, middleware, handler lifecycle | AliasMap, AskManager |
| deterministic execution engine | opt-in utilities wired via middleware |
| zero extras state | state lives in the utility object, not the bot |

Extras integrate exclusively through the standard middleware system.
No subclassing, no hooks, no lifecycle changes.

## AliasMap

Provides aliases for optional methods and properties on `ctx`. Wired via
middleware using the same pattern as `AskManager`.

```python
from titan.extras import AliasMap

aliases = AliasMap()
aliases.register("say", "reply")
bot.middleware(aliases.as_middleware())
```

Rules:
- `alias` must not conflict with an existing attribute of `Context` — otherwise `TitanError` at registration time
- `target` must be an existing attribute of `Context` — otherwise `TitanError` at registration time
- The original attribute is never changed or removed
- Aliases are applied per-request; `ctx` instances outside this middleware are unaffected
- Without `as_middleware()` registration, no alias is ever applied
- Dynamic instance attributes set at runtime are not checked — developer responsibility

## AskManager

Sends a question and awaits the next text reply from the same `(chat_id, user_id)`.
Requires one middleware registration per bot instance.

```python
from titan.extras import AskManager

ask = AskManager()
bot.middleware(ask.as_middleware())

@bot.command("start")
async def start(ctx):
    name = await ask(ctx, "What's your name?")   # AskManager is callable directly
    await ctx.reply(f"Hello, {name}!")
```

### ask.as_middleware()

Returns a middleware function that intercepts incoming messages for pending asks.
Must be registered with `bot.middleware(ask.as_middleware())`.

Interception rules:
- Only regular user messages are intercepted (not callbacks, not channel posts)
- Only intercepts when a future is pending for the exact `(chat_id, user_id)` pair
- Consumed messages do not reach any handler or subsequent middleware

### await ask(ctx, text, reply_markup=None) → str

`AskManager` instances are callable — invoke directly as `await ask(ctx, text)`.

Rules:
- Requires both `chat_id` and `user_id` — raises `TitanError` in channel handlers
- Only one pending ask per `(chat_id, user_id)` at a time — raises `TitanError` otherwise
- No persistence — pending asks are lost on bot restart

## Guarantee

Vanilla `Titan` instances have no `alias()`, no `_pending_asks`, and no ask/alias state of any kind.
`AskManager` and `AliasMap` are regular Python objects; they interact with Titan only through
the standard middleware interface (`bot.middleware(...)`).

---

## Actions

Actions are async context managers on `ctx` that represent Telegram UI states
during the execution of a code block.

### The contract

Every Action in Titan satisfies these rules:

1. **ctx-bound** — accessed via `ctx.action_name()`, never imported directly.
2. **State, not result** — represents a Telegram UI signal, not an operation that produces a value.
3. **`__aenter__` sends the signal** — one `sendChatAction` call at block entry.
4. **`__aexit__` is a no-op** — Telegram expires the signal automatically; no cleanup call is needed.
5. **Exceptions propagate** — `__aexit__` never returns `True`.
6. **`chat_id is None` is safe** — no API call is made; no exception is raised.

### Usage

```python
async with ctx.typing():
    result = await heavy_task()
await ctx.reply(result)
```

### What qualifies as an Action

An operation qualifies as an Action if and only if:
- it maps to a Telegram `sendChatAction` value,
- it is meaningfully used as a context manager wrapping work,
- and it produces no return value the developer uses.

Operations that send messages (`reply`, `send`) or return data are not Actions.
They are direct calls.

### Implemented Actions

| Method | Telegram action |
|---|---|
| `ctx.typing()` | `typing` |

### Stability

The Action contract is frozen. Any new Action added to Titan must satisfy all
six rules above. The internal implementation (`TypingAction` class) is not part
of the public API and is not exported.

→ Full reasoning: [docs/decisions/002-actions.md](docs/decisions/002-actions.md)

---

## titan.recipes — Official Patterns

### What Recipes are

Recipes are curated, tested patterns for using Titan's Core correctly.
They live in `titan.recipes` and are entirely optional. Importing a Recipe adds no state
to the bot and changes no runtime behavior. A bot that uses no Recipes is identical to
one that does — except in the handlers where a Recipe is explicitly called.

### What Recipes are not

Recipes are not a second API layer. They do not introduce new abstractions,
new models, or new capabilities. Everything a Recipe does can be done using
only `bot`, `ctx`, and `bot.telegram` — the Recipe is the documented,
readable form of that usage, nothing more.

### The Core/Recipe boundary

The direction of influence between Core and Recipes is strictly one-way:

```
Core defines what is available.
Recipes use what is available.
```

Recipes may not define Core structure. A Recipe that requires a Core change
in order to be clean is not a reason to make that Core change.

The permitted exception: if Recipe work surfaces a genuine inconsistency
in the Core — one that would affect any developer using that API, with or
without Recipes — that inconsistency may be corrected in Core.

**The test:** *Would this Core change be justified even if no Recipe existed?*

- Yes → fix Core, then write the Recipe cleanly.
- No → accept the limitation; document it; do not modify Core to serve the Recipe.

### Stability

Recipes follow the same stability rules as the rest of Titan. A Recipe's
public interface (`__init__` signature, callable contract) is frozen once
released. Internal implementation may change; the usage contract may not.

### What Recipes may use

| Allowed | Not allowed |
|---|---|
| `@bot.on()`, `@bot.command()`, `@bot.callback()` | New decorators or hooks not in Core |
| `ctx.*` properties and actions | Custom ctx properties introduced for a Recipe |
| `bot.middleware()` | Automatic middleware registration |
| `bot.telegram.*` | New telegram methods introduced for a Recipe |
| Existing models (`Sender`, `Chat`, `Message`) | New models introduced for a Recipe |

---

## 16. Public Extension Points

Titan exposes explicit Extension Points — public integration hooks that
Extensions may target without modifying Core.

Extension Points carry the same stability guarantees as other Public APIs
declared in this document.

**Current Extension Points (v1):**

- `bot.middleware(...)` — participate in the update-processing pipeline
  before handlers run.

**Extension Points vs. Public APIs:**

Public APIs are callable interfaces (`ctx.*`, `bot.telegram.*`, decorators).
Extension Points are integration hooks. An Extension uses Public APIs inside
its logic; it integrates with Titan via Extension Points.

Adding a new Extension Point requires a dedicated ADR.
See [ADR-022](docs/decisions/022-extension-system.md) (Extension System).
