# تحقيق — Telegram Rich Messages في Titan

**الحالة الحالية:** اعتُمد القرار في ADR-023، ووُثّق في `CONTRACT.md`، ونُفّذ مع الاختبارات.
**المرجع النهائي:** [ADR-023 — Rich Message Content Boundary](../../decisions/023-rich-message-content-boundary.md)
**آخر مزامنة للحالة:** 2026-09-30
**تاريخ بدء التحقيق:** 2026-09-04
**النطاق:** Telegram Bot API 10.1–10.3، وما يلزم أو لا يلزم في Titan  
**المرجع الداخلي:** جميع ملفات `docs/internal/investigations/` الحالية، مع قراءة
مباشرة للكود الحالي  
**المصادر الخارجية الأساسية:** Telegram Bot API وBot API changelog الرسميان

هذا الملف سجلّ تاريخي للبحث ومراحل تطور القرار، وليس مواصفة التنفيذ الحالية.
عند اختلاف أي اقتراح أو وصف قديم فيه مع ADR-023 أو `CONTRACT.md`، تكون الأولوية
لـ ADR والعقد الحاليين. المقاطع التي تصف غياب التنفيذ تصف خط الأساس وقت التحقيق،
إلا إذا نصّت صراحةً على أن السلوك ما زال مؤجلاً.

---

## 1. الخلاصة التنفيذية — الحالة الحالية

Rich Messages محتوى داخل الرسالة، وليست نوع Update أو مسار routing جديداً.
الدعم الأساسي في Titan منفذ حالياً:

```text
incoming: Message.rich_message → RichMessage
outgoing: RichContent → ctx.send() / ctx.reply() / ctx.edit()
```

يعتمد القرار النهائي على `RichContent` كقيمة outgoing ذات mode صريح
(`html` أو `markdown` أو `blocks`)، وعلى `RichMessage` كـ read model للمحتوى
الوارد. تقبل أفعال `Context` الحالية `str | RichContent` عبر معامل `text`؛
ولا توجد أفعال `ctx.send_rich()` أو `ctx.reply_rich()` أو `ctx.edit_rich()`.
التفاصيل والقيود النهائية موثقة في ADR-023 و`CONTRACT.md`.

أما drafts وstreaming و`stopped_message_generation` فتبقى خارج دعم الرسائل
الأساسي ومؤجلة بسبب اختلاف lifecycle، وفق ADR-023.

---

## 2. لماذا فتحنا هذا التحقيق؟

### 2.1 المشكلة من منظور المطوّر

المطوّر الذي يبني bot حديثاً لا يريد دائماً فقرة نصية مع `parse_mode`. يريد
أحياناً:

- عنواناً وقائمة وجدولاً واقتباساً قابلاً للطي.
- صيغة رياضية أو footnote أو رابطاً داخل المستند.
- صورة أو فيديو أو ملفاً داخل بنية الرسالة نفسها.
- أزراراً داخل المحتوى أو `reply_markup` إلى جانب المحتوى.
- بث إجابة AI جزئية ثم تثبيتها كرسالة نهائية.

في Titan الحالي، المسار المتاح هو:

```python
await ctx.reply(text, parse_mode="HTML")
await ctx.send(text, reply_markup=keyboard)
await bot.telegram.send_photo(...)
```

هذا يغطي نصاً منسقاً ووسائط منفصلة، لكنه لا يمثل Rich Message ككيان واحد.

### 2.2 ليست المشكلة «Telegram أضاف feature»

وجود قدرة في Telegram لا يكفي وحده لتغيير Titan. السؤال الصحيح:

> هل فقد Titan معلومة أو قدرة يحتاجها المطوّر فعلاً، وهل يقع الفقد في
> abstraction موجودة بالفعل أم أنه capability جديدة خارج حدود Core؟

في لقطة بداية التحقيق بتاريخ 2026-09-04، ظهرت الفجوة التالية:

1. Telegram يعيد `Message.rich_message`.
2. `BotApiTranslator` لا يستخرج إلا `text` من الرسالة.
3. `Message.text` و`Update.text` في Titan لا يقدمان بديلاً.
4. `Telegram` لا يملك `sendRichMessage`.
5. `Context.reply()` و`Context.send()` لا يملكان مدخلاً لمحتوى Rich.

هذه كانت مبررات التحقيق وليست وصفاً للحالة الراهنة: أُضيفت القراءة والإرسال
والتعديل الأساسي لاحقاً وفق ADR-023، وأصبح لها عقد واختبارات.

---

## 3. ما الذي تعنيه Telegram بـ Rich Messages؟

### 3.1 الخط الزمني الرسمي

بحسب `https://core.telegram.org/bots/api-changelog`:

| التاريخ | الإصدار | الإضافة ذات الصلة |
|---|---:|---|
| 2026-06-11 | Bot API 10.1 | الإضافة الأصلية لـ Rich Messages: `RichMessage`, `RichBlock`, `InputRichMessage`, `sendRichMessage`, `sendRichMessageDraft`، وربطها بـ `Message` و`editMessageText` |
| 2026-07-14 | Bot API 10.2 | block input types، الوسائط الصريحة داخل HTML/Markdown، voice note input، ومجموعة أوسع من blocks |
| 2026-08-24 | Bot API 10.3 | أزرار Rich، block buttons، expandable quotations، document blocks، compact tables، ودعم `tg://document?id=` |

هذا مهم معمارياً: السطح لم يستقر على نوع واحد صغير منذ أول إصدار؛ هو يتوسع
على شكل schema Telegram خاص به. لذلك تقليده كاملاً داخل Titan الآن يحمل مخاطرة
أن يصبح Titan نسخة متأخرة من Bot API.

### 3.2 ثلاث طرق لتمثيل الرسالة الصادرة

`InputRichMessage` يفرض أن يُستخدم **واحد فقط** من الحقول الأساسية التالية:

| النمط | ماذا يرسل المطوّر؟ | من يملك parsing؟ |
|---|---|---|
| `markdown` | نص Rich Markdown | Telegram |
| `html` | نص Rich HTML | Telegram |
| `blocks` | قائمة blocks صريحة | Telegram بعد التحقق من schema |

وتوجد حقول مشتركة:

- `media`: وسائط تربطها صيغة `tg://photo?id=...` ونظائرها في HTML/Markdown.
- `is_rtl`: عرض الرسالة من اليمين إلى اليسار.
- `skip_entity_detection`: تعطيل الاكتشاف التلقائي للروابط، البريد، mention،
  hashtag، cashtag، bot command، رقم الهاتف، ورقم البطاقة.

المبدأ الناتج:

```text
Rich Message = content mode + Telegram-defined options
```

ليس:

```text
Rich Message = HTML parsed by Titan into a Titan AST
```

### 3.3 ما الذي يمكن تمثيله؟

الوثائق الرسمية تصف دعم:

- headings وparagraphs.
- bold/italic/underline/strikethrough/marked/spoiler.
- inline code وpreformatted code.
- روابط، email، phone، user mention، anchors وreferences.
- date-time وcustom emoji وsubscript/superscript وLaTeX formulas.
- ordered/unordered lists، checkbox list items.
- block quotations وpull quotations وexpandable quotations.
- collages وslideshows.
- tables مع خلايا وrowspan/colspan وalignment.
- details قابلة للفتح والإخفاء.
- map blocks.
- photo/video/audio/document/animation/voice-note blocks.
- thinking block في draft.
- أزرار Rich في Bot API 10.3.

هذه القائمة تصف **قدرة Telegram**، ولا تعني أن Titan يجب أن يعرض class لكل
عنصر منها في أول نسخة.

### 3.4 الوسائط ليست تفصيلاً داخل النص

في HTML/Markdown:

- يمكن الإشارة إلى media بعناوين `tg://...`.
- الوسائط في rich formatting تُفهم كـ **media blocks** منفصلة.
- Telegram يحدد نوع الوسيط من MIME/URL في بعض المسارات.
- Bot API 10.2 أضاف `InputRichMessageMedia` للربط الصريح بين id و`InputMedia`.
- Bot API 10.3 أضاف document blocks ودعم `tg://document?id=`.
- الوثائق تقيد media blocks بعناوين HTTP/HTTPS حيث ينطبق ذلك، ولا تسمح
  بإخفاء upload semantics داخل نص عادي.

لذلك لا يصح تمثيل rich media كـ `text` مع caption فقط، ولا دمجه تلقائياً مع
واجهة `send_photo()` الحالية.

### 3.5 الحدود الرسمية

Telegram تفرض حالياً:

- 32768 محرف UTF-8 في النص الغني، بما في ذلك alternative text للـ custom
  emoji ومصدر المعادلة.
- 500 block كحد أقصى، مع احتساب العناصر المتداخلة وlist items والصفوف.
- 16 مستوى للتداخل.
- 50 media attachments.
- 20 عموداً في table.

هذه قيود Telegram، وليست مكاناً مناسباً لتكرارها في كل طبقة من Titan قبل
الحاجة. يمكن التحقق منها في boundary واحدة عند التنفيذ أو ترك Telegram يرجع
خطأه في المرحلة الأولى، لكن لا ينبغي أن تتوزع نسخ مختلفة منها في models.

---

## 4. الإرسال، التعديل، والاستقبال

### 4.1 `sendRichMessage`

`sendRichMessage` يعيد `Message` عند النجاح، ويقبل بالإضافة إلى `rich_message`
المعاملات المعتادة مثل:

- `chat_id`
- `reply_parameters`
- `reply_markup`
- `message_thread_id`
- `business_connection_id`
- `disable_notification`
- `protect_content`
- `message_effect_id`
- `suggested_post_parameters`
- `ephemeral_message_parameters` في Bot API 10.3

إذن Rich content لا يستبدل `reply_markup`. هما سطحان مختلفان:

```text
content:       rich_message
presentation:  reply_markup
```

ولا يجوز أن يحوّل Titan كل زر Rich إلى `InlineKeyboardButton`؛ أزرار Rich
داخل المحتوى وأزرار reply markup ليستا نفس الحقل ولا نفس الدلالة.

### 4.2 `editMessageText`

Telegram أضاف `rich_message` إلى `editMessageText`. هذا يعني أن تعديل النص
الغني ليس بالضرورة تعديل `text` مع `parse_mode`. يجب أن يظل في Titan تمييز
واضح بين:

- تعديل رسالة نصية.
- تعديل رسالة Rich.
- تعديل reply markup.

`ctx.edit()` الحالي يملك مسار النص فقط، ولا ينبغي أن يُحمّل تدريجياً كل
الاحتمالات دون قرار صريح حول التوافق وسلوك المعاملات المتعارضة.

### 4.3 `sendRichMessageDraft`

هذا ليس «نسخة أسرع من sendRichMessage». الوثيقة الرسمية تقول:

1. الـ draft جزئي ومؤقت.
2. يعيش كـ preview ephemeral لمدة قصيرة، لا كرسالة محفوظة.
3. لإبقاء النتيجة يجب استدعاء `sendRichMessage` برسالة كاملة.
4. هو مخصص لـ private chat.
5. `draft_id` يحدد هل تتغير المعاينة بالanimation أم تستبدل.
6. `can_stop` يعرض زر إيقاف.
7. ضغط الإيقاف يولد `Update.stopped_message_generation`.
8. `keep_on_stop` يحدد سلوك المعاينة عند الإيقاف، لكنه لا يحولها تلقائياً
   إلى رسالة نهائية محفوظة.

هذا يضيف state وlifecycle وevent semantics. لذلك يُعامل كمسألة مستقلة عن
basic Rich send.

### 4.4 ما الذي يصل إلى Update؟

Rich Message لا تصل في حقل Update جديد. تصل داخل مسار الرسالة العادي:

```text
Update.message.rich_message
Update.edited_message.rich_message
Update.channel_post.rich_message
...
```

ووفق نموذج Telegram، `Update` يملك في كل مرة حقلاً اختيارياً واحداً من عدة
حقول، ومن بينها `message` و`edited_message` و`channel_post` وغيرها. Rich
Message هي قيمة داخل `Message`، لا نوع event موازٍ لـ `callback_query`.

الاستثناء المرتبط بالstreaming هو:

```text
Update.stopped_message_generation
```

وقد أضيف في Bot API 10.3 مع stop controls. هذا event منفصل ويحتاج قراراً
خاصاً في routing، ولا ينبغي خلطه مع وصول رسالة Rich عادية.

### 4.5 Inline query content

Telegram يسمح باستخدام `InputRichMessageContent` كنتيجة لمحتوى inline query.
هذا يؤكد أن `InputRichMessage` ليس فقط payload لـ `sendRichMessage`، بل يمكن
أن يعيش داخل surface أخرى. وفي المقابل، يظل ذلك خارج routing الحالي في Titan
لأن inline queries غير مدعومة كـ event رسمي في Core.

---

## 5. ما هو مؤكد، وما هو افتراض؟

### 5.1 حقائق مصدرية مؤكدة

| الحقيقة | مصدر الإثبات |
|---|---|
| Rich messages موجودة في Bot API 10.1 على الأقل | changelog الرسمي، 2026-06-11 |
| Blocks والمدخلات الصريحة توسعت في 10.2 | changelog الرسمي، 2026-07-14 |
| Rich buttons وdocuments وexpandable quotes ظهرت في 10.3 | changelog الرسمي، 2026-08-24 |
| `Message.rich_message` هو موضع الاستقبال | Bot API الرسمي، تعريف `Message` |
| `InputRichMessage` يفرض html أو markdown أو blocks | Bot API الرسمي، تعريف `InputRichMessage` |
| `sendRichMessage` يعيد `Message` | Bot API الرسمي، تعريف method |
| draft مؤقت ويحتاج final send للحفظ | Bot API الرسمي، تعريف `sendRichMessageDraft` |
| `stopped_message_generation` Update منفصل | changelog الرسمي 10.3 وتعريف `Update` |
| لا يوجد في Titan حالياً `sendRichMessage` أو model رسمي له | قراءة مباشرة للكود |
| `Message.text` في Titan يقرأ `raw["text"]` فقط | `src/titan/models/message.py` |
| `Update.text` في Titan يقرأ `msg["text"]` فقط | `src/titan/update.py` |

### 5.2 افتراضات لا يجوز تحويلها إلى قرارات

- لا نفترض أن كل rich message ستحتاج نفس block classes في Titan.
- لا نفترض أن `rich_message` يصل دائماً مع `text` موازي.
- لا نفترض أن `sendRichMessageDraft` يجب أن يدخل Core مع أول basic send.
- لا نفترض أن `RichMessageButton` هو `InlineButton` باسم جديد.
- لا نفترض أن parsing المحلي سيعطي نفس rendering Telegram.
- لا نفترض أن دعم نوع واحد في Telegram يعني أن Titan يجب أن يعمم على MTProto
  أو منصات أخرى.

---

## 6. خط أساس Titan عند فتح التحقيق — لقطة 2026-09-04

> هذا القسم يوثّق حالة الكود قبل تنفيذ ADR-023، وليس حالة Titan الحالية.
> الواجهة المعتمدة والمنفذة موضحة في القسم 1 وADR-023.

### 6.1 نقطة الدخول والترجمة

`src/titan/bot.py` يبني:

```text
raw_update → Update(raw_update) → Context(update, api)
```

`src/titan/update.py` يملك `BotApiTranslator`. المترجم الحالي يقرأ:

- `message`
- `channel_post`
- `callback_query`

ثم يحول إلى `ParsedBotApiUpdate` مسطح يحتوي `text`, `message_id`,
`user_id`, `username`, `chat_id`, `chat_type`, reply data وcallback data.

هذا جيد بالنسبة لنموذج Titan المبسط، لكنه يعني أن `rich_message` يفقد طريقه
إلى `ParsedBotApiUpdate` إذا احتاجته طبقة أعلى.

### 6.2 نموذج Message

`src/titan/models/message.py` هو data-only object. يملك حالياً:

- `raw`
- `id`
- `text`
- `chat_id`
- `to_dict()`

هذا يجعل إضافة accessor للقراءة منطقية مبدئياً، بشرط أن يبقى data-only وألا
يبدأ في إرسال أو تعديل الرسائل.

### 6.3 Context

`src/titan/ctx.py` يملك:

- `reply(text, parse_mode, reply_markup)`
- `send(text, parse_mode, reply_markup)`
- `edit(text, parse_mode, reply_markup)`

ويستخدم `_api` داخلياً. هذا متسق مع قاعدة العقد:

> `ctx` هو نقطة التنفيذ الوحيدة داخل دورة update-response.

إضافة rich response إلى `bot.telegram` وحده ستكون قدرة موجودة تقنياً لكنها
تتجاوز boundary المعلنة عندما يكون المطوّر داخل handler. إذا دعمنا الإرسال
من handler، يجب أن يمر عبر Context أو عبر امتداد رسمي يبرر خرق هذه القاعدة.

### 6.4 Telegram وTelegramAdapter

`src/titan/telegram.py` يملك request generic، ثم methods محددة مثل:

