# 012 — Design Linter

**Status:** Accepted

---

## Proposal

إضافة `bot.lint()` كقدرة Core في Titan تفحص ما إذا كان تصميم البوت يحترم
فلسفة Titan واتفاقياتها — لا ما إذا كان يعمل (health)، ولا ما إذا كان
موجوداً (inspect).

---

## Investigation

**المشكلة من منظور المطور:**
الفلسفة موجودة في CONTRACT.md، لكنها غير مُنفَّذة في الكود.
المطور ينتهك الاتفاقيات دون علم — الأوامر بأحرف كبيرة، callback_data فارغة،
`on_offset` async تُهمَل بصمت، روترات بلا handlers — والنتيجة إما سلوك غير
متوقع أو صمت تام.

**الفصل مع الأدوات الموجودة:**

| الأداة | السؤال | الوقت |
|---|---|---|
| Contract Validator (ADR-009) | هل التوقيع صحيح؟ | import time |
| Project Health (ADR-005) | هل البنية مكتملة؟ | post-registration |
| Interactive Inspector (ADR-006) | ماذا يحتوي البوت؟ (وصف) | post-registration |
| **Design Linter (#6)** | **هل الاتفاقيات محترمة؟** | **post-registration** |

الحدود واضحة. لا تداخل.

التفاصيل الكاملة: `docs/internal/investigations/design-linter.md`

---

## Decision

### 1 — الشكل: قدرة Core

`bot.lint()` method مباشرة على `Titan` — تتبع نفس نمط `bot.health()`
و`bot.inspect()`.

المبرر: Design Linter يفحص Titan نفسها — الأوامر المسجلة، الـ callbacks،
الـ on_offset، الـ routers — وهذه معلومات يملكها `bot` بالفعل.
إخراجه إلى `titan.linter` يعني صنع طبقة خارجية تضطر لمعرفة تفاصيل Titan
الداخلية، عكس ما فعلناه مع health وinspect.

الخريطة المنطقية لقدرات Titan:

```
bot.inspect()  → ماذا يحتوي البوت؟
bot.health()   → هل المشروع سليم؟
bot.lint()     → هل التصميم محترم؟
```

### 2 — البنية الداخلية

```
src/titan/lint/
    __init__.py       ← تصدير LintFinding + run_lint
    findings.py       ← LintFinding dataclass
    engine.py         ← run_lint(bot) يجمع نتائج كل القواعد
    rules/
        __init__.py
        command_rules.py   ← LINT_001
        callback_rules.py  ← LINT_002
        offset_rules.py    ← LINT_003
        router_rules.py    ← LINT_010، LINT_011
```

`bot.lint()` يستدعي المحرك ويُعيد `list[LintFinding]`.
المحرك يجمع النتائج من كل الـ rules ويُرتّبها حسب الـ code.

### 3 — LintFinding — نوع بيانات مستقل

```python
@dataclass(frozen=True)
class LintFinding:
    level: str     # "WARNING" فقط في v1 — لا ERROR، لا INFO
    code: str      # مثل: "TITAN_LINT_001"
    message: str
    hint: str      # اقتراح التصحيح — إلزامي دائماً
```

**لماذا مستقل عن `HealthFinding`:**
`HealthFinding` يُجيب على "هل البنية مكتملة؟" — قد يكون `ERROR`.
`LintFinding` يُجيب على "هل الاتفاقية محترمة؟" — `WARNING` دائماً في v1.
الدمج يُضيّع الفصل المعماري بين الأداتين.

**`hint` إلزامي:**
Design Linter لا يُبلّغ فقط — يُعلّم. كل finding لا يوجد له hint
لا يستحق وجوده.

### 4 — قواعد v1 = 3أ + 3ب

#### قواعد 3أ — وقت التسجيل

**TITAN_LINT_001 — Command name not lowercase**

```
الانتهاك:  @bot.command("Start")
الكشف:     name != name.lower()
المستوى:   WARNING
الـ hint:  Use lowercase command names. Telegram is case-insensitive
           but Titan convention requires lowercase for consistency.
```

**TITAN_LINT_002 — Empty or whitespace-only callback_data**

```
الانتهاك:  @bot.callback("") أو @bot.callback("   ")
الكشف:     not data.strip()
المستوى:   WARNING
الـ hint:  callback_data cannot be empty or whitespace-only.
           Use a descriptive identifier like "confirm_delete".
```

**TITAN_LINT_003 — Async on_offset**

```
الانتهاك:  bot.run(..., on_offset=async_fn)
الكشف:     inspect.iscoroutinefunction(on_offset) أو فحص __call__ للـ callable object
المعالجة:  TitanError قبل بدء polling
الـ hint:  on_offset must be a synchronous callable. Use a sync function
           and schedule async work separately.
```

#### قواعد 3ب — الحالة المجمّعة (post-registration)

**TITAN_LINT_010 — Router included with no handlers**

```
الانتهاك:  router = Router(); bot.include(router)  ← router فارغ
الكشف:     len(router.commands) == 0
           and len(router.handlers) == 0
           and len(router.callback_handlers) == 0
المستوى:   WARNING
الـ hint:  Router was included but contains no registered handlers.
           Either register handlers on it or remove the include() call.
```

**ملاحظة تقنية:** `bot._included_routers` يخزّن `id(router)` فقط.
للوصول إلى الكائنات الفعلية يُضاف `bot._included_router_objects: list[Router]`
(قائمة مرافقة، بسطر واحد في `__init__` وسطر في `include()`).

**TITAN_LINT_011 — Excessive fan-out on single event**

```
الانتهاك:  > 10 handlers مسجلة على نفس نوع الحدث (e.g. "message")
الكشف:     len(bot.handlers[event]) > 10
المستوى:   WARNING
الـ hint:  Event '{event}' has {n} handlers. Consider splitting
           responsibilities across routers or using middleware
           for shared concerns.
العتبة:    10 handlers — ثابت في v1، قابل للمراجعة لاحقاً
```

### 5 — لا AST داخل src/titan/

الفحص الثابت للكود (هل `bot.telegram` يُستخدم داخل handler؟ هل `ctx.raw`
في منطق دائم؟) يتطلب تحليل AST — وهذا يُحوّل Titan إلى محلل كود لا مكتبة.

الحد الواضح:

```
src/titan/ يعرف نفسه فقط — لا يراقب كود المطور
```

القواعد الأعمق تنتمي إلى `titan-lint` (أداة CLI/ruff plugin مستقبلية)
خارج هذا الريبو وخارج هذا الـ ADR.

### 6 — وقت تشغيل القواعد

| القاعدة | البيانات تُجمع متى؟ | ملاحظة |
|---|---|---|
| LINT_001 (command name) | عند `@bot.command(name)` | متاح دائماً |
| LINT_002 (callback_data) | عند `@bot.callback(data)` | متاح دائماً |
| LINT_003 (on_offset async) | عند `bot.run(..., on_offset=fn)` | يُرفض قبل بدء polling؛ يبقى lint فحصاً دفاعياً للحالة الداخلية |
| LINT_010 (empty router) | عند `bot.include(router)` | متاح دائماً |
| LINT_011 (excessive fan-out) | عند كل تسجيل handler | متاح دائماً |

**قرار LINT_003:** `bot.run()` و`bot.run_async()` يرفضان async `on_offset`
بـ `TitanError` قبل بدء polling. يبقى `bot.lint()` قادراً على الإبلاغ عن
الحالة الدفاعية إذا وُضع callable غير صالح مباشرةً على `self._on_offset`.

**الأثر التشغيلي:** async `on_offset` قد يترك coroutine غير مُنتظرة ويُهمل
حفظ offset؛ لذلك أصبح الرفض الفوري جزءاً من العقد.

### 7 — التصدير

```python
# titan/__init__.py — لا تغيير
```

`LintFinding` غير مُصدَّرة من الجذر في v1 — الوصول الصريح فقط:
```python
from titan.lint import LintFinding  # إن احتاجها المستخدم للـ type annotation
```

---

## Rules

- **لا AST داخل `src/titan/`** — الفحص الثابت للكود ينتمي لأداة خارجية مستقبلية.
- **`hint` إلزامي في كل `LintFinding`** — Design Linter يُعلّم لا يُعاقب.
- **`bot.lint()` لا يُصلح** — مثل `bot.health()`: تُقيّم وتُبلّغ، المطور يقرر.
- **v1 = قواعد 3أ + 3ب** — لا توسع لما بعدهما قبل مستهلك حقيقي جديد.
- **عتبة LINT_011 = 10** — ثابت في v1، قابل للمراجعة بمستهلك حقيقي.

---

## Alternatives

**الخيار المرفوض: `titan.linter` خارج Core**
يُصنع طبقة خارجية تضطر لقراءة تفاصيل Titan الداخلية — عكس نمط health/inspect
الناجح. رُفض لأن Linter يفحص Titan نفسها، لا شيئاً خارجها.

**الخيار المرفوض: دمج LintFinding مع HealthFinding**
يُضيّع الفصل المعماري بين "البنية مكتملة" و"الاتفاقية محترمة". رُفض.

**الخيار المرفوض: TitanError الفوري لـ on_offset async**
مبالغة — الانتهاك ليس عقداً مكسوراً. `WARNING` أصدق. رُفض.

**الخيار المرفوض: قواعد 3ب مؤجلة عن v1**
رُفض — الفصل بين "style checker" و"design linter" يعتمد تحديداً على قواعد
البنية المجمّعة. بدونها الأداة لا تستحق اسمها.

---

## Consequences

**إيجابية:**
- `bot.lint()` تُكمل الثلاثية: inspect (وصف) + health (سلامة) + lint (فلسفة)
- 5 قواعد متنوعة المستوى: من أسماء الأوامر إلى بنية الـ routers
- Titan تصبح نظاماً يعرف نفسه ويُعلّم مستخدميه فلسفته
- `titan-lint` المستقبلية (AST) تُبنى على قاعدة واضحة الحدود

**تغيير بسيط في bot.py:**
- إضافة `_included_router_objects: list[Router]` لتمكين LINT_010
- إضافة `_on_offset` لتمكين LINT_003 كفحص دفاعي للحالة الداخلية
- كلاهما تغيير داخلي لا يمس الـ public API

**محدودية مقبولة:**
- public API يرفض LINT_003 قبل `run()`؛ والفحص الدفاعي متاح قبل وبعد التشغيل
- القواعد الأعمق (anti-patterns في كود المطور) تنتظر `titan-lint` الخارجية
