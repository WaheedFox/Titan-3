# Investigation — Shared / Community Message Links Registry

**الحالة:** Revision تحقيق — لا قرار تنفيذ
**التاريخ:** 2026-09-27  
**المرتبط بـ:** Message Links Protocol (#0)، ADR-008، ADR-018  
**نطاق هذا الملف:** دراسة معمارية فقط. لا يغيّر هذا التحقيق الكود أو العقود أو الاختبارات أو ADRs القائمة.

---

## 1. Executive Summary — Revision

السؤال المركزي في هذه النسخة ليس «هل نضيف مزامنة اختيارية؟»، بل:

> كيف يصبح تسجيل Message Links المشترك جزءاً إلزامياً وتلقائياً من semantics
> لكل Titan runtime ملتزم بالعقد، من دون مطالبة المطوّر بالتصدير أو الرفع يدوياً،
> ومن دون ربط Titan Core مباشرةً بـ GitHub أو تحويله إلى قاعدة بيانات موزعة؟

### النتيجة المنقحة

1. **المشاركة الاختيارية لا تحقق المتطلب.** إذا كان المطوّر يستطيع عدم التفعيل،
   أو عدم الرفع، أو اختيار توقيت النشر، فليس ذلك Shared Message Links Registry
   إلزامياً؛ بل capability إضافية.
2. **الإلزامية المقصودة هي إلزامية التسجيل في مسار Titan، لا وعداً بأن الشبكة
   ستستجيب فوراً.** كل `ctx.send()` و`ctx.reply()` ناجح يجب أن ينتج event محلياً
   durable يدخل مسار النشر المشترك تلقائياً، من دون قرار من المطوّر.
3. **التسجيل الإلزامي والنشر المقبول عن بُعد ليسا الشيء نفسه.** الحالة الصحيحة
   بعد نجاح Telegram وانقطاع registry هي `pending` قابلة للاستئناف، لا إسقاط
   الحدث ولا وصفه بأنه اختياري. أما event الذي لم يُحفظ محلياً فيكون `failed`
   ويكسر invariant المطلوب، حتى لو تعذر التراجع عن رسالة Telegram التي أُرسلت.
4. **النموذج الأقرب للمتطلب هو Mandatory Hybrid:** local durable record +
   mandatory shared-publication pipeline. لا ينتظر `ctx.send()` commit GitHub
   بالضرورة، لكنه لا يسمح بمسار compliant يرسل رسالة ثم يتجاهل shared record.
5. **لا يستطيع Titan Core المحلي وحده فرض الصدق على runtime hostile.** يستطيع
   فرض السلوك على runtime يستخدم نسخة Titan الرسمية كما هي، لكنه لا يستطيع منع
   مالك الجهاز من تعديل الحزمة أو إزالة خطوة النشر أو استدعاء Telegram مباشرة.
   لذلك كلمة mandatory ذات معنى عملي تحتاج boundary ثقة خارجية: relay أو
   publisher موثوق، وهوية bot قابلة للتحقق، وسياسة قبول وتدقيق.
6. **GitHub ليس authority أو enforcement mechanism بمفرده.** يمكنه أن يكون
   publication/storage وaudit/distribution layer خلف publisher موثوق، لكنه لا
   يثبت وحده أن Telegram أرسل الرسالة، ولا يجبر runtime مستقلاً على النشر.
7. **المحتوى ليس mandatory تلقائياً لمجرد أن identity mandatory.** الحد الأدنى
   الإلزامي هو identity projection وprovenance وlifecycle events. Archive أو
   message content أو evidence أو reports طبقات ذات سياسات خصوصية واحتفاظ
   مختلفة، وقد تحتاج موافقة أو مصدر ثقة مختلفاً.
8. `titan_id` الحالي متسلسل داخل store محلي؛ لا يكفي وحده كمفتاح عالمي بين
   runtimes. أي registry مشترك إلزامي يحتاج namespace وbot identity وevent
   idempotency وprovenance قبل أن يدعي verification.
9. **أصغر boundary قابل للدفاع عنه:** عقد Titan Core يضمن إنشاء event/outbox
   محلي بعد نجاح Telegram، وpublisher/relay provider-agnostic يضمن محاولة
   النشر وقابلية الاستئناف، بينما يبقى GitHub backend تفصيلاً خارج Core.
   هذا ليس optional synchronization؛ الاختياري هو backend أو طريقة التوزيع،
   لا أصل التسجيل في runtime compliant.

### ثلاث عبارات يجب عدم خلطها

| المفهوم | معناه | ما يمكن ضمانه |
|---|---|---|
| Optional sharing | المطوّر يقرر هل ينشر ومتى | لا يحقق المتطلب |
| Automatic mandatory registration | كل مسار Titan مؤهل ينشئ event بلا قرار من المطوّر | قابل للفرض في compliant runtime |
| Guaranteed publication | registry موثوق قبلت وحفظت event | يحتاج network/trusted service؛ لا يساوي registration |

هذه النتائج مبنية على source state عند:
`7c43f11627a06c4341bc8aab45ba0fc3ce9b8369`، وعلى مراجعات Task 6 المنشورة
بعده. لا يعني هذا التقرير أن أيّاً من هذه البنية قد نُفذت.

---

## 2. Investigation Scope and Evidence Discipline

### ما تمت قراءته

تم فحص:

- `src/titan/links/manager.py`
- `src/titan/links/identity.py`
- `src/titan/links/store.py`
- `src/titan/links/handler.py`
- `src/titan/links/archive.py`
- `src/titan/ctx.py`
- `src/titan/bot.py`
- `src/titan/update.py`
- `src/titan/privacy/handler.py`
- `docs/decisions/008-message-links-protocol.md`
- `docs/decisions/018-permanent-resource-identity-scope.md`
- `src/titan/timeline/_data.py`
- `ROADMAP.md`
- اختبارات Message Links وprivacy ذات الصلة
- `docs/internal/investigations/message-links-protocol.md`
- سياق Task 5 المقدم كمرفق، لأن تقريراً يحمل اسم Task 5 لم يوجد في المسارات
  المتعقبة داخل المستودع

تم أيضاً فحص convention التحقيقات. الملفات الحالية تعيش في:
`docs/internal/investigations/`، ولذلك أُنشئ هذا الملف هناك.

### تصنيفات الأدلة

- **confirmed by code:** سلوك ظاهر مباشرة في الكود الحالي.
- **confirmed by tests:** سلوك تغطيه اختبارات موجودة.
- **documented contract:** ما تقرره ADR أو وثائق المشروع، ولو لم يطابق التنفيذ
  تماماً.
- **external constraint:** حقيقة موثقة في وثائق GitHub الرسمية.
- **inference:** نتيجة معمارية مستخلصة من الأدلة، وليست سلوكاً منفذاً.
- **open question:** نقطة لا يحسمها HEAD الحالي أو المصادر المتاحة.

### حدود التحقق التنفيذي

لم تُشغّل الاختبارات في هذه البيئة لأن الأمر `pytest` غير مثبت، كما أن تشغيل
probe بسيط اصطدم بغياب `aiohttp`. لم يتم تثبيت اعتماديات أو تعديل البيئة.
لذلك يميز هذا التقرير صراحةً بين قراءة الاختبارات وبين نتيجة تشغيلها.

---

## 3. Existing Message Links Architecture

### 3.1 تهيئة `LinksManager`

**confirmed by code:** `Titan.__init__()` ينشئ `LinksManager` ويعرضه عبر
`bot.links`. كما يسجل `/link` كأمر محجوز خارج `bot.commands` العادية.

المسار الافتراضي يحسب عند إنشاء المدير:

```text
<os.getcwd()>/<.titan>/links.db
```

`LinksManager` ينشئ كائن `SqliteMessageStore` فقط. فتح SQLite وإنشاء المجلد
والجدول يحدث lazy عند أول عملية تحتاج connection.

**confirmed by tests:** الاختبارات تستخدم `SqliteMessageStore(":memory:")`
في معظم fixtures، وتختبر أيضاً مسارات `links.db` و`nested/links.db` و
`.titan/links.db`. الإصلاح في `7c43f11` يحرس حالة directory الفارغ، ولذلك
يعمل المسار النسبي `links.db`.

**documented contract:** ADR-008 يعلن SQLite و`os.getcwd()` وواجهة
`set_data_dir()`. بعض صياغات ADR-018 تقول إن `.titan/links.db` تُنشأ
تلقائياً مع Identity Layer؛ التنفيذ الأدق هو أنها تُنشأ عند أول storage
operation. هذا drift توثيقي قائم، لا تغييراً أنشأه هذا التحقيق.

### 3.2 Message Identity

`TitanMessageIdentity` الحالية تحتوي على:

- `titan_id`
- `bot_username`
- `chat_id`
- `telegram_message_id`
- `deleted`

**confirmed by code:** لا تحتوي Identity Layer على نص الرسالة أو `sent_at` أو
`chat_type`. هذه الحقول موجودة فقط في جدول Archive الاختياري.

**confirmed by tests:** `titan_id` متسلسل في store الواحد، ولا يعاد استخدامه
بعد `mark_deleted()`. يوجد unique constraint محلي على:
`(chat_id, telegram_message_id)`.

**architectural implication:** uniqueness الحالية محلية للـ SQLite store.
لا يوجد في identity model الحالي bot numeric ID أو publisher ID أو runtime
namespace يثبت uniqueness على مستوى عدة قواعد أو عدة ناشرين.

### 3.3 التسجيل عبر `ctx.send()` و`ctx.reply()`

المسار الحالي هو:

```text
Telegram send succeeds
        ↓
extract result.message_id
        ↓
read bot username from _api._me
        ↓
LinksManager.register_sent_message()
        ↓
local MessageStore.save_identity()
        ↓
optional Archive save
```

**confirmed by code:** التسجيل يحدث بعد عودة send الناجحة، وليس قبلها.

**confirmed by code:** إذا لم توجد `message_id` أو `bot_username`، يتم تخطي
التسجيل. وإذا فشل local store، يسجل `ctx` تحذيراً ويعيد نجاح الإرسال دون
رفع فشل التخزين إلى caller.

**confirmed by tests:** الاختبارات تغطي نجاح `ctx.send()` و`ctx.reply()`،
وفشل Telegram send، وbest-effort registration، ورسائل rich content. التسجيل
التلقائي لا يمر عبر raw `bot.telegram` أو استدعاء API مباشر.

**documented contract:** ADR-008 وADR-018 يقدمان identity كجزء دائم من Titan
بعد الإرسال عبر هذين المسارين. التنفيذ يضيف قيداً عملياً: الضمان مشروط
بتوفر metadata المطلوبة وبنجاح التخزين المحلي؛ لا يوقف Telegram عند غيابها.

### 3.4 `/link`

`/link`:

1. يتطلب `reply_to_message`.
2. يتحقق من أن الرسالة الأصلية من bot.
3. يبحث محلياً باستخدام `(chat_id, telegram_message_id)`.
4. يعيد `TitanMessageAddress` إذا وجدت identity.
5. لا ينشئ identity جديدة.

**confirmed by code and tests:** `/link` lookup-only. الرسائل القديمة أو
الرسائل غير المسجلة لا تحصل على identity retroactively. lookup الفاشل بسبب
storage يعيد رسالة خطأ للمستخدم.

هذا مهم للسجل المشترك: إدخال remote lookup في `/link` سيغيّر latency وfailure
semantics الحالية، وليس مجرد إضافة مصدر بيانات آخر.

### 3.5 Archive Layer

Archive opt-in وتعمل في v1 مع `SqliteMessageStore` فقط. جدولها يحوي:

- `titan_id`
- `text`
- `chat_type`
- `sent_at`

**confirmed by code and tests:** عند فشل archive save بعد نجاح identity، يبقى
الإرسال ناجحاً وتُسجّل warning. لا توجد archive تلقائية لكل runtime إلا إذا
فعّلها المطور.

### 3.6 `mark_deleted()` و`/forgetme`

`mark_deleted(titan_id)` يغير `deleted` إلى true ولا يحذف row أو address ولا
يعيد استخدام الرقم.

`/forgetme` يمحو User Data المسجلة في `UserDataRegistry`. `LinksManager` ليس
جزءاً من هذا registry، وADR-018 يصنف Message Identity كـ Permanent Resource
Identity لا User Data.

**confirmed by code, tests, and ADR-018:** `/forgetme` لا يمحو Message Links
الحالية. إذا أصبحت identity عامة مستقبلاً، فهذه النقطة ستصبح contract/privacy
قراراً أكثر حساسية، لا تفصيلاً تنفيذياً.

### 3.7 النتيجة الحالية

السجل الحالي هو:

```text
Local Registry
  one SQLite store per runtime/path
  local reads and writes
  no automatic network publication
  local /link resolver
```

لا يوجد في HEAD backend GitHub أو sync queue أو remote fallback.

---

## 4. Desired Shared Registry Model

### Local Registry

السجل المحلي هو قاعدة مستقلة لكل runtime. يملك:

- التسجيل التشغيلي بعد نجاح Telegram.
- lookup سريعاً لمسار `/link`.
- durability بحسب filesystem.
- identity وarchive بحسب إعدادات runtime.

### Shared Registry

السجل المشترك هو مصدر يمكن لعدة runtimes الوصول إليه. لكي يكون مفيداً يجب
أن يجيب على أسئلة مثل:

- هل يوجد claim عن رسالة بعنوان معين؟
- من publisher الذي نشره؟
- متى نُشر claim؟
- هل هو identity فقط أم archive أم report؟
- هل البيانات current أم stale؟
- هل يمكن الوثوق في source؟

الوصول المشترك وحده لا يساوي truth مشتركاً. يلزم تعريف للهوية العالمية
والـ provenance وسياسة التعديل والحذف.

### Community/Public Registry

السجل المجتمعي يخدم أدوات Titan الأوسع وقد يحتوي بيانات عامة، لكنه لا يجعل
كل ما هو موجود محلياً صالحاً للنشر. **إلزامية registration لا تعني إلزامية
نشر كل byte من البيانات.** يجب أن يكون الحد الأدنى المنشور معروفاً في العقد،
بينما تبقى public visibility لمحتوى الرسالة وarchive وreports قراراً مستقلاً.
لا يجوز أن تتحول سياسة الخصوصية إلى opt-out يوقف identity نفسها.

### أقل record مفيد مبدئياً

لا يوصي هذا التحقيق بمخطط نهائي، لكنه يحدد الحد الأدنى الذي يجب حسمه قبل
أي تصميم:

- public registry key أو namespace واضح.
- bot identity قابلة للتحقق، لا username فقط.
- Titan identity reference.
- Telegram reference بالقدر الضروري فقط.
- publisher/provenance.
- observed/published time إن لزم.
- lifecycle state أو tombstone.
- schema/version.

هذه ليست دعوة لإضافة الحقول الآن؛ بل قائمة بأسئلة لا يحلها نقل الصفوف الحالية
كما هي. `chat_id` وarchive text وmetadata التشغيلية لا ينبغي افتراض نشرها.

### Mandatory record مقابل mandatory content

المتطلب الإلزامي الذي يمكن دراسته هنا هو أن كل event مؤهل لمسار Message Identity
ينتج projection مشتركة دنيا، لا أن يصبح كل محتوى أرسله bot عاماً. الحد الأدنى
المحتمل هو:

- global bot/runtime identity أو namespace قابل للتحقق.
- Titan identity reference.
- Telegram reference بالقدر الذي يسمح بالربط دون كشف غير لازم.
- event type وschema version.
- publisher provenance ووقت القبول أو الملاحظة.
- lifecycle state، بما فيها tombstone عند deletion.

`text` وrich content و`chat_id` الكامل وmetadata الخاصة بالمحادثة وevidence
الموسعة ليست نتيجة تلقائية من كلمة registration. إذا قرر عقد لاحق أن content
جزء من shared record، فلابد أن يحدد مصدره (payload الذي مر عبر `ctx` أو fetch
موثوق بعد الإرسال)، وحدود privacy والاحتفاظ والحذف والحجم. لا يحسم هذا التحقيق
أن كل محتوى يجب أن يصبح public.

---

## 5. GitHub Feasibility

المراجع الخارجية في هذا القسم هي وثائق GitHub الرسمية، ومنها:

- [REST API — repository contents](https://docs.github.com/en/rest/repos/contents)
- [REST API — Git trees](https://docs.github.com/en/rest/git/trees)
- [REST API — Git refs](https://docs.github.com/en/rest/git/refs)
- [REST API — pull requests](https://docs.github.com/en/rest/pulls/pulls)
- [REST API — authentication](https://docs.github.com/en/rest/using-the-rest-api/authenticating-to-the-rest-api)
- [REST API — rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
- [GitHub repository limits](https://docs.github.com/en/repositories/creating-and-managing-repositories/repository-limits)
- [Large files on GitHub](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
- [Controlling `GITHUB_TOKEN` permissions](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/controlling-permissions-for-github_token)
- [GitHub Actions security hardening](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions)

### 5.1 Repository files as storage

**external constraint:** GitHub repository files are Git objects addressed
through commits and refs. The Contents API can read, create, replace, and
delete Base64-encoded content. It is a file/commit interface, not a row-level
query engine.

قيود مهمة موثقة في Contents API:

- directory response لها حد 1,000 ملف؛ الاسترجاع الأوسع يحتاج Git Trees API.
- الملف حتى 1 MB يدعم كل ميزات endpoint.
- بين 1 و100 MB تقتصر بعض الميزات على raw/object media types.
- ما فوق 100 MB غير مدعوم عبر Contents API.
- تحديث ملف موجود يتطلب SHA الحالي للملف.
- توضح الوثائق أن تحديثات الملف والحذف المتزامن قد تتعارض ويجب تنفيذها
  serially.

**inference:** سجل record-per-file سيصطدم بعدد الملفات، أما ملف JSON واحد
فسيجعل كل الكتابات المتزامنة تتصارع على نفس blob ويجعل القراءة/الـ diff
والـ clone أغلى مع النمو. Sharding قد يقلل conflict surface لكنه لا يصنع
فهارس أو queries أو transactions.

### 5.2 Git data and commits

يمكن بناء commits وtrees وتحديث refs عبر Git Data API، لكن ذلك لا يحول Git
إلى قاعدة معاملات:

- commit يمكن أن يمثل مجموعة تغييرات متسقة داخل commit واحد.
- تحديث branch/ref ليس بديلاً عن transaction query/update متعددة الكيانات.
- لا توجد semantics حالية في Titan تمنح كل publisher ownership لرقم
  `titan_id` العالمي.
- branch history مفيدة للتدقيق وقابلية الرجوع، لكنها لا تثبت صحة Telegram
  claim.

**external constraint:** تحديث ref وعمليات Git Data موثقة كعمليات Git
على refs/objects، لا كـ compare-and-swap عام للسجل. لذلك يجب أن يعتمد أي
writer على ref/sha conflict handling الموثق، لا على افتراض أن آخر write
سيُدمج تلقائياً.

### 5.3 REST API as application-facing service

إذا استُخدمت GitHub API مباشرة في runtime، تصبح كل عملية `/link` أو sync
تابعة لـ:

- authentication وصلاحيات repository.
- latency الشبكة وtimeouts.
- rate limits وsecondary abuse/rate limiting.
- status codes وتغيرات الخدمة.
- حجم payload وطريقة pagination.
- تعارض SHA وإعادة القراءة قبل retry.

**external constraint:** GitHub يوثق rate-limit headers وحدود primary وsecondary
ويطلب التعامل مع limits بدلاً من تجاهلها. لا يعتمد هذا التحقيق على رقم ثابت
لأن الحد يختلف بحسب نوع authentication والendpoint والسياسة الحالية.

**inference:** API مناسبة لقراءات bounded أو publication worker محدود، لا
لمسار `ctx.send()` الحساس للزمن ولا لـ `/link` الذي يجب أن يبقى سريعاً ومحلياً
في العقد الحالي. هذا لا يلغي mandatory publication؛ بل يعني أن الإلزامية يجب
أن تُنفذ عبر durable acceptance محلي ثم delivery قابلة للاستئناف، لا عبر جعل
كل send ينتظر HTTP request.

### 5.4 Mandatory publication and the GitHub boundary

إذا كان كل Titan bot ملتزماً بالعقد يجب أن يسجل تلقائياً، فهناك مستويان يجب
فصلهما:

1. **Runtime obligation:** بعد نجاح Telegram، ينشئ runtime eventاً محلياً
   durable ويضعه في publication pipeline بلا opt-in أو developer action.
2. **Remote acceptance:** publisher أو relay يرسل event إلى registry ويستلم
   قبولاً قابلاً للتحقق. قد يحدث لاحقاً بسبب offline أو rate limit أو conflict.

GitHub لا يوفر وحده المستوى الأول؛ فهو لا يرى code path داخل runtime ولا يجبر
صاحب bot على استدعاء API. كما لا يوفر المستوى الثاني كـ application contract
مناسب دون client/relay يعرّف idempotency وretry وconflict وschema. لذلك:

- direct GitHub publishing يجعل token والاعتماد والـ API جزءاً من كل runtime.
- authenticated relay يفصل Core عن GitHub ويضع policy والـ credentials في
  جهة مركزية، لكنه يصبح boundary ثقة جديدة.
- GitHub App أو installation token يحسن إدارة الصلاحيات، لكنه لا يمنع مالك
  runtime من إزالة client أو تزوير event قبل إرساله.
- GitHub Actions يمكنها التحقق والفهرسة بعد commit، لكنها لا تفرض أن كل
  `ctx.send()` أنتج commit ولا تجعل workflow transaction مع Telegram.

**النتيجة:** GitHub يمكن أن يكون storage/publication layer، لا authority
تثبت أن event صدر من Titan runtime سليم. كلمة mandatory تحتاج عقداً في Titan
وpublisher/relay يقبل events، وليس مجرد repository public.

### 5.5 Raw content

Raw content مفيد لتوزيع snapshot أو قراءة record منشور، لكنه ليس query service:

- لا يطبق identity authorization على معنى البيانات.
- لا يقدم transaction مع Telegram.
- لا يثبت أن محتوى الملف صحيح أو حديث بالنسبة لruntime.
- لا يحل indexing أو namespace collision.

يمكن أن يكون raw commit-pinned content جزءاً من distribution layer، لا بديلاً
عن registry semantics.

### 5.6 Pull requests

Pull request workflow يضيف review وchecks وmoderation وaudit مفيدة لسجل
مجتمعي، لكنه يجعل الكتابة:

- غير فورية.
- قابلة للرفض أو التأخير.
- مرتبطة بفرع وmerge policy.
- غير مناسبة لنجاح `ctx.send()` أو لإجابة `/link` اللحظية.

**inference:** PR-based submission مناسب لإدخال claims عامة أو تغييرات
مجتمعية تحتاج مراجعة، وليس لتسجيل كل رسالة runtime على الخط الساخن.

### 5.7 GitHub Actions

Actions يمكنها validate أو normalize أو publish أو build an index بعد push/PR.
لكنها automation غير متزامنة، لا transaction مشتركة مع Telegram.

**external constraint:** GitHub يحذر من checkout وتشغيل workflows المميزة مع
مدخلات PR غير موثوقة، ويوصي بتقييد `GITHUB_TOKEN` إلى أقل permissions ممكنة.
أي workflow يملك write access أو secrets يزيد أثر token compromise وscript
injection.

**inference:** Actions مناسبة كطبقة تحقق/فهرسة/حماية حول registry، وليست
مكاناً لجعل `ctx.send()` ينتظر commit أو نجاح workflow.

### 5.8 Public مقابل private repository

**Public:**

- يتيح community read access وclone وraw access بسهولة.
- يجعل commits وhistory وPR metadata جزءاً من surface العام.
- لا يجعل chat IDs أو content أو relationships آمنة للنشر.
- delete لاحقاً لا يضمن اختفاء القيمة من clones أو forks أو history.

**Private:**

- يحسن التحكم في الوصول، لكنه يتطلب identity/authentication وصلاحيات لكل
  قارئ أو publisher.
- لا يحقق registry مجتمعياً عاماً دون relay أو خدمة وصول.
- لا يلغي مخاطر التسريب من token أو workflow أو collaborator.

**conclusion:** visibility قرار data governance، لا مجرد اختيار backend.

---

## 6. Architectural Options

### A — Local SQLite

**Semantics:** current local identity/archive semantics. `/link` local lookup.  
**Consistency:** strong enough داخل connection/lock المحلي؛ لا consistency بين
runtimes.  
**Durability:** filesystem-dependent.  
**Latency:** منخفضة ولا تحتاج شبكة.  
**Concurrency:** محكومة بالـ local SQLite/lock، لا multi-host registry.  
**Failure handling:** فشل التسجيل بعد Telegram best-effort؛ `/link` يفشل lookup
إذا فشل storage.  
**Offline:** يعمل ما دام filesystem محلياً.  
**Security/privacy:** البيانات لا تُرسل تلقائياً؛ الحماية filesystem.  
**Scalability:** مناسبة لنطاق runtime واحد، لا community-wide queries.  
**Titan compatibility:** الأعلى مع التنفيذ الحالي، لكنه لا يحقق shared registry
ولا automatic community publication.
**Migration:** لا migration مطلوبة.  
**Limit:** لا shared verification أو community discovery، ولا يستطيع المجتمع
التحقق من record إذا بقي كل شيء محلياً.

### B — GitHub-backed Shared Registry

**Semantics:** claims محفوظة كملفات/commits/branches/PRs، وليست rows ذات
transaction semantics.  
**Consistency:** eventual بالنسبة للقراء والـ workflows؛ conflicts طبيعية عند
multiple writers.  
**Durability:** Git history قوية كحفظ source، لكن لا تعني truth ولا recovery
تلقائي من كل public clone.  
**Latency:** شبكة + API + commit وربما PR/Action.  
**Concurrency:** تحتاج serialization أو conflict retries؛ ملف واحد أو shard
قد يصبح hot spot.  
**Failure handling:** انقطاع API أو limit أو conflict يحدث بعد نجاح Telegram؛
لا ينبغي أن يُعاد فشله إلى send إذا كان event المحلي قد قُبل durable، لكنه
يجب أن يبقى `pending` أو `failed` مرئياً ضمن mandatory contract، لا أن يتحول
إلى omission اختياري.
**Offline:** يحتاج queue محلية أو فقد sync؛ لا يمكن افتراض الكتابة أثناء
offline.  
**Security/privacy:** public history وtokens وworkflow خطر إضافي.  
**Scalability:** repository/file/API limits وغياب query/index semantics تجعل
الملايين records غير مناسبة كملفات خام.  
**Titan compatibility:** لا يحقق mandatory publication إذا كان direct client
اختيارياً أو يستطيع المطوّر حذفه. ويمكنه أن يكون backend للنشر الإلزامي فقط
خلف relay/contract موثوق، لا required GitHub backend داخل Core.
**Migration:** backfill صعب لأن local stores قد تملك namespaces متصادمة
والـ archive قد يكون حساساً.

### C — Mandatory Hybrid: Local Durable Store + Mandatory Shared Publication

**Semantics:** local store يثبت identity ومسار `/link`; كل identity event
المؤهل يُسجل تلقائياً في durable outbox أو equivalent، ويُسلّم إلى shared
publisher بلا opt-in. shared acceptance قد تكون asynchronous، لكنها ليست
اختيارية في عقد runtime compliant.
**Consistency:** local authoritative للتشغيل؛ shared eventually consistent
مع state صريحة `accepted/pending/failed/stale`. غياب السجل لا يعني عدم وجود
الرسالة، لكنه يعني أن invariant النشر لم يصل إلى `accepted` بعد.
**Durability:** local record وoutbox يجب أن ينجوا من restart/offline. إذا
فشل حفظهما، فهذه `failed` contract state وليست نجاحاً كاملاً.
**Latency:** لا يضيف remote dependency إلى send أو local `/link` إذا كان
القبول المحلي هو boundary المتزامن.
**Concurrency:** publisher/relay يعالج duplicate/conflict، مع idempotency
key وترتيب لا يتجاوز ما يستطيع registry ضمانه.
**Failure handling:** Telegram success + local durable event + remote failure
هي `pending`، ويجب أن تبقى قابلة للرصد والاستئناف. لا يعاد إرسال Telegram
لمجرد فشل publication.
**Offline:** لا يوقف offline الإرسال المحلي، لكنه يوقف `accepted` remote حتى
يستأنف outbox. Eventual publication مضمونة فقط مع outbox durable وpublisher
عامل وسياسة retry قابلة للحياة؛ وإلا لا يجوز ادعاء الضمان.
**Security/privacy:** mandatory identity projection صغيرة، بينما archive و
content وevidence وreports لها policies منفصلة.
**Scalability:** أفضل من GitHub-only، لكن GitHub يبقى محدوداً كـ registry
عالي الكتابة؛ relay أو service أخرى قد تكون لازمة.
**Titan compatibility:** يحقق المتطلب إذا كان contract في Titan Core إلزامياً
وكان publisher boundary موثوقاً، مع بقاء backend provider-agnostic.
**Migration:** additive من local فقط إذا حُسم global identity وbackfill
provenance؛ لا يجوز اعتبار كل local row verified تاريخياً.

### D — Shared Registry منفصل

**Semantics:** خدمة مصممة للـ reads/writes/query/idempotency/authentication.
يمكنها تعريف consistency وtombstones وindexes صراحةً.  
**Consistency:** قابلة للتصميم بحسب الحاجة، وليست مفروضة على Git.  
**Durability/latency:** يمكن ضبطهما كخدمة، مع تكلفة تشغيلية حقيقية.  
**Concurrency:** transactions أو conditional writes أو idempotency keys
يمكن أن تكون جزءاً من contract.  
**Failure/offline:** يحتاج client cache/outbox وعقد outage واضحاً.  
**Security/privacy:** يمكن فصل public read عن authenticated publish وعن
moderation.  
**Scalability:** أفضل عند كثرة records وqueries، لكنها ليست مجانية أو بسيطة.  
**Titan compatibility:** Core لا يحتاج معرفة المزود، لكن registration event
يصبح contract إلزامياً لا capability يختارها المطوّر. الخدمة أو relay خارجية
تتعامل مع delivery والهوية والـ policy.
**Migration:** تحتاج schema/versioning وخطة import من SQLite.  
**Limit:** تضيف infrastructure كاملة قبل إثبات حجم الاستخدام والثقة المطلوبة.

### المقارنة المعمارية

لا يوجد ranking واحد مستقل عن semantics، لكن mandatory requirement يستبعد
الاختيارية كحل نهائي:

- إذا كان المطلوب `/link` محلياً سريعاً: **A** كافية.
- **B** لا تكفي وحدها؛ direct GitHub لا يفرض publication ولا يقدم trust.
- إذا كان المطلوب shared publication إلزامية دون جعل Telegram ينتظر GitHub:
  **C** هي semantics المطلوبة، مع publisher/relay.
- إذا كان المطلوب خدمة استعلام وكتابة عالمية ذات SLA وconcurrency وenforcement:
  **D** هي الفئة الصحيحة، ولو كانت أكبر من حاجة Titan الحالية.

GitHub لا يصبح **D** لمجرد أن لديه API.

---

## 7. Runtime / Telegram Send Semantics

### ما الذي يعنيه mandatory؟

المعنى المقترح ليس أن `ctx.send()` يجب أن ينتظر commit GitHub في كل مرة. المعنى
هو أن نجاح مسار Titan المؤهل لا يخرج من lifecycle قبل أن ينشئ event محلياً
durable يدخل publication pipeline تلقائياً. لذلك يجب أن:

1. ينتظر `ctx.send()` أو `ctx.reply()` نجاح Telegram أولاً.
2. لا ينشئ identity أو shared claim قبل نجاح Telegram.
3. يحفظ identity وmandatory publication event/outbox عند boundary محلي durable.
4. يعيد نتيجة Telegram دون إعادة إرسالها بسبب network failure في registry.
5. يترك event في `pending` حتى يقبله shared publisher، أو يعلن `failed` إذا
   تعذر حتى حفظ الحد الأدنى المحلي أو انتهت سياسة الاسترداد.

هذا يفرق بين **mandatory obligation** و**synchronous remote availability**.
جعل GitHub synchronous قد يحقق remote acceptance في بعض الحالات، لكنه يربط
delivery بـ network/rate limits/conflicts. جعل التسجيل المحلي mandatory مع
outbox يحافظ على delivery latency، بشرط ألا يُسمى event المنشور فعلاً إلا بعد
قبول publisher.

### مستويات الضمان: من best effort إلى guaranteed delivery

لا يكفي وصف النشر بأنه asynchronous. يجب تحديد ما الذي يبقى بعد كل فشل:

| المصطلح | المعنى الدقيق | هل يحقق mandatory contract؟ |
|---|---|---|
| **best effort** | محاولة واحدة أو تسجيل غير durable؛ قد يضيع الحدث عند crash | لا |
| **retryable** | فشل معروف مع event قابل لإعادة المحاولة | جزء من recovery، وليس ضماناً وحده |
| **durable pending** | event محفوظ في boundary محلي durable مع state وidempotency key | نعم كالتزام محلي، قبل remote acceptance |
| **acknowledged** | relay/registry أعاد قبولاً idempotent قابلاً للتحقق | نعم؛ هذه حالة `accepted` |
| **eventual publication** | وعد بالوصول لاحقاً بشرط بقاء outbox سليماً وعودة publisher والـ registry | ضمان مشروط، لا فوري |
| **guaranteed delivery** | لا فقدان حتى القبول البعيد، تحت assumptions محددة ومعلنة | لا يمكن إطلاقه بلا تحديد durability/availability والحدود |
| **failed permanently** | validation أو policy أو فساد يمنع القبول بعد recovery policy | ليس نجاحاً؛ يجب أن يكون مرئياً وقابلاً للتدقيق |

لذلك لا يجوز تسمية `pending` نجاحاً كاملاً، ولا تسمية best effort
“eventual publication”. الحد الأدنى المنطقي للمتطلب هو: بعد نجاح Telegram، إما
أن يوجد `durable pending` أو `accepted`، أو توجد `failed` صريحة تكشف أن
invariant لم يتحقق. الصمت أو إسقاط event غير مقبولين كنموذج mandatory.

### هل يجب أن تكون identity وpublication event في transaction واحدة؟

**الاستنتاج المعماري:** نعم، يجب أن تشترك identity المحلية وmandatory
publication event في نفس local durability boundary، ويفضل transaction واحدة
في store يدعم atomic commit. السبب هو منع هذه النوافذ:

```text
identity committed → process crash → no publication event
publication event committed → process crash → no identity reference
```

الـ remote write نفسه لا يمكن أن يكون جزءاً من transaction مع Telegram أو
SQLite، لذلك يبقى خارج boundary كـ `pending` ثم `accepted`. أما identity و
outbox/event ففصلهما يترك mandatory contract غير قابل للإثبات بعد crash.

هذا لا يصف سلوكاً موجوداً في HEAD: الكود الحالي يحفظ identity محلياً ثم يعامل
فشل التسجيل كـ best effort، ولا يملك outbox. لذلك يلزم contract/implementation
قرار لاحق يحدد:

- ما الحد الأدنى الذي يُحفظ في transaction.
- هل storage failure يجعل caller يرى `failed` أو status قابلاً للرصد مع بقاء
  Telegram success.
- كيف تُستعاد identity موجودة بلا event، أو event بلا identity، دون اختراع
  claim أو إعادة إرسال Telegram.

لا يمكن rollback لرسالة Telegram بعد نجاحها، ولا يمكن تحقيق exactly-once بين
Telegram وlocal database بمجرد transaction محلية. الممكن هو invariant أقوى
داخل local boundary: كل send ناجح **يُقبل محلياً** مع identity وevent معاً،
ثم تتم remote delivery بشكل idempotent.

### المسارات المشمولة وغير المشمولة

| المسار | المعنى المطلوب |
|---|---|
| `ctx.send()` الناجح | mandatory identity event + shared publication event |
| `ctx.reply()` الناجح | نفس semantics؛ reply ليس استثناءً |
| Telegram send الفاشل | لا identity ولا shared record |
| `edit` | lifecycle event مرتبط بـ identity موجودة؛ لا ينشئ identity جديدة، ونشر المحتوى أو النسخة المعدلة يحتاج policy مستقلة |
| `delete` / `mark_deleted()` | mandatory tombstone إذا كانت identity منشورة أو pending؛ لا يمحو التاريخ تلقائياً |
| `bot.telegram` المباشر | خارج contract الحالي؛ لا يمكن نسبته إلى Titan تلقائياً دون gateway/adapter مستقبلي |
| مسار send مخصص لا يمر عبر `ctx` | خارج ضمان العقد الحالي، ويجب أن يعلن ذلك بوضوح |

إدخال direct `bot.telegram` في هذا الضمان من دون اعتراض مركزي سيخلق ادعاءً
زائفاً بأن Titan يرى كل رسائل bot. boundary الصحيحة هي compliant Titan paths،
لا كل استخدام ممكن لرمز Telegram.

### حدود `bot.telegram` ووضوح completeness

العمليات الداخلة في Shared Message Links contract هي العمليات التي يعرّفها
Titan كـ execution point للهوية: `ctx.send()` و`ctx.reply()` الناجحتان، ومعهما
lifecycle operations المرتبطة بهوية أنشأها هذا المسار إذا حُسم ذلك في العقد.

أما `bot.telegram.send_message()` والاستدعاءات المباشرة الأخرى فهي bypass
مقصود للطبقة الحالية، ولا تنشئ Message Identity تلقائياً في HEAD. لا ينبغي
إدخالها قسراً في هذه revision أو الادعاء أنها مشمولة. هذا متوافق مع الفصل
الحالي بين `ctx` وraw Telegram API، لكنه يخلق خطراً حقيقياً من سوء فهم
completeness:

- Shared Registry يصف **Titan-managed message events**، لا كل نشاط bot على
  Telegram.
- report أو inspector لا يجوز أن يفسر غياب direct-API record كدليل أن الرسالة
  لم تحدث.
- يجب أن تقول الوثائق المستقبلية بوضوح إن mandatory coverage محدودة بـ
  `ctx.send()`/`ctx.reply()`، ما لم يصدر contract مستقل يضيف gateway أو
  instrumentation للمسارات الأخرى.

### الحالات الأساسية

| الحالة | النتيجة المعمارية المطلوبة |
|---|---|
| Telegram يفشل | لا identity محلية ولا shared identity |
| Telegram ينجح، local identity أو outbox يفشل | الرسالة لا يمكن rollback لها؛ حالة `failed` تكشف أن mandatory invariant لم يتحقق، وتحتاج alert/recovery، لا إعادة إرسال أعمى |
| Telegram وlocal/outbox ينجحان، GitHub يفشل | الرسالة وlocal `/link` ناجحتان؛ shared publication إلزامية لكن حالتها `pending`، ولا تُفقد ولا تُسمى accepted |
| Telegram وlocal وGitHub ينجحون | shared claim `accepted/published`؛ لكنه لا يصبح truth موثقاً دون trust/provenance model |
| retry بعد timeout | لا ينشئ duplicate؛ يحتاج key/idempotency أو deduplication |
| restart أثناء sync | يستأنف pending work إذا كان هناك durable outbox؛ وإلا يصبح الالتزام mandatory غير قابل للضمان |
| offline period | يستمر local إن كان filesystem متاحاً؛ shared event يبقى pending حتى يعود publisher |
| stale shared read | يعاد `unknown/stale` semantics، لا `not found` القاطعة |

### Duplicate submission

المسار المحلي الحالي يستخدم `INSERT` مع unique `(chat_id, telegram_message_id)`.
إعادة `save_identity()` لنفس pair قد ترفع خطأ constraint، بينما `ctx` يعامل
فشل registration كـ best-effort. هذا ليس idempotency contract عالمياً.

**inference:** أي shared publisher يحتاج مفتاحاً idempotent يعرف ما إذا كان
الclaim نفسه أعيد إرساله، ويفرق بين:

- retry لنفس event.
- claim جديد لنفس Telegram message.
- claim من runtime آخر.
- conflict بين publishers.

لا يحسم `titan_id` الحالي هذه الحالات لأنه local sequence.

### Synchronous أم asynchronous أم opportunistic؟

- **Synchronous remote write:** يحقق أقوى remote acknowledgment، لكنه يجعل
  network availability جزءاً من send أو يضطر إلى failure coupling. لا يلزم
  اختياره لكي تكون registration mandatory.
- **Asynchronous durable publication:** النموذج الذي يطابق المطلوب بأقل
  تلويث لمسار الإرسال: local acceptance synchronous، وremote acceptance
  eventual. يحتاج outbox/retry/dead-letter/observability كعقود مستقبلية.
- **Opportunistic sync:** لا يحقق mandatory publication لأنه يسمح بضياع event
  بعد restart أو تجاهل failure. يجوز كتحسين transport فقط بعد وجود durable
  obligation، لا كنموذج registry.

هذا تحقيق semantics، وليس قرار implementation أو إضافة queue. كلمة outbox هنا
تصف invariant مطلوباً، ولا تعني أن هذا التحقيق ينفذ queue.

---

## 8. Data Model and Data Boundaries

### Identity

تثبت claim محدوداً: bot/runtime يقول إن message reference ارتبطت بـ Titan
identity بعد send ناجح محلياً. لا تثبت وحدها أن claim صادق أمام طرف ثالث.

### Minimum lifecycle semantics: identity, current state, evidence

يجب ألا يتحول Mandatory Shared Registry تلقائياً إلى نظام versioning كامل:

- **Message Identity:** event إنشاء ثابت يربط الرسالة بـ `titan_id` أو global
  reference بعد نجاح `ctx`، ولا يُعاد استخدامه.
- **Current Message State:** حالة حالية مثل `active` أو `deleted`. `edit` لا
  ينشئ identity جديدة؛ ويمكن أن يحدّث current-state projection فقط إذا قرر
  contract ذلك. `mark_deleted()` ينشر tombstone يحافظ على identity ولا يعني
  محو كل historical data.
- **Historical Evidence:** archive أو snapshot أو signature أو report يثبت
  شيئاً إضافياً. لا يلزم إدخاله في canonical identity event، ولا يجوز أن
  يُستنتج من وجود identity وحده.

أقل semantics لازمة للهدف هي mandatory create event وtombstone lifecycle
للـ identity المنشورة أو pending. أما edit/content history فهو policy منفصلة:
قد يُسجل خارج canonical registry، أو يُمثل current state فقط، من دون فرض
سجل versioning عام لكل تعديل.

### Metadata

`bot_username`, `chat_id`, `telegram_message_id`, timestamps وrelationships
قد تسمح بربط نشاط bot وchat ووقت. بعضها identity metadata، وبعضها potentially
sensitive، حتى إذا كانت الرسالة أو الرابط public.

### Public URL

`TitanMessageAddress` يحوي bot username و`titan_id`. نشره أسهل من نشر archive،
لكن الرابط لا يساوي إذناً لعرض content ولا يثبت provenance.

### Content / Archive

Archive قد يحتوي النص وchat type ووقت الإرسال. وجوده في SQLite المحلية لا يجعل
نشره في community registry مشروعاً. يجب أن يبقى archive طبقة مستقلة مع
consent/visibility policy.

### Evidence

Evidence قد يتضمن snapshot أو signature أو response metadata أو source
attestation. هو ليس identity ولا archive بالضرورة. إدخاله في registry يحتاج
provenance وretention ومراجعة.

### Report

Report هو claim أو بلاغ من جهة؛ لا ينبغي دمجه في canonical identity row.
الـ registry قد يربط report بـ identity، لكنه لا يصبح moderation platform
تلقائياً.

### boundary المقترح

أكثر boundary تحفظاً:

```text
Canonical identity projection
        ≠ local archive
        ≠ evidence
        ≠ community report
```

الربط بين هذه الطبقات يمكن أن يحدث بأدوات مستقلة، لكن تخزينها في GitHub
directory واحد لا يلغي اختلاف trust والخصوصية ودورة الحياة.

---

## 9. Security and Privacy

### تصنيف عملي

**Public candidate، بعد قرار صريح:**

- public Titan address.
- publisher identity أو signed provenance إذا كان نشرها مقصوداً.
- lifecycle state عامة عند الحاجة.

**Identity metadata:**

- bot username.
- Titan ID.
- Telegram message ID.
- deleted state.
- timestamp المرتبط بالنشر أو الملاحظة.

**Potentially sensitive:**

- `chat_id`.
- relationships بين bot وchat وmessage.
- message content.
- archive metadata.
- local paths أو runtime identifiers.
- reports التي تكشف أشخاصاً أو مجتمعات.

### Public repository لا يعني private-safe

commit history قد يحتفظ بقيمة حُذفت من الملف الحالي. Public forks/clones قد
تستمر. لذلك:

- لا تُنشر chat IDs أو archive content افتراضياً.
- لا توضع tokens أو secrets في files أو commits أو Action logs.
- لا يعتمد erase المحلي عبر `/forgetme` على إزالة public history.
- لا يُعامل username كإثبات ملكية أو authenticity.

### Registry poisoning وspoofing

أي publisher غير موثوق يمكنه:

- claim أن bot أرسل message لم يرسله.
- إعادة استخدام key أو namespace.
- نشر deleted/active state كاذبة.
- إرسال duplicates أو replay.
- إغراق repository بملفات أو PRs.
- إدخال content ضار إذا كانت Actions تقوم parsing أو checkout.

GitHub account authentication تثبت من يكتب إلى GitHub، لا من يملك bot أو أن
Telegram أرسل الرسالة. يلزم trust model مستقل قبل استخدام السجل للتحقق.

### Token compromise

Token يملك write access يمكنه تعديل أو حذف أو نشر بيانات ضمن الصلاحية. كما
أن workflow بامتيازات زائدة يوسع blast radius. [وثائق GitHub عن
`GITHUB_TOKEN`](https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/controlling-permissions-for-github_token)
توصي بتقليل permissions، ووثائق hardening تحذر من تشغيل مدخلات PR غير موثوقة
في سياق privileged.

---

## 10. Trust Model

السؤال الحاسم هو: من يملك حق كتابة claim، ومن يملك حق تغييره؟

### طبقات الثقة المطلوبة

```text
Telegram / observed transport
          ↑  (قد لا يراه registry)
Compliant Titan runtime
          ↓ mandatory local event
Titan Core contract
          ↓ provider-agnostic publication interface
Publisher / authenticated relay
          ↓ accepted, normalized, rate-limited event
GitHub repository / registry storage
          ↓
Community readers, inspectors, reports
```

كل طبقة تثبت شيئاً مختلفاً:

- **Bot runtime:** يملك execution context وTelegram credentials، ويمكنه إنشاء
  event، لكنه يظل تحت سيطرة مطور bot.
- **Titan Core:** يستطيع فرض أنه لا يوجد مسار compliant يرسل من `ctx` دون
  تسجيل event، لكنه لا يستطيع فرض code integrity على جهاز المالك.
- **Shared registry client:** ينسق event ولا يصبح موثوقاً لمجرد أنه package
  محلي؛ يمكن حذفه أو تعديله إذا كان داخل runtime.
- **Relay / service:** يمكنه إخفاء GitHub credentials، authentication،
  rate limiting، schema validation، idempotency وaudit. لكنه يحتاج أن يقرر
  هل يقبل self-attestation من runtime أم يحتاج evidence إضافياً.
- **GitHub:** يثبت repository account/app والـ commit/history، لا أن Telegram
  أرسل الرسالة ولا أن runtime شغّل Titan الرسمي.

### هل direct write إلى GitHub يكفي؟

لا. direct write يتطلب token أو GitHub App installation credentials في كل bot
أو في بيئة مشتركة. هذا يخلق مشكلات:

- token distribution وrotation وleast privilege على كل runtime.
- إمكانية سرقة token أو استخدامه خارج message lifecycle.
- إمكانية أن يزيل المطوّر call النشر أو يستبدل payload قبل GitHub.
- account authentication تثبت صلاحية الكتابة إلى repository، لا ownership
  للـ bot ولا حدوث Telegram send.
- repository يتحول إلى hot path عالي الكلفة، مع rate limits وconflicts وabuse.

GitHub App يحسن نموذج الصلاحيات ويجعل installation قابلاً للإلغاء، لكنه لا
يحل enforcement داخل runtime. installation token يثبت أن app أو relay يكتب،
لا أن كل `ctx.send()` مرّ فعلاً عبره.

### هل relay موثوق يحل المسألة؟

relay هو أصغر طبقة تجعل mandatory publication ذات معنى تشغيلياً:

1. runtime compliant يرسل event تلقائياً بعد local acceptance.
2. relay authenticates bot/runtime ويطبق schema وidempotency.
3. relay يسجل `accepted/pending/rejected` ويحتفظ بسجل delivery.
4. relay ينشر إلى GitHub أو backend آخر باستخدام credential واحد محمي.

لكنه لا يحول self-report إلى حقيقة مستقلة. إذا كان runtime يستطيع أن يرسل
`"Telegram succeeded"` كادعاء كاذب، فالrelay لا يعرف ذلك إلا إذا وجدت
attestation أو observation إضافية. لذلك يجب أن يصف registry claim على أنه:

- `runtime-observed` إذا وثق في compliant client.
- `relay-accepted` إذا قبلته طبقة النشر.
- `telegram-verified` فقط إذا وُجدت وسيلة تحقق مستقلة مناسبة.

لا يجوز استخدام كلمة verified للطبقة الأولى أو الثانية تلقائياً.

### Canonical record: authority مقابل transport

قبل وصف record بأنه canonical يجب حسم أربع صلاحيات:

1. **الكتابة:** هل يقبل relay events من كل registered bot، أم من publishers
   authenticated فقط؟
2. **التعديل:** هل record immutable بعد القبول، أم تُضاف corrections وtombstones
   append-only؟
3. **الربط:** كيف يرتبط event بـ bot/runtime وglobal identity دون الاعتماد على
   username وحده؟
4. **الإثبات:** ما الفرق بين self-attestation من runtime، وrelay acceptance،
   وobservation مستقلة؟

الاقتراح الدلالي الأكثر تحفظاً هو أن canonical state تكون نتيجة policy في
publisher/registry: event مقبول، schema صحيح، idempotency محسومة، وlifecycle
state أحدث منسوب إلى actor مسموح. عندها يمكن أن يكون GitHub:

- **transport/public mirror** إذا كان relay هو السجل الذي يقرر القبول.
- **durable publication store** إذا كان commit القابل للتحقق هو output
  canonical لسياسة relay.
- وليس authority مستقلاً إلا إذا عُرّفت صلاحيات repository وbranch والـ
  append-only/tombstone policy كجزء من العقد، وحتى عندها يثبت GitHub
  publication لا وقوع Telegram.

Git history يثبت من نشر commit ومتى وفق timestamps الخاصة به، لكنه لا يثبت
أن payload صادق أو أن event لم يُنشأ بعد تزوير. حذف الملف لا يمحو history أو
forks؛ canonical deletion يجب أن تكون tombstone، بينما data erasure policy
منفصلة.

### سيناريو المطور الخبيث

| الجهة | ما تستطيع فعله | ما يستطيع Titan منعه |
|---|---|---|
| **Compliant runtime** | إرسال رسالة عبر contract الرسمي فقط | يمنع opt-out البرمجي؛ ينشئ event تلقائياً وفق العقد |
| **Modified Titan / fork** | حذف hook، تغيير payload، أو عدم الاتصال بالrelay | لا يستطيع Core المحلي منعه؛ يمكن كشف الإصدار أو طلب attestation فقط |
| **Direct Telegram API** | إرسال رسائل خارج `ctx` بلا identity حالية | لا يشمله contract الحالي؛ يجب عدم تفسير غيابه كعدم حدوثه |
| **Malicious client** | إرسال claims مزيفة أو replay أو namespace collision | relay authentication/schema/idempotency/rate limits تقلل poisoning، لكنها لا تثبت أن Telegram حدث |
| **Bot لا يستخدم Titan** | لا يملك Titan identity أصلاً | خارج نطاق enforcement والـ registry |

الغرض من mandatory contract هو إزالة اعتماد التسجيل على حسن نية المطور في
runtime compliant، لا الادعاء بأن framework المحلي يستطيع إجبار برنامج معدّل
عمداً أو bot خارج Titan.

### نماذج الكتابة

- **أي Titan bot:** سهل، لكنه لا يمنع spoofing أو poisoning.
- **Authenticated publishers:** أفضل، لكنه يثبت credential لا صحة الرسالة.
- **Trusted maintainers:** يرفع review quality ويخفض throughput.
- **Signed submissions:** تضيف provenance/integrity، لكنها تحتاج key lifecycle
  وverification وسياسة rotation.
- **Trusted relay:** يخفي GitHub credentials عن كل runtime ويتيح policy،
  لكنه يصبح service جديدة ذات ثقة مركزية.
- **PR-based submission:** جيد للمراجعة والمجتمع، بطيء للـ runtime.
- **Append-only claims:** يحافظ على التاريخ، لكنه يحتاج tombstones للـ deletion
  ويمنع تصحيح الخطأ إلا بإضافة claim جديد.
- **Moderation layer:** ضرورية إذا أصبح السجل مصدر تقارير مجتمعية، لكنها ليست
  جزءاً من Message Links identity تلقائياً.

### ما الذي يجب إثباته قبل كلمة “verification”؟

على الأقل:

1. bot identity global قابلة للتحقق.
2. publisher authorization لهذا bot.
3. ارتباط message reference برسالة أرسلها bot فعلاً، لا مجرد self-report.
4. provenance للـ observed event.
5. سياسة conflicts وtombstones.
6. distinction بين `verified`, `published`, `unverified`, `stale`, و`disputed`.

لا يملك HEAD الحالي هذه الطبقات. لذلك لا ينبغي تسمية GitHub row “verified
identity” بمجرد وجود commit. المطلوب قبل هذا الوصف هو على الأقل:

1. تعريف compliant runtime وإصداره أو attestation المقبولة.
2. هوية bot عالمية لا تعتمد على username القابل للتغيير وحده.
3. credential أو registration يربط bot بـ publisher/relay.
4. event idempotency يمنع replay والتعارض.
5. سياسة تصحيح وtombstone لا تسمح للكاتب بمحو التاريخ بصمت.
6. تمييز واضح بين self-attested وrelay-accepted وexternally verified.

---

## 11. Failure, Recovery, and Offline Behavior

### Failure domains

الأنظمة الثلاثة مستقلة:

```text
Telegram transport
Local SQLite
GitHub repository/API/Actions
```

نجاح أحدها لا يعني نجاح الآخرين. يجب تسجيل هذه الحقيقة في semantics، لا
إخفاؤها خلف `ctx.send()`.

### Recovery

Mandatory Hybrid يحتاج، مفاهيمياً وcontractually، معرفة pending events
وإمكانية إعادة إرسالها. إذا لم توجد durable queue أو equivalent durable
outbox، فالـ runtime لا يستطيع الوعد بأن كل send أنتج shared registration بعد
restart؛ عندها يكون التصميم ناقصاً، لا مجرد degraded optional sync.

المطلوب التمييز بين الحالات التالية:

- **accepted:** Telegram نجح، event المحلي قُبل، والـ relay/registry أعاد
  acknowledgment قابلاً للتحقق.
- **pending:** Telegram وlocal outbox نجحا، لكن remote acceptance لم يحدث أو
  نتيجته غير معروفة. لا يُحذف event ولا يُعاد Telegram send.
- **failed:** لم يُحفظ event المحلي، أو رُفض نهائياً بعد سياسة retry. هذه
  مخالفة للـ mandatory invariant وتحتاج observability وrecovery، لا إخفاءها
  كنجاح.
- **stale/unknown:** حالة قراءة أو cache، لا حكم على وجود الرسالة أو عدمها.

Retry لا ينبغي أن يكون blind:

- refetch current state عند conflict.
- تحقق من أن event لم يُقبل سابقاً.
- لا تعيد non-idempotent mutation بعد timeout دون التحقق من النتيجة.
- افصل API failure عن validation rejection وعن permission failure.

### Failure matrix

| failure | ما يبقى محلياً | semantics المطلوبة |
|---|---|---|
| process crash قبل local commit | لا يوجد event قابل للضمان | لا يُسمى send مسجلاً؛ يلزم recovery/observability |
| crash بعد atomic identity+outbox commit | identity وevent | `durable pending`، يستأنف بعد restart |
| network/GitHub outage | outbox وattempt metadata | لا فقد؛ retry عند عودة الخدمة، ولا Telegram retry |
| rate limit | event وموعد retry | `retryable/pending` مع احترام backoff، لا flood |
| duplicate delivery | event نفسه وidempotency key | relay يعيد نفس acceptance أو يرفض duplicate بلا row جديد |
| partial local persistence | identity بلا outbox أو العكس | inconsistency صريحة؛ reconcile/quarantine، لا اختراع shared claim |
| corrupted queue/state | bytes غير قابلة للتحقق | `failed` أو quarantine مع alert؛ لا حذف صامت ولا retry أعمى |
| repeated retry | سجل محاولات bounded | idempotent deduplication وdead-letter بعد policy معلنة |
| permanent validation/auth failure | event محفوظ وسبب الرفض | `failed permanently` قابل للتدقيق، مع مسار تصحيح لا يفقد الأصل |

الضمان الواقعي هو **at-least-once local obligation مع remote idempotency**،
وليس exactly-once end-to-end. Eventual publication يمكن ادعاؤها فقط تحت شروط
معلنة: local durable state سليم، publisher يستمر، registry يعود أو يملك
مساراً بديلاً، والحدث لا يُرفض نهائياً. إذا لم تتحقق هذه الشروط فالحالة
المنضبطة هي `failed` أو `unknown`، لا وعد delivery مطلق.

### Deletion

`mark_deleted()` الحالي tombstone محلي، وليس delete row. في shared registry:

- حذف GitHub file قد يمحو latest view لكنه لا يمحو Git history أو clones.
- نشر tombstone يحافظ على معرف identity ويمنع عودة record القديم.
- يجب أن تكون deletion state موثقة كـ observation لا ادعاء content deletion
  الكامل.

### Partial publication

قد يوجد identity محلياً وoutbox event دون shared claim مقبول، أو يوجد shared
claim لا يمكن قراءته بسبب outage أو permission. `/link` الحالي لا ينبغي أن
يخلط بين:

- غير موجود محلياً.
- منشور mandatory لكنه pending أو failed.
- shared غير متاح.
- shared stale.

الفشل بعد Telegram ليس مبرراً لإعادة إرسال Telegram تلقائياً، لأن ذلك قد
ينشئ رسالة مكررة. الاسترداد يخص event publication، مع idempotency key يربط
المحاولات بنفس identity/event.

---

## 12. Scaling and Limits

GitHub قد يتحمل ملفات registry صغيرة أو snapshots محدودة، لكن سجلاً ينمو إلى
مئات الآلاف أو ملايين records يواجه:

- حجم Git history المتراكم، حتى بعد حذف latest files.
- clone/fetch cost للمستخدمين.
- Contents API directory limit.
- file size limits وencoding overhead.
- hot files/conflicts عند append.
- غياب secondary indexes وqueries حسب bot/chat/time.
- تكلفة Actions لإعادة بناء index.
- rate limits وabuse controls.
- صعوبة retention وprivacy erasure من history.

البدائل الثلاثة لها حدود مختلفة:

- SQLite local: ممتاز لكل runtime، لا sharing.
- GitHub: ممتاز source publication/review، ضعيف كـ high-write database.
- service منفصلة: أفضل query/write semantics، لكنها تتطلب تشغيل وأمن وSLA.

**النتيجة:** لا يوجد أساس في HEAD أو وثائق GitHub يبرر افتراض أن repository
خاماً يمكن أن يكون registry عالمي بملايين records دون تصميم indexing/storage
مخصص. لا يقدم هذا التحقيق رقماً حدياً غير موثق.

---

## 13. Community and Verification Use Cases

### `/link`

يبقى local-first. يمكن لأداة خارجية لاحقاً أن تستخدم shared projection، لكن
لا ينبغي أن تجعل `/link` ينتظر GitHub أو أن تعتبر عدم العثور remote دليلاً
على عدم وجود الرسالة.

### Inspector and diagnostics

قد تعرض الأدوات:

- local identity.
- shared publication status.
- last sync error.
- provenance state.

لكن ذلك يحتاج contract جديداً؛ لا يوجد في API الحالية.

### Verification

السجل يمكن أن يساعد في جمع evidence أو cross-runtime lookup، لكنه لا يحقق
verification وحده. verification يحتاج publisher authentication وربطاً
موثوقاً بمالك bot وربما observation من relay مستقل.

### Reports and moderation

يمكن للـ report أن يشير إلى public address أو identity claim. لكن:

- report ليس identity.
- evidence ليس archive تلقائياً.
- registry ليس moderation decision engine.
- وجود claim لا يثبت المخالفة.

هذه الحدود تمنع أن يتحول Message Links Protocol إلى نظام moderation قبل
وجود حاجة وtrust model منفصلين.

---

## 14. Compatibility with Titan Philosophy

Titan يعلن في الكود والوثائق:

- minimal framework.
- stability-driven design.
- contract-first behavior.
- no hidden side effects.
- deterministic execution.
- `ctx` كـ execution point.
- direct `bot.telegram` خارج cycle.
- تجنب platform coupling غير الضروري.

### ما يتوافق

Mandatory publication contract مع provider-agnostic boundary يتوافق مع هذه
المبادئ إذا:

- يضمن event/outbox المحلي بعد نجاح `ctx.send()` و`ctx.reply()` بلا developer
  action.
- لا يجعل GitHub dependency مخفية؛ الـ Core يعرف عقد publication لا مزوداً
  بعينه.
- لا يغير `/link` المحلي إلى remote-first دون contract صريح.
- ينشر identity projection mandatory صغيرة، ولا ينشر archive أو chat metadata
  أو content بلا policy مستقلة.
- تبقى `MessageStore` وpublication interface قابلة للفصل، لا import مباشر لـ
  GitHub داخل Core.
- يعرّف `pending` و`failed` كحالات تشغيلية مرئية، لا كفشل صامت أو optionality.

### ما لا يتوافق

التصميم التالي يلوث Core:

```text
ctx.send()
  → Telegram
  → GitHub API
  → commit/PR/Action
  → identity required for success
```

لأنه يضيف external latency، failure coupling، authentication، rate limits،
وside effects غير متوقعة إلى مسار الإرسال الأساسي.

### أصغر boundary

أصغر boundary معقول هو:

```text
Titan Core / local Message Links
        ├── confirmed local identity
        └── mandatory durable publication event
                    ↓ provider-agnostic interface
Trusted publisher / relay
        ├── authentication
        ├── idempotency/retry
        ├── provenance/policy
        └── GitHub or another registry backend
```

لا يعرف Core هل backend GitHub أو خدمة أخرى، لكنه لا يسمح لمسار compliant
بتحويل publication إلى قرار مطوّر. ولا يُسمى backend المشترك “source of
truth” أو “verified authority” قبل حسم trust وconsistency.

---

## 15. Contract / ADR Impact

### ما يبقى ثابتاً

ضمن Mandatory Hybrid المقترح، تبقى هذه الحدود المحلية ثابتة ما لم يصدر ADR
جديد:

- `bot.links` يبقى public API.
- identity تُنشأ بعد نجاح `ctx.send()`/`ctx.reply()` فقط.
- `/link` لا ينشئ identity.
- `mark_deleted()` tombstone ولا يعيد استخدام `titan_id`.
- Archive opt-in.
- SQLite local default.
- `/forgetme` لا يمحو Permanent Resource Identity وفق العقد الحالي.

### ما يصبح mandatory contract أو external extension

- automatic publication event بعد كل `ctx.send()` و`ctx.reply()` ناجح.
- atomic local persistence boundary تجمع identity وpublication event، أو
  recovery contract يثبت بديلاً مكافئاً.
- durable outbox أو equivalent يثبت أن event لم يُسقط عند restart/offline.
- publisher أو relay خارجي يستقبل event بلا developer opt-in.
- sync status/observability، بما فيه `accepted/pending/failed`.

ويبقى backend المحدد، سواء GitHub أو خدمة أخرى، external extension؛ لا يعني
ذلك أن publication نفسها اختيارية.

### ما يحتاج ADR جديدة أو تعديل قرار

أي التزام بأن:

- كل runtime ينشر تلقائياً.
- كل `ctx.send()` و`ctx.reply()` الناجح ينتج shared registration event.
- pending publication مقبولة مؤقتاً بعد network failure ولا تسقط obligation.
- relay أو publisher موثوق مطلوب للـ authentication والـ delivery.
- shared registry هو source of truth.
- `/link` يقرأ remote.
- GitHub مطلوب لتشغيل Titan.
- identity public أو archive public افتراضياً.
- failure في sync يفشل send.

سيؤثر على ADR-008 وADR-018، وقد يلامس ADR-020 الخاص بطبقة ecosystem، وTimeline
وROADMAP ووثائق Message Links وpublic API.

### Breaking أم additive؟

- إضافة publisher اختياري خارج Core: لا تكفي للمتطلب؛ تكون additive فقط إذا
  كان عقد mandatory publication موجوداً خلفها.
- إضافة remote read اختياري مع `unknown/stale` semantics واضحة: غالباً
  **additive**.
- جعل التسجيل المشترك mandatory: **contract change** في lifecycle وfailure
  semantics حتى لو بقي `/link` محلياً.
- اشتراط atomic identity+event persistence: **contract change** في local
  durability، ولا يوفره HEAD الحالي.
- جعل GitHub إلزامياً أو جعل `/link` remote-first: **contract change** وقد
  يكون breaking في التشغيل والخصوصية.
- جعل `/forgetme` يمحو public history: ليس مجرد implementation change؛ هو
  تغيير في model Permanent Resource Identity وdata governance.

لا تُعدّل هذه الملفات في مرحلة التحقيق.

---

## 16. Test Impact

### التغطية الحالية المقروءة

الاختبارات الحالية تغطي:

- save/get identity.
- sequential IDs وعدم إعادة استخدامها بعد deletion.
- lookup بـ Telegram ID وTitan ID.
- path forms، بما فيها plain `links.db` بعد الإصلاح.
- automatic registration عبر `ctx.send()` و`ctx.reply()`.
- Telegram send failure وعدم التسجيل.
- best-effort registration.
- `/link` success/failure/no reply/non-bot/old message.
- archive save وarchive failure/idempotent archive.
- `mark_deleted()` وبقاء address.
- `set_store()` و`set_data_dir()`.
- concurrency edge cases محلية.
- `/forgetme` وUserDataRegistry بمعزل عن Permanent Resource Identity.

هذه **confirmed by tests as test intent and assertions**. لم تُشغّل هنا بسبب
غياب `pytest` و`aiohttp`.

### فجوات current behavior

لا تغطي الاختبارات الحالية مباشرة بما يكفي:

- restart حقيقي مع manager جديد وقاعدة disk نفسها.
- اختلاف قواعد البيانات عند تغيير cwd.
- full disk-backed Telegram → local → `/link` cycle.
- non-writable filesystem.
- remote absence مقابل remote outage.
- global namespace collision بين runtimes.
- crash windows بين identity وpublication event.
- corrupted أو partially written local outbox.
- direct `bot.telegram` مقابل `ctx` coverage.

### اختبارات مطلوبة فقط إذا اعتمدت architecture جديدة

- contract tests تفصل local identity عن remote publication.
- atomic commit/recovery tests تثبت عدم وجود identity بلا event أو event بلا
  identity بعد process crash.
- idempotency عند retry وtimeout.
- concurrency/conflict tests لملف أو shard مشترك.
- read-after-write وeventual consistency semantics.
- offline queue/restart/recovery.
- rate-limit/backoff وpermanent rejection semantics.
- repeated retry وdead-letter/quarantine للـ corrupted state.
- duplicate publisher claims.
- permission/authentication failure.
- token scope and secret exposure.
- malicious payload/PR/Action tests.
- schema/version forward compatibility.
- tombstone/deletion propagation.
- migration/backfill وnamespace collision.
- provenance/signature verification.
- repository growth وrate-limit behavior باستخدام fixtures أو test server.

يجب ألا تختلط هذه الاختبارات باختبارات العقد المحلي الحالي.

---

## 17. Migration Implications

الانتقال من SQLite محلية إلى shared registry ليس copy files فقط:

1. كل runtime قد يملك sequence مستقل، لذلك `titan_id` وحده قد يتكرر.
2. `bot_username` الحالي ليس بديلاً كافياً عن global bot identity.
3. بعض قواعد SQLite قد تستخدم `set_data_dir()` أو cwd مختلفاً.
4. archive قد يكون local/private ولا يجوز backfill public تلقائياً.
5. duplicate `(chat_id, telegram_message_id)` قد يكون صحيحاً محلياً لكنه
   يتعارض عند namespace غير صحيح.
6. deleted rows تحتاج tombstones كي لا تعود عند re-sync.
7. backfill لا يثبت متى أو من أرسل الرسالة إلا بقدر ما تسجله القاعدة.
8. publish القديم قد يتطلب consent وreview، لا migration صامتة.

الخيار الآمن مفاهيمياً هو إبقاء local SQLite قابلة للقراءة والتشغيل، وإضافة
projection أو publication منفصلة بعد تعريف key/provenance. حذف SQLite أو نقل
runtime behavior ليس جزءاً من هذا التحقيق.

---

## 18. Hidden Risks and Architectural Implications

### Namespace collisions

`AUTOINCREMENT` داخل store محلي لا يصنع global ID. Runtime A وB قد يملكان
`titan_id=1` لنفس أو لبوتين مختلفين. address الحالي يحمل username وID، لكن
shared registry يحتاج collision policy لا تعتمد على حسن النية.

### Bot identity collisions

`bot_username` قابل للتغيير أو الانتحال في claim خارجي، ولا يحمل في identity
الحالية provider-level proof. يلزم حسم canonical bot identity قبل أي verification.

### Replay and duplicate events

إعادة نشر event بعد timeout أو restart قد تصنع duplicate record أو conflict.
Git commit hash يثبت commit، لا يمنع تكرار semantic event في ملفات مختلفة.

### Stale records

غياب remote record قد يعني أنه لم يُنشر أو أن cache قديم أو أن publisher
متوقف. لا يجب تفسيره كـ “الرسالة غير موجودة”.

### Deletion propagation

`deleted=true` local tombstone لا يعني حذف archive من Git history أو من clones.
لابد من فصل lifecycle state عن data erasure.

### Schema evolution

أي public record يحتاج versioning وunknown-field policy وforward compatibility.
Git لا يوفر هذه semantics تلقائياً.

### Audit trail versus truth

Git history ممتاز لتتبع من غيّر ملفاً ومتى، لكنه audit trail للـ publication
لا oracle لـ Telegram.

### Repository bloat

append-only commits مفيدة provenance لكنها قد تضخم history بسرعة. حذف latest
record لا يعالج retention أو public copies.

### Abuse and observability

سجل مجتمعي يحتاج مراقبة حجم الطلبات، failed submissions، conflicts، stale
publishers، وpoisoning reports. هذه قدرة تشغيلية خارج Titan Core.

### Current implementation nuance

حتى local identity ليست guaranteed بلا شروط: `_register_identity()` يتخطى
العملية عند غياب username أو message ID، ويفصل storage failure عن نجاح
Telegram. كما لا يوجد في HEAD publication event أو atomic identity+event
boundary. أي shared design يجب أن يحافظ على الفصل بين Telegram وremote
availability، ويعلن contract جديداً بوضوح حول local failure وrecovery بدلاً من
تغطيتها بكلمة asynchronous.

---

## 19. Findings by Evidence Type

### Confirmed by code

- `Titan` يهيئ `LinksManager` تلقائياً.
- default path يعتمد على `os.getcwd()` وقت إنشاء manager.
- SQLite وArchive lazy.
- identity تُسجّل بعد send في `ctx.send()` و`ctx.reply()`.
- التسجيل لا يمر عبر direct `bot.telegram`.
- `/link` lookup-only.
- `mark_deleted()` يحافظ على identity.
- `/forgetme` لا يمر عبر LinksManager.
- `MessageStore` abstraction موجودة، وArchive v1 مرتبطة بـ SQLite.
- لا يوجد GitHub backend أو remote sync في HEAD.

### Confirmed by tests

- local identity CRUD والـ lookup.
- sequential IDs/tombstone permanence.
- SQLite path fix.
- send/reply registration والـ failure behavior.
- `/link` scenarios.
- archive behavior.
- local concurrency edge cases.

### Documented contract

- Identity layer جزء من Titan وليست opt-in.
- Archive layer اختيارية.
- Message Links domain مستقل.
- Permanent Resource Identity ليست User Data قابلة للمحو.
- `set_store()` و`set_data_dir()` هما نقاط التخصيص الحالية.

### External constraint

- Contents API file/directory size and directory-count limits.
- Existing-file update requires SHA، والتحديثات المتزامنة لبعض endpoints
  تتعارض ويجب serializing.
- REST API لها primary/secondary rate-limit behavior.
- PRs وrefs وActions لها semantics منفصلة.
- `GITHUB_TOKEN` permissions وprivileged workflows لها security constraints.

المراجع الخارجية موضوعة في قسم GitHub Feasibility.

### Inference

- GitHub مناسب أكثر للتخزين والنشر والمراجعة والتوزيع من hot-path registry،
  ولا يحقق enforcement بمفرده.
- Mandatory Hybrid هو boundary الأقل تلويثاً لـ Core إذا كان event/outbox
  إلزامياً، حتى لو كان remote acceptance asynchronous.
- trusted publisher/relay مطلوب إذا كان claim “mandatory” يراد له أن يعني
  أكثر من self-report قابل للحذف.
- identity projection يجب أن تنفصل عن archive/evidence/report.
- verification يحتاج trust/provenance إضافيين.
- global namespace مطلوب قبل shared lookup.
- runtime hostile خارج قدرة enforcement لأي framework محلي.
- mandatory event creation وremote acceptance وguaranteed delivery ثلاث
  guarantees مختلفة.
- identity وpublication event يجب أن يشتركا في local atomic durability boundary
  أو يملكا recovery contract مكافئاً.
- remote guarantee الواقعي at-least-once مع idempotent acceptance، لا exactly-once
  بين Telegram وregistry.

### Open question

- ما bot identity canonical عالمياً؟
- من publisher/relay المسموح له، وما مستوى الثقة الذي يثبته؟
- هل السجل public أم curated/private؟
- ما freshness وavailability المطلوبان؟
- ما الحد الأدنى الإلزامي من publication، وما الذي يبقى content/archive؟
- هل المطلوب publication أم query service؟
- هل `pending` بعد outage مقبولة إلى أجل محدد، وما معنى `failed`؟
- ما policy إصلاح corruption أو partial local state؟
- ما الحد الأدنى من attestation الذي يميز runtime-observed عن telegram-verified؟
- هل canonical registry هو relay أم GitHub mirror أم خدمة مستقلة؟
- هل يجب أن يرفض contract نجاحاً محلياً إذا فشل حفظ identity+event، مع أن Telegram
  لا يمكن rollback له؟
- ما retention/deletion policy؟
- ما حجم الاستخدام الفعلي الذي يبرر service منفصلة؟

---

## 20. Conclusions

### 1. Mandatory Shared Registry Model

النموذج المطلوب ليس:

```text
Developer chooses whether to publish
```

بل:

```text
ctx.send() / ctx.reply()
        ↓
Telegram succeeds
        ↓
Titan creates local identity + durable publication event
        ↓
Publisher / relay accepts and retries automatically
        ↓
Shared Registry records the mandatory projection
```

الـ invariant المقترح هو:

1. لا يوجد shared identity claim قبل نجاح Telegram.
2. كل `ctx.send()` و`ctx.reply()` ناجح في compliant runtime ينتج event محلياً
   بلا opt-in.
3. event لا يضيع عند restart أو offline إذا كان local durable boundary قد
   قُبل.
4. `accepted` تعني أن shared publisher/registry أكد القبول؛ `pending` تعني أن
   الالتزام قائم لكن network acceptance لم يحدث؛ `failed` تعني أن الالتزام
   لم يستطع حتى حفظ event أو رُفض نهائياً.
5. لا يعاد إرسال Telegram لمعالجة فشل publication.
6. identity وpublication event يُقبلان معاً داخل local atomic boundary؛ remote
   acceptance يبقى خارجها.

بهذا تكون **registration mandatory** حتى عندما تكون **publication remote
acceptance eventual**. أما ضمان قبول remote رغم outage كامل فيحتاج availability
وdurability في relay والـ registry، ولا يمكن أن يضمنه Titan Core وحده.

اسم **Mandatory Hybrid** ليس architecture مكتملة ولا implementation قراراً؛ هو
وصف للـ semantics: mandatory local event + shared publication خارج critical
path. يمكن تنفيذ هذا الوصف لاحقاً عبر relay أو service registry، وقد يستخدم
GitHub أو لا يستخدمه.

`ctx.send()` و`ctx.reply()` داخلان في العقد. `edit` و`delete` و
`mark_deleted()` lifecycle events مرتبطة بالidentity، لا identities جديدة.
المسارات التي تستخدم `bot.telegram` مباشرة أو تتجاوز `ctx` خارج الضمان الحالي؛
لا يجوز الادعاء بأن framework يرى تلك الرسائل تلقائياً.

### 2. Trust Boundary

الثقة لا تقع كلها في GitHub:

- Titan Core يفرض event creation على compliant runtime.
- local durable store/outbox يثبت أن runtime قبل obligation.
- publisher/relay authenticates، يتحقق من schema، يمنع replay، ويسجل الحالة.
- GitHub يحفظ وينشر commits أو snapshots ويقدم audit/distribution.
- verification الخارجي، إن لزم، يحتاج bot identity وattestation أو observation
  مستقلة.

Direct GitHub tokens داخل كل bot تجعل enforcement هشاً: يمكن تسريبها أو حذف
خطوة النشر أو تزوير payload. GitHub App يحسن credential scope لكنه لا يفرض
تشغيل Titan الرسمي. relay موثوق هو boundary الأصغر القابل للدفاع، مع الاعتراف
أنه يضيف جهة ثقة مركزية وأن self-attestation لا تثبت Telegram بذاتها.

لا يستطيع framework محلي إجبار مطور hostile يملك الجهاز على تشغيل code لم يعد
موجوداً عنده. الحد الواقعي هو:

- **compliant runtime:** لا developer action، ولا opt-out من registration.
- **modified/hostile runtime:** يمكنه تجاوز Core أو تزوير claims؛ يحتاج النظام
  إلى attestation أو جهة رصد خارجية إذا أراد مقاومة ذلك.

### 3. GitHub Role

GitHub مناسب كـ:

- storage/publication layer خلف publisher أو relay.
- commit history للتدقيق في تغييرات registry.
- distribution وraw/clone وsnapshots.
- validation أو index محدود عبر Actions.
- review وPR للـ policy أو التصحيحات المجتمعية غير الساخنة.

GitHub ليس:

- authority تثبت أن Telegram أرسل الرسالة.
- enforcement mechanism يجبر كل runtime على النشر.
- low-latency transaction database.
- حلًا مستقلاً للـ idempotency والـ retry والـ ordering والـ provenance.
- مكاناً مناسباً تلقائياً لـ archive أو content الحساس.

إذن GitHub وحده لا يوفر trust/enforcement semantics المطلوبة. يمكنه حفظ
publication التي قبلها relay، لكن يجب أن يبقى provider خلف boundary لا يعرفه
Core.

### 4. Failure Semantics

الفشل لا يلغي mandatory obligation:

| الحالة | الحالة المطلوبة |
|---|---|
| Telegram failed | لا identity ولا publication event |
| Telegram succeeded + local acceptance failed | `failed` مرئية؛ لا rollback ولا Telegram retry أعمى |
| local event accepted + GitHub/relay unavailable | `pending` durable مع retry |
| timeout بعد request | تحقق من النتيجة قبل retry، باستخدام idempotency key |
| accepted ثم deletion | tombstone lifecycle event؛ لا ادعاء بأن Git history اختفت |
| restart/offline | استئناف من outbox؛ وإلا لا يجوز ادعاء eventual guarantee |
| exhausted retry أو validation rejection | `failed` مع سبب قابل للرصد، لا إسقاط صامت |

`ctx.send()` لا يحتاج أن ينتظر GitHub إذا كان local acceptance هو synchronous
boundary. لكن نجاحه لا يعني أن shared record `accepted`؛ يجب أن تكون حالة
publication قابلة للفحص، وإلا يتحول “mandatory” إلى شعار لا contract.
كما أن local acceptance نفسه ليس مضموناً في HEAD الحالي: إذا فصل التنفيذ
identity insert عن event persistence، يبقى crash window يخرق invariant. لذلك
الـ atomic boundary مطلب سابق على ادعاء eventual publication.

### 5. Enforcement Limits

يمكن فرض:

- automatic registration في `ctx.send()` و`ctx.reply()` داخل نسخة Titan
  compliant.
- عدم إنشاء event قبل نجاح Telegram.
- identity projection دنيا، idempotency key، وtombstone lifecycle.
- local durability وvisibility للحالات `pending/failed`.

لا يمكن فرضه من Core المحلي وحده:

- أن runtime لم يُعدّل أو أن developer لم يحذف publisher.
- أن claim عن Telegram صحيح أمام طرف ثالث.
- أن GitHub متاح أو يقبل commit فوراً.
- أن content المنشور لا يكشف معلومات حساسة إذا كانت policy خاطئة.
- أن direct `bot.telegram` أو code paths خارج `ctx` مرّت عبر registry.

لذلك “mandatory for all Titan runtimes” يجب أن تعني كل runtimes التي تلتزم
بالعقد الرسمي. أما مقاومة runtime hostile فتحتاج trust anchor خارج الجهاز.

### 6. Smallest Viable Architecture Boundary

أصغر boundary يحقق الهدف دون GitHub coupling هو:

```text
Titan Core
  ctx.send()/ctx.reply()
  local identity
  mandatory durable publication event
  provider-agnostic publisher interface
          ↓
Trusted publisher / relay
  authentication
  schema/version
  idempotency
  retry/dead-letter
  provenance and status
          ↓
Registry backend
  GitHub or another storage/publication service
```

لا يطبق هذا التحقيق أي جزء من هذه البنية. كما أن `outbox` و`relay` هنا
requirements وboundaries تحليلية، لا queue أو service منشأة في هذا التغيير.

الحد الأدنى ليس “Core يرسل إلى GitHub”، بل “Core لا يسمح بفقد event بعد local
acceptance، وpublisher موثوق يعالج delivery”. أما authority فتظل قراراً
منفصلاً: GitHub قد يكون mirror أو durable publication store، بينما canonical
acceptance قد تقع في relay أو registry service.

Mandatory Hybrid هو الاختيار الدلالي الأقرب: local durable storage +
mandatory shared publication. أما اختيار GitHub كـ backend فهو قرار منفصل.
إذا تطلبت المنظومة query/SLA/concurrency عالية، يصبح Shared Registry منفصل
مع relay أو service هو الخيار التشغيلي الصحيح، ويمكن أن يبقى GitHub طبقة
توزيع أو audit فقط.

### 7. Open Questions Before ADR

1. ما canonical global bot identity والـ namespace الذي يمنع collision؟
2. ما الحد الأدنى الإلزامي من identity projection، وهل public دائماً؟
3. ما authentication وattestation المقبولة للـ compliant runtime؟
4. هل relay trust المركزية مقبولة، ومن يدير lifecycle والمفاتيح؟
5. ما freshness/availability ومدة بقاء `pending` قبل اعتبارها `failed`؟
6. كيف تُمثل idempotency وordering وduplicate claims وreplay؟
7. هل `edit` و`delete` تنشر lifecycle/content events، وما retention والتombstone؟
8. ما سياسة archive وmessage content وchat metadata والـ deletion العام؟
9. هل GitHub يتحمل write rate وrepository growth وquery patterns المتوقعة؟
10. ما الذي يثبت `telegram-verified` بدلاً من `runtime-observed`؟
11. كيف تُربط reports وevidence دون تحويل registry إلى moderation engine؟
12. ما contract الذي يغطي direct `bot.telegram` والمسارات خارج `ctx`؟

لا ينبغي إنشاء ADR قبل الإجابة عن هذه الأسئلة، خصوصاً الفرق بين mandatory
registration وguaranteed remote publication.

---

## 21. Open Questions

1. هل الهدف الأساسي public discovery، أم verification، أم archive lookup،
   أم audit/review؟ هذه ليست use case واحدة.
2. هل يوجد owner موثوق لكل bot يستطيع authenticate publisher؟
3. هل يجب أن يكون bot numeric ID جزءاً من global identity؟
4. هل public registry يسمح بإدخال مباشر أم PR/relay فقط؟
5. هل `chat_id` ممنوع public دائماً، أم توجد حالات opt-in؟
6. كيف نمثل `unknown`, `stale`, `disputed`, و`deleted`؟
7. من يملك حق إضافة tombstone أو تصحيح claim؟
8. ما retention policy للـ commits والـ reports والـ evidence؟
9. ما الحجم المتوقع خلال سنة وثلاث سنوات؟
10. هل local acceptance مع outbox كافية، أم توجد حاجة لremote synchronous
    acknowledgment أثناء `ctx.send()`؟
11. هل GitHub هو storage/publication channel فقط، بينما registry الحقيقي relay
    أو service أخرى؟
12. كيف يتوافق أي public deletion request مع Git history وforks؟

---

## 22. Recommended Next Investigation / Implementation Boundary

الخطوة التالية ليست كتابة GitHub backend أو relay. التحقيق التالي يجب أن يحسم،
باستخدام synthetic data فقط:

1. canonical public record وglobal namespace.
2. threat/trust model وpublisher lifecycle.
3. projection الإلزامية المسموح نشرها من local identity.
4. state machine لـ `accepted/pending/failed/stale`.
5. idempotency وconflict behavior.
6. deletion/tombstone/retention policy.
7. workload حقيقي: write rate، read patterns، record growth، وoffline needs.
8. قرار صريح بين GitHub كـ publication layer أو service registry منفصلة،
   مع بقاء mandatory registration ثابتاً في الخيارين.

الحد التنفيذي الذي يجب الحفاظ عليه إلى أن يثبت العكس:

```text
Titan Core
  local Message Links contract
  mandatory event after ctx.send()/ctx.reply()
  no GitHub import
  no remote wait in ctx.send()/ctx.reply()

Provider-agnostic mandatory publication boundary
  durable local acceptance
  publisher/relay with explicit status
  publishes the mandatory privacy-filtered projection
  may use GitHub or another backend
```

لا يوصي هذا التحقيق بإنشاء ADR أو backend أو queue الآن. القرار الصحيح حالياً
هو تثبيت الفرق الدلالي: المطلوب هو mandatory registration تلقائية، مع local
durability وremote publication قابلة للاستئناف؛ وليس optional synchronization.
كما يجب متابعة trust وnamespace وrelay وprivacy قبل اختيار GitHub أو إضافة
shared infrastructure.

---

*هذا الملف تحقيق معماري مستقل. لا يغيّر Task 5 أو ADRs أو ROADMAP أو Timeline
أو source code أو tests.*