- `send_message`
- `edit_message_text`
- `delete_message`
- `answer_callback_query`

`src/titan/adapter.py` يضيف surface مباشرة لعمليات Bot API، منها media
وforward وpin وإعدادات البوت. لا توجد methods Rich حالياً.

الطبقة الحالية قادرة فعلياً على POST لأي method إذا أعطي لها payload، لكن
وجود `request()` الداخلي ليس public Rich support. القدرة المخفية لا تكفي
كعقد مطوّر.

### 6.5 Router وunknown updates

Rich message العادية لا تحتاج route جديداً. إذا جاءت في `message`، فالمسار
الصحيح يظل `on("message")` أو command/semantic route المناسب. هذا متسق مع
تحقيق `api-evolution-unknown-types.md`: لا نضيف route لنوع بيانات داخلي.

أما `stopped_message_generation` فهو Update type مختلف. حالياً سيُصنّف ضمن
unrouted/unsupported بحسب التنفيذ الحالي، ولا ينبغي إصلاحه ضمناً ضمن Rich
model قبل قرار مستقل حول event.

### 6.6 العقد الحالي

`CONTRACT.md` يثبت عدة حدود لها أثر مباشر:

- `Message / Update / Chat / Sender = data-only`.
- `ctx.raw` و`model.raw` escape hatches رسمية.
- العمليات داخل دورة update تمر عبر `ctx`.
- `bot.telegram` surface خارج دورة update.
- الـ public API مستقر، ولا يضاف feature لمجرد أن Telegram أضافه.
- Router أداة تنظيم، وليس شجرة runtime جديدة.
- updates غير المدعومة/المجهولة لا تصل إلى handlers.

هذه القواعد لا تمنع Rich Messages، لكنها تمنع تنفيذها كـ:

- تعديل عشوائي لـ Router.
- parser يخفي Telegram داخل models.
- API ثانية تتجاوز Context.
- mutation methods داخل `Message`.

---

## 7. أين كانت تقع الفجوة قبل التنفيذ؟

```text
Telegram Message.rich_message
          │
          ▼
BotApiTranslator ──(اليوم: يحتفظ بـ text فقط)──▶ ParsedBotApiUpdate
          │
          ▼
Message.raw ──▶ message.text فقط
          │
          ▼
Context.reply/send ──▶ sendMessage فقط
```

الفجوة مكونة من مسارين مستقلين:

### المسألة أ — الاستقبال

الرسالة تصل إلى route صحيح، لكن محتواها Rich غير ممثل في نموذج Message إلا
بشكل raw. هذا يخلق نتيجتين:

- handler قد يرى `ctx.text is None` رغم أن الرسالة تحمل محتوى حقيقياً.
- المطوّر الذي لا يريد الاعتماد على raw لا يملك accessor رسمي.

### المسألة ب — الإرسال

لا يوجد API رسمي لإرسال:

- `InputRichMessage` عبر `ctx`.
- `InputRichMessage` عبر `bot.telegram`.
- Rich edit عبر `ctx.edit` أو adapter.
- Rich draft عبر أي surface.

المسألتان مرتبطتان بالاسم، لكنهما ليستا نفس القرار. يمكن دعم read قبل write،
ويمكن دعم basic write قبل draft streaming.

---

## 8. البدائل المعمارية

### البديل A — raw-only

مثال تصوري:

```python
await bot.telegram.request(
    "sendRichMessage",
    {"chat_id": chat_id, "rich_message": payload},
)
```

**مزايا:**

- أقل كود.
- لا يكرر Telegram schema.
- forward-compatible مع الحقول الجديدة.

**مشكلات:**

- لا يحترم boundary التي تجعل `ctx` نقطة التنفيذ داخل handler.
- لا يقدم `Message.rich_message` رسمي.
- يضع صحة payload كاملة على كل مطوّر.
- يجعل الدعم موجوداً في implementation detail لا في public API.

**الحكم: Reject كحل نهائي.**  
يبقى raw مفيداً كـ escape hatch، لا كخطة دعم رسمية.

### البديل B — مرآة كاملة لـ Telegram

إنشاء class لكل:

- `RichText*`
- `RichBlock*`
- `InputRichBlock*`
- `InputMedia*`
- buttons والوسائط والـ inline content

**مزايا:**

- type safety مرتفعة.
- API Pythonية جميلة.

**مشكلات:**

- حجم كبير قبل إثبات ضغط الاستخدام.
- coupling مباشر مع schema يتغير بين 10.1 و10.3.
- duplication بين Telegram validation وTitan validation.
- تكلفة breaking changes عند كل توسعة.
- لا يضمن rendering مطابقاً لـ Telegram.

**الحكم: Reject حالياً.**  
قد يصبح بعضه مناسباً لاحقاً في طبقة اختيارية إذا ظهر ضغط واضح.

### البديل C — envelope رسمي مع nested Telegram payload

غلاف صغير يثبت:

```text
InputRichMessage
  ├── exactly one: html | markdown | blocks
  ├── media
  ├── is_rtl
  └── skip_entity_detection
```

وتبقى تفاصيل blocks وmedia في بنية صريحة قابلة للتوسع، مع validation للحقول
المتعارضة فقط. في الاستقبال:

```text
Message.rich_message
  ├── blocks
  └── is_rtl
```

**مزايا:**

- يحل الفجوة الحقيقية.
- لا يخفي أن schema مصدرها Telegram.
- يثبت invariants ذات القيمة، خصوصاً اختيار mode واحد.
- يسمح بـ raw escape hatch داخل nested fields.
- يتيح typing تدريجياً بدل مرآة كاملة.

**مشكلات:**

- typing داخل blocks أقل صرامة في البداية.
- بعض أخطاء payload ستظهر من Telegram لا من Titan.
- يحتاج قراراً دقيقاً حول أسماء الغلاف وحدود public API.

**الحكم: Adapt — البديل الموصى به.**

### البديل D — Titan canonical AST ثم translators

ينشئ Titan نموذجاً عاماً لـ rich documents، ثم يحوله إلى Telegram.

**مزايا:**

- قابل نظرياً لدعم MTProto أو منصات أخرى.
- يملك Titan semantics خاصة به.

**مشكلات:**

- لا توجد حالياً حاجة متعددة السطوح تبرره.
- يفرض على Titan امتلاك rendering semantics.
- يخفي فروق Telegram مثل media blocks وRich buttons وdraft lifecycle.
- يحوّل ميزة Telegram إلى product مستقل داخل Core.

**الحكم: Reject الآن، وإعادة فتحه فقط إذا أثبت مشروع متعدد transports أن
المعنى المشترك حقيقي وليس تشابهاً في الاسم.**

---

## 9. القرار المعماري المبدئي — مقترح تاريخي قبل ADR-023

> النقاط هنا سجّلت اتجاه التحقيق الأولي. القرار النهائي المعتمد هو ADR-023،
> الذي عدّل أسماء الـ API وحدودها كما هو موضح في القسم 1.

### 9.1 ما يجب أن يفعله Titan

1. يظل Rich message داخل message route العادي.
2. يضيف قراءة رسمية data-only للمحتوى الوارد.
3. يضيف إرسالاً رسمياً داخل Context وخارجه.
4. يفصل `InputRichMessage` عن `RichMessage` الناتجة.
5. يثبت اختيار mode واحد (`html`/`markdown`/`blocks`) في boundary Titan.
6. يمرر block/media schema دون أن يدعي امتلاك semantics Telegram كاملة.
7. يبقي `reply_markup` سطحاً منفصلاً عن rich content.
8. يعامل drafts وstop updates كمرحلة lifecycle مستقلة.
9. يبقي `raw` متاحاً دائماً للحقول التي لم يغلفها Titan بعد.

### 9.2 ما يجب ألا يفعله Titan

- لا يضيف `on("rich_message")` لرسالة هي أصلاً `message`.
- لا يحول rich message إلى `ctx.text` مصطنعاً.
- لا يقرأ HTML/Markdown ثم يعيد تفسيره محلياً.
- لا يخلط `RichMessageButton` مع `InlineButton`.
- لا يضع operations داخل `Message`.
- لا يجعل المطوّر يستدعي `_api` أو `request()` مباشرة كحل رسمي.
- لا يضيف كل Telegram types إلى `titan.models` دفعة واحدة.
- لا يضع Rich support داخل Router أو middleware.
- لا يضيف streaming state إلى `Context` قبل حسم ownership والإيقاف والإلغاء.
- لا يغير CONTRACT أو السلوك الحالي لـ `send()` و`reply()` لمجرد إضافة method
  جديدة، إلا بعد تحديد توافق المعاملات المتعارضة.

### 9.3 أين توضع Rich Messages؟

```text
src/titan/
    rich/
        __init__.py       # غلاف الإدخال/الإخراج، إن ثبتت public boundary
        models.py         # data-only envelope فقط
    models/message.py     # accessor للـ RichMessage الواردة
    update.py             # تمرير rich_message دون route جديد
    ctx.py                # reply/send/edit Rich داخل دورة update
    telegram.py           # raw transport methods
    adapter.py            # bot.telegram methods خارج الدورة
```

وجود مجلد `rich/` اقتراح placement لا تنفيذ مطلوب. يجب ألا ينشأ إلا بعد حسم
الأسماء العامة. لا ينبغي وضعه في `keyboard.py` أو `router.py` أو `extras`.

---

## 10. أقل API مقترحة في مرحلة التصميم الأولى — تاريخية وغير معتمدة

الأسماء التالية كانت مقترحات للنقاش وليست API معتمدة؛ رُفضت الأفعال
`*_rich` وقيمة `RichInput` لصالح `RichContent` مع أفعال `Context` الحالية،
وفق ADR-023:

```python
rich = RichInput.markdown("## Hello")
rich = RichInput.html("<h2>Hello</h2>")
rich = RichInput.blocks(blocks=[...])

await ctx.reply_rich(rich, reply_markup=keyboard)
await ctx.send_rich(rich)
await bot.telegram.send_rich_message(chat_id, rich)
```

والقراءة:

```python
if ctx.message.rich_message is not None:
    blocks = ctx.message.rich_message.blocks
```

القواعد التي يجب أن يثبتها التصميم، بصرف النظر عن الاسم:

- `markdown`, `html`, و`blocks` لا تجتمع.
- `media` لا تُقبل كبديل عن content mode.
- `RichMessage` الواردة ليست نفس `InputRichMessage`.
- كل model يبقى data-only وله `raw` و`to_dict()` حيث ينطبق contract.
- `ctx.reply_rich()` يستخدم reply semantics، و`ctx.send_rich()` لا يستخدمها.
- `bot.telegram.send_rich_message()` لا يختبئ خلف Context ولا يسجل handler state.
- لا يوجد implicit conversion من `str` إلى Rich input في المرحلة الأولى.

### 10.1 هل نوسع `ctx.send()` الحالي؟

المساران:

| الخيار | الحكم |
|---|---|
| `ctx.send(text=None, rich_message=...)` | يحافظ على اسم واحد لكنه يخلق حالات متعارضة ويجعل signature أكثر غموضاً |
| `ctx.send_rich()` و`ctx.reply_rich()` | يوضح intent، يترك `send()` القديم ثابتاً، ويسهل اختبار semantics |

**التفضيل المبدئي وقتها:** methods صريحة جديدة. رُفض هذا التفضيل لاحقاً:
`RichContent` الصريحة تختار النقل الغني داخل `send()` و`reply()` و`edit()`
مع الإبقاء على اسم المعامل `text` للتوافق؛ والجمع مع `parse_mode` مرفوض
وفق العقد الحالي.

### 10.2 هل نضيف كل block models؟

ليس في المرحلة الأولى. الغلاف يمكن أن يستخدم:

- typed envelope للـ mode والخيارات العامة.
- `list[dict[str, Any]]` أو بروتوكول payload واضح للـ blocks.
- raw media/button payloads داخل scope معلن.

بعد وجود أمثلة استخدام فعلية يمكن ترقية العناصر المتكررة إلى builders أو
models اختيارية. الترقية يجب أن تكون إضافة لا إعادة تعريف لما يرسله Telegram.

---

## 11. أثر القرار على CONTRACT — قائمة ما قبل التنفيذ

> القائمة التالية تسجل ما كان مطلوباً قبل اعتماد ADR-023. أُضيف عقد الدعم
> الأساسي إلى `CONTRACT.md`؛ راجع ADR-023 وواجهة الحالة الحالية في القسم 1.

### لا يتغير

- routing للرسائل.
- معنى `on("message")`.
- قواعد middleware.
- `ctx.raw` و`Message.raw`.
- `Message` data-only.
- `bot.telegram` كطبقة خارج دورة update.
- سياسة drop للـ updates غير المدعومة.
- `InlineButton` و`InlineKeyboard`.

### ما كان مطلوباً إضافته إلى العقد

قبل اعتماد القرار، كان يلزم توثيق:

1. وجود `Message.rich_message` عند وجود Telegram field.
2. الفرق بين `RichMessage` الواردة و`InputRichMessage` الصادرة.
3. أن rich messages العادية تمر من `message` route.
4. semantics `reply_rich` و`send_rich`.
5. معاملة `html`/`markdown`/`blocks` كـ mutually exclusive.
6. هل `raw` nested blocks مضمون أم مجرد Telegram-owned data.
7. هل Rich drafts و`stopped_message_generation` داخل v1 أم مؤجلان.

### ما بقي خارج نطاق ADR-023 أو مؤجلاً

- streaming drafts وownership أثناء توقف handler.
- إدخال `stopped_message_generation` إلى event system.
- أي abstraction cross-transport.
- typed block builders واسعة النطاق.

كان هذا سبب طلب مراجعة وقرار معماري قبل التنفيذ؛ وقد حسم ADR-023 حدود الدعم
الأساسي. أما العناصر المؤجلة فتحتاج قراراً منفصلاً قبل تنفيذها.

---

## 12. خطة التنفيذ الأصلية وحالتها الحالية

كانت هذه الخطة مكتوبة قبل ADR-023. نُفذ الدعم الأساسي للإرسال والاستقبال
والتعديل باستخدام `RichContent` و`RichMessage` وأفعال `Context` الحالية،
مع اختبارات. بقيت drafts/streaming وbuilders إضافية خارج النطاق ومؤجلة.

### Phase 0 — Fixtures وفهم schema

- حفظ أمثلة raw منفصلة لـ:
  - message غني بـ markdown.
  - message غني بـ blocks.
  - media-rich message.
  - edited rich message.
  - rich message مع reply markup.
  - `stopped_message_generation`.
- التحقق من أن fixtures لا تعتمد على `text` موجوداً عرضاً.

### Phase 1 — Basic send (منفذة)

- أُضيفت قيمة outgoing العامة `RichContent`، واختير mode صريح لكل payload.
- أُضيف إرسال `RichContent` عبر `ctx.send()` و`ctx.reply()` مع الحفاظ على
  أفعال `Context` ومعامل `text` الحاليين.
- اختُبرت مطابقة payload وحدود الإرسال في اختبارات Rich.

### Phase 2 — Basic receive (منفذة)

- أُضيف `Message.rich_message` كـ `RichMessage` للقراءة data-only، من دون
  إنشاء route جديد.
- يبقى `ctx.text` بلا قيمة عندما لا يحتوي التحديث على `text`؛ لا يُختلق
  projection من Rich content.

### Phase 3 — Rich edit (منفذة)

- يقبل `ctx.edit()` قيمة `RichContent`، وتغطي الاختبارات payload التعديل
  والتحقق من mode.
- يتعارض `parse_mode` مع `RichContent` ويُرفض محلياً وفق العقد.

### Phase 4 — Draft streaming

- دراسة lifecycle منفصلة.
- تحديد من يملك draft id.
- تحديد كيف يصل stop event إلى handler.
- تحديد سلوك shutdown/cancellation.
- عدم اعتبار preview ephemeral رسالة مرسلة لأغراض Message Links أو archive.

### Phase 5 — Optional typed builders

- استخراج أكثر blocks استخداماً من أمثلة حقيقية.
- إضافة builders اختيارية لا تمنع raw blocks.
- عدم استيراد عشرات الأنواع إلى Core بلا ضغط مثبت.

---

## 13. استراتيجية الاختبار

كانت النقاط التالية استراتيجية الاختبار وقت التحقيق. أُضيفت اختبارات التنفيذ
لـ Rich content في مجموعة الاختبارات الحالية؛ لا تُقرأ القائمة الآتية على
أنها شرط مؤجل أو دليل على غياب التنفيذ.

### Translation

- message يحتوي `rich_message` ولا يحتوي `text`.
- message يحتوي Rich وreply markup.
- message Rich داخل channel post.
- edited message لا يتحول خطأً إلى message route غير موجود.
- unknown fields لا تكسر translator.

### Model

- `Message.rich_message is None` عند غياب field.
- `Message.rich_message` data-only.
- `raw` و`to_dict()` لا يتغيران.
- Rich input وRich output ليسا نفس النوع عن طريق الخطأ.

