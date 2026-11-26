using System.Globalization;
using System.Text;

namespace StudentsPortal.Client.Services;

public sealed class I18n
{
    private static readonly PersianCalendar Persian = new();
    private static readonly string[] PersianMonths =
        ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"];

    public string Language { get; private set; } = "fa";
    public bool IsFa => Language == "fa";
    public string Dir => IsFa ? "rtl" : "ltr";
    public event Action? Changed;

    public string this[string key] => Texts.TryGetValue(key, out var t) ? (IsFa ? t.Fa : t.En) : key;

    public string Format(string key, params object[] args)
        => string.Format(CultureInfo.InvariantCulture, this[key], args.Select(a => a is IFormattable f && a is not DateTime
            ? Digits(f.ToString(null, CultureInfo.InvariantCulture)) : a).ToArray());

    public void SetLanguage(string language)
    {
        var next = language == "en" ? "en" : "fa";
        if (next == Language) return;
        Language = next;
        Changed?.Invoke();
    }

    public string Pick(string? en, string? fa) => IsFa && !string.IsNullOrWhiteSpace(fa) ? fa! : en ?? fa ?? "";

    public string N(double? value, int decimals = 0)
    {
        if (value is null || double.IsNaN(value.Value)) return "—";
        var text = value.Value.ToString("N" + decimals, CultureInfo.InvariantCulture);
        return IsFa ? Digits(text.Replace(",", "٬").Replace(".", "٫")) : text;
    }

    public string N(long value) => N((double)value);
    public string N(int value) => N((double)value);

    public string Pct(double? value, int decimals = 1) => value is null ? "—" : (IsFa ? "٪" : "") + N(value, decimals) + (IsFa ? "" : "%");

    public string Digits(string text)
    {
        if (!IsFa) return text;
        var sb = new StringBuilder(text.Length);
        foreach (var c in text) sb.Append(c is >= '0' and <= '9' ? (char)('۰' + (c - '0')) : c);
        return sb.ToString();
    }

    public string Date(DateTime? value)
    {
        if (value is null || value.Value.Year >= 2299) return "—";
        var d = value.Value.Kind == DateTimeKind.Utc ? value.Value.ToLocalTime() : value.Value;
        return IsFa
            ? Digits($"{Persian.GetYear(d):0000}/{Persian.GetMonth(d):00}/{Persian.GetDayOfMonth(d):00}")
            : d.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
    }

    public string DateTimeText(DateTime? value)
    {
        if (value is null || value.Value.Year >= 2299) return "—";
        var d = value.Value.Kind == DateTimeKind.Utc ? value.Value.ToLocalTime() : value.Value;
        return Date(d) + " " + Digits(d.ToString("HH:mm:ss", CultureInfo.InvariantCulture));
    }

    public string LongDate(DateTime value)
        => IsFa ? Digits($"{Persian.GetDayOfMonth(value)} {PersianMonths[Persian.GetMonth(value) - 1]} {Persian.GetYear(value)}")
                : value.ToString("d MMMM yyyy", CultureInfo.InvariantCulture);

    public string Ago(DateTime? value)
    {
        if (value is null) return this["never"];
        var span = DateTime.UtcNow - (value.Value.Kind == DateTimeKind.Local ? value.Value.ToUniversalTime() : value.Value);
        if (span.TotalSeconds < 60) return Format("ago_seconds", Math.Max(0, (int)span.TotalSeconds));
        if (span.TotalMinutes < 60) return Format("ago_minutes", (int)span.TotalMinutes);
        if (span.TotalHours < 24) return Format("ago_hours", (int)span.TotalHours);
        return Format("ago_days", (int)span.TotalDays);
    }

    public string Status(string? code) => code switch
    {
        "A" => this["status_active"], "G" => this["status_graduated"], "W" => this["status_withdrawn"], _ => code ?? "—",
    };

    public string Error(string? code) => code is null ? "" : this["err_" + code];

