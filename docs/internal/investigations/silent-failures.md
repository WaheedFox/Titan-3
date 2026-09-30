# تحقيق — Silent Failures في Titan

**الحالة الحالية:** تحقيق تاريخي تمت مزامنة نتائجه مع التنفيذ والعقد الحاليين.
التغييرات المنفذة موثقة في `CHANGELOG.md`، وSF-03 موضح في `CONTRACT.md`
و`ROADMAP.md`.

**القرارات النهائية:**
- SF-01: Fail Fast في `AliasMap.register()` (الخيار أ) — منفَّذ.
- SF-02: تحذير runtime في `MiddlewareChain.run()` عند إرجاع middleware لقيمة غير `None` (الخيار ب) — منفَّذ. لا استثناء يُرفع، تدفق التنفيذ يبقى محكوماً بـ `next()` فقط.
- SF-03: مسألة API design مستقلة، وليست bug حالية. التعديل المباشر على registries غير مدعوم وسلوكه غير معرَّف في `CONTRACT.md` §1؛ قرار جعلها read-only مؤجل كما في `ROADMAP.md`.
- SF-04: لا تغيير — موثق في ADR-004.
- SF-05: لا تغيير — best-effort مقصود.
- SF-06: فشل `get_me()` عند startup يسجل تحذيراً ويستمر البدء — منفَّذ.

**الغرض الأصلي:** حصر السلوكيات الصامتة وتشخيصها وتقديم البدائل قبل القرار.
العبارات والأمثلة في التفاصيل التالية تسجل حالة التحقيق السابقة؛ لا تصف
بالضرورة التنفيذ الحالي.

---

## ملخص

| # | الموقع | النتيجة الحالية |
|---|---|---|
| SF-01 | `AliasMap.register()` | **حُلّ:** تعارض alias مع `Context` attribute يرفع `TitanError` فوراً. |
| SF-02 | `MiddlewareChain.run()` | **حُلّ:** إرجاع قيمة غير `None` ينتج تحذير runtime؛ لا تتغير دلالة `next()`. |
| SF-03 | `bot.commands` / `bot.handlers` | **قرار API design مستقل:** التعديل المباشر غير مدعوم وسلوكه غير معرّف؛ read-only enforcement مؤجل في ROADMAP، وليس bug مطلوب إصلاحها الآن. |
| SF-04 | `ctx.reply()` وأخواتها | لا تغيير — قرار موثق في ADR-004. |
| SF-05 | `ctx._register_identity()` | لا تغيير — best-effort مقصود. |
| SF-06 | `bot.run_async()` startup | **حُلّ:** فشل `get_me()` يصدر تحذيراً ويستمر startup. |

---

## SF-01 — Alias يكتب ctx attribute موجودة بصمت (حُلّ)

**الحالة الحالية:** نُفذ الخيار أ: `AliasMap.register()` يرفض alias يتعارض
مع `Context` attribute باستخدام `TitanError`. الكود والأمثلة التالية تصف
التحقيق قبل الإصلاح؛ والبدائل أدناه سجل تاريخي.

### الكود

```python
# src/titan/extras/alias.py

def register(self, alias: str, target: str) -> None:
    if not hasattr(Context, target):       # ✅ يتحقق: هل target موجود في Context؟
        raise TitanError(...)
    self._map[alias] = target              # ❌ لا يتحقق: هل alias يتعارض مع attribute موجودة؟

def apply(self, ctx: Context) -> None:
    for alias, target in self._map.items():
        setattr(ctx, alias, getattr(ctx, target))  # ❌ setattr دون أي فحص للتعارض
```

### السلوك الفعلي

```python
aliases = AliasMap()
aliases.register("text", "reply")   # لا خطأ هنا — "text" ليست method في Context class
bot.middleware(aliases.as_middleware())

@bot.command("start")
async def start(ctx):
    await ctx.text("مرحباً!")   # ← يعمل (= ctx.reply)
    msg = ctx.text              # ← property أصبحت method — سلوك مختلف كلياً
```

`ctx.text` property (نص الرسالة) تُستبدل بـ `ctx.reply` method على كل update يمر بالـ middleware.
المطور الذي يستخدم `ctx.text` في نفس handler يحصل على coroutine function بدلاً من string — صمت تام.