### Context

- `reply_rich` يرسل `reply_parameters` عند الحاجة.
- `send_rich` لا يضيف reply parameters.
- لا يمكن جمع `html` و`markdown` و`blocks`.
- `reply_markup` يمر منفصلاً.
- عدم وجود chat id لا يسبب إرسالاً كما في semantics الحالية.

### Adapter

- method والـ payload names يطابقان Telegram.
- لا يتم إرسال الحقول الاختيارية الفارغة بلا سبب.
- error propagation يظل `TelegramError`.
- لا middleware أو routing يدخلان في adapter.

### Routing

- Rich message عادية تصل إلى `on("message")`.
- لا ينشأ `on("rich_message")`.
- `stopped_message_generation` لا يُمرر إلى message handler فارغاً.
- سياسة unsupported/unknown صريحة ومغطاة إذا أضيف event أو بقي مؤجلاً.

### Compatibility

- كل اختبارات `send()` و`reply()` الحالية تبقى كما هي.
- لا تتغير signatures أو payloads القديمة.
- لا يتغير سلوك `ctx.raw`, `Message.raw`, `to_dict()`.

---

## 14. الأسئلة التي سُجلت أثناء التحقيق وحالتها

كانت الأسئلة التالية مفتوحة وقت صياغة التحقيق الأول. حُسمت حدود الدعم الأساسي
في ADR-023؛ بقيت lifecycle الخاصة بـ drafts/streaming وبعض التوسعات خارج النطاق
ومؤجلة:

1. هل public envelope يسمى `RichInput`, `InputRichMessage`, أم اسم Titan
   مستقل يمنع الالتباس مع Telegram؟
2. هل nested blocks تبدأ raw بالكامل أم بواجهات builders محدودة؟
3. هل `Message.rich_message` يعرض `blocks` raw أم model output wrapper؟
4. هل basic Rich support يدخل v1 أم يبقى في extras/extension؟
5. كيف تُسجّل رسالة Rich في Message Links إذا لم يكن لها text؟
6. هل archive يخزن raw content، rendered approximation، أم لا شيء؟
7. هل draft streaming يستحق event رسمي في Titan، أم يبقى adapter-only؟
8. كيف يتعامل `stopped_message_generation` مع قاعدة drop الحالية؟
9. هل Rich buttons تكامل مستقل عن `InlineKeyboard` أم يكفي raw payload مبدئياً؟
10. هل سيحتاج Titan مستقبلاً abstraction cross-transport، أم أن Rich يبقى
    Telegram-specific كما هو الآن؟

---

## 15. خلاصة قرارات مرحلة التحقيق الأولى — سجل تاريخي

| المسألة | الخلاصة في مرحلة التحقيق الأولى | السبب |
|---|---|---|
| route جديد لـ Rich Message | **Reject** | Rich محتوى داخل Message وليس Update type |
| تجاهل field والاعتماد على `raw` فقط | **Reject كدعم رسمي** | يفقد المطوّر accessor ثابتاً رغم أن الحقل جزء واضح من Telegram |
| دعم basic send/read | **Adapt** | فجوة حقيقية، ويمكن حلها دون تغيير execution model |
| مرآة كاملة لكل Telegram Rich classes | **Reject حالياً** | over-engineering وcoupling مع schema متحرك |
| غلاف input يثبت mode والخيارات العامة | **Adopt** | أصغر invariant مفيد وقابل للتطور |
| parser HTML/Markdown داخل Titan | **Reject** | Telegram مالك semantics والrendering |
| `reply_markup` داخل Rich abstraction | **Reject الخلط** | surface مختلف عن rich content |
| `sendRichMessageDraft` مع basic send | **Defer** | lifecycle وstop event ومسؤولية مختلفة |
| typed builders لاحقاً | **Defer/Adapt** | لا تُبنى إلا على ضغط استخدام مثبت |
| إعادة كتابة التحقيق من الصفر | **Reject** | يُحافَظ على نتائج التحقيق؛ تُزامن الحالة المتقادمة فقط |

---

## 16. النتيجة المقترحة قبل ADR-023 — سجل تاريخي

> الرسم التالي يصف صياغة التحقيق الأولى؛ أسماء الواجهة فيه ليست API الحالية.
> يُرجع القرار النهائي إلى ADR-023 والقسم 1.

المكان الصحيح لـ Rich Messages في Titan هو **حد الرسالة، لا حد الـ Update
router**:

```text
Telegram capability
    ↓
RichContent للإرسال / RichMessage للاستقبال
    ↓
Context.send() / reply() / edit() + Message.rich_message
    ↓
CONTRACT يثبت الفواصل ولا ينسخ Telegram بالكامل
```

أصغر خطوة صحيحة هي دعم envelope رسمي محدود، مع إبقاء التفاصيل المتغيرة
Telegram-owned داخل payload واضح. ما يجب ألا نفعله هو تحويل Rich Messages إلى
مشروع rendering داخل Titan قبل أن يثبت الاستخدام ذلك.

**الحالة عند كتابة هذا المقطع:** كان التنفيذ متوقفاً على حسم API والعقد.
حُسمت هذه النقاط للدعم الأساسي في ADR-023 ونُفذت؛ drafts/streaming ما زالت
مؤجلة كمسألة lifecycle مستقلة.

---

## المصادر

1. Telegram Bot API: <https://core.telegram.org/bots/api>
2. Telegram Bot API changelog: <https://core.telegram.org/bots/api-changelog>
3. Titan contract: `CONTRACT.md`
4. Titan update translation: `src/titan/update.py`
5. Titan message model: `src/titan/models/message.py`
6. Titan context: `src/titan/ctx.py`
7. Titan transport: `src/titan/telegram.py`
8. Titan adapter: `src/titan/adapter.py`
9. Investigation — API Evolution & Unknown Update Types:
   `docs/internal/investigations/api-evolution-unknown-types.md`
10. Investigation — Telegram Surface Preparation:
     `docs/internal/investigations/telegram-surface-prep.md`

---

# Architectural Design / Discussion

**الحالة الحالية:** سجل تاريخي لمراحل التصميم التي سبقت ADR-023 والتنفيذ.
**تاريخ كتابة هذه المرحلة:** 2026-09-04
**المرجع النهائي:** ADR-023 و`CONTRACT.md` والتنفيذ الحالي.

> عناوين `DECISION` و`PROPOSAL` والـ API examples أدناه توثّق استدلالاً
> ومقترحات في مراحلها الزمنية؛ ليست كلها قرارات نافذة أو أسماء API حالية.
> عند التعارض، المرجع هو ADR-023. لا تزال drafts/streaming مؤجلة كما يحدد ADR.

هذا القسم لا يعيد التحقيق. يأخذ حقائقه من التحقيق أعلاه، ثم يراجع النقاط
المفتوحة ويحوّلها إلى قرارات تصميمية. حيث تختلف هذه القرارات عن اقتراح مبدئي
في القسم السابق، يذكر السبب صراحة.

---

## 17. معيار التصميم

المنافسة هنا ليست سباقاً إلى إعلان أن Titan يدعم method جديدة في Telegram.
الأطر الأخرى قد تصل إلى ذلك قبله أو بعده. المعيار المطلوب هو:

```text
هل تجعل Titan المطوّر يفهم:
    أين يكتب المحتوى؟
    أين يرسله؟
    ماذا استلم؟
    وما الذي لا يملكه Titan؟
بأقل surface ممكن ومن دون سلوك مخفي؟
```

ميزة Titan المفترضة ليست امتلاك classes أكثر، بل جعل boundary صحيحة مرئية.
الـ API الجيدة هنا يجب أن تبدو صغيرة لأنها فصلت القرارات الصحيحة، لا لأنها
أخفت Telegram خلف abstraction غامضة.

---

## 18. مراجعة البدائل في الأطر الأخرى

المقارنة التالية تفصل بين ما ظهر في الوثائق أو المصدر، وبين الاستنتاج
المعماري، وبين ما سنقترحه لـ Titan. حالة الإصدارات أدناه snapshot بتاريخ
2026-09-04؛ لا تُحوَّل إلى حكم دائم على أي مشروع.

### 18.1 python-telegram-bot

**الواقع الموثق:**

- الصفحة الرئيسية لوثائق PTB تعرض `v22.8` وتذكر أن أنواع وmethods Bot API
  المدعومة أصلاً هي Bot API 10.0.
- issue `#5261` المفتوح بعنوان Full Support for Bot API 10.1 يضع
  `RichMessage`, `Message.rich_message`, `InputRichMessage`,
  `sendRichMessage`, `sendRichMessageDraft` و`editMessageText.rich_message`
  ضمن checklist غير مكتمل في snapshot الصفحة.
- نفس issue يذكر أن workaround هو استعمال raw Bot API request layer وبناء
  payloads كـ plain dictionaries إلى أن يكتمل الدعم typed.

**الاستنتاج:**

PTB يوضح تكلفة الاعتماد الكامل على generated/typed mirror: عندما يظهر surface
كبير دفعة واحدة، يصبح توقيت framework مرتبطاً بسرعة إدخال كل class وmethod.
وفي الوقت نفسه، raw escape hatch مفيد جداً للـ forward compatibility لكنه لا
يحل تجربة المطوّر الرسمية.

**ما نتعلمه لـ Titan:**

- لا نخلط «typed support غير مكتمل» مع «لا توجد قدرة transport».
- لا ننتظر مرآة كاملة كي نعطي boundary صغيرة صحيحة.
- لا نجعل raw هو الـ public API الوحيد.

### 18.2 aiogram

**الواقع الموثق:**

- وثائق aiogram `3.30.0` تعرض `RichMessage` كنوع public.
- تعريف `RichMessage` يملك `blocks` كـ discriminated union لجميع أنواع
  `RichBlock`، و`is_rtl`.
- وثائق `SendRichMessage` و`SendRichMessageDraft` تعرض methods كـ typed method
  objects، ويمكن استدعاؤها كـ `bot.send_rich_message(...)` أو تمرير object
  إلى bot.
- `sendRichMessageDraft` موثق كـ preview ephemeral، ويحتاج إرسالاً نهائياً
  منفصلاً للحفظ، مع `draft_id`, `can_stop`, و`keep_on_stop`.

**الاستنتاج:**

aiogram اختار تمثيل Telegram قريباً جداً من schema: type لكل union member،
وmethod object لكل endpoint. هذا ممتاز لمن يريد اكتمالاً وتحقّقاً مبكرين،
لكنه يجعل surface المستخدم مرآة مباشرة لتفاصيل Telegram، ويجعل
`RichMessage` و`InputRichMessage` جزءاً من قاموس كبير يجب تتبعه باستمرار.

**ما نتعلمه لـ Titan:**

- فصل input عن output ليس اختياراً تجميلياً؛ هو منع لتمرير response model
  إلى send method.
- discriminated unions مهمة داخل implementation أو extension عندما نحتاج
  إليها، لكنها ليست سبباً لفرض كل union على Core من اليوم الأول.
- draft semantics لا تختفي لمجرد أن method نفسها typed.

### 18.3 PyTelegramBotAPI / TeleBot

**الواقع الموثق:**

- وثائق PyTelegramBotAPI الحالية تعرض `TeleBot` و`AsyncTeleBot` كواجهتين
  synchronous وasynchronous.
- في source snapshot الحالي للمستودع، توجد دوال
  `apihelper.send_rich_message` و`asyncio_helper.send_rich_message`، وتبني
  payload من `rich_message.to_json()`.
- توجد أيضاً دوال draft المقابلة.
- اختبارات `types.py` في نفس snapshot تفكك أمثلة `RichText*` و`RichBlock*`
  إلى أنواع Telegram-specific، ما يدل على أن طبقة types هي موضع المعرفة
  التفصيلية بالـ schema.

**الاستنتاج:**

TeleBot يميل إلى توسيع transport helper وtypes مع schema Telegram مباشرة.
هذا عملي ومألوف لمن يريد تغطية Bot API، لكنه لا ينتج وحده قراراً حول:

- هل Rich content جزء من semantic message model؟
- هل reply markup وRich buttons نفس abstraction؟
- كيف يختلف draft lifecycle عن send؟

**ما نتعلمه لـ Titan:**

- وجود helper منخفض المستوى مفيد.
- `to_json()` boundary واضحة أفضل من تمرير object عشوائي إلى كل مكان.
- لكن transport coverage وحدها ليست design لـ Context أو Message Links أو
  lifecycle.

### 18.4 ملخص المقارنة

| البعد | PTB | aiogram | PyTelegramBotAPI/TeleBot | درس Titan |
|---|---|---|---|---|
| public abstraction | typed API قيد اللحاق في snapshot | mirror typed واسع | types + helpers قريبة من API | نحتاج envelope صغيراً معلناً |
| nested blocks | غير مكتمل في snapshot | union typed لكل block | Telegram-specific types | لا نبدأ بمرآة كاملة |
| transport | raw workaround عند النقص | method objects وbot methods | `apihelper` وasync helper | نحتاج Context وAdapter معاً |
| incoming model | لا يظهر كدعم مكتمل في issue snapshot | `RichMessage` public | types تفكك Rich objects | `Message.rich_message` يجب أن يكون رسمياً |
| drafts | خارج الدعم المكتمل في snapshot | method typed لكن semantics صريحة | helper موجود | method ليست lifecycle |
| Telegram coupling | يتأخر عند التغيير | مرتفع وواضح | مرتفع وعملي | نملك Telegram coupling، لكن نضعه في boundary معلنة |

**النتيجة:** لا ننسخ framework واحداً. نأخذ من PTB قيمة escape hatch، ومن
aiogram فصل input/output ووضوح draft، ومن TeleBot فصل transport helper عن
types. ثم نضيف قرار Titan الذي لا يظهر تلقائياً من أي واحد منها: Rich Message
لا يغيّر routing، ولا يملك Message operations، ولا يدخل Message Links في
تفسير المحتوى.

---

## 19. القرار الأول — اسم الـ abstraction وشكله

### DECISION

نعتمد مفهوميْن منفصلين:

```text
RichMessage       = تمثيل incoming data-only بعد أن أرسلته Telegram
RichMessageInput  = تمثيل outgoing content قبل إرساله إلى Telegram
```

المسميات النهائية يجب أن تكون public في Titan، لكن لا نستخدم
`InputRichMessage` كاسم Titan الرسمي؛ ذلك اسم Telegram ويمكن أن يوحي بأن
Titan مجرد namespace آخر للـ Bot API.

### WHY

`Message.rich_message` هو response/content received، بينما
`sendRichMessage` يحتاج input له ثلاثة modes متعارضة. دمجهما في `RichMessage`
واحد يصنع object يمكن أن يكون:

- blocks output غير صالح كـ input.
- html input لم يُحلل بعد.
- raw response مع حقول لا يقبلها send method.

الفصل يجعل اتجاه البيانات ظاهراً في type والاسم، ويمنع API ذكية تعتمد على
الـ runtime لاكتشاف الاتجاه.

### SHAPE

`RichMessageInput` لا يدعي تمثيل كل Telegram classes، لكنه يثبت boundary:

```text
RichMessageInput
    exactly one of:
        markdown: str
        html: str
        blocks: sequence of block payloads
    optional:
        media
        is_rtl
        skip_entity_detection
```

`RichMessage` الواردة تعرض على الأقل:

```text
RichMessage
    blocks
    is_rtl
    raw
    to_dict()
```

وجود `raw` و`to_dict()` يتبع contract الموجود على models، وليس ترخيصاً لتجاهل
الـ accessor.

### ALTERNATIVES CONSIDERED

1. `RichMessage` واحد للاتجاهين.
2. استخدام أسماء Telegram حرفياً: `InputRichMessage` و`RichMessage`.
3. اسم عام مثل `Document` أو `RichDocument`.
4. عدم وجود model، والاكتفاء بـ dictionaries.

### WHY REJECTED

- الاسم الواحد يخلط input/output.
- أسماء Telegram حرفياً تجعل Titan surface تابعاً للاسم الخارجي وتزيد
  الالتباس عند إضافة semantic policy.
- `Document` أوسع من القدرة الحالية؛ Rich Message ليست document abstraction
  عامة ولا يجب أن تصبح وعداً cross-transport.
- dictionary-only يعيد raw-only البديل المرفوض في التحقيق، ولا يثبت حتى
  قاعدة mode الواحد.

### IMPACT ON TITAN

- `Message` يحصل على accessor لا operation.
- `Context` و`TelegramAdapter` يستقبلان input واضح الاتجاه.
- لا حاجة إلى route جديد أو model عام لكل أنواع Telegram.
- كان يلزم لهذا القرار بند public في CONTRACT؛ أُضيف في العقد المعتمد،
  وتفاصيل التنفيذ النهائي موضحة في ADR-023.

---

## 20. القرار الثاني — Telegram representation مقابل Titan semantic model

### DECISION

