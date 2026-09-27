# Titan Roadmap

هذا الملف هو المكان الرسمي لتتبع أفكار التطوير المستقبلية لـ Titan.

---

## كيف يعمل هذا الملف

**للمطورين الذين يريدون اقتراح ميزة:**

قبل فتح issue على GitHub، اقرأ قسم "مرفوضة بوعي" أولاً.
إذا كانت فكرتك موجودة هناك مع سبب الرفض — الرد محسوم.
إذا لم تكن موجودة — افتح issue وسنضيفها هنا بعد التقييم.

**للمشرفين:**

كل فكرة تصل عبر issue أو PR أو نقاش تُضاف لقسم "قيد الدراسة" أولاً.
لا ميزة تُضاف لـ Titan مباشرة — كل شيء يمر عبر هذا الملف.

---

## القواعد

1. **لا ميزة تُضاف بدون تحديث هذا الملف أولاً**
2. **لا ميزة تكسر CONTRACT.md** — إذا تعارضت مع العقد فهي مرفوضة تلقائياً
3. **كل رفض يُوثَّق مع سببه** — حتى لا يتكرر نفس النقاش
4. **الاستقرار أولاً** — ميزة مفيدة لكنها تزيد السطح تُؤجَّل، لا تُرفض
5. **الحجم لا يكفي مبرراً** — "مكتبات أخرى تدعمها" ليس سبباً للإضافة

---

## قيد الدراسة

أفكار وصلت ونحن نفكر فيها. لا قرار بعد.

| الفكرة | المصدر | تاريخ الإضافة |
|---|---|---|
| **Network timeout على `aiohttp.ClientSession`** — حالياً لا يوجد `ClientTimeout`، ما يعني أن طلباً معلقاً على مستوى الشبكة (ليس Telegram بل البنية التحتية) يمكن أن يتجمد إلى الأبد. تحسين داخلي لا يلمس الـ API. | مراجعة داخلية | 2026-06-27 |
| **`logging` بدلاً من `print()`** — المكتبات لا تُخرج على stdout مباشرة. `logging.getLogger("titan")` يتيح للمطور التحكم الكامل في الإخراج دون تغيير أي واجهة. | مراجعة داخلية | 2026-06-27 |
| **Traceback كامل في أخطاء الـ handlers** — حالياً يُسجَّل فقط `str(e)`. إضافة `traceback.format_exc()` تمنح المطور معلومة حقيقية عند الـ debugging دون أي تغيير في السلوك أو الـ API. | مراجعة داخلية | 2026-06-27 |
| **`on_offset` يبتلع `async def` بصمت** — إذا مرر المطور دالة async كـ `on_offset`، تُنشأ coroutine ولا تُنفَّذ أبداً بدون أي خطأ أو تحذير. يحتاج إما كشفاً صريحاً أو توثيقاً واضحاً بأنها sync فقط. | مراجعة داخلية | 2026-06-27 |
| **معالجة متوازية للتحديثات** — الفكرة مفتوحة، لكن الحل عبر `asyncio.create_task` غير معتمد لأنه يكسر قابلية التنبؤ في ترتيب التنفيذ. أي تصميم مستقبلي يجب أن يحافظ على استقرار السلوك من منظور المطور. | مراجعة داخلية | 2026-06-27 |

---

## مرشحة للإصدار القادم

أفكار تمت الموافقة عليها مبدئياً وستُضاف في إصدار قادم.
الموافقة هنا لا تعني موعداً محدداً.

| الفكرة | الإصدار المستهدف | الملاحظات |
|---|---|---|
| Inline mode | v1.x | inline_query handler — يحتاج دراسة API |

---

## مرفوضة بوعي

هذه الأفكار قُيِّمت ورُفضت بقرار واعٍ. إعادة طرحها بدون حجة جديدة لن تغير القرار.

