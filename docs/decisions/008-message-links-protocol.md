# 008 — Message Links Protocol

**Status:** Accepted

---

## Proposal

إضافة بروتوكول هوية للرسائل التي يُرسلها البوت عبر Titan.

كل رسالة يُرسلها البوت عبر `ctx.send()` أو `ctx.reply()` تحصل تلقائياً
على هوية ثابتة تُمثَّل بـ `TitanMessageAddress`:

```
https://t.me/MyBot/482
```

هذا العنوان ليس رابط Telegram native. هو **Titan Message Address** — بروتوكول هوية فوق Telegram يفهمه Titan وأدواته.

القيمة الأساسية ليست التنقل، بل:
- تحديد رسالة بعينها بهوية ثابتة.
- إعطاؤها مرجعاً قابلاً للمشاركة بين المستخدمين والأدوات.
- تمكين Titan والأدوات المستقبلية من الإشارة إلى رسالة محددة بدقة.

---

## Investigation

راجع: [`docs/internal/investigations/message-links-protocol.md`](../internal/investigations/message-links-protocol.md)

التحقيق كشف عن بنية ذات طبقتين:

- **Identity Layer:** مسؤولية Titan — دائمة، تلقائية، بدون opt-in لمساري
  `ctx.send()` و`ctx.reply()`.
- **Archive Layer:** مسؤولية المطور — اختيارية تماماً.

وكشف عن نقطتين تحتاجان لمس خفيف في Core:
- `reply_to_message` غير مستخرج في `Update`.
- `ctx.send()` / `ctx.reply()` تُعيدان استجابة Telegram التي تحتوي على `telegram_message_id` — الـ intercepting متاح بدون تعديل Telegram API.

---

## Decision

### ١. طبيعة الميزة: Domain مستقل

Message Links Protocol ليست utility ولا command منفرد. هي بروتوكول وهوية لها مستقبل مستقل.

تعيش كاملةً في:

```
src/titan/links/
    __init__.py     — public API: enable_archive(), وغيرها
    identity.py     — TitanMessageIdentity + Identity Layer
    archive.py      — Archive Layer (اختيارية)
    store.py        — MessageStore interface + SqliteMessageStore
    handler.py      — /link command handler
    address.py      — TitanMessageAddress — بناء العناوين وتحليلها
```

هذا المجلد يمثل البروتوكول كاملاً: الإنشاء، الإدارة، التخزين، المعالجة، والتوسعات المستقبلية.

### ٢. الفصل بين الكود والبيانات

```
titan/links/        — كود وبنية الميزة (داخل package)
.titan/links.db     — بيانات تشغيلية (داخل مشروع المطور)
```

`.titan/links.db` ليس جزءاً من كود Titan. هو قاعدة بيانات ينشئها runtime لحفظ هوية الرسائل بجوار كود المطور.

### ٣. `TitanMessageAddress` — وحدة الهوية

الهوية لا تُمثَّل بـ `titan_id` منفرداً. الوحدة الأساسية هي `TitanMessageAddress` لأن الهوية مرتبطة بالبوت صاحب الرسالة:

```python
@dataclass(frozen=True)
class TitanMessageAddress:
    bot_username: str   # "MyBot"
    titan_id: int       # 482

    def __str__(self) -> str:
        return f"https://t.me/{self.bot_username}/{self.titan_id}"
```

`titan_id` وحده رقم مجرد. `TitanMessageAddress` هوية كاملة.

### ٤. `TitanMessageId` — Auto-increment Sequential

التسلسل الطبيعي per-bot: `1، 2، 3، …`

**السبب:** يتسق مع فلسفة Titan — "لا magic، لا سلوك خفي." الرسالة `482` تعني: "الرسالة الرابعة والثمانون وأربعمائة التي أرسلها هذا البوت." هذا مقروء ومعبّر.

**الـ tradeoff الموثق:** يكشف حجم الرسائل لمن يرى العناوين. هذا مقبول ومُوثَّق — ليس مخفياً.

**ما لا يُستخدم:**
- UUID: يكسر المقروئية.
- Opaque offset: يضيف تعقيداً بدون فائدة معمارية حقيقية.

### ٥. التخزين — SQLite افتراضي + واجهة مجردة

```python
class MessageStore(Protocol):
    async def save_identity(self, identity: TitanMessageIdentity) -> None: ...
    async def get_by_titan_id(self, titan_id: int) -> TitanMessageIdentity | None: ...
    async def get_by_telegram_id(self, chat_id: int, telegram_message_id: int) -> TitanMessageIdentity | None: ...
    async def mark_deleted(self, titan_id: int) -> None: ...
```

`SqliteMessageStore` هو التطبيق الافتراضي. المطور لا يكتب شيئاً في الحالة الاعتيادية.

المسار الافتراضي: `.titan/links.db` نسبةً إلى `os.getcwd()` عند تهيئة Identity Layer.