Rich Messages في Titan هي **Telegram-specific capability ذات boundary رسمية**،
وليست canonical document model محايدة.

Titan semantic model في هذه المرحلة يقتصر على:

```text
message identity + message metadata + rich content presence
```

ولا يحاول إعطاء معنى عام لـ:

- map.
- Telegram formula rendering.
- `tg://` references.
- Rich buttons.
- client-specific layout blocks.

### WHY

الـ blocks ليست مجرد syntax. بعضها يملك دلالة مرتبطة بعميل Telegram وطريقة
عرضه، وبعضها يخلط content بوسائط أو controls. تحويلها إلى `DocumentNode`
عاماً سيجبر Titan على اختراع semantics قبل أن يحتاجها، ثم يضع translator
مخفياً بين Titan وTelegram.

Titan هنا لا يحتاج أن يكون مستقلاً عن Telegram؛ هو framework Telegram في
الأساس. الاستقلال المفيد هو في الفصل بين:

```text
Titan execution boundary
    و
Telegram-owned rich schema
```

### ALTERNATIVES CONSIDERED

- Canonical AST عام لكل rich content.
- تحويل blocks إلى plain text حتى يبقى model بسيطاً.
- نسخ Telegram classes كاملة إلى `titan.models`.

### WHY REJECTED

- canonical AST over-engineering ولا يوجد transport ثانٍ يثبت الحاجة.
- plain text يفقد hierarchy وmedia وbuttons ويعيد المشكلة الأصلية.
- النسخ الكامل يربط Core بتغيرات Bot API ويضاعف مسؤولية التحقق.

### IMPACT ON TITAN

يجب أن تكون documentation صريحة بأن `blocks` و`media` Telegram-owned. لا
يجب أن يوحي اسم Titan بأن payload سيعمل مع MTProto أو منصة أخرى من دون قرار
مستقل.

---

## 21. القرار الثالث — html / markdown / blocks

### DECISION

نقدم modes الثلاثة كما يقدمها Telegram، لكن لا نقدم parser أو conversion
تلقائياً بينها:

```text
markdown → Telegram rich Markdown
html     → Telegram rich HTML
blocks   → Telegram explicit block schema
```

يتم التحقق مبكراً من mutual exclusion فقط. لا يتم تحويل `str` تلقائياً إلى
Markdown، ولا HTML إلى blocks، ولا blocks إلى HTML.

### WHY

هذه ليست ثلاث syntaxes لنفس compiler يملكه Titan. Telegram يملك:

- parsing rules.
- allowed tags.
- entity detection.
- nested formatting limits.
- media link rules.
- client rendering.

أي parser محلي سيكون إما نسخة ناقصة أو abstraction تخفي فروقاً يجب أن
يراها المطوّر. البساطة هنا أن يختار المطوّر mode صراحة، لا أن نعده بتحويل
سحري.

### IMPACT ON TITAN

- errors الخاصة بتعدد modes تكون `TitanError` قبل الطلب.
- أخطاء syntax/rendering الخاصة بـ Telegram تبقى `TelegramError`.
- `parse_mode` القديم يظل خاصاً بـ `send()` و`reply()` ولا يعاد تفسيره
  كـ Rich mode.
- لا تتغير semantics الحالية للنصوص العادية.

---

## 22. القرار الرابع — blocks: raw schema أم builders؟

### DECISION

المرحلة الأساسية تستخدم **raw block payloads داخل envelope رسمي**:

```text
RichMessageInput.blocks
    = sequence of Telegram-shaped block mappings
```

لكن raw لا يكون payload message كله. Titan يملك envelope واضحاً يثبت mode
والخيارات، بينما تبقى أسماء block types وحقولها Telegram-specific.

لا نضيف builders محدودة في Core الآن. إذا ظهرت builders لاحقاً، تكون طبقة
اختيارية فوق نفس payload contract وليست بديلاً إلزامياً له.

### WHY

التحقيق أثبت أن schema تتوسع سريعاً بين 10.1 و10.3: headings وtables وmedia
ثم buttons وdocuments وexpandable quotations. بناء builder صغير قد يبدو
جميلًا، لكنه سيخلق قائمة رسمية مبتورة ويجبر المستخدم على الخروج إلى raw عند
أول نوع جديد.

المفارقة المهمة:

```text
raw بلا boundary       = فوضى
raw داخل boundary       = forward-compatible escape surface
```

### ALTERNATIVES CONSIDERED

1. كل block class في Core.
2. builders لأكثر خمسة blocks استعمالاً.
3. JSON string كامل يمر إلى `sendRichMessage`.
4. raw `dict` لكل الرسالة دون envelope.

### WHY REJECTED

- الخيار 1 مرآة ضخمة ومتغيرة.
- الخيار 2 يخلق API من الدرجة الأولى والثانية ويخفي سبب اختيار الأنواع.
- الخيار 3 يضحي بالتحقق والـ serialization الواضح.
- الخيار 4 لا يثبت mode ولا يفصل rich content عن method parameters.

### IMPACT ON TITAN

- `blocks` تظل Telegram-specific بوضوح.
- لا تُصدَّر عشرات classes من `titan.models`.
- يمكن إضافة `titan.rich.builders` لاحقاً دون تغيير Context أو Adapter.
- يجب أن تختبر implementation لاحقاً exact serialization لا rendering.

---

## 23. القرار الخامس — public API ومكانها

### DECISION

Rich basic support يدخل Core، وتكون نقاطه ثلاثاً فقط:

```python
await ctx.reply_rich(content, reply_markup=keyboard)
await ctx.send_rich(content, reply_markup=keyboard)
await bot.telegram.send_rich_message(chat_id, content, ...)
```

وللقراءة:

```python
ctx.message.rich_message
```

وللتعديل، method صريحة منفصلة:

```python
await ctx.edit_rich(content, reply_markup=keyboard)
await bot.telegram.edit_rich_message(chat_id, message_id, content, ...)
```

الأسماء أعلاه كانت قرار intent مبدئياً يحتاج أن ينعكس في CONTRACT قبل التنفيذ؛
ليست الواجهة المعتمدة. العقد الحالي يوثق الأفعال الحالية مع `RichContent`،
كما يوضح ADR-023.

### WHY

هذه هي نفس boundary الحالية:

```text
داخل handler       → ctx
خارج update cycle   → bot.telegram
رسالة واردة         → Message
```

إضافة `rich_message` parameter إلى `ctx.send()` و`ctx.reply()` تبدو أقصر،
لكنها تنتج حالات غامضة:

```python
ctx.send(text, rich_message=...)
ctx.send(None, rich_message=...)
ctx.send(text, parse_mode="HTML", rich_message=...)
```

method صريحة تجعل intent قابلاً للقراءة وتترك API النص الحالية ثابتة.

### ALTERNATIVES CONSIDERED

- توسيع `send`/`reply` بمعامل اختياري.
- إضافة method واحدة `ctx.send_content(...)`.
- adapter-only ثم السماح باستدعائه من handler.
- وضع rich send في `titan.extras`.

### WHY REJECTED

- overload يخلط modes ويصعب توثيق التعارض.
- `send_content` اسم عام لا يوضح Telegram rich semantics.
- adapter-only يخالف قاعدة `ctx` كنقطة تنفيذ داخل الدورة.
- extras ليست مكان capability أساسية تجعل Message الواردة ناقصة؛ extras
  للـ DX utilities لا لطبقة Telegram content.

### IMPACT ON TITAN

سيكون هناك API جديدة، لكن لا تغيير سلوكي في API القديمة. `Router` وmiddleware
لا يتغيران. `titan.rich` placement مناسب إن احتاجت النماذج ملفاً مستقلاً،
لكن لا ننشئ بنية package قبل مرحلة التنفيذ.

---

## 24. القرار السادس — incoming Rich Messages

### DECISION

Rich message الواردة تظهر كـ:

```python
ctx.message.rich_message
```

وتبقى داخل `on("message")` أو route الرسالة الموجود. لا نضيف
`on("rich_message")`.

`ctx.text` لا يحصل على fallback اصطناعي. إذا لم يرسل Telegram `text`، يبقى
`None`.

### WHY

Rich Message تمثل content variant داخل Message، لا event variant داخل Update.
إضافة route جديد ستكرر message handlers وتفصل ما يجب أن يبقى في دورة واحدة.

أما اختراع `ctx.text` من blocks فسيخلق semantic كاذبة:

- أي نص نختار من table؟
- هل caption يصبح النص؟
- هل details المغلق يدخل؟
- ماذا نفعل بالـ map أو button؟

### IMPACT ON TITAN

- `BotApiTranslator` يحتاج تمرير field لا إنشاء route.
- `Message.rich_message` هو accessor الرسمي.
- `Message.raw` يظل المصدر الكامل عند field لم يغلفه Titan بعد.
- handlers القديمة التي تعتمد على `ctx.text is not None` لن تبدأ بمعالجة Rich
  صامتاً؛ هذا يحافظ على backward compatibility.

---

## 25. القرار السابع — outgoing Rich Messages وreply markup

### DECISION

نستخدم abstraction واحدة للمحتوى الصادر، لكن لا نخلطها مع واجهة الأزرار
الحالية:

```text
RichMessageInput       = content
InlineKeyboard         = reply markup
Rich buttons in blocks = Telegram-owned content control
```

`reply_markup` يبقى معاملًا مستقلاً في `send_rich` و`reply_rich`.

### WHY

Telegram يضع Rich buttons داخل block content، بينما `InlineKeyboardMarkup`
يعيش في method parameter. لهما lifecycle وموضع عرض مختلفان، حتى إن تشابه
بعض actions مثل URL وcallback.

تحويل Rich button إلى `InlineButton` سيحذف أو يغير معنى attributes مثل
الموضع داخل المستند، inline context، والـ button type الخاص بالـ Rich schema.

### ALTERNATIVES CONSIDERED

- توحيد كل الأزرار في `InlineButton`.
- جعل `RichButton` Titan model من البداية.
- حذف rich buttons ودعم reply markup فقط.

### WHY REJECTED

- التوحيد سيكون تشابهاً سطحياً ويخسر دلالة Telegram.
- `RichButton` model مبكر قبل إثبات نمط استعمال متكرر.
- حذف القدرة يجعل abstraction غير كاملة في Bot API 10.3.

### IMPACT ON TITAN

في المرحلة الأولى، Rich buttons داخل `blocks` تمر كـ raw block payload. أما
`InlineKeyboard` فتبقى typed/public كما هي اليوم. أي builder مستقبلي للـ
Rich buttons يجب أن يكون منفصلاً صراحةً عن `InlineButton`.

---

## 26. القرار الثامن — editing

### DECISION

التعديل يكون صريحاً لا overload:

```text
edit()       = existing text edit semantics
edit_rich()  = rich_message edit semantics
```

`ctx.edit_rich()` يحتفظ بنفس قيد `ctx.edit()` الحالي: يعمل في callback context
فقط، ما لم يقرر ADR لاحقاً تغيير execution boundary. التعديل خارج الدورة
يمر من `bot.telegram.edit_rich_message(...)`.

لا نسمح بجمع `text` و`rich_message` في الطلب نفسه. ولا نحول `edit()` إلى
method تعرف تلقائياً هل المحتوى text أم Rich.

### WHY

Telegram أضاف `rich_message` إلى `editMessageText`، لكنه لم يجعل semantics
النص وRich متطابقة. وضوح method يمنع حالات التعديل المتعارضة، ويحافظ على
قراءة code intent.

### IMPACT ON TITAN

- لا تتغير `ctx.edit()` الحالية.
- يحتاج `Message Links` لاحقاً معرفة أن edit لا ينشئ identity جديدة.
- يجب اختبار أن edit لا يسجل رسالة جديدة ولا يعيد تخصيص TitanMessageId.

---

## 27. القرار التاسع — Message Links والـ archive

### 27.1 Identity

**DECISION:** Message Links تتعامل مع Rich message كرسالة عادية من ناحية
الهوية، لا من ناحية المحتوى.

```text
ctx.send/ctx.reply succeeds
    → Telegram message_id
    → Titan identity registration
    → same address rules

bot.telegram.send_rich_message succeeds
    → Telegram message_id
    → existing adapter semantics
    → no automatic Context identity registration
```

لا نولد عنواناً جديداً بسبب كون المحتوى Rich، ولا نربط العنوان بوجود archive.

**WHY:** الهوية تصف وجود الرسالة ومكانها. Rich representation ليست جزءاً من
مفتاح الهوية. هذا يحافظ على المبدأ الموجود: identity layer مستقلة عن archive.

### 27.2 Content archive

**DECISION:** لا نخزن Rich content تلقائياً في archive الحالي. إذا لم يتغير
archive contract، تسجل رسالة Rich هويتها، لكن لا ندعي أن archive النصي يملك
نسخة قابلة لإعادة العرض من blocks أو HTML/Markdown.

**WHY:** تخزين rendered text أو plain-text projection سيكون فقداً للمعلومات
وقد يعطي resolver نتيجة تبدو كاملة وهي ليست كذلك. تخزين raw payload يحتاج
قرار privacy، الحجم، media references، versioning، وserialization contract.

**ALTERNATIVES CONSIDERED:**

- استخراج plain text من Rich تلقائياً.
- تخزين `InputRichMessage` كما أرسل.
- تخزين `RichMessage` كما عاد.
- عدم تغيير archive إطلاقاً.

**WHY REJECTED / DEFERRED:**

- plain text projection ليست reversible ولا canonical.
- input وoutput قد يختلفان بسبب parsing وmedia resolution.
- raw archive يربط التخزين بإصدار Telegram ويحتاج privacy/storage policy.
- إبقاء archive كما هو هو الخيار الآمن الآن، مع فتح ADR مستقل عند الحاجة.

### IMPACT ON TITAN

`_register_identity` يجب أن يستمر best-effort دون أن يتطلب text. لا ينبغي أن
تمنع archive limitation إرسال Rich أو تغيّر address behavior. أي دعم محتوى
Rich في archive يأتي لاحقاً كقدرة مستقلة، لا كأثر جانبي لـ `send_rich`.

---

## 28. القرار العاشر — Core أم extension؟

### يدخل Core

1. `RichMessageInput` envelope وقاعدة mode الواحد.
2. `Message.rich_message` accessor data-only.
3. basic send عبر Context.
4. basic send عبر TelegramAdapter.
5. basic rich edit مع semantics صريحة.
6. serialization والـ raw boundary.

**السبب:** هذه ليست convenience utilities؛ هي امتداد مباشر لمسار Message
الحالي. إبقاؤها خارج Core سيجعل الرسالة الواردة ناقصة ويجبر المطوّر على raw.

### يبقى extension أو مؤجلاً

1. builders لكل blocks.
2. parser/renderer من Markdown أو HTML إلى blocks.
3. تحويل content بين Telegram وtransport آخر.
4. Rich button DSL.
5. archive projection أو persistence للـ Rich content.
6. AI document formatter أو block planner.
7. draft session manager.

**السبب:** هذه طبقات DX أو product behavior أو lifecycle، وليست boundary
الأساسية المطلوبة لتمرير قدرة Telegram بصدق.

### تصحيح اقتراح سابق

القسم البحثي اقترح أن raw blocks تكون في envelope وقد تضاف builders لاحقاً.
هذه المناقشة تثبت ذلك أكثر: **لا نضع builders حتى المحدودة في Core الآن**.
الاستثناء الوحيد الممكن لاحقاً هو helper بسيط لصناعة `markdown` أو `html`،
لأنه لا يدعي معرفة block schema؛ وحتى ذلك ليس مطلوباً للتنفيذ الأول.

---

## 29. القرار الحادي عشر — drafts وstreaming

### DECISION

Basic Rich Messages وRich drafts مساران منفصلان. لا يدخل draft session manager
ولا `stopped_message_generation` إلى أول basic Core design.

يمكن لاحقاً إضافة low-level method، لكن لا نضيف abstraction lifecycle قبل ADR
مستقل يحدد ownership والإلغاء والـ shutdown.

### WHY

`sendRichMessage` هو request ينتج Message ويمكن تسجيل هويته. أما
`sendRichMessageDraft` فهو preview مؤقت:

```text
draft start
    → repeated partial updates
    → optional user stop
    → timeout/ephemeral disappearance
    → explicit final send
```

هذه ليست نفس state machine. إدخالها في `ctx.send_rich()` سيجعل method عادية
تملك فجأة:

- draft id generation.
- background scheduling.
- refresh timing.
- stop event.
- finalization policy.
- cancellation behavior.
- interaction مع lifecycle registry.

هذا بالضبط نوع hidden execution path الذي يرفضه عقد Titan.

### lifecycle design المطلوب قبل التنفيذ

إذا اعتمدنا drafts لاحقاً، يجب أن يكون هناك owner صريح، مثلاً session
اختيارية، تملك:

```text
(chat_id, draft_id, current content, state)
```

والحالات يجب أن تكون واضحة على الأقل:

```text
created → streaming → finalized
                    ↘ stopped
                    ↘ cancelled
                    ↘ expired
```

القواعد المقترحة:

- لا identity ولا archive عند draft preview.
- identity تنشأ فقط بعد final `sendRichMessage` الناجح.
- stop لا يعني finalization.
- `keep_on_stop` لا يعني persistence.
- لا background task مخفي يبدأ بمجرد إنشاء object.
- session owner هو الذي يوقف refresh عند `cancel`.

### cancellation / shutdown

عند shutdown:

1. يتوقف إرسال partial drafts الجديدة.
2. لا يحاول Titan finalization تلقائياً؛ لأن ذلك side effect غير متوقع.
3. تُلغى session صراحةً وتُلاحظ task exceptions.
4. لا تُنشأ Message Link لشيء لم يُرسل كرسالة نهائية.
5. إذا اكتمل final send قبل cancellation، تطبق عليه قواعد الرسالة العادية.

هذا متسق مع lifecycle contract الحالي الذي يملك tasks الناتجة عن polling،
لكنه لا يضيف draft task ownership قبل تعريفها.

### ALTERNATIVES CONSIDERED

- جعل `send_rich` يختار draft عند تمرير flag.
- تحديث draft تلقائياً من middleware.
- إرسال draft مرة واحدة وترك المطور يدير الباقي raw.
- session lifecycle رسمية في Core الآن.

### WHY REJECTED / DEFERRED

- flag يخفي state machine داخل send.
- middleware ليست مكان business/lifecycle logic.
- raw-only لا يعطي تجربة رسمية، لكنه يبقى escape hatch مؤقتاً.
- Core session الآن توسع كبير بلا قرار حول event routing وshutdown.

---

## 30. أثر التصميم على كل طبقة

| الطبقة | basic Rich | draft/streaming |
|---|---|---|
| `Update` | تمرير message field دون route جديد | event stop يحتاج قراراً منفصلاً |
| `Message` | `rich_message` data-only accessor | draft ليس Message نهائية |
| `Context` | `send_rich`, `reply_rich`, وربما `edit_rich` | لا session مخفية |
| `Telegram` | request method داخلية للـ rich endpoint | مؤجل حتى lifecycle ADR |
| `TelegramAdapter` | إرسال/تعديل خارج update cycle | low-level أو مؤجل، بلا manager تلقائي |
| `Router` | لا تغيير | event policy مستقلة إن اعتمد stop |
| Middleware | لا تغيير | لا streaming orchestration |
| Message Links | identity بعد final send فقط | لا identity للpreview |
| Archive | لا projection تلقائية | raw archive يحتاج ADR |
| CONTRACT | methods/accessor وmode rules | event/lifecycle بند مستقل |

---

## 31. backward compatibility

### DECISION

التصميم إضافة additive، مع إبقاء كل semantics الحالية كما هي:

- `ctx.send(text, ...)` لا يتغير.
- `ctx.reply(text, ...)` لا يتغير.
- `ctx.edit(text, ...)` لا يتغير.
- `ctx.text` لا يتحول إلى projection من Rich.
- `Message.text` لا يتحول إلى projection من Rich.
- `on("message")` يحتفظ بمعناه.
- لا route جديد للرسائل الغنية.
- `raw` و`to_dict()` لا يتغيران.
- لا تتغير signatures القديمة ولا payloads القديمة.

### WHY

الـ feature الجديدة لا تبرر إعادة تفسير نص قديم أو إدخال overload غامض. أكبر
خطر توافق ليس exception واضحاً؛ هو أن handler قد يبدأ فجأة في اعتبار Rich
content نصاً عادياً أو أن archive يَعد بمحتوى غير قابل لإعادة البناء.

### IMPACT

كان ينبغي أن يسجل CONTRACT هذا التمييز قبل التنفيذ؛ وهو موثق الآن: قد تكون
`ctx.text is None` مع وجود `message.rich_message`. هذا ليس bug، بل فصل بين
semantic fields.

---

## 32. تأثير التصميم على CONTRACT — قائمة ما قبل التنفيذ

كانت القائمة التالية checklist قبل التنفيذ. اعتُمد ADR-023، وأُضيف عقد الدعم
الأساسي إلى `CONTRACT.md`، ونُفذ مع الاختبارات؛ الأسماء النهائية موضحة في
القسم 1 وADR-023.

1. تعريف `RichMessage` و`RichMessageInput` ومجال كل منهما.
2. `Message.rich_message` كضمان data-only.
3. `ctx.send_rich()` و`ctx.reply_rich()` وقيودهما.
4. `bot.telegram.send_rich_message()` كـ adapter capability.
5. `edit_rich` إن دخلت المرحلة نفسها.
6. mode exclusivity.
7. بقاء reply markup منفصلاً.
8. أن Rich message العادية لا تضيف event route.
9. أن draft preview ليس Message نهائية ولا Message Link.
10. تأجيل `stopped_message_generation` إلى عقد/ADR مستقل.

كان ترك هذه الحدود غير موثقة سيكرر المشكلة التي يعالجها CONTRACT: سلوك موجود
لكنه غير معلن. أُغلق هذا الشرط للدعم الأساسي في القرار والعقد المعتمدين.

---

## 33. استراتيجية الاختبار التصميمية — سجل تاريخي

كانت هذه قائمة التحقق المقترحة قبل التنفيذ. توجد الآن اختبارات لتنفيذ Rich
content؛ لا تُقرأ العناصر أدناه كدليل على غياب الاختبارات أو كشرط مؤجل كله.

### Contract tests

- mode واحد فقط يقبل.
- modeان أو ثلاثة يرفعان TitanError قبل network request.
- `RichMessageInput` لا يقبل response-only shape كأنه input.
- `Message.rich_message` لا يملك API calls.

### Translation tests

- incoming `message.rich_message` يظل في message route.
- Rich-only message لا تخترع `text`.
- Rich message مع `text` لا تفقد أي field.
- unknown nested Rich fields لا تكسر القراءة الأساسية.

### Serialization tests

- exact `rich_message` JSON.
- عدم إرسال optional fields التي لم يحددها المطوّر.
- media وblocks يبقيان في موضعهما.
- `reply_markup` لا يندمج داخل `rich_message`.

### Context/adapter tests

- `reply_rich` يضيف reply parameters الصحيحة.
- `send_rich` لا يضيف reply parameters.
- adapter لا يشغل middleware أو routing.
- `edit_rich` لا ينشئ identity جديدة.

### Identity/archive tests

- final rich send يسجل identity عند نجاح Telegram response.
- draft preview لا يسجل identity.
- rich send لا يتطلب text حتى ينجح identity layer.
- archive الحالي لا يدعي استرجاع Rich content ما لم يُعتمد عقد جديد.

### Lifecycle tests المؤجلة

- draft stop لا يعني finalization.
- shutdown لا يرسل final message ضمناً.
- cancellation تنظف owner task ولا تترك task غير ملحوظ.
- final send المتسابق مع cancellation له policy محددة وقابلة للاختبار.

---

## 34. ما نرفض إضافته الآن

هذه الرفضات ليست إنكاراً لإمكانية المستقبل؛ هي حماية لحجم القرار الحالي:

1. **لا canonical Rich Document abstraction** — لا يوجد transport ثاني يثبتها.
2. **لا parser من HTML/Markdown إلى blocks** — Telegram هو parser والrenderer.
3. **لا classes لكل RichText/RichBlock في Core** — schema متحركة والتغطية
   الكاملة ليست شرطاً لحل الفجوة.
4. **لا Rich button unification** — تشابه action لا يساوي تشابه semantic.
5. **لا `on("rich_message")`** — ليس Update type.
6. **لا text projection تلقائية** — projection غير قابلة للعكس وقد تغير
   handler behavior.
7. **لا archive raw content تلقائي** — privacy/storage/versioning غير محسومة.
8. **لا draft manager مخفي** — lifecycle وshutdown غير محسومين.
9. **لا middleware streaming orchestration** — يخالف ملكية middleware.
10. **لا fallback صامت إلى `sendMessage`** — يخفي فشل capability ويعطي
    rendering مختلفاً من دون قرار المطوّر.
11. **لا اعتماد على client rendering في tests** — نختبر payload contract،
    لا UI Telegram غير المتاح في unit tests.
12. **لا abstraction cross-platform مبكرة** — Rich الحالية Telegram-specific.

---

## 35. جدول المقترحات قبل المراجعة العدائية — تاريخي

| القرار | النتيجة |
|---|---|
| اسم input/output | `RichMessageInput` منفصل عن `RichMessage` |
| مدلول Rich | Telegram-specific boundary رسمية، لا canonical AST |
| content modes | html/markdown/blocks، واحد فقط، بلا conversions |
| blocks | raw Telegram-shaped payloads داخل envelope؛ لا builders في Core |
| incoming | `Message.rich_message` داخل message route |
| outgoing داخل handler | `ctx.reply_rich` و`ctx.send_rich` |
| outgoing خارج handler | `bot.telegram.send_rich_message` |
| editing | methods صريحة Rich، لا overload للنص |
| reply markup | مستقل عن Rich content |
| Rich buttons | raw blocks أولاً، لا توحيد مع `InlineButton` |
| Message Links | identity بعد final send، مستقلة عن representation |
| archive | لا Rich projection أو storage تلقائي الآن |
| Core | basic read/send/edit boundary |
| extension | builders، formatter، archive، cross-transport |
| drafts | مسار منفصل، مؤجل حتى lifecycle ADR |
| routing | لا route جديد |
| compatibility | additive فقط، ولا fallback نصي صامت |

---

## 36. نطاق مقترح قبل المراجعة العدائية — سجل تاريخي

> هذه صياغة نطاق ما قبل ADR-023 وليست قائمة عمل حالية. حُسم الدعم الأساسي
> ونُفذ؛ راجع القسم 1. بقيت drafts/streaming والتوسعات المذكورة خارج النطاق.

كان نطاق التنفيذ الأول المقترح، قبل الاعتماد، صغيراً:

```text
1. RichMessageInput envelope
2. Message.rich_message read model
3. Telegram send/edit transport methods
4. Context send/reply/edit methods
5. Adapter send/edit methods
6. exact payload and translation tests
7. CONTRACT update
```

ولا يدخل معه:

```text
draft sessions
stop event routing
archive persistence
block builders
HTML/Markdown parser
Rich button DSL
cross-transport model
```

هذه ليست قائمة backlog عامة؛ هي boundary تمنع أن يتحول التنفيذ الأول إلى
مشروع Rich subsystem كامل.

---

## 37. الفرضية المعمارية قبل الاختبار — سجل تاريخي

القرار الأكثر أهمية ليس إضافة `send_rich_message`. القرار هو عدم السماح
لـ Rich Messages بأن تغيّر فلسفة Titan:

```text
Message content لا يساوي Update type
Input لا يساوي Output
Context لا يساوي Adapter
Identity لا تساوي Archive
Draft لا يساوي Message
Rich button لا يساوي Inline button
Raw escape hatch لا يساوي public abstraction
```

بهذه الفواصل، يستطيع Titan أن يدعم قدرة Telegram الحالية من دون أن يصبح
نسخة مصغرة من schema Telegram، ومن دون أن يبيع abstraction عامة لا يملك
معناها. وإذا نظر مطوّر framework آخر إلى التصميم، فالشيء الجدير بالتعلم ليس
أن Titan أنشأ classes أقل؛ بل أنه عرف بالضبط أي فرق يجب ألا يخفيه.

**الحالة عند كتابة هذا الاقتراح:** كان التنفيذ متوقفاً على المراجعة العدائية
والموافقة على ADR والعقد. أُغلقت هذه البوابة لاحقاً بقبول ADR-023 وتنفيذ
الدعم الأساسي؛ يظل draft lifecycle مؤجلاً.

---

## مصادر المقارنة المعمارية

11. python-telegram-bot documentation v22.8:
    <https://docs.python-telegram-bot.org/>
12. python-telegram-bot — Full Support for Bot API 10.1, issue #5261:
    <https://github.com/python-telegram-bot/python-telegram-bot/issues/5261>
13. aiogram — `RichMessage`:
    <https://docs.aiogram.dev/en/latest/api/types/rich_message.html>
14. aiogram — `SendRichMessage`:
    <https://docs.aiogram.dev/en/latest/api/methods/send_rich_message.html>
15. aiogram — `SendRichMessageDraft`:
    <https://docs.aiogram.dev/en/latest/api/methods/send_rich_message_draft.html>
16. PyTelegramBotAPI documentation:
    <https://pytba.readthedocs.io/en/latest/index.html>
17. PyTelegramBotAPI `apihelper.py` Rich Message methods:
    <https://github.com/eternnoir/pyTelegramBotAPI/blob/177cb2571edaca04cf206208f792eee88a0969e4/telebot/apihelper.py>
18. PyTelegramBotAPI `asyncio_helper.py` Rich Message methods:
    <https://github.com/eternnoir/pyTelegramBotAPI/blob/177cb2571edaca04cf206208f792eee88a0969e4/telebot/asyncio_helper.py>
19. PyTelegramBotAPI Rich type tests:
    <https://github.com/eternnoir/pyTelegramBotAPI/blob/177cb2571edaca04cf206208f792eee88a0969e4/tests/test_types.py>

---

## 38. Adversarial Review — محاولة كسر التصميم

هذا القسم لا يتعامل مع عناوين `DECISION` السابقة كقرارات نهائية. إنها
فرضيات صيغت قبل هذا الاختبار. معيار النجاح هنا ليس أن نجد لكل فرضية تبريراً،
بل أن نعرف أي edge case يفرض تغييرها.

### 38.1 النتيجة العامة قبل التفاصيل

المراجعة لا تهدم الاتجاه المعماري كله، لكنها تكشف مبالغتين:

1. فصل input عن output صحيح، لكن اسم `RichMessageInput` أقرب من اللازم إلى
   Telegram وأقل Titan-native من المطلوب.
2. `ctx.send_rich()` و`ctx.reply_rich()` و`ctx.edit_rich()` واضحة، لكنها ليست
   بالضرورة أصغر سطح API. بعد إدخال value object صريح للمحتوى، تصبح أفعال
   Titan الموجودة (`send`, `reply`, `edit`) قادرة على حمل النوعين دون ambiguity.

كما تكشف المراجعة أن إرسال Rich عبر `bot.telegram` لا يساوي إرسالها عبر
`Context` من ناحية Message Links: الـ adapter الحالي direct transport ولا
يمتلك `LinksManager`. لذلك كان القول السابق إن كل `send_rich` يسجل identity
واسعاً أكثر من contract الحالي، وتم تصحيحه في §27.

### 38.2 سجل الفرضيات

| الفرضية السابقة | حالة الاختبار | النتيجة |
|---|---|---|
| `RichMessage` منفصل عن input | تمرير incoming object إلى send | تصمد مع تغيير الاسم المقترح |
| raw blocks داخل envelope | block جديد، unknown field، mutation | تصمد مع guardrails، لا wrapper شكلي |
| html/markdown/blocks modes | strings تحتاج Telegram grammar | تصمد كم modes، يتغير شكل الإنشاء |
| `Message.rich_message` | Rich-only أو text + rich | تصمد كـ accessor اختياري |
| methods `*_rich` في Context | surface صغير مقابل value dispatch | **تحتاج تغييراً** إلى existing verbs |
| Rich بلا text | handlers و`has_text()` وmessage route | تصمد، لكن يجب توثيق non-text بوضوح |
| identity مستقلة عن المحتوى | إرسال من Context ومن adapter | تصمد فقط لمسار Context؛ adapter لا يسجل تلقائياً |
| لا archive تلقائي | `enable_archive()` وRich payload | تصمد مع حفظ `text=None` وعدم ادعاء replay |
| Rich buttons خارج keyboard | callback/URL button في block | تصمد؛ هما موضعان مختلفان |
| basic داخل Core | incoming field وsend path | تصمد؛ builders/lifecycle خارجها |
| drafts مستقلة | stop/expiry/finalize/shutdown | تصمد بقوة |
| قائمة الرفض | الحاجة إلى convenience لا تعني Core | تصمد، لكن `RichContent` helper يصبح مطلوباً |

---

## 39. الاختبارات العدائية بالتفصيل

### 39.1 RichMessage مقابل RichMessageInput

**حالة الكسر:**

```python
received = ctx.message.rich_message
await ctx.send(received)
```

إذا قبل النظام ذلك، فهو يفترض أن response blocks يمكن إعادة إرسالها بلا
تغيير. هذا غير مضمون: response قد تحتوي resolved file objects، fields
مضافة من Telegram، أو representation لا تقبلها input endpoint.

**النتيجة:** الفصل بين الاتجاهين يصمد. لكن `RichMessageInput` نفسه يكرر
قاموس Telegram (`InputRichMessage`) بدلاً من التعبير عن أن المطوّر يبني
**محتوى**.

**التغيير المقترح بعد الكسر:**

```text
RichMessage  = incoming Telegram rich representation
RichContent   = outgoing Titan content value
```