### سبب الوجود

`register()` صُمّم ليتحقق أن `target` موجود في `Context` (منع الأخطاء المطبعية).
لم يُصمَّم ليتحقق أن `alias` لا يتعارض مع attribute موجودة — الفجوة غير مقصودة.

### التصنيف

**Bug / فجوة غير مقصودة.** CONTRACT §9: *"الأسماء الأصلية في ctx تبقى ثابتة بدون أي تغيير"* —
لكن attributes الـ ctx instance (مثل `ctx.text`) ليست محمية، فقط Class attributes.

### البدائل المعمارية

**أ. Fail Fast عند `register()`:** فحص إضافي:
```python
if hasattr(Context, alias):
    raise TitanError(f"'{alias}' is an existing ctx attribute — choose a different alias name.")
```
✅ مبكر وصريح. ⚠️ يمنع aliases على instance-level attrs فقط، لا dynamic attrs.

**ب. Fail Fast عند `apply()`:** فحص عند كل update:
```python
if hasattr(ctx, alias) and alias not in self._map:
    raise TitanError(f"Alias '{alias}' conflicts with existing ctx attribute.")
```
✅ يصطاد التعارضات الديناميكية. ⚠️ overhead لكل update.

**ج. تحذير بدلاً من exception:** `_log.warning(...)` في `register()` أو `apply()`.
✅ لا كسر API. ⚠️ قد يُتجاهل.

**د. توثيق وتثبيت:** لا تغيير في الكود — إضافة تحذير صريح في docstring.
✅ صفر تأثير على existing code. ⚠️ المطور لا يزال يستطيع الوقوع في الفخ.

### تأثير الإصلاح على CONTRACT.md

الخيار (أ) يُعدّل سلوك `AliasMap.register()` — breaking change لمن يستخدم alias names
تتعارض مع ctx attributes. يستلزم تحديث CONTRACT §9 (AliasMap rules).

---

## SF-02 — Middleware return value مُتجاهلة دون كشف (حُلّ)

**الحالة الحالية:** نُفذ الخيار ب: `MiddlewareChain.run()` يسجل تحذيراً
عند إرجاع middleware قيمة غير `None`، مع بقاء التحكم في التدفق عبر `next()`.
المقتطفات التالية تسجل الحالة السابقة للإصلاح، والبدائل سجل تاريخي.

### الكود

```python
# src/titan/middleware.py

async def run(self, ctx: Context, handler: ...) -> None:
    async def build(index: int) -> None:
        if index >= len(self._chain):
            await handler()
            return

        async def next_fn() -> None:
            await build(index + 1)

        await self._chain[index](ctx, next_fn)   # ← return value مُتجاهلة تماماً

    await build(0)
```

### السلوك الفعلي

```python
@bot.middleware
async def guard(ctx, next):
    if not authorized(ctx):
        return True    # ❌ المطور يظن هذا يوقف الـ chain مثل Express.js

    await next()       # ← هذا يوقف الـ chain فعلاً — لا return value
```

`return True` تُتجاهل — الـ chain يتوقف فقط لأن `next()` لم يُستدعَ.
النتيجة: `return True` و `return` يُنتجان **نفس السلوك تماماً**.
لكن المطور القادم من Express/Koa يتوقع أن القيمة المُرجعة لها معنى — لا تحذير.

### سبب الوجود

CONTRACT §10 يُعلن صراحةً: *"Any returned value from middleware is ignored and considered invalid usage."*
هذا قرار تصميم مقصود — middleware في Titan يتحكم في الـ flow عبر `next()` فقط.
لكن الإعلان في CONTRACT لا يُرافقه كشف في runtime.

### التصنيف

**التصنيف وقت التحقيق، قبل الإصلاح:** كانت مخالفة CONTRACT غير مُنفَّذة،
وأقرب إلى "soft enforcement gap" منها إلى bug. نُفذ التحذير لاحقاً كما هو
مبين في الحالة الحالية أعلاه.

### البدائل المعمارية