المسار والـ backend قابلان للتهيئة عبر `bot.links` — الواجهات الدقيقة تُحسم عند التنفيذ وتُعلن في `titan/links/__init__.py`.

### ٦. `bot.links` — واجهة عامة

`bot.links` property عامة لأن Message Links Protocol جزء من هوية Titan، لا implementation detail.

**ما هو مضمون كـ API:**
- `bot.links` نفسه — متاح دائماً بعد `Titan.__init__()`.
- `bot.links.enable_archive()` — تفعيل Archive Layer.
- `bot.links.set_store(store)` — استبدال backend التخزين.
- `bot.links.set_data_dir(path)` — تغيير مسار SQLite.
- `bot.links.get_address_for_telegram_id(chat_id, telegram_message_id)` — جلب عنوان Titan.
- `bot.links.get_address_for_titan_id(titan_id)` — جلب عنوان Titan.
- `bot.links.mark_deleted(titan_id)` — تعليم رسالة كمحذوفة في Identity Layer.

**ما ليس مضموناً:**
- الطبقات الداخلية (`SqliteMessageStore`، `_store`، إلخ) — تفاصيل تنفيذ، لا يعتمد عليها المطور مباشرةً.
- بنية `bot.links` الداخلية — تتطور بدون ضمان backward compatibility.

التخصيص يتم عبر `bot.links` حصراً — لا عبر بناء طبقات داخلية مباشرةً:

```python
# مدعوم — عبر bot.links
bot.links.set_store(MyCustomStore())
bot.links.set_data_dir("/var/data/mybot")
await bot.links.mark_deleted(titan_id)

# غير مدعوم — لا يُبنى LinksManager مباشرةً من المطور
bot.links = LinksManager(store=MyCustomStore())   # خارج API المضمون
```

**تغييرَا Core المقرَّران (اثنان فقط):**

**أولاً:** تهيئة `bot.links` في `Titan.__init__()`:

```python
# bot.py
from titan.links.identity import IdentityLayer

class Titan:
    def __init__(self, token: str) -> None:
        ...
        self.links = IdentityLayer()
```

**ثانياً:** استخراج `reply_to_message` في `Update`:

```python
# update.py
@property
def reply_to_message_id(self) -> int | None:
    msg = self.get_message()
    if not msg:
        return None
    reply = msg.get("reply_to_message")
    return reply.get("message_id") if reply else None
```

هذان التغييران هما الحد الكامل لما يمس Core. `titan.links` لا تعرف Core — الاعتماد في اتجاه واحد فقط.

### ٧. Archive Layer — تفعيل بدون تلويث Core

```python
# كود المطور
bot.links.enable_archive()

# أو عبر import صريح
from titan.links import enable_archive
enable_archive(bot)
```

Archive Layer تستمع لأحداث Identity Layer — لا تتدخل في Core مباشرة.

### ٨. الرسائل القديمة — Forward-only

Identity Layer تُنشئ الهوية **عند إرسال الرسالة** فقط.

عندما يرد مستخدم بـ `/link` على رسالة أُرسلت قبل تفعيل النظام:

```
هذه الرسالة أُرسلت قبل تفعيل Message Links Protocol.
لا تملك هوية Titan.
```

**السبب:** Retroactive Registration تكسر خاصية auto-increment الزمنية. الهوية تصف لحظة وجود حقيقية — ليس لحظة اكتشاف متأخرة.

### ٩. `/link` — كشف لا إنشاء

`/link` لا تُنشئ الهوية، تكشفها.

تعمل تلقائياً بدون أي تهيئة من المطور:
- المستخدم يرد على رسالة البوت بـ `/link`.
- Titan يستخرج `reply_to_message.message_id` من الـ update.
- يُرجع `TitanMessageAddress` للرسالة.

هذا يستلزم استخراج `reply_to_message` في `Update` — تغيير بسيط ومحدود.

**سياسة تعارض `/link`:**

`/link` أمر محجوز بواسطة Titan. إذا سجّل المطور handler لـ `/link` صراحةً:

```python
@bot.command("link")   # تعارض مع Titan
async def my_link(ctx):
    ...
```

يرفع Titan `TitanError` عند التسجيل — نفس السلوك عند تعارض أي أمرين مسجلَّين. `bot.include()` يُرسل نفس الخطأ إذا جاء التعارض من router.

الأمر محجوز في مرحلة التهيئة — لا تعارض صامت، لا override غير مقصود.

### ١٠. Resolver Layer (Official Bot) — خارج نطاق v1

Titan Official Bot يعمل كـ resolver للمستخدمين العاديين. هو مستهلك للهوية لا منشئ لها. الهوية تعيش عند بوت المطور دائماً.

آلية التواصل بين Official Bot وبوت المطور تُحسم في مرحلة مستقبلية.

---

## Rule

**بروتوكول الهوية ليس utility.**