`RichContent` لا يقبل `RichMessage` تلقائياً. إذا أراد المطوّر إعادة الإرسال،
فعليه تحويل blocks صراحةً إلى `RichContent.blocks(...)`. هذا الفشل المقصود
أفضل من round-trip سحري قد ينجح أحياناً ويفشل بعد تحديث Bot API.

**الحكم:** الفصل صحيح؛ الاسم `RichMessageInput` مرشح للتغيير إلى
`RichContent`. لا نثبت الاسم قبل اختبار أمثلة الاستخدام الفعلية.

### 39.2 هل raw blocks abstraction ضعيفة؟

**حالة الكسر الأولى — discoverability:**

```python
await ctx.send_rich({
    "blocks": [
        {"type": "paragraph", "text": "hello"}
    ]
})
```

هذا يسمح بتمرير payload message كامل في الموضع الذي يجب أن يكون فيه blocks
فقط، ويجعل الخطأ يظهر من Telegram لا من Titan.

**حالة الكسر الثانية — mutation:**

```python
blocks = [{"type": "paragraph", "text": "draft"}]
content = RichContent.blocks(blocks)
blocks[0]["text"] = "changed behind Titan's back"
```

إذا احتفظ Titan بنفس references، فالمحتوى الذي سجله المطور ليس المحتوى الذي
أرسله فعلياً. وإذا نسخ deep copy بلا توثيق، فقد تظهر كلفة غير متوقعة مع media
payloads.

**حالة الكسر الثالثة — unknown block:**

Telegram يضيف block type جديداً. Validator صارم في Titan يرفضه قبل أن يصبح
Titan قادراً على دعمه، بينما validator غائب يترك typo مثل `paragaph` يصل إلى
network.

**النتيجة:** raw `dict` عارٍ ضعيف، ومرآة typed كاملة زائدة. القرار الأنسب
أخف من الاثنين:

```text
RichContent.blocks(sequence_of_mappings)
    يثبت أن المدخل blocks sequence
    ينسخ أو يجمد boundary وفق contract واضح
    يحافظ على unknown keys
    يتحقق من الشكل العام فقط
    لا يتحقق من كل Telegram union
```

لا نضيف `RichBlock` class إذا كان دوره الوحيد تغليف `dict` بلا invariant.
الـ abstraction الأخف هي constructor/value object نفسه، مع type alias أو
protocol داخلي عند الحاجة. Builders الحقيقية تبقى extension.

**الحكم:** لا نلغي raw blocks، لكن عبارة “raw block payloads” يجب ألا تعني
“أي object يصل إلى network”. نحتاج boundary shape وmutation policy قبل ADR.

### 39.3 هل html وmarkdown first-class modes؟

**حالة الكسر:**

- مطوّر يكتب HTML صالحاً وفق HTML العام لكنه غير صالح وفق rich HTML في
  Telegram.
- مطوّر يضع media reference في Markdown ولا يمرر `media`.
- مطوّر يخلط `parse_mode="HTML"` مع rich HTML.
- مطوّر يريد تغيير النص من Markdown إلى blocks في edit مع الحفاظ على
  message identity.

هذه الحالات لا تجعل modes الثلاثة غير صحيحة؛ بل تثبت أن `html` و`markdown`
ليسا “نصاً عادياً مع styling”. هما input modes رسمية لها grammar وقيود
Telegram، مثل blocks لكن بدرجة أقل وضوحاً.

**التغيير المقترح:**

لا يكون الشكل public object ذا ثلاث optional fields يمكن أن تكون في حالات
غير صحيحة. يكون الإنشاء صريحاً:

```python
RichContent.html("<b>hello</b>")
RichContent.markdown("**hello**")
RichContent.blocks([...])
```

هذا يجعل first-class mode ظاهراً من call site ويجعل mutual exclusion invariant
بنيوياً. لا parser ولا conversion ولا fallback إلى `sendMessage`.

**الحكم:** first-class modes تصمد؛ field-bag shape السابقة تحتاج تغييراً إلى
constructors/factories.

### 39.4 هل `Message.rich_message` هو الشكل الصحيح؟

**حالة الكسر الأولى:** رسالة تملك `text` و`rich_message` معاً. إذا أجبرنا
النموذج على variant واحد، قد نفقد field حقيقية من Telegram.

**حالة الكسر الثانية:** رسالة Rich-only تدخل `on("message")`، وhandler قد
يستدعي `ctx.text.startswith(...)`.

**حالة الكسر الثالثة:** client أو Bot API يضيف nested block غير معروف. إذا
كان accessor يحاول بناء union كامل، ينكسر parsing للرسالة كلها.

**النتيجة:**

- `Message.rich_message` هو field accessor الصحيح لأنه يطابق موضع Telegram
  ولا يخترع `Message.content` عاماً بلا transport ثانٍ.
- وجود `text` و`rich_message` معاً يجب الحفاظ عليهما، لا اختيار واحد منهما.
- `rich_message is None` هو absent semantics، و`text is None` ليس خطأ.
- unknown nested data يجب أن يبقى في `raw` ولا يمنع الوصول إلى message
  metadata الأساسية.

لا نضيف route `rich_message`. كما أن المشكلة الثانية ليست regression جديدة
خاصة بـ Rich: `on("message")` يستقبل أصلاً رسائل media التي قد لا تملك text.
لكن يجب أن يوضح contract أن message handler لا يحق له افتراض `ctx.text`.

**الحكم:** accessor يصمد، ولا نضيف generic content field أو route جديد.

### 39.5 هل `send_rich()` هو Titan-native؟

**حالة الكسر:**

السطح المقترح يكرر نفس الخيارات والسلوك:

```text
send / send_rich
reply / reply_rich
edit / edit_rich
```

وإذا ظهر مستقبلاً نوع content آخر، فسنضيف `send_x`, `reply_x`, `edit_x`.
هذا يجعل أفعال Titan انعكاساً لأنواع Telegram بدلاً من أن تكون أفعالاً
مستقرة تحمل content.

**البديل الذي يصمد أمام الاختبار:**

```python
await ctx.send("plain text")
await ctx.send(RichContent.html("<b>rich</b>"))

await ctx.reply("plain text")
await ctx.reply(RichContent.blocks([...]))

await ctx.edit("new text")
await ctx.edit(RichContent.markdown("**updated**"))
```

القيمة الصريحة `RichContent` تمنع ambiguity؛ لا يوجد dispatch مبني على
dictionary أو string heuristic. القواعد تكون:

- `str` يحتفظ بسلوك النص الحالي.
- `RichContent` يختار rich endpoint.
- `dict` لا يتحول تلقائياً إلى RichContent.
- `parse_mode` مع `RichContent` يرفض قبل network.
- `reply_markup` يبقى method-level option.

في `TelegramAdapter`، يبقى `send_rich_message` و`edit_rich_message` مناسبين
لأن adapter هو transport-facing surface ويعكس Telegram operation. أما
Context فهو المكان الذي يجب أن يكون Titan-native.

**الحكم:** هذه أول نقطة تغيّر حقيقية: نفضّل existing verbs مع
`RichContent` في Context، ونلغي الحاجة إلى `ctx.send_rich`,
`ctx.reply_rich`, و`ctx.edit_rich` من المقترح الأول. لا نسمي ذلك final قبل
اختبار signatures الحالية وقيود CONTRACT.

### 39.6 Rich Message بدون text

**حالة الكسر:**

```python
@bot.on("message")
async def handler(ctx):
    return ctx.text.upper()
```

هذا handler قد يفشل مع media حالياً أيضاً. Rich-only يجعل الحالة أوضح، لا
يخلق contract جديداً. أما command extraction فهو آمن لأن `update.text` يبقى
`None` ولا يُستخرج command من Rich blocks.

**القرار المعدّل:**

- message route يستقبل الرسالة.
- `ctx.text` و`ctx.message.text` يظلان `None`.
- `ctx.message.rich_message` هو الفحص الصريح.
- لا text projection تلقائية.
- أي helper مستقبلي للـ matching يجب أن يعلن هل يطابق text فقط أو كل
  content، ولا يغير `on("message")` بصمت.

**الحكم:** يصمد، مع توثيق أقوى لا abstraction جديدة.

### 39.7 Message Links

**حالة الكسر:**

```text
ctx.send(RichContent)
    → Context يملك LinksManager
    → يسجل message_id مع text=None

bot.telegram.send_rich_message(...)
    → TelegramAdapter لا يملك LinksManager
    → لا تسجيل تلقائي، مثل send_message الحالي
```

إذا قلنا إن كل rich send يولد Titan identity، نكون قد كسرنا الفصل الحالي
بين Context وAdapter. وإذا جعلنا adapter يسجل تلقائياً، نحتاج حقن manager
وتغيير semantics لكل adapter sends، وهذا ليس أثراً صغيراً لـ Rich.

**القرار المعدّل:**

- Context-mediated send فقط يدخل identity protocol تلقائياً.
- direct adapter send يتبع semantics الموجودة ولا يسجل identity تلقائياً.
- edit لا ينشئ identity.
- draft preview لا ينشئ identity.
- `text=None` قيمة صحيحة في archive عندما يكون archive مفعلاً، لكنها لا
  تعني أن Rich content محفوظ.

**الحكم:** مبدأ استقلال الهوية عن المحتوى يصمد، لكن scope التسجيل يجب أن
يكون “كل Context send” لا “كل send method”.

### 39.8 archive وserialization

**حالة الكسر الأولى:** `enable_archive()` موجود فعلاً ويحفظ `text=None` للرسائل
غير النصية. رفض أي interaction مع archive قد يوحي أن Rich message لا يمكن
أرشفتها حتى كهوية، وهذا غير صحيح.

**حالة الكسر الثانية:** حفظ raw input لا يضمن replay؛ file handles وmedia URLs
قد تنتهي، وresponse blocks قد تختلف عن input.

**حالة الكسر الثالثة:** `Message.to_dict()` يعيد raw Telegram message. هذا raw
snapshot مفيد، لكنه ليس بالضرورة archive semantic contract.

**القرار المعدّل:**

نميز ثلاث طبقات:

```text
Identity record       = يُنشأ لمسار Context بعد final send
Existing archive v1   = يسجل text=None، ولا يدعي Rich replay
Raw Message snapshot  = موجود عبر Message.raw/to_dict عند توفره
```

أي `RichArchive` قابل لإعادة العرض يحتاج ADR منفصلاً يحدد:

- هل نحفظ input أم response؟
- هل نحتفظ بالـ media reference أم bytes؟
- كيف نتعامل مع private URLs وprivacy؟
- ما versioning policy للـ Telegram schema؟
- هل archive resolver يعرض raw أم rendered projection؟

**الحكم:** لا archive Rich semantic الآن، لكن لا نرفض حفظ identity أو raw
snapshot الموجودين بالفعل.

### 39.9 Rich Buttons والـ keyboard system

**حالة الكسر:**

- Rich block button قد يريد callback.
- Inline keyboard button قد يريد callback أيضاً.
- المطوّر يريد أن يعيد استخدام handler نفسه.

تشابه callback action لا يحسم أن الكيانين واحد. الفرق الحاسم هو موضع الزر
في payload وlifecycle الذي يستجيب له Telegram. إسقاط Rich button في
`reply_markup` قد يغير layout، وإدخاله في block قد يغير event semantics.

**القرار:** يبقيان منفصلين في representation. لكن “خارج keyboard system
تماماً” صياغة زائدة: Rich buttons جزء من **content controls** ولهذا يحتاج
documentation وpossibly shared callback payload utilities لاحقاً، لا
`InlineKeyboardButton` نفسه.

**الحكم:** الفصل يصمد؛ نخفف العبارة من “خارج keyboard system تماماً” إلى
“ليس جزءاً من InlineKeyboard abstraction”.

### 39.10 Core مقابل extension

**حالة الكسر الأولى:** إذا بقي blocks raw بالكامل، هل يصبح Core مجرد transport
pass-through لا يستحق model؟

**حالة الكسر الثانية:** إذا وضعنا `RichContent` خارج Core، فلن يستطيع `Message`
و`Context` التحدث بنفس اللغة، وستعود الحاجة إلى Telegram raw في handler.

**حالة الكسر الثالثة:** builder صغير للـ paragraph قد يوفر قيمة كبيرة بلا
كلفة schema كبيرة.

**النتيجة:**

- `RichContent` و`Message.rich_message` وcontent dispatch تدخل Core.
- block schema الكامل لا يدخل Core.
- constructor `RichContent.blocks` يدخل Core لأنه boundary، لا builder.
- builders الودية يمكن أن تدخل extension عندما يثبت استعمالها.
- parser وrenderer وarchive projection وcross-transport تبقى خارج Core.

**الحكم:** boundary Core تصمد، لكن constructor value object جزء من Core؛
ليس كل ما يتعلق بـ blocks extension.

### 39.11 drafts/streaming

**حالة الكسر:**

1. يبدأ draft.
2. يتوقف المستخدم.
3. تصل tick متأخرة بعد stop.
4. يحصل shutdown أثناء finalization.
5. تنتهي صلاحية preview قبل tick التالية.
6. يحاول المطور إعادة استخدام `draft_id` في chat آخر.

أي API `ctx.send(RichContent, stream=True)` ستخفي هذه الحالات داخل method
بسيطة، وأي background task غير مملوكة للـ lifecycle قد تستمر بعد `run_async`
أو تحاول استعمال session أُغلقت.

**القرار:** drafts تستحق API مستقلة، لكن ليس مجرد
`send_rich_message_draft()` مكشوفة للمستخدم ثم الادعاء أن المشكلة حُلت.
الـ API المستقبلية يجب أن تكون session/handle صريحة، مع:

- ownership لشات وdraft id.
- monotonic state transition.
- stop token أو cancellation primitive.
- finalization صريحة.
- no identity/archive للpreview.
- shutdown policy لا تعمل finalization ضمنياً.
- تجاهل ticks المتأخرة بعد terminal state.

**الحكم:** قرار الفصل بين الرسائل الأساسية وdrafts ما زال قائماً. نُفذ دعم
Rich content الأساسي عبر API المعتمدة في ADR-023؛ أما drafts فمؤجلة ولا توجد
لها API نهائية في النطاق الحالي.

### 39.12 ما الذي لا نبنيه؟

المراجعة حاولت كسر قائمة الرفض باحتياجات عملية:

- المطور يريد `RichContent.html(...)` — هذا ليس parser، ويجب أن يدخل candidate
  الأساسي.
- المطور يريد paragraph helper — يمكن أن يكون extension، لا يبرر كل schema.
- المطور يريد إعادة إرسال incoming rich message — يحتاج conversion صريح، لا
  round-trip implicit.
- المطور يريد archive للـ rich content — يحتاج ADR storage/privacy، لا side
  effect.
- المطور يريد streaming — يحتاج session lifecycle، لا flag.
- المطور يريد callback مشتركاً — يمكن مشاركة data convention، لا model
  button.

**الحكم:** “لا نبني هذا” ما زالت إجابة صحيحة في معظم المساحات، لكن لا ينبغي
أن تمنع value constructors البسيطة التي تثبت intent وتقلل raw misuse.

---

## 40. التصميم المرشح بعد الكسر

هذه ليست قرارات نهائية؛ إنها النسخة التي نجت بعد تعديل النقاط التي فشلت:

### Content model

```text
RichMessage  = incoming Telegram representation
RichContent  = outgoing Titan value

RichContent.html(markup, media=..., is_rtl=...)
RichContent.markdown(markup, media=..., is_rtl=...)
RichContent.blocks(sequence_of_mappings, is_rtl=...)
```

الـ constructors تجعل mode الواحد invariant. `RichContent` لا يقبل
`RichMessage` ولا dict message كامل. `blocks` mapping payloads تبقى raw
بالمعنى المقصود، لكن تمر عبر boundary shape وmutation policy محددتين.

### Context model

```text
ctx.send(str | RichContent)
ctx.reply(str | RichContent)
ctx.edit(str | RichContent)
```

المحتوى هو الذي يحدد transport path، لا اسم method الإضافي. `str` يحافظ على
السلوك القديم. `RichContent` يختار Rich endpoint. `parse_mode` مع
`RichContent` خطأ محلي. `reply_markup` منفصل.

### Adapter model

يبقى adapter transport-facing:

```text
bot.telegram.send_message(...)
bot.telegram.send_rich_message(...)
bot.telegram.edit_message_text(...)
bot.telegram.edit_rich_message(...)
```

ولا تُنقل إليه Message Links تلقائياً؛ هذا يحافظ على الفرق الموجود بين direct
adapter calls وContext operations.

### Incoming model

```text
ctx.message.rich_message: RichMessage | None
ctx.text: str | None
```

كلاهما يمكن أن يوجد أو يغيب وفق raw Telegram message. لا generic projection،
ولا event route جديد.

### Lifecycle boundary

