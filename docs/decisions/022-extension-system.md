# 022 — Extension System

**Status:** Accepted

---

## Proposal

تعريف "Extension" كمفهوم رسمي في Titan — مختلف عن Recipe ومختلف عن Project Template —
وإنشاء معيار يُنظِّم الامتدادات الرسمية والمجتمعية في طبقة Ecosystem.

---

## Context

Titan لديها طبقة Ecosystem تُعرِّف كيف يبني المجتمع حولها:

- `ecosystem/recipes/` — وصفات: أنماط معالجة قابلة لإعادة الاستخدام داخل handlers
- `ecosystem/templates/` — قوالب: مشاريع بوت كاملة تُنسخ وتُملَك

لكن ثمة نمط موجود بالفعل في `titan.extras` لم يُسمَّ رسمياً بعد:
`AliasMap` و`AskManager` هما كائنان يُضيفان قدرة قابلة للتركيب عبر نقاط التكامل
المُعلنة في Titan — وهذا بالضبط ما يُسمى "Extension" في أطر أخرى.

المشكلة: لا يوجد تعريف رسمي يُمكِّن المجتمع من بناء امتدادات على نفس النمط،
ولا معيار يُوضِّح الحدود، ولا اتفاقية تسمية تجعل الامتدادات قابلة للاكتشاف.

---

## Investigation

### ما يوجد فعلاً

`titan.extras` تطبيق حي للنمط:

```python
manager = AskManager()
bot.middleware(manager.as_middleware())  # تكامل عبر Public Extension Point
# ثم داخل handler:
answer = await manager.ask(ctx, "ما اسمك؟")
```

كلا الكائنين يشتركان في:
- تهيئة منفصلة عن التسجيل
- استقلالية تامة عن Core — يمكن حذفهما بلا أثر على `bot.py`
- تفاعل مزدوج: في نقطة التكامل، وفي handlers مباشرة

### ما يميز Extension عن Recipe

الحد ليس الحجم — هو نقطة التكامل:

- **Recipe** تعيش داخل handler فقط: `await recipe(ctx)`
- **Extension** تتكامل عبر Public Extension Points المُعلنة في Titan

### مقارنة بالأنظمة المشابهة

- **pytest plugins / FastAPI** — نقطة التكامل الواحدة الصريحة هي ما أنتج ecosystem حقيقياً بلا ثقل.
- **VS Code / Django** — manifest، auto-discovery، lifecycle hooks → رُفض. يجلب "magic" وسطح API ثانٍ يحتاج صيانة مستقلة.

الدرس: اتفاقية تسمية + نقطة تكامل واحدة معروفة + لا auto-loading = ecosystem كافٍ.

### هل يحتاج Titan Loader أو Registry؟

لا — لأسباب بنيوية لا تفضيلية:

- Auto-loading ينتهك "لا شيء يحدث عند الاستيراد" — مبدأ موجود في CONTRACT
- Registry مركزي = بنية تحتية تحتاج صيانة — رُفض في Recipes لنفس السبب
- Discovery مدمج = يجعل Core تعلم بالامتدادات — ينتهك فصل المسؤوليات

اتفاقية `titan-extension-<name>` على PyPI تكفي لاكتشاف حزم الامتدادات
المجتمعية. هذا لا يحدد قناة توزيع Titan Core، التي تبقى GitHub.

---

## Decision

### ١. تعريف Extension

Extension في Titan هو كائن Python يُضيف **قدرة قابلة للتركيب** إلى مشروع Titan
عبر **Public Extension Points** التي يُعلنها Titan — بدون تعديل Core.

نقطة التكامل هي المحور، لا شكل الكائن. أي آلية تُحقق التكامل عبر Public Extension
Point مُعلنة في `CONTRACT.md` تُعدّ صحيحة — بغض النظر عن وجود `as_middleware()`
أو غيره. نقاط التكامل مرتبطة بما يُعلنه Titan في أي وقت، لا بما يوجد اليوم.

### ٢. titan.extras كمرجع رسمي للنمط

`titan.extras` هو التطبيق الرسمي الأول لنمط Extensions داخل Titan.
لا تغيير في الكود أو الأسماء — إعادة تأطير في التوثيق فقط.

### ٣. اتفاقية التسمية

| | الشكل |
|---|---|
| اسم الحزمة | `titan-extension-<name>` |
| اسم الاستيراد | `titan_extension_<name>` |

### ٤. الموقع في /ecosystem

```
ecosystem/
└── extensions/
    └── STANDARD.md    ← التعريف الرسمي والحدود
```

### ٥. ما لا يُبنى

- لا Loader أو Registry أو Discovery
- لا تغيير في `titan.extras` أو مساراته
- لا template لإنشاء Extension — STANDARD + نمط extras كافٍ كمرجع حي

---

## Rule

Extension يتكامل عبر Public Extension Points التي يُعلنها Titan — لا أكثر.
`bot.middleware()` هو مثال نقطة التكامل الحالية، وليس تعريف Extension.
أي نقطة تكامل جديدة تُضيفها Titan مستقبلاً تتسع لها Extensions الموجودة بدون
تعديل في هذا المعيار أو هذا ADR.

---

## Alternatives Considered

**Extension كمفهوم أوسع من titan.extras:**
فُحص ما إذا كانت Extension تعني شيئاً يتجاوز نمط `titan.extras` — مثل lifecycle hooks،
manifest، أو dependency injection. رُفض: فتح هذا السؤال يعيد إنتاج الأنظمة الثقيلة
(VS Code، Django) التي رُفضت بالفعل في Ecosystem Layer.

**تثبيت as_middleware() كعقد Extension:**
فُحص جعل `as_middleware()` جزءاً من تعريف Extension. رُفض: هو نمط تنفيذ ظهر في
`titan.extras`، وليس عقداً. تثبيته يُقيِّد نقاط التكامل المستقبلية قبل معرفتها.

**Registry أو Discovery مُدمج:**
فُحص إنشاء قائمة مركزية أو auto-discovery عند التثبيت. رُفض: يُضيف بنية تحتية
تحتاج صيانة ويجعل Core تعلم بالامتدادات — ينتهك فصل المسؤوليات.

---

## Consequences

**ما يُكتسب:**
- مفهوم رسمي لـ Extension يُميّزه عن Recipe وProject Template
- المجتمع يملك معياراً واضحاً للبناء عليه
- `titan.extras` يكتسب هوية معمارية واضحة كأول تطبيق رسمي للنمط
- المعيار مرن: يستوعب نقاط تكامل مستقبلية دون تغيير

**القيود المقبولة:**
- الاكتشاف يعتمد على اتفاقية التسمية لا على أداة مخصصة
- لا مرجع تنفيذي كامل لأول Extension مجتمعية — STANDARD + titan.extras يكفيان

**ما يبقى خارج نطاق هذا القرار:**
- نقاط تكامل جديدة في Titan — تُقرَّر بـ ADR مستقل عند الحاجة
- قائمة مجتمعية بالامتدادات المعروفة — تُضاف لاحقاً عند وجود امتدادات فعلية
- أدوات تحقق (linter، validator) — تُبنى عند الحاجة