    private static readonly Dictionary<string, (string En, string Fa)> Texts = new()
    {
        ["app_name"] = ("Students Data Platform", "سامانه داده دانشجویان"),
        ["app_tagline"] = ("Operational records and analytics in one place", "مدیریت داده‌های عملیاتی و تحلیلی در یک سامانه"),
        ["nav_operations"] = ("Operations", "عملیات"),
        ["nav_analytics"] = ("Analytics", "تحلیل"),
        ["nav_platform"] = ("Platform", "زیرساخت"),
        ["nav_account"] = ("Account", "حساب کاربری"),
        ["nav_dashboard"] = ("Dashboard", "داشبورد"),
        ["nav_students"] = ("Students", "دانشجویان"),
        ["nav_applicants"] = ("Applicants", "متقاضیان"),
        ["nav_offerings"] = ("Course offerings", "ارائه دروس"),
        ["nav_enrollments"] = ("Enrollments", "ثبت‌نام دروس"),
        ["nav_live"] = ("Live CDC", "تغییرات زنده (CDC)"),
        ["nav_pipeline"] = ("Pipelines & quality", "پایپ‌لاین و کیفیت داده"),
        ["nav_users"] = ("Manage users", "مدیریت کاربران"),
        ["nav_profile"] = ("My panel", "پنل من"),
        ["sign_out"] = ("Sign out", "خروج"),
        ["dark_mode"] = ("Dark", "تیره"),
        ["light_mode"] = ("Light", "روشن"),
        ["language"] = ("Language", "زبان"),
        ["switch_language"] = ("فارسی", "English"),
        ["role_Admin"] = ("Administrator", "مدیر سیستم"),
        ["role_User"] = ("Analyst", "کارشناس"),
        ["menu"] = ("Menu", "منو"),
        ["offline"] = ("You are offline. Showing the cached application shell.", "اتصال برقرار نیست؛ نسخه ذخیره‌شده برنامه نمایش داده می‌شود."),

        ["search"] = ("Search", "جستجو"),
        ["clear"] = ("Clear", "پاک کردن"),
        ["clear_filters"] = ("Clear filters", "حذف فیلترها"),
        ["insert"] = ("Insert", "افزودن"),
        ["update"] = ("Update", "ویرایش"),
        ["delete"] = ("Delete", "حذف"),
        ["save"] = ("Save", "ذخیره"),
        ["cancel"] = ("Cancel", "انصراف"),
        ["select"] = ("Select", "انتخاب"),
        ["history"] = ("History", "تاریخچه"),
        ["refresh"] = ("Refresh", "بروزرسانی"),
        ["loading"] = ("Loading…", "در حال بارگذاری…"),
        ["no_records"] = ("No records found.", "رکوردی یافت نشد."),
        ["all"] = ("All", "همه"),
        ["none"] = ("None", "هیچ‌کدام"),
        ["optional"] = ("optional", "اختیاری"),
        ["page_of"] = ("Page {0} of {1}", "صفحه {0} از {1}"),
        ["showing"] = ("{0} records", "{0} رکورد"),
        ["previous"] = ("Previous", "قبلی"),
        ["next"] = ("Next", "بعدی"),
        ["yes"] = ("Yes", "بله"),
        ["no"] = ("No", "خیر"),
        ["confirm_delete"] = ("Delete record #{0}? This cannot be undone.", "رکورد شماره {0} حذف شود؟ این عمل قابل بازگشت نیست."),
        ["saved"] = ("Saved successfully.", "با موفقیت ذخیره شد."),
        ["deleted"] = ("Deleted successfully.", "با موفقیت حذف شد."),
        ["saved_cdc"] = ("Saved. The change reaches the warehouse through CDC within seconds.", "ذخیره شد. این تغییر از طریق CDC ظرف چند ثانیه به انبار داده می‌رسد."),
        ["read_only"] = ("Read-only access: editing requires the administrator role.", "دسترسی فقط‌خواندنی: ویرایش نیازمند نقش مدیر سیستم است."),
        ["never"] = ("never", "هنوز انجام نشده"),
        ["ago_seconds"] = ("{0}s ago", "{0} ثانیه پیش"),
        ["ago_minutes"] = ("{0} min ago", "{0} دقیقه پیش"),
        ["ago_hours"] = ("{0} h ago", "{0} ساعت پیش"),
        ["ago_days"] = ("{0} days ago", "{0} روز پیش"),
        ["source_batch"] = ("Batch", "دسته‌ای"),
        ["source_cdc"] = ("CDC", "CDC"),
        ["source_seed"] = ("Seed", "پیش‌فرض"),
        ["id"] = ("ID", "شناسه"),
        ["actions"] = ("Actions", "عملیات"),
        ["status"] = ("Status", "وضعیت"),
        ["details"] = ("Details", "جزئیات"),
        ["jalali_hint"] = ("Solar Hijri: {0}", "معادل شمسی: {0}"),

        ["err_required"] = ("This field is required.", "تکمیل این فیلد الزامی است."),
        ["err_invalid"] = ("The value is not valid.", "مقدار وارد شده معتبر نیست."),
        ["err_too_long"] = ("The value is too long.", "مقدار وارد شده بیش از حد طولانی است."),
        ["err_out_of_range"] = ("The value is out of range.", "مقدار خارج از بازه مجاز است."),
        ["err_duplicate"] = ("A record with the same key already exists.", "رکوردی با همین کلید وجود دارد."),
        ["err_weak_password"] = ("Use 10 to 128 characters.", "رمز عبور باید بین ۱۰ تا ۱۲۸ کاراکتر باشد."),
        ["err_wrong_password"] = ("The current password is incorrect.", "رمز عبور فعلی صحیح نیست."),
        ["err_cannot_demote_self"] = ("You cannot deactivate or demote your own account.", "امکان غیرفعال‌سازی یا تغییر نقش حساب خودتان وجود ندارد."),
        ["err_invalid_credentials"] = ("Invalid username or password.", "نام کاربری یا رمز عبور نادرست است."),
        ["err_reference_missing"] = ("A referenced record (student, course or term) does not exist.", "رکورد مرجع (دانشجو، درس یا ترم) وجود ندارد."),
        ["err_has_dependents"] = ("This record is referenced by other records and cannot be deleted.", "این رکورد توسط رکوردهای دیگر استفاده شده و قابل حذف نیست."),
        ["err_constraint"] = ("The source database rejected the values.", "پایگاه داده مبدأ مقادیر را نپذیرفت."),
        ["err_validation"] = ("Please correct the highlighted fields.", "لطفاً فیلدهای مشخص‌شده را اصلاح کنید."),
        ["err_warehouse_unavailable"] = ("The data warehouse is not reachable yet. The first load may still be running.", "انبار داده هنوز در دسترس نیست؛ ممکن است بارگذاری اولیه در حال اجرا باشد."),
        ["err_source_unavailable"] = ("The operational database is not reachable.", "پایگاه داده عملیاتی در دسترس نیست."),
        ["err_unexpected"] = ("Something went wrong. Please try again.", "خطایی رخ داد؛ لطفاً دوباره تلاش کنید."),
        ["err_network"] = ("The server could not be reached.", "ارتباط با سرور برقرار نشد."),
        ["err_forbidden"] = ("You do not have permission for this action.", "مجوز انجام این عملیات را ندارید."),
        ["err_not_found"] = ("The record was not found.", "رکورد یافت نشد."),
        ["err_rate_limited"] = ("Too many attempts. Please wait a minute.", "تعداد تلاش‌ها زیاد است؛ یک دقیقه صبر کنید."),

        ["login_title"] = ("Sign in", "ورود به سامانه"),
        ["login_subtitle"] = ("Use the account provided by your administrator.", "با حساب کاربری که مدیر سیستم در اختیار شما گذاشته وارد شوید."),
        ["username"] = ("Username", "نام کاربری"),
        ["password"] = ("Password", "رمز عبور"),
        ["sign_in"] = ("Sign in", "ورود"),
        ["login_footer"] = ("SQL Server · Kafka · Spark · Airflow · PostgreSQL · ClickHouse", "SQL Server · Kafka · Spark · Airflow · PostgreSQL · ClickHouse"),
        ["login_heading"] = ("Sign in to your account", "ورود به حساب کاربری"),
        ["keep_signed_in"] = ("Keep me signed in", "مرا به خاطر بسپار"),
        ["show_password"] = ("Show password", "نمایش رمز عبور"),
        ["hide_password"] = ("Hide password", "پنهان کردن رمز عبور"),
        ["features_title"] = ("What this platform does", "امکانات سامانه"),
        ["feature_1"] = ("Manage students, applicants, course offerings and enrollments in the operational database.",
                         "مدیریت دانشجویان، متقاضیان، ارائه دروس و ثبت‌نام‌ها در پایگاه داده عملیاتی."),
        ["feature_2"] = ("Every change reaches the data warehouse within seconds through change data capture.",
                         "رسیدن هر تغییر به انبار داده در چند ثانیه از طریق ثبت تغییرات (CDC)."),
        ["feature_3"] = ("Nightly batch loads keep the full history with slowly changing dimensions.",
                         "بارگذاری دسته‌ای شبانه با حفظ کامل تاریخچه به روش ابعاد کندتغییر (SCD)."),
        ["feature_4"] = ("Analytical dashboards for enrollment, GPA, class capacity and admissions.",
                         "داشبوردهای تحلیلی ثبت‌نام، معدل، ظرفیت کلاس‌ها و پذیرش."),
        ["feature_5"] = ("Pipeline monitoring with data quality rules and reconciliation.",
                         "پایش پایپ‌لاین‌ها همراه با قواعد کیفیت داده و تطبیق رکوردها."),
        ["feature_6"] = ("Persian and English interface, Jalali calendar, installable as an app.",
                         "رابط فارسی و انگلیسی، تقویم شمسی و قابل نصب به‌صورت اپلیکیشن."),
        ["guide_title"] = ("Platform guide", "راهنمای سامانه"),
        ["guide_button"] = ("Guide", "راهنما"),
        ["guide_intro"] = ("This panel sits on top of a complete data engineering pipeline. Records you edit here are written to the operational database (SQL Server) and reach the ClickHouse data warehouse by two paths: change data capture within seconds, and a nightly batch that maintains the full history.",
                           "این پنل روی یک زنجیره کامل مهندسی داده قرار دارد. رکوردهایی که اینجا ویرایش می‌کنید در پایگاه داده عملیاتی (SQL Server) ذخیره می‌شوند و از دو مسیر به انبار داده ClickHouse می‌رسند: ثبت تغییرات (CDC) در چند ثانیه، و بارگذاری دسته‌ای شبانه که تاریخچه کامل را نگه می‌دارد."),
        ["guide_sec_analytics"] = ("Analytics", "تحلیل"),
        ["guide_dashboard"] = ("Warehouse indicators and charts, filtered by degree and entry term.", "شاخص‌ها و نمودارهای انبار داده با فیلتر رشته و ترم ورود."),
        ["guide_live"] = ("Every change event with its end-to-end latency, refreshed every three seconds.", "همه رویدادهای تغییر با تأخیر انتها به انتها، با به‌روزرسانی هر سه ثانیه."),
        ["guide_pipeline"] = ("Nightly batch runs, their steps and the data quality results.", "اجراهای دسته‌ای شبانه، مراحل هر اجرا و نتیجه کنترل کیفیت داده."),
        ["guide_sec_operations"] = ("Operations", "عملیات"),
        ["guide_crud"] = ("Insert, update and delete operational records. Editing is available to administrators.", "درج، ویرایش و حذف رکوردهای عملیاتی. ویرایش برای مدیران سیستم فعال است."),
        ["guide_history"] = ("Each student's warehouse versions (SCD Type 2) next to the operational record.", "نسخه‌های هر دانشجو در انبار داده (SCD نوع ۲) در کنار رکورد عملیاتی."),
        ["guide_sec_try"] = ("Try it in one minute", "در یک دقیقه امتحان کنید"),
        ["guide_try_1"] = ("Open Students and change a student's city or status.", "صفحه دانشجویان را باز کنید و شهر یا وضعیت یک دانشجو را تغییر دهید."),
        ["guide_try_2"] = ("Open Live CDC: the event appears within a few seconds.", "صفحه تغییرات زنده را باز کنید: رویداد ظرف چند ثانیه نمایش داده می‌شود."),
        ["guide_try_3"] = ("Open the student's history: a new version is added and the previous one is closed.", "تاریخچه همان دانشجو را باز کنید: نسخه جدید اضافه و نسخه قبلی بسته شده است."),
        ["guide_sec_keys"] = ("Keyboard shortcuts", "میان‌برهای صفحه‌کلید"),
        ["guide_key_open"] = ("Open this guide", "باز کردن این راهنما"),
        ["guide_key_close"] = ("Close the guide", "بستن راهنما"),
        ["guide_dont_show"] = ("Do not open after sign-in", "بعد از ورود باز نشود"),
        ["guide_got_it"] = ("Got it", "متوجه شدم"),
        ["or"] = ("or", "یا"),

        ["dashboard_title"] = ("Dashboard", "داشبورد"),
        ["dashboard_subtitle"] = ("Student population, enrollment and admissions from the ClickHouse warehouse", "جمعیت دانشجویی، ثبت‌نام و پذیرش بر اساس انبار داده ClickHouse"),
        ["view_applicants"] = ("View applicants", "مشاهده متقاضیان"),
        ["add_student"] = ("Add student", "افزودن دانشجو"),
        ["degree"] = ("Degree", "رشته"),
        ["entry_term"] = ("Entry term", "ترم ورود"),
        ["all_degrees"] = ("All degrees", "همه رشته‌ها"),
        ["all_terms"] = ("All terms", "همه ترم‌ها"),
        ["all_statuses"] = ("All statuses", "همه وضعیت‌ها"),
        ["kpi_total"] = ("Total students", "کل دانشجویان"),
        ["kpi_active"] = ("Active", "فعال"),
        ["kpi_graduated"] = ("Graduated", "فارغ‌التحصیل"),
        ["kpi_withdrawn"] = ("Withdrawn", "انصرافی"),
        ["of_total"] = ("{0} of total", "{0} از کل"),
        ["chart_cohort"] = ("Students by entry year", "دانشجویان بر اساس سال ورود"),
        ["chart_cohort_hint"] = ("Cohort size per year of entry", "اندازه هر ورودی بر اساس سال ورود"),
        ["chart_status"] = ("Status breakdown", "توزیع وضعیت تحصیلی"),
        ["students_unit"] = ("students", "دانشجو"),
        ["chart_term"] = ("Course enrollments by term", "ثبت‌نام دروس به تفکیک ترم"),
        ["chart_term_hint"] = ("Additive measure from fact_enrollment", "سنجه جمع‌پذیر از جدول fact_enrollment"),
        ["chart_gpa"] = ("GPA by department", "معدل به تفکیک دانشکده/گروه"),
        ["chart_gpa_hint"] = ("Σ quality points ÷ Σ GPA credits", "مجموع امتیاز کیفی ÷ مجموع واحدهای معدل‌دار"),
        ["chart_degrees"] = ("Top degrees by enrollment", "رشته‌های پرجمعیت"),
        ["chart_grades"] = ("Grade distribution", "توزیع نمرات"),
        ["chart_fill"] = ("Seat fill rate by department", "نرخ تکمیل ظرفیت کلاس‌ها"),
        ["chart_fill_hint"] = ("Enrolled ÷ capacity (drill-across of two facts)", "ثبت‌نام‌شده ÷ ظرفیت (ترکیب دو جدول واقعیت)"),
        ["chart_admissions"] = ("Applications and admissions by year", "درخواست‌ها و پذیرش‌ها به تفکیک سال"),
        ["applications"] = ("Applications", "درخواست‌ها"),
        ["admitted"] = ("Admitted", "پذیرفته‌شده"),
        ["recent_changes"] = ("Recently changed students", "آخرین تغییرات دانشجویان"),
        ["recent_changes_hint"] = ("Latest dimension versions, batch or CDC", "آخرین نسخه‌های دایمنشن، دسته‌ای یا CDC"),
        ["view_all"] = ("View all", "مشاهده همه"),
        ["student"] = ("Student", "دانشجو"),
        ["source"] = ("Source", "منبع"),
        ["fresh_batch"] = ("Last batch load", "آخرین بارگذاری دسته‌ای"),
        ["fresh_cdc"] = ("Last CDC change", "آخرین تغییر CDC"),
        ["fresh_today"] = ("CDC events today", "رویدادهای CDC امروز"),
        ["warehouse_empty"] = ("The warehouse is empty. The initial Airflow load starts automatically and takes a few minutes.", "انبار داده هنوز خالی است. بارگذاری اولیه Airflow به‌صورت خودکار اجرا می‌شود و چند دقیقه طول می‌کشد."),

        ["students_title"] = ("Student management", "مدیریت دانشجویان"),
        ["students_subtitle"] = ("Select a row to update or delete a student. Changes are captured by CDC.", "برای ویرایش یا حذف، یک ردیف را انتخاب کنید. تغییرات توسط CDC ثبت می‌شوند."),
        ["personal_info"] = ("Personal information", "اطلاعات فردی"),
        ["contact_info"] = ("Contact information", "اطلاعات تماس"),
        ["academic_info"] = ("Academic information", "اطلاعات تحصیلی"),
        ["first_name"] = ("First name", "نام"),
        ["middle_name"] = ("Middle name", "نام میانی"),
        ["last_name"] = ("Last name", "نام خانوادگی"),
        ["full_name"] = ("Name", "نام و نام خانوادگی"),
        ["date_of_birth"] = ("Date of birth", "تاریخ تولد"),
        ["gender"] = ("Gender", "جنسیت"),
        ["gender_F"] = ("Female", "زن"),
        ["gender_M"] = ("Male", "مرد"),
        ["email"] = ("Email address", "پست الکترونیک"),
        ["telephone"] = ("Telephone", "تلفن"),
        ["street"] = ("Street address", "نشانی"),
        ["city"] = ("City", "شهر"),
        ["state"] = ("State", "ایالت"),
        ["zip"] = ("ZIP code", "کد پستی"),
        ["class_standing"] = ("Class standing", "سال تحصیلی"),
        ["enrollment_term"] = ("Enrollment term", "ترم ورود"),
        ["student_status"] = ("Student status", "وضعیت تحصیلی"),
        ["select_degree"] = ("Select degree", "انتخاب رشته"),
        ["select_term"] = ("Select term", "انتخاب ترم"),
        ["select_status"] = ("Select status", "انتخاب وضعیت"),
        ["status_active"] = ("Active", "فعال"),
        ["status_graduated"] = ("Graduated", "فارغ‌التحصیل"),
        ["status_withdrawn"] = ("Withdrawn", "انصراف"),
        ["student_records"] = ("Student records", "فهرست دانشجویان"),
        ["search_students"] = ("Student ID, name or email", "شماره دانشجویی، نام یا ایمیل"),
        ["editing_record"] = ("Editing #{0}", "در حال ویرایش رکورد {0}"),
        ["new_record"] = ("New record", "رکورد جدید"),

        ["history_title"] = ("Student history", "تاریخچه دانشجو"),
        ["history_subtitle"] = ("SCD Type 2 versions in dim_student and the academic record from fact_enrollment", "نسخه‌های SCD نوع ۲ در dim_student و کارنامه از fact_enrollment"),
        ["operational_record"] = ("Operational record (SQL Server)", "رکورد عملیاتی (SQL Server)"),
        ["scd_versions"] = ("Dimension versions (ClickHouse)", "نسخه‌های دایمنشن (ClickHouse)"),
        ["version"] = ("Version", "نسخه"),
        ["current"] = ("Current", "جاری"),
        ["expired"] = ("Expired", "منقضی"),
        ["deleted_flag"] = ("Deleted in source", "حذف‌شده در مبدأ"),
        ["valid_from"] = ("Valid from", "معتبر از"),
        ["valid_to"] = ("Valid to", "معتبر تا"),
        ["surrogate_key"] = ("Surrogate key", "کلید جایگزین"),
        ["reason_new"] = ("First version", "نسخه اول"),
        ["reason_type2"] = ("Type 2 change", "تغییر نوع ۲"),
        ["reason_type1"] = ("Type 1 correction", "اصلاح نوع ۱"),
        ["reason_deleted"] = ("Deleted", "حذف"),
        ["reason_seed"] = ("Seed", "پیش‌فرض"),
        ["changed_fields"] = ("Changed", "تغییر"),
        ["transcript"] = ("Academic record by term", "کارنامه به تفکیک ترم"),
        ["term"] = ("Term", "ترم"),
        ["courses"] = ("Courses", "دروس"),
        ["credits_earned"] = ("Credits earned", "واحد گذرانده"),
        ["gpa"] = ("GPA", "معدل"),
        ["cumulative_gpa"] = ("Cumulative GPA", "معدل کل"),
        ["enrollments_count"] = ("Course enrollments", "تعداد ثبت‌نام دروس"),
        ["enrollments_unit"] = ("enrollments", "ثبت‌نام"),
        ["auto_refresh"] = ("Auto refresh", "بروزرسانی خودکار"),
        ["not_in_warehouse"] = ("This student is not in the warehouse yet. A new record appears a few seconds after it is saved.", "این دانشجو هنوز در انبار داده نیست؛ رکورد جدید چند ثانیه پس از ذخیره نمایش داده می‌شود."),
        ["back_to_students"] = ("Back to students", "بازگشت به فهرست دانشجویان"),

        ["applicants_title"] = ("Applicants", "متقاضیان"),
        ["applicants_subtitle"] = ("Admission applications. Updates flow to dim_applicant (SCD1) and fact_application.", "درخواست‌های پذیرش؛ تغییرات به dim_applicant (SCD1) و fact_application منتقل می‌شوند."),
        ["application_info"] = ("Application", "اطلاعات درخواست"),
        ["received_date"] = ("Received on", "تاریخ دریافت"),
        ["application_type"] = ("Application type", "نوع درخواست"),
        ["application_status"] = ("Decision", "نتیجه"),
        ["type_U"] = ("Undergraduate", "کارشناسی"),
        ["type_G"] = ("Graduate", "تحصیلات تکمیلی"),
        ["type_T"] = ("Transfer", "انتقالی"),
        ["type_I"] = ("International", "بین‌المللی"),
        ["decision_A"] = ("Admitted", "پذیرفته‌شده"),
        ["decision_D"] = ("Denied", "ردشده"),
        ["decision_N"] = ("Pending", "در انتظار"),
        ["hs_gpa"] = ("High-school GPA", "معدل دبیرستان"),
        ["sat_math"] = ("SAT math", "SAT ریاضی"),
        ["sat_reading"] = ("SAT reading", "SAT خواندن"),
        ["sat_writing"] = ("SAT writing", "SAT نوشتن"),
        ["essay"] = ("Essay score", "نمره مقاله"),
        ["admission_points"] = ("Admission points", "امتیاز پذیرش"),
        ["search_applicants"] = ("Applicant ID, name or email", "شناسه، نام یا ایمیل متقاضی"),
        ["applicant_records"] = ("Applicant records", "فهرست متقاضیان"),

        ["offerings_title"] = ("Course offerings", "ارائه دروس"),
        ["offerings_subtitle"] = ("Course sections per term. Seat utilisation is read from the warehouse.", "گروه‌های درسی هر ترم؛ میزان تکمیل ظرفیت از انبار داده خوانده می‌شود."),
        ["offering"] = ("Course offering", "ارائه درس"),
        ["department"] = ("Department", "گروه آموزشی"),
        ["select_department"] = ("Select department", "انتخاب گروه"),
        ["all_departments"] = ("All departments", "همه گروه‌ها"),
        ["course_number"] = ("Course number", "شماره درس"),
        ["section"] = ("Section", "گروه"),
        ["capacity"] = ("Capacity", "ظرفیت"),
        ["enrolled"] = ("Enrolled", "ثبت‌نام‌شده"),
        ["course"] = ("Course", "درس"),
        ["search_offerings"] = ("Offering ID, course number or title", "شناسه ارائه، شماره یا عنوان درس"),
        ["offering_records"] = ("Offering records", "فهرست ارائه‌ها"),

        ["enrollments_title"] = ("Course enrollments", "ثبت‌نام دروس"),
        ["enrollments_subtitle"] = ("Enroll students in sections and record grades. Each change updates fact_enrollment.", "ثبت‌نام دانشجو در گروه درسی و ثبت نمره؛ هر تغییر fact_enrollment را بروزرسانی می‌کند."),
        ["student_id"] = ("Student ID", "شماره دانشجویی"),
        ["offering_id"] = ("Offering ID", "شناسه ارائه"),
        ["grade"] = ("Grade", "نمره"),
        ["no_grade"] = ("Not graded", "بدون نمره"),
        ["enrollment_records"] = ("Enrollment records", "فهرست ثبت‌نام‌ها"),

        ["live_title"] = ("Live change data capture", "رصد زنده تغییرات (CDC)"),
        ["live_subtitle"] = ("SQL Server CDC → Debezium → Kafka → Spark Structured Streaming → ClickHouse", "SQL Server CDC ← Debezium ← Kafka ← Spark Structured Streaming ← ClickHouse"),
        ["live_try"] = ("Try it: edit a student on the Students page and watch the event arrive here and in the student's history.", "امتحان کنید: یک دانشجو را در صفحه دانشجویان ویرایش کنید و رسیدن رویداد را اینجا و در تاریخچه دانشجو ببینید."),
        ["events_hour"] = ("Events in the last hour", "رویدادهای یک ساعت اخیر"),
        ["median_latency"] = ("Median end-to-end latency", "میانه تأخیر انتها به انتها"),
        ["p95_latency"] = ("95th percentile latency", "صدک ۹۵ تأخیر"),
        ["events_per_minute"] = ("Events per minute (last 30 minutes)", "رویداد در دقیقه (۳۰ دقیقه اخیر)"),
        ["by_table"] = ("By source table (24 h)", "به تفکیک جدول مبدأ (۲۴ ساعت)"),
        ["recent_events"] = ("Recent events", "آخرین رویدادها"),
        ["table"] = ("Table", "جدول"),
        ["operation"] = ("Operation", "عملیات"),
        ["key"] = ("Key", "کلید"),
        ["latency"] = ("Latency", "تأخیر"),
        ["events"] = ("Events", "رویدادها"),
        ["avg"] = ("Average", "میانگین"),
        ["processed_at"] = ("Applied at", "زمان اعمال"),
        ["op_c"] = ("Insert", "درج"),
        ["op_u"] = ("Update", "ویرایش"),
        ["op_d"] = ("Delete", "حذف"),
        ["op_r"] = ("Snapshot", "اسنپ‌شات"),
        ["ms"] = ("ms", "میلی‌ثانیه"),
        ["no_events"] = ("No change events yet. Edit a record to generate one.", "هنوز رویدادی ثبت نشده؛ برای تولید رویداد یک رکورد را ویرایش کنید."),

        ["pipeline_title"] = ("Pipelines and data quality", "پایپ‌لاین‌ها و کیفیت داده"),
        ["pipeline_subtitle"] = ("Batch runs orchestrated by Airflow and the quality rules of the latest batch", "اجراهای دسته‌ای Airflow و نتایج قواعد کیفیت داده آخرین اجرا"),
        ["architecture"] = ("Architecture", "معماری"),
        ["path_batch"] = ("Batch path · SCD", "مسیر دسته‌ای · SCD"),
        ["path_stream"] = ("Near-real-time path · CDC", "مسیر نزدیک به بلادرنگ · CDC"),
        ["runs"] = ("Recent runs", "اجراهای اخیر"),
        ["batch"] = ("Batch", "اجرا"),
        ["started"] = ("Started", "شروع"),
        ["duration"] = ("Duration", "مدت"),
        ["rows"] = ("Rows", "ردیف"),
        ["steps"] = ("Steps", "مراحل"),
        ["success"] = ("Succeeded", "موفق"),
        ["failed"] = ("Failed", "ناموفق"),
        ["quality"] = ("Data quality (latest batch)", "کیفیت داده (آخرین اجرا)"),
        ["rule"] = ("Rule", "قاعده"),
        ["severity"] = ("Severity", "شدت"),
        ["failed_rows"] = ("Failed rows", "ردیف‌های ناسازگار"),
        ["passed"] = ("Passed", "قبول"),
        ["severity_error"] = ("Error", "خطا"),
        ["severity_warning"] = ("Warning", "هشدار"),
        ["tools"] = ("Platform tools", "ابزارهای زیرساخت"),
        ["open_airflow"] = ("Airflow (orchestration)", "Airflow (زمان‌بندی)"),
        ["open_grafana"] = ("Grafana (monitoring)", "Grafana (پایش)"),
        ["open_kafka"] = ("Kafka UI (topics)", "Kafka UI (تاپیک‌ها)"),
        ["no_runs"] = ("No batch has run yet. The first run starts automatically when Airflow is ready.", "هنوز اجرایی ثبت نشده؛ اولین اجرا با آماده شدن Airflow به‌صورت خودکار آغاز می‌شود."),

        ["users_title"] = ("Manage users", "مدیریت کاربران"),
        ["users_subtitle"] = ("Application accounts, roles and access", "حساب‌های کاربری، نقش‌ها و دسترسی‌ها"),
        ["role"] = ("Role", "نقش"),
        ["active"] = ("Active", "فعال"),
        ["inactive"] = ("Inactive", "غیرفعال"),
        ["created"] = ("Created", "ایجاد"),
        ["last_login"] = ("Last sign-in", "آخرین ورود"),
        ["new_user"] = ("New user", "کاربر جدید"),
        ["edit_user"] = ("Edit user", "ویرایش کاربر"),
        ["password_reset_hint"] = ("Leave empty to keep the current password.", "برای حفظ رمز فعلی خالی بگذارید."),

        ["profile_title"] = ("My panel", "پنل من"),
        ["profile_subtitle"] = ("Manage your account and display preferences", "مدیریت حساب کاربری و تنظیمات نمایش"),
        ["account"] = ("Account", "حساب"),
        ["member_since"] = ("Account {0} · created {1}", "حساب {0} · ایجاد {1}"),
        ["preferences"] = ("Display preferences", "تنظیمات نمایش"),
        ["theme"] = ("Theme", "پوسته"),
        ["save_profile"] = ("Save profile", "ذخیره اطلاعات"),
        ["change_password"] = ("Change password", "تغییر رمز عبور"),
        ["current_password"] = ("Current password", "رمز عبور فعلی"),
        ["new_password"] = ("New password", "رمز عبور جدید"),
        ["confirm_password"] = ("Confirm new password", "تکرار رمز عبور جدید"),
        ["password_rules"] = ("10–128 characters. Changing it signs out other sessions.", "۱۰ تا ۱۲۸ کاراکتر؛ با تغییر رمز، نشست‌های دیگر بسته می‌شوند."),
        ["password_mismatch"] = ("The passwords do not match.", "رمز عبور و تکرار آن یکسان نیستند."),
        ["password_changed"] = ("Password changed.", "رمز عبور تغییر کرد."),

        ["not_found_title"] = ("Page not found", "صفحه پیدا نشد"),
        ["not_found_text"] = ("The page you requested does not exist.", "صفحه‌ای که درخواست کرده‌اید وجود ندارد."),
        ["go_home"] = ("Go to dashboard", "رفتن به داشبورد"),
    };
}