```text
basic Rich content → Core
block builders      → extension
archive Rich replay → separate ADR
draft streaming     → separate lifecycle API/ADR
```

---

## 41. ما تغيّر وما صمد

### تغيّر بسبب المراجعة

1. `RichMessageInput` لم يعد الاسم المفضل؛ `RichContent` أكثر Titan-native.
2. constructors/factories تحل محل object ذي optional fields الثلاثة.
3. Context يفضّل `send/reply/edit` مع `RichContent` بدلاً من ثلاث methods
   `*_rich`.
4. Message Links scope أصبح صريحاً: التسجيل التلقائي لمسار Context فقط.
5. “Rich buttons خارج keyboard system” صارت “ليست InlineKeyboard
   abstraction”.
6. archive لا يُرفض كلياً؛ `text=None` وraw snapshot ممكنان، لكن replay
   semantic مؤجل.

### صمد بعد الاختبار

1. الفصل بين incoming وoutgoing.
2. Telegram-specific boundary بدلاً من canonical AST.
3. html/markdown/blocks بلا parser أو conversion.
4. `Message.rich_message` داخل message route.
5. عدم إسقاط Rich-only إلى text.
6. raw blocks مع boundary خفيفة، لا typed mirror كاملة.
7. identity مستقلة عن representation.
8. drafts/streaming كـ lifecycle مستقل.
9. رفض middleware orchestration وfallback الصامت.
10. عدم تعديل الكود أو CONTRACT في مرحلة الاختبار السابقة لاعتماد ADR.

---

## 42. بوابة الانتقال إلى ADR — سجل تاريخي، أُغلقت

> هذا القسم يسجل الأسئلة التي سبقت ADR-023. حُسمت حدود الدعم الأساسي فيه،
> ونُفذت ووُثقت في العقد؛ أما drafts/streaming فبقيت مؤجلة.

قبل اعتماد ADR-023، كان الانتقال يتطلب حسم خمس نقاط:

1. هل الاسم النهائي هو `RichContent` أم `RichMessageInput`؟
2. هل existing verbs مع typed content أفضل فعلاً من `*_rich` في signatures
   Titan الحالية؟
3. ما الحد الأدنى الدقيق لـ blocks boundary: قبول mapping فقط، أم copy/freeze
   أم wrapper يملك invariant إضافياً؟
4. هل basic editing يدخل نفس ADR أم يؤجل إلى ADR مستقل؟
5. هل `RichContent` يملك invariants وسلوكاً حقيقياً، أم أنه مجرد envelope
   جميل حول dict؟

أصبحت هذه النقاط مادة ADR-023 المعتمد، وأُكمل بعدها تحديث العقد والتنفيذ
والاختبارات. يوضح المخطط التالي ترتيب العمل الذي كان مقترحاً آنذاك:

```text
Adversarial Review
    → ADR
    → CONTRACT update
    → implementation
    → tests
```

**الحالة وقت كتابة هذا القسم:** لم يكن التصميم قد حُسم؛ غيّرت المراجعة العدائية
بعض المقترحات. حُسمت الحالة لاحقاً في ADR-023، وهو المرجع النهائي.

---

## 43. Focused Gate Review — سجل تاريخي سابق لـ ADR-023

> هذا الاختبار يوثق مراجعة التوقيع وmutation قبل ADR-023 والتنفيذ؛
> التوقيعات والاقتراحات أدناه لا تصف الواجهة الحالية.

كان هذا اختباراً مركزاً للنقاط المفتوحة آنذاك، لتحديد ما إذا كانت الفرضية
المرشحة تستحق الدخول في ADR.

### 43.1 تدقيق signatures المتاحة آنذاك

التوقيعات الفعلية في تلك المرحلة، قبل توسيع نوع `text`:

```python
ctx.reply(text: str, parse_mode: str | None = None, reply_markup: Any | None = None)
ctx.send(text: str, parse_mode: str | None = None, reply_markup: Any | None = None)
ctx.edit(text: str, parse_mode: str | None = None, reply_markup: Any | None = None)
```

والـ adapter وtransport يستخدمان أيضاً `text` كاسم public للمعامل النصي.
هذا مهم لأن التوافق لا يعني positional calls فقط:

```python
await ctx.send(text="hello")
await ctx.reply(text="hello", parse_mode="HTML")
```

#### المرشح A — تغيير الاسم إلى `content`

```python
ctx.send(content: str | RichContent, ...)
```

**يفشل compatibility test:** أي code يستخدم `text=` سيحصل على
`unexpected keyword argument`. حتى لو كان هذا التغيير أجمل دلالياً، فهو
breaking change وفق contract الحالي.

#### المرشح B — توسيع نوع `text` مع إبقاء الاسم

```python
ctx.send(text: str | RichContent, ...)
ctx.reply(text: str | RichContent, ...)
ctx.edit(text: str | RichContent, ...)
```

هذا يحافظ على positional وkeyword calls القديمة، ولا يحتاج overload runtime.
الـ dispatch ليس heuristic: `str` مسار النص، و`RichContent` مسار Rich، وraw
`dict` مرفوض.

الثمن الحقيقي هو أن اسم `text` يصبح تاريخياً لا وصفياً عندما تكون القيمة
`RichContent`. يمكن أن يشرح docstring المعامل كـ “text or content”، لكن لا
يجوز تغيير اسمه بلا قرار compatibility مستقل.

#### المرشح C — إبقاء `text` كما هو وإضافة `*_rich`

```python
ctx.send_rich(RichContent)
ctx.reply_rich(RichContent)
ctx.edit_rich(RichContent)
```

هذا يحافظ على signatures تماماً ويجعل intent واضحاً، لكنه يضاعف أفعال
Context ويعيد السؤال الذي كُسر في §39.5: هل كل content type مستقبلي سيصنع
ثلاث methods إضافية؟

#### المرشح D — إضافة `content=` اختياري إلى الأفعال القديمة

```python
ctx.send(text: str | None = None, content: RichContent | None = None, ...)
```

**يفشل ambiguity test:**

```python
ctx.send(text="a", content=RichContent.html("b"))
ctx.send(content=RichContent.html("b"))
ctx.send(None, RichContent.html("b"))
```

سيحتاج هذا إلى قواعد تعارض أكثر من القيمة التي يعطيها، ويجعل signature
مليئة بحالات invalid state.

#### نتيجة signature test

المرشح الأقوى حالياً هو **B**:

```text
Context: existing verbs + union type، مع إبقاء اسم text للتوافق
Adapter: Telegram-specific rich methods تبقى مستقلة
```

لكن هذا ليس حسم ADR بعد. قبل اعتماده يجب أن يقبل CONTRACT صراحةً أن `text`
هو historical parameter name يقبل `str | RichContent`، وأن `parse_mode` مع
RichContent خطأ محلي. إذا رفضت فلسفة Titan هذا التنازل الاسمي، يعود المرشح C
كخيار compatibility-first، لا كفشل في التصميم.

### 43.2 اختبار copy مقابل freeze مقابل reference

استخدمت probe محلياً على payload يمثل table nested، unknown future field، وmedia
reference opaque. الاختبار غيّر nested cell بعد إنشاء القيمة، ثم اختبر
serialization وهوية media leaf. النتيجة:

| السياسة | تسرب nested mutation؟ | JSON serialization | هوية media leaf |
|---|---:|---:|---:|
| reference | نعم | نعم | محفوظة |
| shallow copy | نعم | نعم | محفوظة |
| `deepcopy` | لا | نعم | مفقودة |
| recursive freeze | لا | لا مباشرةً | محفوظة |
| structural snapshot | لا | نعم | محفوظة |

وعلى payload table من 10,000 cell، كان probe تقريبيًا على Python 3.13:

```text
reference            ~0.01ms / 20 operations
shallow copy         ~0.01ms / 20 operations
deepcopy             ~249ms  / 20 operations
structural snapshot  ~77ms   / 20 operations
```

الأرقام ليست benchmark contract؛ هي وسيلة لكشف trade-off. النمط هو المهم:

- reference أرخص لكنه يجعل `RichContent` view متغيرة لا value.
- shallow copy يعطي أماناً وهمياً لأن nested mappings ما زالت مشتركة.
- deepcopy يحمي البنية لكنه ينسخ objects لا يملك Titan معناها، وقد يكسر
  identity أو file/media handles.
- recursive freeze يحتاج wrapping عميقاً، و`MappingProxyType` ليس JSON
  payloadاً جاهزاً؛ سينشئ unfreeze serializer خاصاً به.
- structural snapshot يحمي container structure ويحافظ على opaque leaves،
  وتكلفته متناسبة مع payload بدلاً من نسخ arbitrary object graph.

### 43.3 القرار المرشح للـ mutation policy

المرشح الأفضل هو:

```text
RichContent value
    يأخذ structural snapshot للحاويات عند الإنشاء
    لا يحتفظ بمراجع dict/list الخاصة بالمطور
    يعيد plain dict/list عند serialization
    يحافظ على scalar/media-reference leaves
    لا يدعي أنه deep-copies arbitrary user objects
```

هذا ليس “الأكثر أماناً” بصورة مجردة؛ هو الأقل كلفة الذي يحقق invariant
اللازم: تعديل block nested عند المطور بعد إنشاء `RichContent` لا يغير القيمة
المسجلة. أما media object opaque، فإن قبوله أصلاً يجب أن يكون قراراً منفصلاً:
إما أن يتحول إلى payload عند الإنشاء، أو يُقبل كـ leaf له serialization contract
خاص. لا يجوز أن تسكت abstraction عن هذه النقطة.

**الحكم:** لا reference ولا shallow copy. لا freeze public. structural
snapshot هو المرشح الذي يدخل ADR، مع حسم شكل media leaves داخله.

### 43.4 اختبار: هل RichContent abstraction حقيقية؟

نقارنها بالـ raw dict، لا بالـ classes الكثيرة:

```python
ctx.send({"html": "<b>x</b>"})
```

إذا قُبل هذا، فـ `RichContent` تجميلي؛ لأن dispatch والـ mode contract ما زالا
يعتمدان على فحص dict.

أما:

```python
ctx.send(RichContent.html("<b>x</b>"))
```

فيكون abstraction حقيقية فقط إذا امتلكت invariants التالية:

1. **Mode invariant:** لا يمكن أن يوجد html وmarkdown وblocks في قيمة واحدة.
2. **Type distinction:** `RichMessage` الواردة وraw dict لا يقبلان مكان
   `RichContent` بلا تحويل صريح.
3. **Serialization owner:** القيمة تعرف كيف تنتج payload Rich الصحيح، ولا
   يكرر `Context` و`Adapter` منطق mode.
4. **Dispatch semantics:** وجود RichContent يختار Rich transport بلا string
   parsing أو dict heuristic.
5. **Mutation policy:** القيمة لا تتغير بسبب mutation خارجي للـ containers.
6. **Extension boundary:** builders المستقبلية تنتج نفس القيمة، ولا تغيّر
   Context أو transport contract.
7. **Error boundary:** `parse_mode` أو mode conflict يرفضان محلياً، بينما
   grammar/rendering Telegram errors تبقى Telegram errors.

إذا حذفنا هذه السبعة وبقي class يحوي `payload: dict` فقط، فالأفضل عدم وجوده.
أما إذا ثبتت، فهو ليس wrapper تجميلياً؛ إنه **typed semantic boundary**
صغيرة بين Titan content وTelegram representation.

### 43.5 قرار مؤقت بعد الاختبار

المراجعة لا تحسم الاسم النهائي ولا تنشئ ADR، لكنها تغير ترتيب الاحتمالات:

```text
الأقوى:
    RichContent constructors + existing Context verbs
    structural snapshot للحاويات
    raw block mappings داخل boundary
    adapter methods Telegram-specific

احتياطي:
    RichContent constructors + Context *_rich
    إذا تعذر الحفاظ على text= مع union type أو رفضه CONTRACT

المرفوض:
    raw dict dispatch
    shallow-copy illusion
    public recursive freeze
    content= إلى جانب text=
    deep-copy arbitrary media/user objects
```

---

## 44. تحديث بوابة ADR — سجل تاريخي

بعد هذا الاختبار، البوابات الخمس ليست “إجراءات شكلية”:

1. **الاسم:** `RichContent` هو المرشح، لكن لم يُعتمد نهائياً.
2. **Context verbs:** union على `text` يحافظ على `text=`؛ يجب اختبار قبوله
   كـ API public مقابل وضوح `*_rich`.
3. **blocks boundary:** structural snapshot مرشح، مع حسم media leaves.
4. **editing:** يجب تحديد هل يدخل نفس ADR مع send/reply أم يملك contract
   مختلفاً بسبب callback-only semantics الحالية.
5. **قيمة RichContent:** اجتازت اختبار “ليست مجرد dict wrapper” بشكل مبدئي،
   بشرط أن تدخل invariants السبعة في ADR ولا تُترك كـ implementation detail.

لذلك لا يزال الترتيب الصحيح:

```text
focused gate review
    → ADR بصياغة invariants
    → CONTRACT compatibility wording
    → implementation
    → tests
```

**الحالة وقت كتابة هذا القسم:** لم يكن قد اعتُمد ADR بعد. انتقل هذا المسار
لاحقاً إلى ADR-023؛ وتوثق هذه الفقرة مراحل الاختبار التي سبقته.

---

## 45. Final Design Gate — محاولة الإسقاط الأخيرة

هذا القسم هو آخر اختبار قبل ADR، وليس ADR نفسه. لا يفترض أن
`RichContent` أو `structural snapshot` فائز مسبقاً. يبدأ من أقوى حجة ضد كل
واحد، ثم يقارن أقل البدائل التي تحقق نفس الحدود.

كل نتيجة تحمل نوعها:

```text
FACT       = أثبته source/probe أو contract موجود
INFERENCE  = نتيجة منطقية من facts
PROPOSAL   = اختيار Titan مرشح للـ ADR في تلك المرحلة، وليس القرار النهائي
```

---

## 46. محاولة قتل RichContent

### 46.1 أقوى حجة ضده

Telegram يملك schema input واضحة، وTitan يملك أصلاً `ctx.raw` و
`model.raw` كـ escape hatches. لذلك يمكن القول:

```python
await ctx.send(rich_message={"html": "<b>hello</b>"})
```

لا نحتاج class جديداً؛ نتحقق من أن واحداً فقط من `text` و`rich_message` موجود،
ثم نمرر dictionary إلى Telegram. هذا أقل code، أقل public imports، وأسرع
في مواكبة أنواع Telegram الجديدة.

هذه ليست حجة سطحية. إنها تفوز فعلاً إذا كانت Rich feature مجرد endpoint
نادر لا يحتاج أن تدخل semantic message model أو Context dispatch.

### 46.2 البدائل بدون RichContent

| البديل | ما يكسبه | أين ينكسر |
|---|---|---|
| `rich_message={...}` keyword | أقل classes وcopy | invalid states، dict heuristic، لا type distinction |
| `rich_html=`, `rich_markdown=`, `rich_blocks=` | intent ظاهر | ثلاث مجموعات options وحالات تعارض كثيرة |
| `ctx.send({...})` | surface أصغر نظرياً | لا يميز rich payload عن arbitrary dict |
| adapter-only | Core لا يعرف schema | incoming model وContext boundary ناقصان |
| استعمال `RichMessage` للـ send | لا type جديد | response وinput في اتجاه واحد خاطئ |
| factory functions تعيد dict | syntax أخف | القيمة النهائية ما زالت untyped dict |
| `RichContent` tagged value | invariant + dispatch + serialization | public type وقرار mutation policy |

### 46.3 اختبار الاستخدام الطبيعي

المطلوب ليس أن يبدو المثال جميلاً فقط، بل أن تمنع الحدود أخطاء حقيقية:

```python
await ctx.send("hello")                         # existing text
await ctx.send(text="hello")                    # existing keyword
await ctx.send(RichContent.html("<b>hello</b>"))
await ctx.reply(RichContent.blocks([
    {"type": "paragraph", "text": "hello"}
]))
await ctx.edit(RichContent.markdown("**updated**"))
```

في تصميم no-class، لا توجد نقطة واحدة تميز آخر ثلاثة calls من dictionary
عشوائي سوى convention أو runtime inspection. وفي تصميم `RichContent`، القيمة
نفسها تحمل mode:

```text
str           → legacy text dispatch
RichContent   → rich dispatch
dict          → reject locally
RichMessage   → reject as wrong direction
```

هذا ليس تجميلاً. إنه يمنع `Context` من اكتشاف semantics عن طريق فحص مفاتيح
dict، ويجعل invalid construction قابلاً للاكتشاف قبل network.

### 46.4 اختبار incoming / editing / errors

