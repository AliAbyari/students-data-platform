from datetime import date

import pytest

from studentsdw.jalali import to_jalali


@pytest.mark.parametrize("gregorian, expected", [
    (date(2024, 3, 20), (1403, 1, 1)),
    (date(2025, 3, 21), (1404, 1, 1)),
    (date(2026, 11, 26), (1405, 9, 5)),
    (date(2004, 9, 1), (1383, 6, 11)),
    (date(2000, 1, 1), (1378, 10, 11)),
])
def test_known_dates(gregorian, expected):
    assert to_jalali(gregorian) == expected
