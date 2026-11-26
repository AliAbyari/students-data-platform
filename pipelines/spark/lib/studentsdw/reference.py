GENDER = {"M": ("Male", "مرد"), "F": ("Female", "زن")}

STUDENT_STATUS = {"A": ("Active", "فعال"), "G": ("Graduated", "فارغ‌التحصیل"), "W": ("Withdrawn", "انصراف")}

APPLICATION_TYPE = {"U": ("Undergraduate", "کارشناسی", 1), "G": ("Graduate", "تحصیلات تکمیلی", 2),
                    "T": ("Transfer", "انتقالی", 3), "I": ("International", "بین‌المللی", 4)}

APPLICATION_STATUS = {"A": ("Admitted", "پذیرفته‌شده", 1), "D": ("Denied", "ردشده", 2), "N": ("Pending", "در انتظار", 3)}

GRADE = {"A": ("Excellent", "عالی", 1), "B": ("Good", "خوب", 2), "C": ("Average", "متوسط", 3),
         "D": ("Below average", "ضعیف", 4), "F": ("Fail", "مردود", 5), "W": ("Withdrawn", "حذف", 6),
         "I": ("Incomplete", "ناتمام", 7)}

SESSION = {"SP": ("Spring", "بهار", 1), "SU": ("Summer", "تابستان", 2), "FA": ("Fall", "پاییز", 3)}

DEGREE_LEVEL_FA = {"U": "کارشناسی", "G": "تحصیلات تکمیلی"}

CLASS_STANDING_FA = {"U1": "سال اول", "U2": "سال دوم", "U3": "سال سوم", "U4": "سال چهارم",
                     "G1": "تحصیلات تکمیلی - سال اول", "G2": "تحصیلات تکمیلی - سال دوم"}

DEPARTMENT_SCHOOL = {
    "BE": ("مهندسی پزشکی", "School of Engineering", "دانشکده فنی و مهندسی"),
    "CE": ("مهندسی عمران", "School of Engineering", "دانشکده فنی و مهندسی"),
    "CM": ("مهندسی شیمی", "School of Engineering", "دانشکده فنی و مهندسی"),
    "EE": ("مهندسی برق", "School of Engineering", "دانشکده فنی و مهندسی"),
    "ME": ("مهندسی مکانیک", "School of Engineering", "دانشکده فنی و مهندسی"),
    "MG": ("مدیریت مهندسی", "School of Engineering", "دانشکده فنی و مهندسی"),
    "CH": ("شیمی", "School of Science", "دانشکده علوم پایه"),
    "CS": ("علوم کامپیوتر", "School of Science", "دانشکده علوم پایه"),
    "MA": ("ریاضی", "School of Science", "دانشکده علوم پایه"),
    "PH": ("فیزیک", "School of Science", "دانشکده علوم پایه"),
    "LA": ("علوم انسانی", "School of Liberal Arts", "دانشکده علوم انسانی"),
}

US_STATE = {
    "CT": ("Connecticut", "Northeast"), "ME": ("Maine", "Northeast"), "MA": ("Massachusetts", "Northeast"),
    "NH": ("New Hampshire", "Northeast"), "RI": ("Rhode Island", "Northeast"), "VT": ("Vermont", "Northeast"),
    "NJ": ("New Jersey", "Northeast"), "NY": ("New York", "Northeast"), "PA": ("Pennsylvania", "Northeast"),
    "IL": ("Illinois", "Midwest"), "IN": ("Indiana", "Midwest"), "MI": ("Michigan", "Midwest"),
    "OH": ("Ohio", "Midwest"), "WI": ("Wisconsin", "Midwest"), "IA": ("Iowa", "Midwest"),
    "KS": ("Kansas", "Midwest"), "MN": ("Minnesota", "Midwest"), "MO": ("Missouri", "Midwest"),
    "NE": ("Nebraska", "Midwest"), "ND": ("North Dakota", "Midwest"), "SD": ("South Dakota", "Midwest"),
    "DE": ("Delaware", "South"), "DC": ("District of Columbia", "South"), "FL": ("Florida", "South"),
    "GA": ("Georgia", "South"), "MD": ("Maryland", "South"), "NC": ("North Carolina", "South"),
    "SC": ("South Carolina", "South"), "VA": ("Virginia", "South"), "WV": ("West Virginia", "South"),
    "AL": ("Alabama", "South"), "KY": ("Kentucky", "South"), "MS": ("Mississippi", "South"),
    "TN": ("Tennessee", "South"), "AR": ("Arkansas", "South"), "LA": ("Louisiana", "South"),
    "OK": ("Oklahoma", "South"), "TX": ("Texas", "South"), "AZ": ("Arizona", "West"),
    "CO": ("Colorado", "West"), "ID": ("Idaho", "West"), "MT": ("Montana", "West"), "NV": ("Nevada", "West"),
    "NM": ("New Mexico", "West"), "UT": ("Utah", "West"), "WY": ("Wyoming", "West"), "AK": ("Alaska", "West"),
    "CA": ("California", "West"), "HI": ("Hawaii", "West"), "OR": ("Oregon", "West"),
    "WA": ("Washington", "West"), "PR": ("Puerto Rico", "Territories"), "GU": ("Guam", "Territories"),
    "VI": ("U.S. Virgin Islands", "Territories"), "AS": ("American Samoa", "Territories"),
    "MP": ("Northern Mariana Islands", "Territories"),
}


def lookup_frame(spark, mapping: dict, columns: list[str]):
    rows = [(key, *(value if isinstance(value, tuple) else (value,))) for key, value in mapping.items()]
    return spark.createDataFrame(rows, columns)