| الفكرة | سبب الرفض |
|---|---|
| **Intent Mapping Layer** (`@bot.intent` + `bot.map`) | Python تحلها مجاناً بدوال عادية. لا قيمة مضافة تبرر طبقة جديدة في الـ contract. |
| **Member Model** (`ctx.get_member()`) | `ChatMember` في Telegram ليست بنية ثابتة — هي state machine متعدد الأشكال. أي نموذج سيكون ناقصاً أو مضللاً. البديل: `bot.telegram.get_chat_member()`. |
| **Interop / Adapter Registry** (`bot.register_adapter`) | Dict بغلاف. المطور يخزن المتغير بنفسه بسطر واحد. لا مبرر لتجميده في الـ contract. |
| **`ctx.ban()`** | مكرر مع `ctx.ban_user()`. اسمان لنفس الشيء يزيدان السطح بدون قيمة. |
| **`bot.log()` كـ public API** | Logging داخلي لا يخص المطور. أعيدت تسميته `_log()` internal. |
| **Webhook support** | يغير نموذج التشغيل بالكامل. Titan مصممة على polling. الدعم يعني تعقيداً في الـ lifecycle لا يتوافق مع فلسفة البساطة الحالية. |
| **Nested Routers** | يحول Router من أداة تنظيم إلى routing tree. هذا يضيف تعقيداً في الـ dispatch لا يعكسه المستخدم. |
| **Router Middleware** | Middleware متعلق بالبوت كله، ليس بملف واحد. الفصل يُربك ترتيب التنفيذ. |

---

## منجزة