أي ميزة تمس هوية كل رسالة يرسلها البوت عبر مساري `ctx.send()` أو
`ctx.reply()` وتملك بروتوكولاً وتخزيناً ومستقبلاً مستقلاً تستحق domain
واضحاً، لا ملفاً منفرداً أو إضافةً في Core.

**التخزين التشغيلي ليس كود Titan.**

الفصل بين `titan/links/` (كود) و`.titan/links.db` (بيانات) ليس تنظيمياً — هو مبدأ: Titan لا يمتلك بيانات المطور، يُنشئ مكاناً لها.

---

## Alternatives Considered

**UUID كـ TitanMessageId**

يُخفي الحجم تماماً ويمنع أي inference.

لم يُختر لأنه يكسر مقروئية العنوان — `https://t.me/MyBot/a3f2c1d4-7b2e-...` ليس عنواناً مفهوماً، وفلسفة Titan تقدّم الوضوح على الإخفاء.

**Retroactive Registration**

عند `/link` على رسالة قديمة، تُنشأ هوية بناءً على `telegram_message_id` المتاح.

لم يُختر لأن `titan_id` التسلسلي يفقد دلالته الزمنية: رسالة أُرسلت أولاً تحصل على `titan_id` متأخر. الهوية يجب أن تعكس لحظة الإرسال لا لحظة الاكتشاف.

**Identity Layer كـ middleware**

تسجيل Identity Layer كـ `bot.middleware` بدلاً من تهيئتها في `Titan.__init__()`.

لم يُختر لأن middleware تشغّله المطور اختيارياً، وIdentity Layer إلزامية. إلزامية middleware تكسر نموذج Titan للـ middleware كطبقة اختيارية.

**`bot._links` بدل `bot.links`**

إبقاء الواجهة internal بـ underscore.

لم يُختر لأن Message Links Protocol جزء من هوية Titan ظاهر للمطور، لا implementation detail. المطور يُفعّل Archive Layer ويتعامل مع `bot.links` — هذا يستلزم API عامة واضحة.

---

## v1 Limitations (Known, Accepted)

### أ. `ctx.reply()` لا تُعيد `TitanMessageAddress` مباشرةً

**الوضع الحالي:** `ctx.reply()` و`ctx.send()` تُعيدان استجابة Telegram الخام (`dict`). الهوية تُسجَّل تلقائياً داخلياً، لكن `TitanMessageAddress` لا تصل للمطور مباشرةً.

للوصول البرمجي للعنوان:
```python
result = await ctx.reply("مرحباً")
msg_id = result["result"]["message_id"]
address = await bot.links.get_address_for_telegram_id(ctx.chat_id, msg_id)
```

**السبب:** في v1 المسار الأساسي للمستخدم هو `/link`. التسجيل تلقائي وشفاف — المطور لا يحتاج العنوان في كل رسالة. تغيير signature `ctx.reply()` لإعادة Union أو tuple يُكسر العقد الحالي.

**مرشحة لـ v2:** `ctx.reply()` قد تُعيد `TitanMessageAddress` مباشرةً، أو تُوفَّر `ctx.reply_with_address()` كبديل. القرار مؤجَّل حتى تتضح أنماط الاستخدام الفعلي.

### ب. التسجيل يقتصر على `ctx.reply()` و`ctx.send()`

رسائل تُرسَل عبر `ctx.telegram.send_message()` أو `self._api` مباشرةً لا تُسجَّل هوية تلقائياً. هذا مقبول في v1 — الغالبية العظمى من الرسائل تمر عبر `ctx.reply()` أو `ctx.send()`.

### ج. Archive تعمل مع `SqliteMessageStore` فقط

Custom stores لا تدعم Archive Layer في v1. القيد موثق في واجهة `LinksManager`.

---

## Consequences

**ما يُكتسب:**
- كل رسالة يرسلها أي بوت Titan عبر `ctx.send()` أو `ctx.reply()` تملك
  هوية ثابتة بدون أي جهد من المطور.
- `/link` تعمل تلقائياً بدون تسجيل handler.
- Archive Layer متاحة لمن يحتاجها بسطر واحد.
- `bot.links.mark_deleted()` تُتيح للمطور تعليم الرسالة كمحذوفة بدون لمس طبقات داخلية.
- Domain مستقل يستوعب التوسعات المستقبلية (Official Bot، Architect AI، أدوات المطور) بدون لمس Core.

**القيود المقبولة:**
- Auto-increment يكشف حجم الرسائل. موثق، مقبول.
- الرسائل السابقة لتثبيت النظام لا تملك هوية Titan. Forward-only بوعي.
- التغييرات على Core محدودة: تهيئة `bot.links` في `Titan.__init__()` + استخراج `reply_to_message` في `Update` + intercepting `ctx.reply()`/`ctx.send()`.
- SQLite يعمل في معظم البيئات. من يحتاج backend مختلف يستخدم `MessageStore` interface.