**أ. `validate_middleware()` تكشف coroutines ذات return annotation:**
```python
# في titan/validation.py — تفحص هل fn ترجع شيئاً غير None
import inspect
hints = typing.get_type_hints(fn)
if hints.get("return") not in (None, type(None), inspect.Parameter.empty):
    raise TitanError("Middleware must not return a value.")
```
✅ مبكر (import time). ⚠️ يصطاد return annotation فقط، لا runtime values.

**ب. كشف runtime بـ `inspect.iscoroutine()`:**
```python
result = await self._chain[index](ctx, next_fn)
if result is not None:
    _log.warning("Middleware returned a non-None value — return values are ignored. ...")
```
✅ يصطاد كل حالة. ⚠️ يُنفَّذ لكل update لكل middleware — overhead.

**ج. توثيق صريح في `validate_middleware()` docstring + CONTRACT — لا تغيير:**
✅ صفر overhead. ⚠️ لا تغذية راجعة للمطور.

### تأثير الإصلاح على CONTRACT.md

الخيار (أ) يضيف قيداً جديداً على return type annotation — قد يكسر middleware موجودة.
الخيار (ب) لا يكسر أي API — يُضيف تحذير runtime. لا تعديل لـ CONTRACT.

---

## SF-03 — bot.commands / bot.handlers / bot.callback_handlers: قرار API design مستقل

**الحالة الحالية:** ليست bug مطلوبة للإصلاح. هذه registries ما زالت public
وقابلة للتعديل على مستوى Python، لكن `CONTRACT.md` §1 يصرح بأن التعديل المباشر
غير مدعوم وسلوكه غير معرّف. جعلها read-only قرار API design منفصل ومؤجل في
`ROADMAP.md`، لأنه قد يغيّر سلوكاً عاماً؛ لا تنفذ حماية هنا.

الأمثلة والتحليل التاليان يوثّقان سبب طرح السؤال والبدائل التي دُرست، لا
تكليفاً بتغيير السلوك الحالي.

### الكود

```python
# src/titan/bot.py

def __init__(self, token: str) -> None:
    ...
    self.commands: dict[str, Handler] = {}           # plain instance attribute
    self.handlers: dict[str, list[Handler]] = {}     # plain instance attribute
    self.callback_handlers: dict[str, Handler] = {}  # plain instance attribute
```

### السلوك الفعلي

```python
@bot.command("start")
async def start(ctx): ...

bot.commands = {}   # ← يُعيد الـ dict كاملاً بصمت — /start يختفي
bot.handlers = None # ← يكسر routing الداخلي — bot.run() لاحقاً: AttributeError أو KeyError

# أو بشكل أدق — خطأ شائع:
bot.commands["help"] = my_func  # ← يتجاوز validation/duplicate checks تماماً
```

الكتابة المباشرة تتجاوز:
- فحص التكرار (`TitanError` على duplicate command)
- تسجيل `_command_sources` (المستخدم في رسائل conflict)
- lint/health checks (لا تعلم بالتعديل)

### سبب الوجود

هذه attributes كانت public منذ البداية — قراءتها ضرورية لـ `inspect()` و`health()` و`lint()`.
هذه registries باقية كـ public data يمكن قراءتها لأغراض الفحص. العقد الحالي
لا يدعم تعديلها مباشرة ويعد سلوكه غير معرّف؛ أما فرض read-only فعلياً فمسألة
توافق مستقلة ما زالت في ROADMAP.

### التصنيف

**قرار API design مستقل، وليس bug حالية.** يقرر `CONTRACT.md` §1 أن التعديل
المباشر غير مدعوم وسلوكه غير معرّف. احتمال تقديم registries read-only مسجل
في `ROADMAP.md` كسؤال توافق منفصل؛ لا يعني ذلك أن الحالة الحالية إصلاح عاجل.

### البدائل المعمارية

البدائل التالية سُجلت أثناء التحقيق. لا تُعد قراراً لتنفيذ تغيير؛ الخيار (د)
هو التوثيق الحالي، وأي read-only protection تبقى مؤجلة للقرار المستقل.

