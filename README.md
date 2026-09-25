# Titan

إطار عمل Python غير متزامن لبناء بوتات Telegram.

بسيط. واضح. لا يتغير تحت قدميك.

> **خط الأساس العام:** Titan B1 (`1.0.0b1`) هو أول خط أساس عام. إصدارات alpha السابقة (`1.0.0a1` و`1.0.0a2`) إصدارات تمهيدية تاريخية، وليست خطوط أساس عامة سابقة.

[![CI](https://github.com/WaheedFox/Titan/actions/workflows/ci.yml/badge.svg)](https://github.com/WaheedFox/Titan/actions/workflows/ci.yml)

> 🌐 [English version → README.en.md](README.en.md)

---

## التثبيت

ثبّت Titan مباشرةً من مستودع GitHub الرسمي:

```bash
pip install git+https://github.com/WaheedFox/Titan.git
```

---

## البداية السريعة

```python
from titan import Titan

bot = Titan("YOUR_TOKEN")

@bot.command("start")
async def start(ctx):
    await ctx.reply("أهلاً! أنا جاهز.")

bot.run()
```

---

## لماذا Titan؟

Titan مناسبة للمطورين الذين يريدون أن تبقى بوتات Telegram مفهومة مع نموها.

- **توجيه صريح** — لكل من الأوامر والأحداث والـ callbacks والـ middleware
  والـ routers وظيفة واضحة.
- **نموذج ذهني صغير** — `bot` ينظم التطبيق، و`ctx` يمثل التحديث الحالي،
  و`bot.telegram` هو المسار الصريح للوصول إلى Telegram API.
- **سلوك async قابل للتوقع** — تُوزَّع التحديثات على عمال مستقلين لكل محادثة،
  فلا يؤدي العمل في محادثة واحدة تلقائياً إلى تسلسل محادثات لا علاقة لها بها.
- **عقود مستقرة** — الـ Public API وسلوك الأخطاء ودلالات التشغيل المهمة موثقة،
  وليست متروكة للتخمين.
- **رؤية تشغيلية** — افحص البوت، واختبر صحته، ودقّق تصميمه، وتحقق من زمن
  التحديث قبل أن تتحول المشكلة الصغيرة إلى لغز في الإنتاج.

### إذا كان إطارك الحالي يبدو بطيئاً أو صعب الفهم

أحياناً لا تكون المشكلة في Telegram نفسها، بل في كمية الطبقات التي تفصل بين
التحديث والـ handler الخاص بك.

صُممت Titan للمطورين الذين سئموا من:

- تأثر محادثات لا علاقة لها بعمل بطيء في محادثة واحدة؛
- عدم معرفة المسار الذي سلكه التحديث؛
- إخفاء الطبقات الكبيرة لما يستلمه الـ handler فعلياً؛
- نمو الـ boilerplate أسرع من نمو البوت؛
- اكتشاف أخطاء الإعداد والتسجيل عند التشغيل فقط؛
- غموض دورة الحياة والـ offset وسلوك إعادة التشغيل؛
- صعوبة تتبع تغير سلوك الإطار بين الإصدارات.

Titan لا تلغي زمن الشبكة أو حدود Telegram أو الكود الحاجب أو منطق التطبيق
البطيء. هدفها الأكثر فائدة هو جعل نموذج التنفيذ صريحاً، وعزل العمل في
المحادثات غير المرتبطة، وتوفير أدوات ترى من خلالها ما يفعله البوت فعلياً.

---

## مجتمع Titan

يحيط بالمشروع مجتمع مباشر وصغير حول بوتات Waheed ومكتبة Titan والمشاريع
المرتبطة بها. لكل مساحة هدف مختلف:

<table>
  <tr>
    <td align="center" width="25%">
      <a href="https://t.me/WaheedUpdates">
        <img src="docs/assets/community/waheed-updates.jpg" width="112" alt="الصورة التعريفية لقناة Waheed Updates">
      </a><br>
      <b><a href="https://t.me/WaheedUpdates">Waheed Updates</a></b><br>
      <sub>المصدر الرسمي لإعلانات بوتات Waheed ومكتبة Titan والمشاريع الأخرى.</sub>
    </td>
    <td align="center" width="25%">
      <a href="https://t.me/WaheedSupport">
        <img src="docs/assets/community/waheed-support.jpg" width="112" alt="الصورة التعريفية لمجموعة Waheed Support">
      </a><br>
      <b><a href="https://t.me/WaheedSupport">Waheed Support</a></b><br>
      <sub>مجموعة الدعم الرسمية. راجع <code>/rules</code> و<code>/help</code> قبل السؤال.</sub>
    </td>
    <td align="center" width="25%">
      <a href="https://t.me/WaheedChat">
        <img src="docs/assets/community/waheed-chat.jpg" width="112" alt="الصورة التعريفية لمجموعة Waheed Chat">
      </a><br>
      <b><a href="https://t.me/WaheedChat">Waheed Chat</a></b><br>
      <sub>مساحة النقاش حول بوتات Waheed ومكتبة Titan والمشاريع المرتبطة.</sub>
    </td>
    <td align="center" width="25%">
      <a href="https://t.me/WaheedMarket">
        <img src="docs/assets/community/waheed-market.jpg" width="112" alt="الصورة التعريفية لسوق Waheed Market">
      </a><br>
      <b><a href="https://t.me/WaheedMarket">Waheed Market</a></b><br>
      <sub>السوق الخاص بالعروض والصفقات والإعلانات المدعوم من Waheed.</sub>
    </td>
  </tr>
</table>

استخدم **Waheed Updates** للإصدارات والإعلانات، و**Waheed Support** للدعم،
و**Waheed Chat** للنقاش، و**Waheed Market** لأنشطة السوق.

---

## المفاهيم الأساسية

Titan توفر خمس طرق للتفاعل مع بوتك. كل طريقة لها دور محدد.

| الطريقة | الدور |
|---|---|
| `bot.on(event)` | استقبال أي حدث Telegram بالاسم |
| `bot.command(name)` | استقبال أمر محدد مثل `/start` |
| `bot.callback(data)` | استقبال ضغطة زر inline محددة |
| `bot.middleware` | تشغيل منطق قبل كل handler |
| `bot.telegram` | استدعاء Telegram API مباشرة |

### `bot.on` — استقبال الأحداث

```python
@bot.on("message")
async def on_message(ctx):
    await ctx.reply("وصلتني رسالتك.")

@bot.on("callback")
async def on_callback(ctx):
    await ctx.answer_callback()

@bot.on("channel")
async def on_channel(ctx):
    pass  # منشورات القناة
```

الأحداث المدعومة: `message`، `callback`، `channel`، `new_member`، `left_member`.

### `bot.command` — استقبال الأوامر

```python
@bot.command("start")
async def start(ctx):
    await ctx.reply("مرحباً!")

@bot.command("help")
async def help(ctx):
    await ctx.reply("أرسل أي رسالة للبدء.")
```

### `bot.callback` — استقبال أزرار Inline

```python
@bot.callback("confirm")
async def on_confirm(ctx):
    await ctx.answer_callback("تم التأكيد.")

@bot.callback("cancel")
async def on_cancel(ctx):
    await ctx.answer_callback("تم الإلغاء.")
```

إذا لم يوجد handler مطابق لـ `callback_data`، يُحوَّل التحديث إلى `bot.on("callback")`.

### `bot.middleware` — منطق ما قبل التنفيذ

يعمل قبل كل handler. استخدمه للـ logging، التحقق من الصلاحيات، ومنع الـ spam.

```python
@bot.middleware
async def guard(ctx, next):
    print(f"تحديث من المستخدم {ctx.user_id}")
    await next()
```

- `await next()` ← يكمل التنفيذ للـ handler
- `return` بدون استدعاء `next()` ← يوقف التحديث هنا

### `bot.telegram` — الوصول المباشر للـ API

للعمليات خارج سياق الرسالة الواحدة.

```python
await bot.telegram.send_message(chat_id=123, text="رسالة مباشرة.")
await bot.telegram.get_chat_member(chat_id=123, user_id=456)
await bot.telegram.pin_message(chat_id=123, message_id=789)
```

`bot.telegram` يتجاوز الـ middleware والـ ctx — للاستدعاء المباشر والصريح فقط.

---

## السياق (`ctx`)

كل handler يستلم كائن `ctx` يحمل بيانات التحديث الحالي وأدوات التفاعل.

### البيانات

```python
ctx.user_id        # int | None — معرّف المستخدم
ctx.chat_id        # int | None — معرّف الشات
ctx.text           # str | None — نص الرسالة
ctx.callback_data  # str | None — بيانات الزر المضغوط
ctx.is_banned      # bool — هل المستخدم في قائمة الحظر

ctx.sender         # بيانات المرسل: .id, .first_name, .username, .is_bot
ctx.chat           # بيانات الشات: .id, .type, .title, .username
ctx.message        # بيانات الرسالة: .id, .text
```

### الأفعال

```python
await ctx.reply("مرحباً")
await ctx.send("مرحباً")
await ctx.edit("نص محدّث")        # داخل callback handlers فقط
await ctx.delete_message()
await ctx.ban_user()
await ctx.leave()
await ctx.answer_callback("تم")
await ctx.fetch_permissions()      # يفحص صلاحية البوت في الشات
```

### الوصول الخام

```python
ctx.raw  # JSON الكامل القادم من Telegram
```

وجود `ctx.raw` مضمون وجزء من العقد. لكن *بنيته* تتبع Telegram API وقد تتغير — استخدمه فقط عند الحاجة لبيانات غير متاحة عبر `ctx` مباشرة.

---

## أزرار Inline

```python
from titan import Titan, InlineKeyboard

bot = Titan("YOUR_TOKEN")

@bot.command("start")
async def start(ctx):
    keyboard = (
        InlineKeyboard()
        .row()
        .button("نعم ✅", callback_data="confirm")
        .button("لا ❌", callback_data="cancel")
    )
    await ctx.reply("هل أنت متأكد؟", reply_markup=keyboard)

@bot.callback("confirm")
async def on_confirm(ctx):
    await ctx.answer_callback("تم التأكيد!")

@bot.callback("cancel")
async def on_cancel(ctx):
    await ctx.answer_callback("تم الإلغاء.")

bot.run()
```

---

## Router

يتيح لك تقسيم الـ handlers عبر ملفات متعددة ودمجها في البوت الرئيسي.

```python
# admin.py
from titan import Router

router = Router()

@router.command("ban")
async def ban(ctx):
    await ctx.ban_user()
    await ctx.reply("تم الحظر.")

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

Router يدعم: `on()`، `command()`، `callback()`.

Router لا يدعم: `middleware()` أو `include()` المتداخل.

---

## الأسماء البديلة (Aliases)

تتيح لك تعريف أسماء مخصصة لـ methods الـ ctx عبر `AliasMap` من `titan.extras`.

```python
from titan.extras.alias import AliasMap

aliases = AliasMap()
aliases.register("قل", "reply")
aliases.register("اطرد", "ban_user")

bot.middleware(aliases.as_middleware())

@bot.on("message")
async def handler(ctx):
    await ctx.قل("مرحباً")   # نفس ctx.reply()
    await ctx.اطرد()          # نفس ctx.ban_user()
```

الاسم الأصلي يبقى متاحاً بدون أي تغيير. Aliases طبقة تسمية فقط — لا تغير في السلوك.

`AliasMap` كيان مستقل — يمكن مشاركته بين routers متعددة:

```python
router1.middleware(aliases.as_middleware())
router2.middleware(aliases.as_middleware())
```

---

## نظام الحظر

```python
bot.banned_users  # set[int] — تديرها أنت بالكامل

bot.banned_users.add(user_id)
bot.banned_users.discard(user_id)
```

عندما يكون المستخدم في `bot.banned_users`، تكون `ctx.is_banned` قيمتها `True` قبل تشغيل الـ middleware. Titan لا تتصرف تلقائياً — الـ middleware تقرر ماذا تفعل.

```python
@bot.middleware
async def guard(ctx, next):
    if ctx.is_banned:
        return
    await next()
```

---

## تشغيل البوت

```python
# متزامن — الأنسب في أغلب الحالات
bot.run()

# غير متزامن — عندما تُدير event loop خاص بك
import asyncio
asyncio.run(bot.run_async())
```

كلا الأسلوبين ينفّذان نفس المنطق الداخلي.

---

## حواف حادة معروفة

---

### مشاكل سابقة تم إصلاحها

#### `bot.include()` — التحقق قبل التعديل

إذا احتوى الـ `Router` على handlers وأمر يتعارض مع أمر مسجَّل مسبقاً، فإن `bot.include()` تتحقق من التعارضات قبل أي تعديل في حالة البوت، ثم ترمي `TitanError` دون إضافة الـ Router جزئياً.

```python
@bot.command("start")
async def existing(ctx): ...

router = Router()

@router.on("message")
async def handler(ctx): ...  # لا يُضاف عند فشل التحقق

@router.command("start")
async def conflict(ctx): ...  # يُسبب TitanError

bot.include(router)
# TitanError مُرمى — ولا تُضاف handlers الـ Router
```

**التعامل معه:** عالج التعارض ثم أعد محاولة `include()` بالـ Router الصحيح.

---

#### `bot.callback("")` — لا يُنفَّذ أبداً

التسجيل بـ `callback_data` فارغة (`""`) ينجح بدون خطأ، لكن الـ handler لا يُستدعى أبداً عند وصول update يحمل `callback_data=""`. المنطق الداخلي يتعامل مع `""` كغياب البيانات.

```python
@bot.callback("")        # يُسجَّل بنجاح
async def handler(ctx):  # لا يُنفَّذ أبداً
    ...
```

**التعامل معه:** لا تستخدم سلسلة فارغة كـ `callback_data`. استخدم قيمة وصفية دائماً مثل `"noop"` أو `"skip"`.

---

### ضمانات غائبة (سلوك صحيح لكن بلا حماية)

هذه ليست أخطاء — Titan تتصرف بشكل متسق، لكنها لا تحمي من أنماط الاستخدام الخاطئة التالية:

**استدعاء `next()` مرتين في middleware**
يؤدي إلى تنفيذ كل handler مرتين. Titan لا تكتشف هذا. اتبع قاعدة: استدعاء `next()` مرة واحدة فقط.

**تسجيل أمر بشرطة مائلة: `bot.command("/start")`**
يُسجَّل بنجاح لكن لا يُطابق أي update أبداً. الاسم الصحيح هو `"start"` بدون شرطة مائلة.

**تسجيل `error_handler` أكثر من مرة**
يحتفظ Titan بموضع واحد لمعالج الأخطاء لكل bot. التسجيل الأخير يستبدل السابق
ويعالج الاستثناءات غير المعالجة اللاحقة. هذا سلوك مقصود، ولا يصدر تحذيراً أو
استثناءً.

**`AliasMap.register()` باسم يطابق خاصية موجودة في `ctx`**
يفحص `AliasMap.register()` الاسم مقابل الخصائص والـ methods المعرفة على `Context`، ويرمي `TitanError` عند التعارض معها. هذا الفحص لا يغطي كل خصائص الـ instance مثل `raw` و`sender` و`chat` و`message` و`permissions` و`is_banned`.

```python
aliases.register("text", "reply")
# TitanError — text خاصية موجودة في Context
```

استخدم أسماء لا تتعارض مع خصائص `Context` أو خصائص الـ instance.

**تمرير `async def` إلى `on_offset`**
`on_offset` تتوقع دالة عادية (synchronous). تمرير `async def` يرمي `TitanError` قبل بدء polling.

```python
async def save(offset):   # خطأ — دالة async
    ...

bot.run(on_offset=save)   # TitanError قبل بدء polling
```

استخدم دالة عادية. إذا احتجت async داخلها، فجدول العمل صراحةً على event loop يعمل.

---

## الفلسفة

Titan إطار عمل مبني على الاستقرار.

- الأشياء البسيطة تبقى بسيطة.
- الأشياء المعقدة ممكنة عبر `bot.telegram`.
- الـ API لا يتغير بدون إصدار جديد.
- لا سلوك خفي. لا magic. لا سباق ميزات.

---

## المساهمة

Titan يُبنى بأيدي أشخاص يهتمون بالواجهات الواضحة، والقرارات القابلة
للاستمرار، والتوثيق الصريح.

- [دليل المساهمة](CONTRIBUTING.md)
- [سجل Titan — The Titan Ledger](CONTRIBUTORS.md)

---

## الرخصة

**W.A.S.L v1.0** — رخصة واصل التجارية للبرمجيات
راجع ملف [LICENSE](LICENSE) للاطلاع على الشروط الكاملة.

---

© Copyright by **Waheed**. All rights reserved.
*(Alien's Zone ~ building real robots to help humanity thrive and stay alive! ^^)*
