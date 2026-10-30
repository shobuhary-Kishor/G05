import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from g05_analysis import (BRACKET_ORDER, SEX_LABEL_SETS, display_names,  # noqa: E402
                          report_workbook_bytes, run_analysis,
                          students_workbook_bytes, validate_columns)


def make_register() -> pd.DataFrame:
    rows = [
        # MEDIUM, SEX, DOB, QUAL, INCOME, MARKS, SCHID, SCHNAME
        ("TAMIL", 0, "2016-01-10", "QUALIFIED", "BELOW", 151, 1, "School A,"),
        ("TAMIL", 1, "2016-02-11", "---", "BELOW", 75, 1, "School A,"),
        ("TAMIL", 1, "2016-03-12", "---", "ABOVE", 50, 1, "School A,"),
        ("TAMIL", 0, "2016-12-01", "---", "BELOW", "ABS", 1, "School A,"),
        ("TAMIL", 0, "2016-05-05", "---", "BELOW", 70, 2, "School B,"),
        ("TAMIL", 1, "2016-06-06", "QUALIFIED", "ABOVE", 140, 2, "School B,"),
        ("SINHALA", 1, "2016-07-07", "---", "BELOW", 90, 3, "T/SINHALA MAHA VIDYALAYA,"),
    ]
    cols = ["MEDIUM", "SEX", "DATE OF BIRTH", "WHETHER QUALIFIED", "INCOME",
            "TOTAL MARKS", "SCHID", "SCHNAME"]
    df = pd.DataFrame(rows, columns=cols)
    df["ZONE"] = "MUTUR"
    df["NSID"] = float("nan")
    return df


def test_validate_columns():
    assert validate_columns(make_register()) == []
    assert "TOTAL MARKS" in validate_columns(pd.DataFrame({"x": [1]}))


def test_totals_and_exclusion():
    res = run_analysis(make_register())
    t = res["totals"]
    assert t["Schools"] == 2          # Sinhala school excluded by default
    assert t["APP"] == 6
    assert t["SAT"] == 5 and t["ABSENT"] == 1
    assert t["Above_T"] == 4          # 151, 75, 70, 140 (threshold is inclusive)
    assert t["Qualified"] == 2
    assert t["CutOff"] == 140
    assert res["diagnostics"]["excluded_rows"] == 1


def test_threshold_is_inclusive_and_configurable():
    res70 = run_analysis(make_register(), threshold=70)
    res75 = run_analysis(make_register(), threshold=75)
    assert res70["totals"]["Above_T"] == 4
    assert res75["totals"]["Above_T"] == 3


def test_school_ranks_and_percentages():
    s = run_analysis(make_register())["school"].set_index("SCHID")
    assert s.loc[1, "SAT"] == 3 and s.loc[1, "ABSENT"] == 1
    assert s.loc[2, "P_CutOff"] == 50.0
    assert s.loc[2, "P_T"] == 100.0 and s.loc[2, "P_T_Rank"] == 1


def test_distribution_and_labels():
    res = run_analysis(make_register())
    dist = res["school_dist"].set_index("SCHID")
    assert list(dist.columns[1:]) == BRACKET_ORDER
    assert dist.loc[1, "Absent"] == 1
    assert dist.loc[1, "150+"] == 1
    assert display_names(res["zone"], 70).columns.tolist().count("P_70") == 1


def test_sex_labels_and_demographics():
    res = run_analysis(make_register(), sex_labels=SEX_LABEL_SETS["0 = Male, 1 = Female"])
    assert set(res["students"]["SEX_LABEL"]) == {"Male", "Female"}
    assert res["demo"]["income"]["APP"].sum() == 6
    assert res["demo"]["birth_month"]["BIRTH_MONTH"].iloc[0] == "Jan"


def test_exports():
    res = run_analysis(make_register())
    assert report_workbook_bytes(res)[:2] == b"PK"
    assert students_workbook_bytes(res)[:2] == b"PK"


def test_missing_columns_raises():
    with pytest.raises(ValueError):
        run_analysis(pd.DataFrame({"a": [1]}))
