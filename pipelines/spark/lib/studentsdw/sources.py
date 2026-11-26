from __future__ import annotations

import re

_CAMEL = re.compile(r"(?<!^)(?=[A-Z])")


def snake(name: str) -> str:
    return _CAMEL.sub("_", name).lower()


SOURCE_TABLES: dict[str, list[str]] = {
    "Departments": ["DepartmentCode", "DepartmentName"],
    "Sessions": ["SessionCode", "SessionName"],
    "Terms": ["TermCode", "SessionCode", "Year"],
    "DegreeLevels": ["DegreeLevelCode", "DegreeLevelName"],
    "DegreeTypes": ["DegreeTypeCode", "DegreeTypeName", "DegreeLevelCode"],
    "Degrees": ["DegreeId", "DepartmentCode", "DegreeTypeCode", "DegreeName"],
    "ClassStandings": ["ClassStandingCode", "ClassStandingName", "DegreeLevelCode", "RequiredCredits"],
    "Grades": ["Grade", "Points", "IncludeInGpa"],
    "Courses": ["DepartmentCode", "CourseNumber", "CourseTitle", "CourseDescription", "Credits",
                "MaximumSectionSize"],
    "CourseOfferings": ["CourseOfferingId", "DepartmentCode", "CourseNumber", "TermCode", "Section", "Capacity"],
    "Students": ["StudentId", "FirstName", "MiddleName", "LastName", "Gender", "StreetAddress", "City", "State",
                 "ZipCode", "Telephone", "email", "DateOfBirth", "DegreePursued", "ClassStandingCode",
                 "StudentStatus", "EnrollmentTerm"],
    "Applicants": ["ApplicantId", "FirstName", "MiddleName", "LastName", "Gender", "StreetAddress", "City", "State",
                   "ZipCode", "Telephone", "Email", "DateOfBirth", "ApplicationReceivedDate", "EntryTerm",
                   "ApplicationType", "Gpa", "SatMathScore", "SatReadingScore", "SatWritingScore", "EssayScore",
                   "ApplicationStatus", "AdmissionPoints"],
    "CourseEnrollments": ["CourseEnrollmentId", "CourseOfferingId", "StudentId", "Grade"],
}

PARTITION_COLUMNS: dict[str, str] = {
    "CourseEnrollments": "CourseEnrollmentId",
    "Applicants": "ApplicantId",
    "Students": "StudentId",
}


def staging_table(source_table: str) -> str:
    return f"stg.{snake(source_table)}"