| الميزة | الحالة | القرار | الاختبارات |
|---|---|---|---|
| **Project Health (#8)** — `bot.health()` تُرجع قائمة بالمشكلات الهيكلية والتشغيلية بثلاثة مستويات: ERROR / WARNING / INFO. لا تُصلح، تُقيّم فقط. | مكتملة — 2026-07-08 | [ADR-005](docs/decisions/005-project-health.md) | 392 اختباراً — كلها ناجحة |
| **Interactive Inspector (#1)** — `bot.inspect()` تُرجع `BotSnapshot` (frozen dataclass): أسماء الأوامر والـ callbacks، عدد handlers لكل حدث، عدد الـ middleware، وجود error handler، عدد الـ routers، توفر capabilities. Inspector يصف ولا يُقيّم. | مكتملة — 2026-07-08 | [ADR-006](docs/decisions/006-interactive-inspector.md) | 435 اختباراً — كلها ناجحة |
| **Migration Assistant (#2)** — طبقتان: `docs/migration/` (أدلة انتقال فلسفية من PTB/aiogram/telebot) + `titan.migration` Knowledge API (frameworks(), concepts(), compare() → ConceptMapping). الـ API ليست فقط لمساعدة الانتقال — هي **قاعدة معرفة عامة** يمكن أن تستخدمها Architect AI وRuntime hints ومولدات التوثيق وأي أداة ذكية مستقبلاً. الـ API تبقى صغيرة ومركزة — أي وظيفة جديدة تنتظر حاجة حقيقية. Version Migration وCLI Scanner مؤجلان. | مكتملة — 2026-07-09 | [ADR-007](docs/decisions/007-migration-assistant.md) | 480 اختباراً — كلها ناجحة |
| **Message Links Protocol (#0)** — كل رسالة يُرسلها البوت عبر `ctx.send()` أو `ctx.reply()` تحصل على هوية دائمة وعنوان قابل للمشاركة. `TitanMessageAddress` (رابط `https://t.me/{bot}/{id}`)، `TitanMessageIdentity` (سجل قابل للتعديل)، `SqliteMessageStore` (تخزين كسول)، `LinksManager` (API العامة)، `/link` command محجوزة داخلياً. الهوية تُسجَّل فقط بعد إرسال ناجح مؤكد عبر هذين المسارين. | مكتملة — 2026-07-10 | [ADR-008](docs/decisions/008-message-links-protocol.md) | 560 اختباراً — كلها ناجحة |
| **Runtime Contract Validator (#4)** — أي handler أو middleware أو error handler مُسجَّل بتوقيع خاطئ (غير async أو عدد parameters خاطئ) يرفض فوراً بـ TitanError عند تنفيذ الـ decorator — أثناء تحميل الملف، قبل `bot.run()`. رسائل الخطأ موجهة للمطور مع التوقيع الصحيح. Callable objects بـ `async __call__` مدعومة. البنية قابلة للتوسع عبر `_validate_contract()` المشترك. | مكتملة — 2026-07-10 | [ADR-009](docs/decisions/009-runtime-contract-validator.md) | 640 اختباراً — كلها ناجحة |
| **Architectural Timeline (#8)** — `titan.timeline`: الذاكرة المعمارية لـ Titan، مُعرَّضة برمجياً. `ArchiveEntry` (frozen dataclass، عامة بما يكفي لاستيعاب أنواع إدخالات مستقبلية غير ADR) + API صغيرة: `entries()`, `entry()`, `by_status()`, `latest()`, `rules()`. `_data.py` مصدر الحقيقة الوحيد — لا runtime parsing لـ Markdown. `docs/decisions/README.md` يُولَّد منه عبر `scripts/generate_decisions_readme.py`، لا العكس. `by_tag()` مؤجَّلة بوعي — لا مستهلك فعلي بعد. فحص الاتساق بين `_data.py` والملفات الفعلية (CI) خارج نطاق v1 — يتبع لـ Project Health / CI tooling، لا لـ Timeline نفسها. | مكتملة — 2026-07-10 | [ADR-010](docs/decisions/010-timeline.md) | 674 اختباراً — كلها ناجحة |
| **Playground (#5)** — `titan.playground`: مختبر معماري تفاعلي (ليس sandbox كود). `Titan.feed_update()` قدرة Core جديدة (مدخل أحداث رسمي غير مرتبط بـ polling) — تفويض مباشر إلى `_handle_update` بدون أي منطق مكرر أو خاص بـ Playground. `RecordingTelegram` بديل duck-typed معزول داخل الحزمة يطبّق فقط الطرق التي يستدعيها `Context` فعلياً، ويفشل بوضوح (`AttributeError`) لأي طريقة غير مدعومة. `factory.py`: `fake_message`, `fake_command`, `fake_callback` فقط. غير مُصدَّرة من الجذر — الاستيراد صريح دائماً من `titan.playground`. | مكتملة — 2026-07-10 | [ADR-011](docs/decisions/011-playground.md) | 686 اختباراً — كلها ناجحة |
| **Design Linter (#6)** — `bot.lint()` قدرة Core تُكمل الثلاثية: inspect (وصف) + health (سلامة) + lint (فلسفة). `LintFinding` نوع مستقل مع `hint` إلزامي — Linter يُعلّم لا يُعاقب. 5 قواعد في v1: 3أ وقت التسجيل (LINT_001 command lowercase، LINT_002 callback_data غير فارغة، LINT_003 on_offset غير async) + 3ب حالة مجمّعة (LINT_010 router فارغ، LINT_011 fan-out > 10). لا AST داخل `src/titan/` — `titan-lint` مستقبلية منفصلة. | مكتملة — 2026-07-11 | [ADR-012](docs/decisions/012-design-linter.md) | 720 اختباراً — كلها ناجحة |
| **Titan Atlas (#9)** — طبقة المعرفة المعمارية لـ Titan (`titan.atlas`). تفهم قرارات المشروع، تعرض فلسفته، وتجعل المطورين والأدوات يفهمون لماذا أصبح Titan كما هو. ليست chatbot ولا LLM wrapper — deterministic knowledge layer فوق `titan.timeline`. أربع دوال عامة: `search()`, `explain()`, `rules()`, `decisions()`. غير مُصدَّرة من جذر الحزمة. | مكتملة — 2026-07-12 | [ADR-014](docs/decisions/014-architect-ai.md) | 831 اختباراً — كلها ناجحة |
| **Performance Profiler (#7)** — `titan.profiler`: أداة تطوير تقيس wall time لكل update في بيئة محكومة. تبني فوق `feed_update()` + `titan.playground`. لا تعديلات في Core. `profile_update(bot, fake_command("start"), n=100)` → `ProfilingSession` مع `summary()`. | مكتملة | [ADR-013](docs/decisions/013-performance-profiler.md) | 36 اختباراً — كلها ناجحة |
| **User Privacy & Erasure Protocol (#11)** — بروتوكول معماري شامل لدورة حياة User Data في Titan. ثلاثة أجناس من البيانات محدَّدة بوضوح (Transient / Permanent Resource Identity / User Data). `UserDataRegistry` المصدر الوحيد للحقيقة. `UserDataModule` Protocol بأربعة أعضاء إلزامية. `bot.enable_ask()` نقطة الربط الرسمية لـ AskManager. `/mydata` و`/forgetme` محجوزتان في كل بوت Titan. التقرير مُجمَّد عميقاً (MappingProxyType recursive). `bot.declare_user_data()` للـ modules الخارجية. الفصل بين First-party وThird-party مُطبَّق. | مكتملة — 2026-07-20 | [ADR-015](docs/decisions/015-data-lifecycle-responsibility.md) · [ADR-016](docs/decisions/016-user-data-registry.md) · [ADR-017](docs/decisions/017-reserved-privacy-commands.md) | 885 اختباراً — كلها ناجحة |
| **GitHub Actions / CI** — workflow يعمل على كل push وPR، يشغّل الاختبارات على Python 3.10–3.12، ويبني wheel وsdist ويتحقق من وجود `py.typed` داخل wheel. | مكتملة | `.github/workflows/ci.yml` | pytest + packaging check |

---

## ميزات مخططة — قيد التحقيق المعماري

هذه الميزات مُعتمدة للتحقيق. لا تنفيذ قبل إنهاء كل مرحلة:
**تحقيق → ADR → تنفيذ → اختبارات → مراجعة كود → إغلاق.**

| الميزة | الحالة | الملاحظات |
|---|---|---|
| **Read-only Runtime Registries** — هل `bot.commands` / `bot.handlers` / `bot.callback_handlers` يجب أن تصبح read-only (property + `MappingProxyType`) أم تبقى public-by-design مع توثيق فقط (القرار الحالي في CONTRACT §1)؟ سؤال API design مستقل، وليس "إصلاحاً جانبياً" — أي حماية كاملة هي breaking change تستحق ADR مستقلة. لا استعجال، ولا تُنفَّذ قبل الإطلاق. | قيد الدراسة — لا قرار قبل الإطلاق | خلفية القرار: `docs/internal/investigations/silent-failures.md` (SF-03) |

---

## مؤجلة بوعي

أفكار قُيِّمت وتبيَّن أنها صحيحة في مبدئها، لكن الوقت لم ينضج لتنفيذها.
التأجيل ليس رفضاً — هو قرار توقيت.

| الفكرة | سبب التأجيل | شرط الرجوع إليها |
|---|---|---|
| **Userbot Support (#10)** — دعم سطحَي تفاعل Telegram: Bot API + MTProto (Userbot-style accounts)، ضمن إطار واحد بمسار معالجة واحد (Unified Telegram Surface). أكبر قرار معماري منذ إنشاء Titan. التحقيق المعماري الأولي مكتمل في `docs/internal/investigations/userbot-support.md`، والاتجاه المبدئي (Unified Telegram Surface) مختار، لكن لا ADR ولا كود. | قرار تأجيل واعٍ — 2026-07-15. لا حاجة عملية حقيقية داخل Titan حالياً، ولا طلب كافٍ من المستخدمين أو المساهمين. التركيز يعود لـ Titan Core والخارطة الحالية. لا يُستكمل أي كود أو تجريد أو تحضير معماري متعلق بـ Userbot حتى يتحقق شرط الرجوع. | يُعاد النظر إذا تحقق أحد: (1) حاجة عملية حقيقية داخل Titan نفسها، (2) طلب واضح من المستخدمين أو المساهمين، (3) أصبح هدفاً مخططاً لـ Titan v2. |
| **Timeline ↔ Docs Consistency Check (CI)** — فحص آلي يتأكد أن `titan.timeline._data.py` متسق مع `docs/decisions/README.md` (لم يُنسَ تشغيل السكربت بعد إضافة ADR جديد) | خارج نطاق `titan.timeline` v1 عمداً — Timeline مسؤولة عن حفظ وعرض الذاكرة المعمارية فقط. مراقبة الاتساق واكتشاف الانحرافات مسؤولية Project Health / CI tooling، لا الميزة نفسها. لا مستهلك فعلي يطلبها الآن. | يُعاد النظر عند إضافة فحوصات مستوى-مشروع (project-level، لا bot-level) إلى `bot.health()` أو أداة CI مستقلة. |
| **Version Migration Assistant** — أداة تساعد المطورين على ترقية بوتاتهم بين إصدارات Titan المختلفة عند وجود breaking changes | Titan لا يملك v2 بعد — لا مشكلة حقيقية تُحل الآن. Framework Migration (v1) أولى. | يُعاد النظر عند صدور Titan v2 مع breaking changes موثقة. |
| **Migration CLI / Code Scanner** — أداة تفحص مشروعاً بـ PTB أو aiogram وتقترح التحويل تلقائياً (`titan migrate project/`) | تعني بناء "مترجم لغات برمجية مصغر" قبل أن يثبت Titan نفسه. المشكلة الحقيقية في v1 هي الفهم، لا الأتمتة. | يُعاد النظر عند وجود مجتمع نشط يحتاج الأتمتة بالفعل. |

---

## سلوكيات صامتة — أُغلقت المرحلة

مرحلة Silent Failures أُغلقت. القرارات النهائية موثَّقة في
`docs/internal/investigations/silent-failures.md` و`CHANGELOG.md`.

| الأمر | القرار النهائي | الحالة |
|---|---|---|
| **Alias يُلغي ctx attribute موجودة بصمت** | Fail Fast في `AliasMap.register()` — `TitanError` فوري عند التعارض | مُنفَّذ — 2026-07-12 |
| **Middleware تُرجع قيمة بصمت** | تحذير runtime في `MiddlewareChain.run()` عند إرجاع قيمة غير `None` — لا استثناء، لا تغيير في تحكم التدفق | مُنفَّذ — 2026-07-12 |
| **`bot.commands` / `bot.handlers` / `bot.callback_handlers` مكشوفة للكتابة المباشرة** | لا حماية برمجية الآن — نُقلت لسؤال API design مستقل | انظر "Read-only Runtime Registries" أعلاه |
| **`get_me()` عند startup يُبتلع بصمت** | تحذير بدلاً من `except: pass` — البدء يستمر بعده | مُنفَّذ — 2026-07-12 |

---

## تحسينات جودة داخلية — غير مُعلّقة على الإطلاق

| الفكرة | الملاحظة |
|---|---|
| **Test Isolation Improvement (#12)** — بعض اختبارات import-time (`test_inspector.py`, `test_migration.py`) تمسح `sys.modules` لكل مفتاح يحتوي "titan" أثناء التشغيل، ما يُفسد أي `unittest.mock.patch("titan.module.attr")` بمسار نصي يُنفَّذ بعدها في نفس الجلسة (يُصبح no-op صامتاً). لا يؤثر على المستخدم، لكن مع نمو المشروع (831 اختباراً وتزيد) هذا النوع من التلوث يصبح مزعجاً. | تحسين مستقل لاحقاً — لا يوقف أي إصدار |

---

## ملاحظة للمساهمين

Titan لا تتنافس في سباق الميزات.

إذا كانت مكتبة أخرى تدعم ما تريد ولا تدعمه Titan — هذا قد يكون **قراراً واعياً** وليس نقصاً.

اقرأ [CONTRACT.md](CONTRACT.md) قبل أي مساهمة.
