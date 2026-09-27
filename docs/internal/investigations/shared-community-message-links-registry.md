# Investigation — Shared / Community Message Links Registry

**الحالة:** تحقيق — لا قرار تنفيذ  
**التاريخ:** 2026-09-27  
**المرتبط بـ:** Message Links Protocol (#0)، ADR-008، ADR-018  
**نطاق هذا الملف:** دراسة معمارية فقط. لا يغيّر هذا التحقيق الكود أو العقود أو الاختبارات أو ADRs القائمة.

---

## 1. Executive Summary

السؤال ليس: «كيف ننقل `links.db` إلى GitHub؟». السؤال الصحيح هو:

> هل يمكن أن يصبح سجل Message Links مشتركاً بين عدة bots وruntimes دون أن يتحول
> Titan Core إلى عميل GitHub أو إلى نظام قاعدة بيانات موزعة؟

النتيجة:

1. **Shared Message Links Registry قابل للتنفيذ معمارياً**، لكن ليس كامتداد
   صامت لـ `ctx.send()` أو كبديل مباشر لـ SQLite.
2. **GitHub مناسب كطبقة نشر وتوزيع ومراجعة وأرشفة مصدرية محدودة**، وليس مناسباً
   عادةً كسجل application-facing متزامن يحتاج latency منخفضة، استعلامات كثيرة،
   كتابة متزامنة، أو semantics تشبه قاعدة البيانات.
3. **النموذج الأكثر توافقاً مع Titan هو Hybrid**: يبقى التسجيل المحلي durable
   والمسار الحالي هو المصدر التشغيلي لمسار الإرسال و`/link`، بينما تكون المزامنة
   إلى سجل مشترك قدرة اختيارية خارج Core.
4. يجب أن يكون الفشل في السجل المشترك قابلاً للفصل عن نجاح Telegram. لا ينبغي
   أن يجعل انقطاع GitHub رسالة Telegram فاشلة، ولا أن يخلق identity قبل نجاح
   الإرسال.
5. السجل العام المقترح لا ينبغي أن يخزن تلقائياً محتوى الرسائل أو كل metadata
   المحلية. Identity وpublic URL وarchive وevidence وreports حدود مختلفة.
6. `titan_id` الحالي متسلسل داخل store محلي؛ لا يكفي وحده كمفتاح عالمي بين
   runtimes. أي سجل مشترك يحتاج namespace وprovenance موثوقين قبل أن يدعي
   التحقق.
7. لا يمكن اعتبار Git history دليلاً على أن رسالة Telegram حدثت فعلاً. هو
   دليل على أن publisher أرسل commit، لا على صحة claim نفسه.
8. أصغر boundary آمن هو capability اختيارية خارج Titan Core: publisher/reader
   يستهلكان identities المحلية المؤكدة، ولا يعرف Core GitHub ولا يفرض وجوده.

هذه النتائج مبنية على الحالة الحالية في `HEAD` عند:
`7c43f11627a06c4341bc8aab45ba0fc3ce9b8369`.

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
كل ما هو موجود محلياً صالحاً للنشر. يجب أن تكون public visibility قراراً
صريحاً لكل نوع بيانات، لا أثراً جانبياً لتفعيل sync.

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

**inference:** API مناسبة لقراءات bounded أو مزامنة محدودة، لا لمسار `ctx.send()`
الحساس للزمن ولا لـ `/link` الذي يجب أن يبقى سريعاً ومحلياً في العقد الحالي.

### 5.4 Raw content

Raw content مفيد لتوزيع snapshot أو قراءة record منشور، لكنه ليس query service:

- لا يطبق identity authorization على معنى البيانات.
- لا يقدم transaction مع Telegram.
- لا يثبت أن محتوى الملف صحيح أو حديث بالنسبة لruntime.
- لا يحل indexing أو namespace collision.

يمكن أن يكون raw commit-pinned content جزءاً من distribution layer، لا بديلاً
عن registry semantics.

### 5.5 Pull requests

Pull request workflow يضيف review وchecks وmoderation وaudit مفيدة لسجل
مجتمعي، لكنه يجعل الكتابة:

- غير فورية.
- قابلة للرفض أو التأخير.
- مرتبطة بفرع وmerge policy.
- غير مناسبة لنجاح `ctx.send()` أو لإجابة `/link` اللحظية.

**inference:** PR-based submission مناسب لإدخال claims عامة أو تغييرات
مجتمعية تحتاج مراجعة، وليس لتسجيل كل رسالة runtime على الخط الساخن.

### 5.6 GitHub Actions

Actions يمكنها validate أو normalize أو publish أو build an index بعد push/PR.
لكنها automation غير متزامنة، لا transaction مشتركة مع Telegram.

**external constraint:** GitHub يحذر من checkout وتشغيل workflows المميزة مع
مدخلات PR غير موثوقة، ويوصي بتقييد `GITHUB_TOKEN` إلى أقل permissions ممكنة.
أي workflow يملك write access أو secrets يزيد أثر token compromise وscript
injection.

**inference:** Actions مناسبة كطبقة تحقق/فهرسة/حماية حول registry، وليست
مكاناً لجعل `ctx.send()` ينتظر commit أو نجاح workflow.

### 5.7 Public مقابل private repository

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
**Titan compatibility:** الأعلى؛ هذا هو العقد الحالي.  
**Migration:** لا migration مطلوبة.  
**Limit:** لا shared verification أو community discovery.

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
لا ينبغي أن يُعاد فشله إلى send.  
**Offline:** يحتاج queue محلية أو فقد sync؛ لا يمكن افتراض الكتابة أثناء
offline.  
**Security/privacy:** public history وtokens وworkflow خطر إضافي.  
**Scalability:** repository/file/API limits وغياب query/index semantics تجعل
الملايين records غير مناسبة كملفات خام.  
**Titan compatibility:** مناسب فقط كـ optional external capability، وغير مناسب
كـ required Core backend.  
**Migration:** backfill صعب لأن local stores قد تملك namespaces متصادمة
والـ archive قد يكون حساساً.

### C — Hybrid: Local Durable Store + Shared Registry

**Semantics:** local store يثبت identity ومسار `/link`; shared store يوزع
claim أو snapshot أو index اختياري.  
**Consistency:** local authoritative للتشغيل؛ shared eventually consistent.
يجب عرض stale/unknown بدلاً من الإيحاء بأن غياب السجل يعني عدم وجود الرسالة.  
**Durability:** يحتفظ local بالرسالة عند offline، ويحتاج sync recovery.  
**Latency:** لا يضيف remote dependency إلى send أو local `/link`.  
**Concurrency:** shared writer يعالج duplicate/conflict، بينما local لا يتأثر
بـ remote outage.  
**Failure handling:** Telegram success + local success + sync failure حالة
مسموحة ومعلومة؛ retry يحتاج idempotency.  
**Offline:** local outbox/queue مفاهيمياً مطلوبة إن كان sync مضموناً لاحقاً؛
لا يُفترض وجود implementation في هذا التحقيق.  
**Security/privacy:** يمكن نشر identity projection صغيرة وترك archive محلياً.  
**Scalability:** أفضل من GitHub-only، لكن GitHub يبقى محدوداً كـ shared backend.  
**Titan compatibility:** الأعلى بين النماذج التي تقدم sharing، إذا بقيت
capability خارج Core.  
**Migration:** additive من local، مع backfill ومطابقة namespace/provenance.

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
**Titan compatibility:** Core لا يحتاج معرفة المزود؛ capability خارجية.  
**Migration:** تحتاج schema/versioning وخطة import من SQLite.  
**Limit:** تضيف infrastructure كاملة قبل إثبات حجم الاستخدام والثقة المطلوبة.

### المقارنة المعمارية

لا يوجد ranking واحد مستقل عن semantics:

- إذا كان المطلوب `/link` محلياً سريعاً: **A** كافية.
- إذا كان المطلوب نشر snapshot مجتمعي ومراجعة بشرية: **B** قد تكفي بدور
  publication/audit.
- إذا كان المطلوب sharing دون تلويث lifecycle الحالي: **C** هي boundary
  الأوضح.
- إذا كان المطلوب خدمة استعلام وكتابة عالمية ذات SLA وconcurrency: **D** هي
  الفئة الصحيحة، ولو كانت أكبر من حاجة Titan الحالية.

GitHub لا يصبح **D** لمجرد أن لديه API.

---

## 7. Runtime / Telegram Send Semantics

### هل ينتظر `ctx.send()` الـ shared registry؟

لا، إذا بقي العقد الحالي مستقراً. `ctx.send()` يجب أن:

1. ينتظر Telegram.
2. لا ينشئ identity قبل نجاح Telegram.
3. يحفظ local identity بعد النجاح.
4. يعيد نتيجة Telegram حتى لو فشل remote publication.

جعل GitHub synchronous يضيف network dependency وrate limits وcommit conflict
إلى أبسط فعل في Titan، ويحوّل external outage إلى runtime behavior مخفي.

### الحالات الأساسية

| الحالة | النتيجة المعمارية المطلوبة |
|---|---|
| Telegram يفشل | لا identity محلية ولا shared identity |
| Telegram ينجح، local يفشل | الرسالة ناجحة؛ identity قد تكون مفقودة، كما في best-effort الحالي؛ يلزم observability |
| Telegram وlocal ينجحان، GitHub يفشل | الرسالة وlocal `/link` ناجحتان؛ shared state متأخرة أو pending |
| Telegram وlocal وGitHub ينجحون | shared claim منشور، لكن لا يصبح truth موثقاً دون trust model |
| retry بعد timeout | لا ينشئ duplicate؛ يحتاج key/idempotency أو deduplication |
| restart أثناء sync | يستأنف pending work إن كان هناك durable outbox؛ وإلا يبقى sync غير مضمون |
| offline period | يستمر local إن كان filesystem متاحاً؛ shared publication تتأخر |
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

- **Synchronous remote write:** غير متوافق مع بساطة وlatency Core.
- **Asynchronous durable sync:** الأكثر اتزاناً إذا ثبتت حاجة sharing؛ يحتاج
  queue/outbox وretry وdead-letter/observability كعقود مستقبلية.
- **Opportunistic sync:** أبسط وأقل ضماناً؛ مناسب لنشر غير حرج فقط.

هذا تحقيق semantics، وليس قرار implementation أو إضافة queue.

---

## 8. Data Model and Data Boundaries

### Identity

تثبت claim محدوداً: bot/runtime يقول إن message reference ارتبطت بـ Titan
identity بعد send ناجح محلياً. لا تثبت وحدها أن claim صادق أمام طرف ثالث.

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
identity” بمجرد وجود commit.

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

Hybrid يحتاج، مفاهيمياً، معرفة pending events وإمكانية إعادة إرسالها. إذا
لم توجد durable queue، فالـ opportunistic publisher لا يستطيع الوعد بـ
eventual publication بعد restart.

Retry لا ينبغي أن يكون blind:

- refetch current state عند conflict.
- تحقق من أن event لم يُقبل سابقاً.
- لا تعيد non-idempotent mutation بعد timeout دون التحقق من النتيجة.
- افصل API failure عن validation rejection وعن permission failure.

### Deletion

`mark_deleted()` الحالي tombstone محلي، وليس delete row. في shared registry:

- حذف GitHub file قد يمحو latest view لكنه لا يمحو Git history أو clones.
- نشر tombstone يحافظ على معرف identity ويمنع عودة record القديم.
- يجب أن تكون deletion state موثقة كـ observation لا ادعاء content deletion
  الكامل.

### Partial sync

قد يوجد identity محلياً ولا يوجد shared claim، أو يوجد shared claim لا يمكن
قراءته بسبب outage أو permission. `/link` الحالي لا ينبغي أن يخلط بين:

- غير موجود محلياً.
- غير منشور shared.
- shared غير متاح.
- shared stale.

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

Shared Registry capability اختيارية خارج Core تتوافق مع هذه المبادئ إذا:

- لا تغير نجاح/فشل `ctx.send()` المحلي.
- لا تجعل GitHub dependency مخفية.
- لا تغير `/link` المحلي دون contract صريح.
- لا تنشر archive أو chat metadata دون opt-in وسياسة واضحة.
- تبقى `MessageStore` abstraction قابلة للفصل، لا import مباشر لـ GitHub
  داخل Core.

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
        ↑ confirmed local identities
Optional Shared Registry capability
        ├── publisher
        ├── reader
        └── provenance/policy
```

لا يعرف Core هل backend GitHub أو خدمة أخرى. ولا يُسمى backend المشترك
“source of truth” قبل حسم trust وconsistency.

---

## 15. Contract / ADR Impact

### ما يبقى ثابتاً

إذا اختير Hybrid اختياري:

- `bot.links` يبقى public API.
- identity تُنشأ بعد نجاح `ctx.send()`/`ctx.reply()` فقط.
- `/link` لا ينشئ identity.
- `mark_deleted()` tombstone ولا يعيد استخدام `titan_id`.
- Archive opt-in.
- SQLite local default.
- `/forgetme` لا يمحو Permanent Resource Identity وفق العقد الحالي.

### ما يصبح extension

- shared read capability.
- publisher أو relay خارجي.
- sync status/observability.
- public identity projection.
- signed/provenance metadata.

### ما يحتاج ADR جديدة أو تعديل قرار

أي التزام بأن:

- كل runtime ينشر تلقائياً.
- shared registry هو source of truth.
- `/link` يقرأ remote.
- GitHub مطلوب لتشغيل Titan.
- identity public أو archive public افتراضياً.
- failure في sync يفشل send.

سيؤثر على ADR-008 وADR-018، وقد يلامس ADR-020 الخاص بطبقة ecosystem، وTimeline
وROADMAP ووثائق Message Links وpublic API.

### Breaking أم additive؟

- إضافة publisher اختياري خارج Core: **additive** إذا لم تغير السلوك الحالي.
- إضافة remote read اختياري مع `unknown/stale` semantics واضحة: غالباً
  **additive**.
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

### اختبارات مطلوبة فقط إذا اعتمدت architecture جديدة

- contract tests تفصل local identity عن remote publication.
- idempotency عند retry وtimeout.
- concurrency/conflict tests لملف أو shard مشترك.
- read-after-write وeventual consistency semantics.
- offline queue/restart/recovery.
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
Telegram. أي shared design يجب أن يحافظ على هذا الفصل أو يعلن contract جديداً
بوضوح.

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

- GitHub مناسب أكثر للنشر والمراجعة والتوزيع من hot-path registry.
- Hybrid هو boundary الأقل تلويثاً لـ Core إذا ثبتت الحاجة.
- identity projection يجب أن تنفصل عن archive/evidence/report.
- verification يحتاج trust/provenance إضافيين.
- global namespace مطلوب قبل shared lookup.

### Open question

- ما bot identity canonical عالمياً؟
- من publisher المسموح له؟
- هل السجل public أم curated/private؟
- ما freshness وavailability المطلوبان؟
- هل المطلوب publication أم query service؟
- ما retention/deletion policy؟
- ما حجم الاستخدام الفعلي الذي يبرر service منفصلة؟

---

## 20. Conclusions

### 1. هل Shared Message Links Registry قابل للتنفيذ؟

نعم، كطبقة اختيارية تفصل local runtime عن shared publication/read. لا، إذا
كان المقصود استبدال local SQLite مباشرةً بجعل كل `ctx.send()` يكتب إلى شبكة.

### 2. هل GitHub مناسب؟

مناسب لـ:

- curated public dataset صغير أو متوسط.
- PR/review/moderation.
- commits كـ provenance للتغييرات.
- snapshots وdistribution وoffline clone.
- Actions للتحقق أو بناء index محدود.

غير مناسب عادةً لـ:

- low-latency synchronous writes.
- multi-writer database semantics.
- ملايين records مع queries غنية.
- privacy-sensitive archive.
- إثبات صحة Telegram claims بمجرد commit.

### 3. ما قيود الاستخدام الآمن؟

- لا تجعل GitHub dependency في Core.
- لا تنشر chat IDs أو archive افتراضياً.
- استخدم authenticated least-privilege publishers.
- افصل public read عن write/moderation.
- عالج SHA conflicts وrate limits وtimeouts.
- اجعل duplicate/retry idempotent.
- استخدم tombstones لا delete illusion.
- لا تضع secrets في repository أو workflow logs.
- عرّف stale/unknown semantics.

### 4. هل يتحمل GitHub semantics المطلوبة؟

يتحمل publication/audit/review semantics، ولا يتحمل وحده semantics قاعدة
بيانات عالمية synchronous ذات query وconcurrency وSLA دون طبقات إضافية.

### 5. هل نحتاج local persistence/cache/queue؟

local persistence مطلوبة للحفاظ على contract الحالي. queue/outbox مطلوبة
مفاهيمياً إذا كان eventual sync مضموناً بعد restart/offline؛ أما opportunistic
publication فلا تستطيع وعداً بذلك.

### 6. ما الحدود بين Identity وArchive وEvidence وReports؟

Identity تثبت reference claim، Archive يخزن content، Evidence يدعم provenance،
وReport هو claim مجتمعي. لا ينبغي دمجها في public row واحد أو نشرها بنفس
السياسة.

### 7. ما أصغر boundary؟

Optional Shared Registry capability خارج Core، تستهلك local identities
المؤكدة وتنتج publication/read/provenance منفصلة. Core يبقى GitHub-agnostic.

### 8. ما الذي يجب إثباته قبل ADR؟

- canonical global identity/namespace.
- trust model وpublisher authorization.
- public/private data boundary.
- sync failure/idempotency/recovery semantics.
- deletion/tombstone/retention semantics.
- expected scale وquery patterns.
- هل GitHub publication كافٍ أم نحتاج service registry.
- evidence أن هناك حاجة تشغيلية تتجاوز local SQLite.

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
10. هل توجد حاجة فعلية لكتابة online أثناء `ctx.send()`، أم تكفي export/sync؟
11. هل GitHub هو distribution channel فقط، بينما registry الحقيقي خدمة أخرى؟
12. كيف يتوافق أي public deletion request مع Git history وforks؟

---

## 22. Recommended Next Investigation / Implementation Boundary

الخطوة التالية ليست كتابة GitHub backend. التحقيق التالي يجب أن يحسم، باستخدام
synthetic data فقط:

1. canonical public record وglobal namespace.
2. threat/trust model وpublisher lifecycle.
3. projection المسموح نشرها من local identity.
4. state machine لـ local success/shared pending/shared accepted/shared stale.
5. idempotency وconflict behavior.
6. deletion/tombstone/retention policy.
7. workload حقيقي: write rate، read patterns، record growth، وoffline needs.
8. قرار صريح بين:
   - GitHub publication only،
   - Hybrid مع shared read محدود،
   - service registry منفصلة.

الحد التنفيذي الذي يجب الحفاظ عليه إلى أن يثبت العكس:

```text
Titan Core
  local Message Links contract
  no GitHub import
  no remote wait in ctx.send()/ctx.reply()

Optional infrastructure
  consumes confirmed local identity
  publishes a privacy-filtered projection
  exposes explicit sync/provenance state
  may use GitHub or another backend
```

لا يوصي هذا التحقيق بإنشاء ADR أو backend أو queue الآن. القرار الصحيح حالياً
هو إبقاء Message Links محلية ومستقرة، ومتابعة التحقيق في trust وnamespace
والحاجة الفعلية قبل إضافة shared infrastructure.

---

*هذا الملف تحقيق معماري مستقل. لا يغيّر Task 5 أو ADRs أو ROADMAP أو Timeline
أو source code أو tests.*