| الحالة | no-class dict design | `RichContent` |
|---|---|---|
| incoming `Message.rich_message` | يمكن إضافته منفصلاً | accessor منفصل وواضح |
| `text` وRich معاً في incoming | يحتاج policy أخرى | كلاهما محفوظان في `Message` |
| edit Rich | `text=None, rich_message=...` ambiguity | `edit(RichContent)` dispatch صريح |
| modeان في outgoing | runtime validation للـ dict | لا ينشأ من constructors |
| `parse_mode` مع Rich | manual conditional | TitanError محلي |
| Telegram grammar invalid | Telegram error | TelegramError، لا يختلط مع TitanError |
| unknown block type | pass-through أو reject | pass-through داخل blocks boundary |

### 46.5 هل يمكن جعل RichContent أصغر؟

نعم. `RichContent` لا يحتاج:

- class لكل block.
- renderer.
- parser.
- network methods.
- archive methods.
- generic `DocumentNode`.
- arbitrary `payload: dict` public constructor.

الحد الأدنى الحقيقي هو tagged input value بثلاثة constructors:

```text
RichContent.html(markup, ...)
RichContent.markdown(markup, ...)
RichContent.blocks(blocks, ...)
```

والقيمة تملك فقط invariants والـ serialization boundary. إذا لم نلتزم بذلك،
فحجة إلغاء RichContent تصبح أقوى.

### 46.6 النتيجة المعمارية

**FACT:** raw dictionaries أقل كلفة في البداية.  
**FACT:** raw dictionaries لا تعطي type distinction أو mode invariant وحدها.  
**INFERENCE:** لأن Rich تدخل Context dispatch وincoming Message وediting، فهي
أكثر من endpoint transport منفرد.  
**PROPOSAL:** نُبقي `RichContent`، لكن نضيقها إلى tagged input value ولا
نحولها إلى rich document model.

**الحكم:** محاولة قتل `RichContent` فشلت، لكن محاولة تقليصها نجحت. الذي
يستحق ADR هو value صغير، لا class غني.

---

## 47. محاولة قتل structural snapshot

### 47.1 أقوى حجة ضده

`Context.send()` الحالية تنفذ request مباشرة ولا تنشئ queue أو background
task. لذلك يمكن أن يكون `RichContent` مجرد view على data المطور، ثم تُقرأ
البيانات عند serialization. نسخ nested containers عند constructor قد يكون
كلفة بلا فائدة، خصوصاً إذا كان المطور يبني table تدريجياً قبل الإرسال.

هذه الحجة أقوى من “reference أسرع” فقط؛ إنها تسأل أين يجب أن يحدث snapshot:
عند إنشاء القيمة أم عند تسليم الطلب إلى transport؟

### 47.2 البدائل

| السياسة | nested mutation قبل send | mutation بعد serialization | opaque object | التعقيد |
|---|---|---|---|---|
| reference حتى النهاية | يظهر في payload | قد يتسرب أثناء await | محفوظ | منخفض، لكن غير deterministic |
| shallow copy عند الإنشاء | nested يتسرب | قد يتسرب | محفوظ | منخفض، وحماية وهمية |
| `deepcopy` عند الإنشاء | محمي | محمي | قد يفقد identity | مرتفع وكاسر للـ objects |
| recursive freeze | محمي | محمي | محفوظ | مرتفع وserializer مطلوب |
| structural snapshot عند الإنشاء | لا يظهر | محمي | محفوظ إذا copy containers فقط | متوسط |
| **snapshot عند serialization** | يظهر عمداً قبل submit | لا يظهر بعد submit | يُحوّل/يُحفظ عند boundary | منخفض-متوسط |

### 47.3 نتيجة probe السابق

الـ probe المحلي على nested table وunknown field وmedia opaque أثبت:

```text
reference          → nested mutation leak
shallow copy       → nested mutation leak
deepcopy           → no leak, media identity lost
recursive freeze   → no leak, not directly JSON-serializable
structural copy    → no leak, media leaf preserved
```

كما أن تكلفة structural copy أقل من `deepcopy` في payload كبير، لكنها ليست
صفراً. هذه الأرقام لا تثبت policy وحدها؛ هي تثبت فقط أن “ننسخ كل شيء” ليس
مجانيًا وأن shallow copy لا يحقق الغرض.

### 47.4 اختبار submission boundary

نصوغ semantics بدلاً من الاعتماد على object policy:

```text
1. RichContent يسمح للمطور ببناء/تعديل containers قبل submit.
2. عند دخول Context أو Adapter إلى send operation:
       serialize مرة واحدة إلى plain dict/list payload.
3. بعد اكتمال serialization لا تُقرأ containers الأصلية مرة أخرى.
4. network await يستعمل payload snapshot، لا RichContent view.
5. لا ينسخ Titan arbitrary opaque objects لمجرد أنها موجودة في payload.
```

بهذا:

- reference قبل submit سلوك مقصود ومفيد للبناء التدريجي.
- mutation بعد submit لا يغير request الجاري.
- لا نحتاج freeze wrappers.
- لا ننسخ media/file handles اعتباطاً.
- لا نكذب ونقول إن RichContent immutable value عند constructor.

### 47.5 القرار الذي يقتل structural snapshot السابق

النتيجة الأقوى ليست `structural snapshot at construction`، بل:

```text
serialization-boundary snapshot
```

وهذا **يستبدل** المرشح السابق في §43. لا يعني ذلك reference حي أثناء
network؛ بل يعني أن copy/normalization تحدث عند boundary الوحيدة التي تحتاج
determinism: لحظة تحويل المحتوى إلى request payload.

**FACT:** current basic Context operations لا تملك draft queue أو delayed
serializer.  
**INFERENCE:** لا توجد قيمة معمارية لنسخ payload في constructor إذا كان
serialization يحدث فور بدء operation.  
**PROPOSAL:** RichContent يحتفظ بالبنية حتى submit، ثم ينتج plain payload
واحداً. Contract يضمن أن serialization يحدث قبل أول network await.

### 47.6 حدود هذا القرار

هذا القرار لا يصلح تلقائياً لـ:

- draft sessions.
- background retries.
- queue-based delivery.
- content object يعيش بين tasks متوازية.

هذه الحالات يجب أن تملك payload snapshot عند enqueue أو session transition.
وهذا سبب إضافي لعدم خلط drafts مع basic send.

**الحكم:** تم إسقاط `structural snapshot at construction`. البديل الأدنى
القابل للدفاع هو snapshot عند serialization boundary، مع reject لـ shallow
copy وdeepcopy arbitrary objects وpublic freeze.

---

## 48. اختبار signatures الحالية فعلياً

### 48.1 ما أثبته المصدر

من `src/titan/ctx.py`:

```python
async def reply(
    self,
    text: str,
    parse_mode: str | None = None,
    reply_markup: Any | None = None,
) -> Any: ...

async def send(
    self,
    text: str,
    parse_mode: str | None = None,
    reply_markup: Any | None = None,
) -> Any: ...

async def edit(
    self,
    text: str,
    parse_mode: str | None = None,
    reply_markup: Any | None = None,
) -> Any: ...
```

تم استخراج أسماء parameters ومواضع defaults عبر AST، ثم اختبار binding عبر
`inspect.Signature.bind` على الشكل نفسه. الاستيراد المباشر لـ `Context` لم يكن
متاحاً في sandbox لأن `aiohttp` غير مثبتة؛ لذلك لا ندعي runtime execution
للـ API، بل نعرض هنا نتيجة source/signature binding فقط.

### 48.2 matrix binding

| الاستدعاء | signature الحالية | union مع إبقاء `text` | تغيير الاسم إلى `content` |
|---|---:|---:|---:|
| `ctx.send("hello")` | binds | binds | binds |
| `ctx.send(text="hello")` | binds | binds | rejects |
| `ctx.send(RichContent.html(...))` | binds runtime فقط، ثم يفشل transport | binds | binds |
| `ctx.send(content=RichContent.html(...))` | rejects | rejects | binds |

الصف الثالث مهم: Python binding الحالية تقبل أي object positional لأن type
annotations لا تتحقق runtime؛ لكنها سترسله إلى `send_message` النصية، فلا
يعني ذلك أن Rich مدعوم. Candidate union يضيف dispatch implementation واضحاً،
لا overload.

### 48.3 نتيجة signature gate

المرشح الذي يحقق الأمثلة الثلاثة ويحافظ على backward compatibility هو:

```python
ctx.send(text: str | RichContent, ...)
ctx.reply(text: str | RichContent, ...)
ctx.edit(text: str | RichContent, ...)
```

مع القواعد:

- إبقاء اسم `text` عمداً لحماية `text=` القديمة.
- توثيق الاسم تاريخياً كـ “text or RichContent”.
- تشجيع Rich usage positional لأن `text=RichContent(...)` صحيح binding لكنه
  أقل وضوحاً.
- رفض `content=` في هذه الأفعال؛ لا نضيف parameter ثانياً.
- رفض `parse_mode` عندما تكون القيمة RichContent.
- عدم قبول dict كـ implicit Rich.

هذا ليس overloads ولا semantics مصطنعة: نوع القيمة يحدد dispatch مباشرةً.
التنازل الوحيد هو اسم parameter تاريخي، وهو ثمن compatibility قابل للتوثيق.

البديل `*_rich` يبقى fallback فقط إذا أثبت CONTRACT أن union على parameter
اسمه `text` غير مقبول دلالياً. لا يوجد سبب لاختياره تلقائياً بعد نجاح gate.

---

## 49. اختبار RichContent كـ API حقيقية

### 49.1 الاستخدام الطبيعي

```python
content = RichContent.html(
    "<h1>Hello</h1>",
    media={"hero": "https://example.test/hero.png"},
)

await ctx.send(content)
await ctx.reply(RichContent.blocks([
    {"type": "paragraph", "text": "Details"},
    {
        "type": "table",
        "rows": [{"cells": [{"text": "A"}]}],
        "future_field": {"enabled": True},
    },
]))
```

**FACT:** الاستخدام يميز mode من call site ولا يحتاج `parse_mode`.  
**INFERENCE:** هذا أقل غموضاً من `rich_message={...}`، حتى مع بقاء blocks
raw.  
**PROPOSAL:** public constructors هي الطريقة الرسمية؛ لا public constructor
عام يقبل “أي payload”.

### 49.2 incoming Message.rich_message

```python
incoming = ctx.message.rich_message
if incoming is not None:
    blocks = incoming.blocks
```

**FACT:** incoming representation ليست input representation.  
**PROPOSAL:** `RichMessage` read model يبقى منفصلاً، و`Message.text` يمكن أن
يكون `None`، وكلاهما يمكن أن يوجد في raw message نفسه. لا تحويل تلقائي من
`RichMessage` إلى `RichContent`.

### 49.3 editing

```python
await ctx.edit(RichContent.markdown("**changed**"))
```

**FACT:** `ctx.edit` الحالية callback-only وparameterها `text`.  
**PROPOSAL:** نفس method تستقبل union، وتختار rich edit عندما تكون القيمة
RichContent، من دون تغيير callback-only boundary. لا identity جديدة ولا
archive record جديد عند edit.

### 49.4 invalid construction

المسار الرسمي لا يسمح بإنشاء:

```text
html + markdown
markdown + blocks
html + blocks
no mode
```

لأن كل constructor ينشئ mode واحداً. وإذا احتاج implementation إلى internal
normalizer، فهو لا يصبح public escape hatch. Raw blocks داخل mode blocks فقط.

### 49.5 nested mutation

**PROPOSAL:** mutation مسموح قبل submit ويُلتقط عند serialization boundary؛
بعدها request يعمل على payload snapshot. هذا يثبت semantics دون ادعاء
immutability شاملة.

### 49.6 serialization

**PROPOSAL:**

```text
RichContent.html(...)     → {"html": "...", ...}
RichContent.markdown(...) → {"markdown": "...", ...}
RichContent.blocks(...)   → {"blocks": [...], ...}
```

لا يكرر `Context` و`Telegram` mode logic. `reply_markup` يبقى خارج
`rich_message`. unknown nested fields تبقى كما هي في blocks. media references
تخضع لserialization boundary الخاصة بها، لا لـ `deepcopy` arbitrary.

### 49.7 Titan errors مقابل Telegram errors

```text
TitanError:
    dict passed instead of RichContent
    parse_mode with RichContent
    invalid blocks container shape
    invalid Context-only state

TelegramError:
    invalid rich HTML/Markdown grammar
    unsupported Telegram field combination
    media resolution/upload failure
    chat/account permission failure
```

القاعدة ليست أن Titan يتحقق من كل Telegram schema؛ بل أن Titan يتحقق من
حدوده هو، ويترك semantics Telegram لـ Telegram.

### 49.8 هل بقيت abstraction أم أصبحت wrapper؟

بعد تقليصها، `RichContent` لا تزال تملك قيمة لا يملكها dict:

```text
dict                         RichContent
---                          -----------
لا mode invariant             mode invariant
قد يدخل بأي route             dispatch type واضح
لا اتجاه input/output          RichMessage مرفوض بلا تحويل
serialization مكرر             serialization owner واحد
mutation semantics غامضة       submit-boundary semantics
Telegram errors مختلطة          Titan/Telegram error boundary
```

إذا أزيلت هذه الضمانات، يجب حذف RichContent. أما مع بقائها، فهي abstraction
حقيقية صغيرة، وليست مجرد class حول dict.

---

## 50. محاولة إيجاد تصميم أبسط من المرشح

بعد كل الاختبارات، التصميم الأبسط الذي يحافظ على نفس الحدود هو:

```text
Incoming:
    Message.rich_message → RichMessage | None

Outgoing:
    RichContent.html(...)
    RichContent.markdown(...)
    RichContent.blocks(...)

Context:
    send(text: str | RichContent)
    reply(text: str | RichContent)
    edit(text: str | RichContent)

Adapter:
    Telegram-specific rich methods

Mutation:
    serialize-on-submit، لا constructor deep copy

Routing:
    existing message route

Identity:
    Context sends only، final messages only

Archive:
    text=None في v1، no Rich replay promise

Drafts:
    separate lifecycle، not in basic API
```

أي تصميم أقل من هذا يخسر واحداً من:

- backward-compatible `text=`.
- mode invariant.
- incoming/outgoing distinction.
- direct Context boundary.
- deterministic request payload.
- error boundary.

وأي تصميم أكثر من هذا يضيف على الأقل واحداً من:

- duplicated `*_rich` methods.
- full Telegram typed mirror.
- parser/renderer.
- freeze/deepcopy policy لا يحتاجها basic operation.
- archive/lifecycle semantics غير مطلوبة.

---

## 51. حكم Final Design Gate

### ما أثبته الاختبار

1. signatures الحالية تستخدم `text`، و`text=` compatibility حقيقية وليست
   تفصيلاً شكلياً.
2. union على نفس parameter يحقق الأمثلة المطلوبة بلا overloads.
3. raw dict وحده لا يثبت type distinction أو dispatch contract.
4. `deepcopy` arbitrary objects يضر media/opaque identity.
5. shallow copy لا يحل nested mutation.
6. freeze يحتاج serialization layer إضافية.
7. snapshot عند serialization boundary يحقق determinism بتكلفة أقل من
   constructor deep copy.
8. `Message.rich_message` يبقى منفصلاً عن outgoing content.
9. Context وAdapter لهما identity semantics مختلفة بالفعل.

### الاستنتاج المعماري

1. RichContent ليست مبررة لأنها class؛ مبررة لأنها typed boundary تملك
   invariants.
2. snapshot يجب أن يتعلق بلحظة submit، لا بلحظة إنشاء value.
3. أقل API surface ليس دائماً أقل abstraction؛ raw dict أقل surface لكنه
   ينقل التعقيد إلى كل caller وroute.
4. أسماء `*_rich` ليست خطأ تلقائياً، لكنها تصبح duplication غير ضرورية إذا
   قبلنا union على parameter الحالي مع الحفاظ على `text=`.

### اقتراح Titan قبل ADR

المرشح الذي يستحق ADR هو:

```text
RichContent tagged value
    + existing Context verbs with text-compatible union
    + serialization-boundary snapshot
    + raw blocks only inside blocks constructor
    + Telegram-specific adapter methods
```

وليس:

```text
RichMessageInput model
    + constructor structural snapshot
    + ctx.send_rich/reply_rich/edit_rich
    + raw dict dispatch
```

### بوابة الانتقال

الآن فقط يصبح الانتقال إلى ADR مبرراً، لا لأن التصميم “نجا” بالاسم، بل لأن
محاولات إسقاطه أدت إلى تغييرات حقيقية:

```text
RichMessageInput → RichContent
constructor snapshot → serialization-boundary snapshot
Context *_rich → existing verbs + explicit value
Rich buttons خارج keyboard → ليست InlineKeyboard abstraction
```

**الحالة وقت كتابة هذا القسم:** لم يكن ADR أو التنفيذ قد حدثا بعد. أُغلق هذا
المسار لاحقاً بقبول ADR-023 وتنفيذ الدعم الأساسي؛ المرشح أعلاه سجلّ تاريخي
ولا يحل محل القرار المعتمد. كانت الخطوة التالية آنذاك صياغة ADR، وقد نُفذت
لاحقاً بقبول ADR-023.