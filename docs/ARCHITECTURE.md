# معماری و تصمیم‌های طراحی

## ۱. از سیستم عملیاتی تا انبار داده

| مفهوم | در این پروژه |
|---|---|
| **TPS / Operational Database** | SQL Server، پایگاه داده `Students` با عملیات `INSERT / UPDATE / DELETE` که از طریق پنل Blazor انجام می‌شود |
| **Data Source** | همان پایگاه داده رابطه‌ای؛ لاگین `etl_reader` فقط دسترسی خواندن و دسترسی به جدول‌های تغییر CDC دارد |
| **Staging** | PostgreSQL، اسکیمای `stg`: کپی خام، بدون Constraint و برچسب‌خورده با `_batch_id` |
| **DW / Information Source (OLAP)** | ClickHouse، پایگاه داده `students_dw` با مدل ابعادی |
| **Presentation Sub-System** | Grafana برای پایش و Blazor PWA برای گزارش و کاربر نهایی |

گزارش‌های عملیاتی (SSRS، Crystal Report) مستقیماً روی پایگاه داده عملیاتی اجرا می‌شوند. داشبوردهای تحلیلی (Power BI، Grafana) روی انبار داده اجرا می‌شوند تا بار تحلیلی روی سیستم تراکنشی نیفتد. پنل این پروژه هر دو را نشان می‌دهد: CRUD روی SQL Server و تحلیل روی ClickHouse.

## ۲. ویژگی‌های انبار داده از دید Bill Inmon

| ویژگی | پیاده‌سازی |
|---|---|
| **Subject-Oriented** | مدل حول موضوع‌های کسب‌وکار ساخته شده است: ثبت‌نام درس (`fact_enrollment`)، پذیرش (`fact_application`) و ظرفیت کلاس (`fact_course_offering`)، نه حول جدول‌های سیستم عملیاتی |
| **Integrated** | کدها یکپارچه و رمزگشایی شده‌اند (وضعیت، جنسیت، نوع درخواست)، برچسب‌ها دوزبانه‌اند، دانشکده و منطقه جغرافیایی اضافه شده‌اند و متقاضی و دانشجو با ایمیل و تاریخ تولد به هم وصل می‌شوند |
| **Time-Variant** | `dim_date` با تقویم میلادی و شمسی، `dim_term` با کلید زمانی، و SCD2 با `valid_from` / `valid_to` |
| **Non-Volatile** | هیچ ردیفی Update یا Delete فیزیکی نمی‌شود. هر تغییر یک نسخه جدید با `row_version` بزرگ‌تر است (ReplacingMergeTree) و حذف به صورت `is_deleted = 1` ثبت می‌شود. تاریخچه حفظ می‌شود |

## ۳. مدل ابعادی (Kimball)

مدل از طراحی SQL Server پروژه (`StudentsDW`) به ClickHouse منتقل شده است.

- **Dimensionها:** `dim_date`، `dim_term` (کلید هوشمند `year*10+order`)، `dim_department`، `dim_course`، `dim_degree`، `dim_class_standing`، `dim_grade`، `dim_application_profile` (Junk)، `dim_applicant` (SCD1)، `dim_student` (SCD2 + Type 1)
- **Factها:** `fact_enrollment` (Transaction)، `fact_application` (Transaction)، `fact_course_offering` (Periodic Snapshot)
- **اعضای ویژه:** `-1 = Unknown` و `-2 = Not applicable`، بنابراین هیچ کلید Fact خالی نیست
- **سنجه‌ها:** Flagها به صورت ۰/۱ ذخیره می‌شوند تا جمع‌پذیر باشند. نسبت‌ها (معدل، نرخ پرشدگی) هنگام تجمیع از اجزای جمع‌پذیر محاسبه می‌شوند
- **لایه معنایی:** `v_*` حالت جاری و یکتا (FINAL و فیلتر حذف نرم) و `rpt_*` نماهای آماده گزارش

## ۴. دو روش پیاده‌سازی لایه Transformation

### ۴-۱. روش Batch با SCD (Airflow + Spark → PostgreSQL → ClickHouse)

```
register_batch → extract_to_staging → validate_staging → load_dimensions → load_facts → reconcile → close_batch
```

