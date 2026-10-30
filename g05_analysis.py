"""
G05 (Grade 5 Scholarship) Analyzer - ZEO Muthur
===============================================
Reusable analysis engine used by the Streamlit app (app.py). Also a CLI:

    python g05_analysis.py G05.xlsx
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
REQUIRED_COLUMNS = ["SCHID", "SCHNAME", "ZONE", "TOTAL MARKS", "WHETHER QUALIFIED"]
OPTIONAL_COLUMNS = ["MEDIUM", "SEX", "INCOME", "DATE OF BIRTH"]
DEFAULT_EXCLUDE = ["T/SINHALA MAHA VIDYALAYA,"]
DEFAULT_THRESHOLD = 70
MAX_MARKS = 200

BINS = [-1, 9, 19, 29, 39, 49, 59, 69, 99, 130, 149, np.inf]
LABELS = ["1-9", "11-19", "20-29", "30-39", "40-49", "50-59",
          "60-69", "70-99", "100-130", "131-149", "150+"]
BRACKET_ORDER = LABELS + ["Absent"]

SEX_LABEL_SETS = {
    "Raw codes (0 / 1)": {0: "Code 0", 1: "Code 1"},
    "0 = Male, 1 = Female": {0: "Male", 1: "Female"},
    "0 = Female, 1 = Male": {0: "Female", 1: "Male"},
}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ---------------------------------------------------------------------------
# CLEANING
# ---------------------------------------------------------------------------
def validate_columns(df: pd.DataFrame) -> list[str]:
    cols = {str(c).strip() for c in df.columns}
    return [c for c in REQUIRED_COLUMNS if c not in cols]


def clean_register(df: pd.DataFrame, exclude_schools=(), sex_labels: dict | None = None):
    """Return (clean_df, n_excluded)."""
    d = df.copy()
    d.columns = [str(c).strip() for c in d.columns]
    for c in OPTIONAL_COLUMNS:
        if c not in d.columns:
            d[c] = np.nan

    d["SCHNAME"] = d["SCHNAME"].astype(str).str.strip()
    excl = {str(s).strip() for s in exclude_schools}
    n_before = len(d)
    d = d[~d["SCHNAME"].isin(excl)].copy()
    n_excluded = n_before - len(d)
    d = d.reset_index(drop=True)

    d["SERIAL"] = np.arange(1, len(d) + 1)
    d["ZONE"] = d["ZONE"].astype(str).str.strip()
    d["MEDIUM"] = d["MEDIUM"].astype(str).str.strip().str.upper().replace("NAN", np.nan)
    d["INCOME"] = d["INCOME"].astype(str).str.strip().str.upper().replace("NAN", np.nan)

    d["TOTAL_MARKS_RAW"] = d["TOTAL MARKS"].astype(str).str.strip()
    d["MARKS"] = pd.to_numeric(d["TOTAL_MARKS_RAW"], errors="coerce")
    d["ABSENT"] = d["MARKS"].isna()
    d["QUALIFIED"] = d["WHETHER QUALIFIED"].astype(str).str.strip().str.upper().eq("QUALIFIED")
    d["QUALIFIED_TXT"] = np.where(d["QUALIFIED"], "QUALIFIED", "---")

    mr = pd.cut(d["MARKS"], bins=BINS, labels=LABELS, include_lowest=True)
    d["MARK_RANGE"] = mr.astype(object).where(mr.notna(), "Absent")

    d["SEX_CODE"] = pd.to_numeric(d["SEX"], errors="coerce")
    labels = sex_labels or SEX_LABEL_SETS["Raw codes (0 / 1)"]
    d["SEX_LABEL"] = d["SEX_CODE"].map(labels).fillna("Unknown")

    dob = pd.to_datetime(d["DATE OF BIRTH"], errors="coerce")
    d["DOB"] = dob
    d["BIRTH_YEAR"] = dob.dt.year
    d["BIRTH_MONTH"] = dob.dt.month.map(lambda m: MONTHS[int(m) - 1] if pd.notna(m) else np.nan)
    return d, n_excluded


# ---------------------------------------------------------------------------
# SUMMARIES
# ---------------------------------------------------------------------------
def summarize(df: pd.DataFrame, keys, threshold: int = DEFAULT_THRESHOLD) -> pd.DataFrame:
    keys = [keys] if isinstance(keys, str) else list(keys)
    out = (df.groupby(keys, dropna=False)
             .agg(APP=("SERIAL", "size"),
                  SAT=("MARKS", lambda x: int(x.notna().sum())),
                  Above_T=("MARKS", lambda x: int((x >= threshold).sum())),
                  Above_CutOff=("QUALIFIED", "sum"),
                  Avg_Marks=("MARKS", "mean"),
                  Median_Marks=("MARKS", "median"),
                  Max_Marks=("MARKS", "max"))
             .reset_index())
    out["Above_CutOff"] = out["Above_CutOff"].astype(int)
    out["ABSENT"] = out["APP"] - out["SAT"]
    sat = out["SAT"].replace(0, np.nan)
    out["P_T"] = (out["Above_T"] / sat * 100).round(2).fillna(0.0)
    out["P_CutOff"] = (out["Above_CutOff"] / sat * 100).round(2).fillna(0.0)
    out["P_T_Rank"] = out["P_T"].rank(method="min", ascending=False).astype(int)
    out["P_CutOff_Rank"] = out["P_CutOff"].rank(method="min", ascending=False).astype(int)
    for c in ["Avg_Marks", "Median_Marks"]:
        out[c] = out[c].round(1)
    return out[keys + ["APP", "SAT", "ABSENT", "Above_T", "Above_CutOff", "P_T", "P_CutOff",
                       "P_T_Rank", "P_CutOff_Rank", "Avg_Marks", "Median_Marks", "Max_Marks"]]


def display_names(df: pd.DataFrame, threshold: int) -> pd.DataFrame:
    """Rename generic threshold columns, e.g. Above_T -> Above_70."""
    return df.rename(columns={"Above_T": f"Above_{threshold}", "P_T": f"P_{threshold}",
                              "P_T_Rank": f"P_{threshold}_Rank"})


def distribution(df: pd.DataFrame, keys) -> pd.DataFrame:
    keys = [keys] if isinstance(keys, str) else list(keys)
    idx = [df[k] for k in keys]
    return (pd.crosstab(idx, df["MARK_RANGE"])
              .reindex(columns=BRACKET_ORDER, fill_value=0).reset_index())


def run_analysis(df: pd.DataFrame, exclude_schools=DEFAULT_EXCLUDE,
                 threshold: int = DEFAULT_THRESHOLD, sex_labels: dict | None = None) -> dict:
    missing = validate_columns(df)
    if missing:
        raise ValueError("Register is missing required column(s): " + ", ".join(missing))
    d, n_excluded = clean_register(df, exclude_schools, sex_labels)

    school = summarize(d, ["SCHID", "SCHNAME"], threshold)
    zone = summarize(d, ["ZONE"], threshold)
    school_dist = distribution(d, ["SCHID", "SCHNAME"])
    zone_dist = distribution(d, ["ZONE"])

    q = d[d["QUALIFIED"]]
    unq = d[~d["QUALIFIED"] & d["MARKS"].notna()]
    cut = float(q["MARKS"].min()) if len(q) else np.nan
    max_unq = float(unq["MARKS"].max()) if len(unq) else np.nan
    overlap = d[~d["QUALIFIED"] & (d["MARKS"] >= cut)] if len(q) else d.iloc[0:0]
    qual_cut_by_income = (q.groupby("INCOME")["MARKS"].agg(["count", "min", "max"])
                          .reset_index().rename(columns={"count": "Qualified", "min": "Lowest", "max": "Highest"})
                          if len(q) else pd.DataFrame())

    non_numeric = (d.loc[d["ABSENT"], "TOTAL_MARKS_RAW"].value_counts()
                   .rename_axis("Value").reset_index(name="Count"))
    unexpected_marks = d[d["ABSENT"] & ~d["TOTAL_MARKS_RAW"].str.upper().isin(["ABS", "AB"])]
    school_names = d.groupby("SCHID")["SCHNAME"].nunique()
    diagnostics = {
        "excluded_rows": n_excluded,
        "non_numeric_marks": non_numeric,
        "unexpected_marks": unexpected_marks,
        "marks_out_of_range": d[(d["MARKS"] < 0) | (d["MARKS"] > MAX_MARKS)],
        "missing_dob": d[d["DOB"].isna()],
        "unknown_sex": d[d["SEX_LABEL"] == "Unknown"],
        "unknown_income": d[~d["INCOME"].isin(["BELOW", "ABOVE"])],
        "schid_multi_names": school_names[school_names > 1].index.tolist(),
        "cutoff_min_qualified": cut,
        "max_unqualified": max_unq,
        "cutoff_overlap": overlap,
        "qual_cut_by_income": qual_cut_by_income,
        "qualified_absent": d[d["QUALIFIED"] & d["ABSENT"]],
    }

    t = int(threshold)
    totals = {
        "Schools": int(len(school)), "APP": int(len(d)), "SAT": int(d["MARKS"].notna().sum()),
        "ABSENT": int(d["ABSENT"].sum()), "Above_T": int((d["MARKS"] >= t).sum()),
        "Qualified": int(d["QUALIFIED"].sum()),
        "Avg": float(d["MARKS"].mean()), "Median": float(d["MARKS"].median()),
        "Max": float(d["MARKS"].max()), "Min": float(d["MARKS"].min()),
        "CutOff": cut,
    }
    totals["P_T"] = round(totals["Above_T"] / totals["SAT"] * 100, 2) if totals["SAT"] else 0.0
    totals["P_CutOff"] = round(totals["Qualified"] / totals["SAT"] * 100, 2) if totals["SAT"] else 0.0

    demo = {
        "sex": summarize(d, "SEX_LABEL", t),
        "income": summarize(d, "INCOME", t),
        "medium": summarize(d, "MEDIUM", t),
        "birth_month": summarize(d, "BIRTH_MONTH", t),
        "birth_year": summarize(d, "BIRTH_YEAR", t),
    }
    demo["birth_month"]["_o"] = demo["birth_month"]["BIRTH_MONTH"].map(
        {m: i for i, m in enumerate(MONTHS)})
    demo["birth_month"] = demo["birth_month"].sort_values("_o").drop(columns="_o")

    return {"students": d, "school": school, "zone": zone, "school_dist": school_dist,
            "zone_dist": zone_dist, "totals": totals, "demo": demo,
            "diagnostics": diagnostics, "threshold": t}


# ---------------------------------------------------------------------------
# EXPORT
# ---------------------------------------------------------------------------
def report_workbook_bytes(res: dict) -> bytes:
    """Same four sheets as the original report, plus demographics."""
    t = res["threshold"]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        display_names(res["school"], t).to_excel(w, sheet_name="School_Performance", index=False)
        display_names(res["zone"], t).to_excel(w, sheet_name="Zone_Performance", index=False)
        res["school_dist"].to_excel(w, sheet_name="School_Score_Distributions", index=False)
        res["zone_dist"].to_excel(w, sheet_name="Zone_Score_Distributions", index=False)
        for k, name in [("sex", "By_Sex"), ("income", "By_Income"), ("medium", "By_Medium"),
                        ("birth_month", "By_Birth_Month")]:
            display_names(res["demo"][k], t).to_excel(w, sheet_name=name, index=False)
    return buf.getvalue()


STUDENT_COLS = ["SERIAL", "SCHID", "SCHNAME", "ZONE", "MEDIUM", "SEX_LABEL", "DOB", "INCOME",
                "TOTAL_MARKS_RAW", "MARKS", "MARK_RANGE", "QUALIFIED_TXT"]


def students_workbook_bytes(res: dict) -> bytes:
    d = res["students"][STUDENT_COLS].copy()
    d["DOB"] = d["DOB"].dt.date
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        d.to_excel(w, sheet_name="All Candidates", index=False)
        d[d["QUALIFIED_TXT"] == "QUALIFIED"].to_excel(w, sheet_name="Qualified", index=False)
    return buf.getvalue()


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("G05.xlsx")
    result = run_analysis(pd.read_excel(path))
    Path("Mutur_Exam_Analysis_Report.xlsx").write_bytes(report_workbook_bytes(result))
    print("Wrote Mutur_Exam_Analysis_Report.xlsx")
    print(result["totals"])