**أ. `@property` مع getter فقط:**
```python
@property
def commands(self) -> dict[str, Handler]:
    return self._commands

@commands.setter
def commands(self, value) -> None:
    raise TitanError("bot.commands is read-only. Use @bot.command() to register handlers.")
```
✅ يمنع الكتابة المباشرة. ⚠️ كسر لمن يقرأ `bot.commands` ويعدّل القاموس مباشرةً
(مثل `bot.commands["x"] = f` — الـ setter لا يصطاده، الـ getter يُعيد reference للـ dict الداخلي).

**ب. إعادة نوع read-only من getter:**
```python
@property
def commands(self) -> types.MappingProxyType:
    return types.MappingProxyType(self._commands)
```
✅ يمنع `bot.commands["x"] = f` و `bot.commands = {}` معاً.
⚠️ breaking change — كل من يُقارن `bot.commands` بـ dict سيتأثر.

**ج. `__setattr__` guard:**
```python
def __setattr__(self, name, value):
    if name in ("commands", "handlers", "callback_handlers") and hasattr(self, name):
        raise TitanError(f"bot.{name} is read-only after initialization.")
    super().__setattr__(name, value)
```
✅ يمنع إعادة التعيين الكاملة. ⚠️ لا يمنع تعديل القاموس من الداخل.

**د. توثيق فقط — public بوعي:**
CONTRACT يُصرّح: *"تعديل bot.commands مباشرةً غير مدعوم — سلوكه غير معرَّف."*
✅ صفر تغيير. ⚠️ لا تغذية راجعة.

### تأثير الإصلاح على CONTRACT.md

يوثق `CONTRACT.md` §1 بالفعل أن التعديل المباشر غير مدعوم وسلوكه غير معرّف.
فرض read-only فعلياً (مثل MappingProxyType) قد يكون breaking change، ويظل
قراراً مستقلاً كما هو مدرج في `ROADMAP.md`؛ لا يتطلب هذا التحقيق تغيير العقد.

---

## SF-04 — ctx methods تُعيد None مع تحذير عند chat_id غائب

### الكود

```python
# src/titan/ctx.py — reply(), send(), delete_message(), ban_user(), leave()

chat_id = self.chat_id
if chat_id is None:
    _log.warning("ctx.reply() called with no chat_id in this update — message not sent.")
    return None
```

### التصنيف

**قرار تصميم موثق — ADR-004 "Soft Contract".**

ADR-004 يُصنّف هذا كـ "Soft Contract": مستحيل حالياً (update بدون chat_id نادر جداً)
لكن قد يصبح صحيحاً في حالات مستقبلية — warning مناسب.
CONTRACT §4 يُقرّ بهذا التصنيف.

### ملاحظة

التحذير موجود لكنه يعتمد على أن المطور قد هيَّأ logging.
إذا لم يُهيَّأ `logging.basicConfig()`، التحذير يختفي بصمت.

**هذا ليس bug في Titan** — إنه سلوك logging standard في Python.
لكنه يعني أن "Soft Contract" قد يصبح "Silent Contract" في بيئات بدون logging.

---

## SF-05 — `_register_identity()` exception مُبتلعة

### الكود

```python
# src/titan/ctx.py

try:
    await self._links.register_sent_message(...)
except Exception as exc:
    _log.warning("Message Links: identity registration failed for ...: %s", exc)
```

### التصنيف

**قرار تصميم موثق — best-effort.**

Docstring يُصرّح: *"الفشل غير مميت — الرسالة وصلت، الهوية تُسجَّل best-effort."*
هذا صحيح معمارياً: فشل تسجيل الهوية لا يجب أن يُفشل إرسال الرسالة.

**لا تغيير مطلوب هنا.**

---

## SF-06 — bot startup: get_me() failure مُبتلعة بصمت تام (حُلّ)

**الحالة الحالية:** استُبدل الصمت بتحذير عند فشل `get_me()`، ويستمر startup
بعد التحذير. مقتطف الكود التالي يوثق الحالة السابقة للإصلاح؛ البدائل أدناه
سجل تاريخي وليست خيارات تنفيذ مفتوحة.

### الكود

```python
# src/titan/bot.py — run_async()

try:
    me = await self._api.get_me()
    username = me.get("username", "unknown")
    self._log(f"Running as @{username}")
except Exception:
    pass    # ← لا warning، لا log، لا شيء
```