1. **استخراج:** Spark همه جدول‌ها را با JDBC از SQL Server می‌خواند و در `stg.*` بازنویسی می‌کند. جدول‌های حجیم به صورت موازی و با تقسیم روی کلید Identity خوانده می‌شوند.
2. **کیفیت داده:** ۱۵ قاعده شامل یکتایی کلید، Orphan، دامنه مقادیر و سازگاری ترم اجرا می‌شود. قواعد `error` اجرا را متوقف می‌کنند و قواعد `warning` فقط ثبت می‌شوند.
3. **تشخیص تغییر:** برای هر ردیف Hash محاسبه و با نسخه موجود در انبار مقایسه می‌شود. این روش شناسایی تغییر بر اساس Snapshot است و به CDC نیاز ندارد.
4. **SCD:**
   - **Type 1** برای `dim_applicant` و Dimensionهای مرجع: بازنویسی همان کلید
   - **Type 2** برای `dim_student` روی شهر، ایالت، کد پستی، رشته، سال تحصیلی و وضعیت: نسخه جدید با کلید جایگزین جدید، و بستن نسخه قبلی (`is_current = 0`، `valid_to`)
   - **Type 1 روی Dimension نوع ۲** (نام، ایمیل، تاریخ تولد): اصلاح روی همه نسخه‌های تاریخی اعمال می‌شود
   - حذف در مبدأ به صورت حذف نرم ثبت می‌شود
5. **Fact افزایشی:** فقط ردیف‌های جدید یا تغییرکرده نوشته می‌شوند. کلیدهای Dimension یک تراکنش قدیمی حفظ می‌شوند تا به نسخه‌ای که هنگام وقوع رویداد جاری بوده اشاره کنند، مگر اینکه `-1` باشند. در این حالت هر اجرا دوباره تلاش می‌کند آن‌ها را resolve کند (Late-arriving dimension).

### ۴-۲. روش Near Real-Time با CDC (Debezium + Kafka + Spark Streaming)

1. CDC در SQL Server روی `Students`، `CourseEnrollments`، `CourseOfferings` و `Applicants` فعال است.
2. Debezium با `snapshot.mode = no_data` فقط تغییرات بعد از شروع را منتقل می‌کند، چون بارگذاری اولیه مسئولیت مسیر Batch است.
3. Spark Structured Streaming هر ۵ ثانیه یک Micro-batch را پردازش می‌کند. رویدادها بر اساس کلید اصلی به آخرین تصویر کاهش می‌یابند، به شکل Staging تبدیل می‌شوند و **به همان توابع SCD و Fact مسیر Batch** داده می‌شوند.
4. تأخیر انتها به انتها (از Commit در SQL Server تا اعمال در ClickHouse) برای هر رویداد در `cdc_event_log` ثبت و در Grafana و پنل نمایش داده می‌شود.

### ۴-۳. هم‌زیستی دو مسیر

| مسئله | راه‌حل |
|---|---|
| Batch داده قدیمی‌تر از CDC را بازنویسی نکند | `row_version` برای Batch برابر زمان شروع استخراج و برای CDC برابر زمان Commit است. هر تغییر فقط وقتی اعمال می‌شود که نسخه آن جدیدتر باشد |
| برخورد کلید جایگزین بین دو مسیر | کلیدها به صورت بلوک‌های پیوسته از Sequenceهای PostgreSQL (`control.*_key_seq`) و با Advisory Lock تخصیص داده می‌شوند |
| اجرای مجدد (Idempotency) | اجرای دوباره یک Batch یا Micro-batch تغییری ایجاد نمی‌کند، چون Hash و نسخه برابرند |
| Update در موتور ستونی | ReplacingMergeTree: تغییر یعنی درج نسخه جدید. عملیات مجموعه‌ای (بستن نسخه، حذف نرم، انتشار Type 1) با `INSERT … SELECT` داخل خود ClickHouse انجام می‌شود |

## ۵. امنیت و عملیات

- لاگین‌های جدا با حداقل دسترسی: `etl_reader` فقط خواندن و CDC، `portal_app` خواندن و نوشتن بدون دسترسی به CDC
- پنل: هش رمز با PBKDF2 (ASP.NET Core Identity)، JWT همراه با Session Stamp (هر حساب یک نشست فعال دارد)، Rate Limit روی ورود، نقش‌های Admin و User
- پرس‌وجوهای ClickHouse همگی پارامتری هستند و با `readonly=2` اجرا می‌شوند
- لاگ مراحل (`etl_step_log`)، نتایج کیفیت داده (`dq_result`) و تله‌متری CDC در خود انبار داده ذخیره می‌شوند