### السلوك الفعلي

إذا فشل `get_me()` (token خاطئ، مشكلة شبكة، timeout):
- البوت يُكمل التشغيل
- لا رسالة في logs
- `_api._me` يبقى `None` → `_register_identity()` تنبّه لاحقاً لكل رسالة مُرسلة
- الـ polling يبدأ — وإذا كان الفشل بسبب token خاطئ سيفشل عند أول `get_updates()`

المطور يرى: ـ لا شيء عند الـ startup، ثم أخطاء Telegram عند أول update.

### سبب الوجود

يبدو أن القصد: "لا تمنع البدء إذا فشل get_me() — قد يكون مؤقتاً."
لكن الصمت التام يجعل تشخيص المشكلة صعباً.

### التصنيف

**التصنيف وقت التحقيق، قبل الإصلاح:** كانت فجوة غير موثقة، وليست سلوكاً
مقصوداً كـ SF-04/SF-05. استُبدل الصمت لاحقاً بتحذير مع استمرار startup كما هو
مبين في الحالة الحالية أعلاه.

### البدائل المعمارية

**أ. تسجيل تحذير بدلاً من الصمت:**
```python
except Exception as exc:
    _log.warning("Could not fetch bot info at startup: %s — continuing.", exc)
```
✅ أقل صمتاً، لا يمنع البدء. ⚠️ قد يُقلق المطور دون داعٍ في حالات timeout عابرة.

**ب. Fail Fast — رفع exception:**
```python
except Exception as exc:
    raise TitanError(f"Failed to connect to Telegram at startup: {exc}") from exc
```
✅ واضح جداً. ⚠️ كسر لمن يتوقع أن البوت يبدأ دائماً ثم يُعيد المحاولة.

**ج. إبقاء الوضع مع توثيق:**
CONTRACT أو ROADMAP يُصرّح: get_me() فشله عند البدء لا يوقف الـ startup — silent by design.
✅ صفر تغيير. ⚠️ لا تغذية للمطور.

---

## ملخص المسارات وحالتها الحالية

| # | الحالة الحالية | الجهد / الأثر |
|---|---|---|---|
| **SF-01** | منفذ: Fail Fast في `AliasMap.register()` عند تعارض alias. | لا تعديل عقد إضافي مطلوب هنا. |
| **SF-02** | منفذ: تحذير runtime لقيمة middleware غير `None`. | لا تغيير في دلالة التدفق عبر `next()`. |
| **SF-03** | قرار API design منفصل: direct mutation غير مدعوم وسلوكه غير معرّف؛ read-only enforcement مؤجل في ROADMAP. | ليس bug للإصلاح الآن؛ أي حماية تحتاج قرار توافق مستقل. |
| **SF-04** | لا تغيير — موثق في ADR-004. | السلوك المقصود باقٍ. |
| **SF-05** | لا تغيير — best-effort مقصود. | السلوك المقصود باقٍ. |
| **SF-06** | منفذ: تحذير عند فشل `get_me()` مع استمرار startup. | لا تعديل عقد إضافي مطلوب هنا. |

---

## أسئلة القرار كما كانت أثناء التحقيق وحالتها الآن

الأسئلة أدناه تحفظ سياق التحقيق ولا تعني أن المسارات المنفذة ما زالت مفتوحة.

- **SF-01:** حُسم الخيار أ ونُفذ في `AliasMap.register()`.
- **SF-02:** حُسم تحذير runtime في `MiddlewareChain.run()` ونُفذ.
- **SF-03:** ما زال سؤال API design مستقلاً: العقد يمنع الاعتماد على direct
  mutation ويصف سلوكه بغير المعرّف؛ `ROADMAP.md` يؤجل قرار read-only enforcement.
  لا يُصنّف bug ولا إصلاحاً جانبياً.
- **SF-06:** حُسم تسجيل warning بدلاً من الصمت، مع استمرار startup، ونُفذ.

تظل نتائج SF-04 وSF-05 قرارات تصميم مقصودة كما هو موضح في أقسامها وADR-004.
