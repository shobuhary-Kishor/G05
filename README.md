# 📘 G05 Analyzer — ZEO Muthur

A Streamlit app for analysing the **Grade 5 Scholarship (G05)** register:
school and zone performance, % above a marks threshold, % qualified, rankings,
score-bracket distributions, demographics, qualified-student lists and
data-quality checks. It reproduces the original `Mutur_Exam_Analysis_Report.xlsx`
exactly (School_Performance, Zone_Performance, School_Score_Distributions,
Zone_Score_Distributions) and adds much more.

## Features

| Page | What it does |
|---|---|
| Zone Overview | Applicants / sat / absent / ≥ threshold / qualified, mean-median-max, cut-off mark, score brackets, histogram, sex-income-medium split, top & bottom schools |
| School Performance | Filters, % ≥ threshold vs % qualified scatter, ranking charts, table + CSV |
| School Drill-down | One school vs zone (distribution, ranks, candidates list) |
| Compare Schools | 2–6 schools side by side |
| Score Distributions | School × bracket heatmap (counts or %), stacked bars, tables |
| Demographics | Sex, income, medium, birth month/year: rates and mark spread |
| Qualified Students | Filterable list, qualified per school |
| Student Explorer | Filter/search all candidates, CSV export |
| Data Quality | ABS handling, out-of-range marks, cut-off consistency, DOB/sex/income checks |
| Downloads | Original-format Excel report (+ demographics) and candidate workbook |

**Sidebar → Analysis settings:** exclude schools (default: `T/SINHALA MAHA VIDYALAYA,`
as in your original script), marks threshold (default 70), and the meaning of the
register's `SEX` codes (0/1).

> The SEX column only holds 0/1. Choose the correct meaning in the sidebar;
> until then the app shows "Code 0 / Code 1".

## Expected columns

Required: `SCHID`, `SCHNAME`, `ZONE`, `TOTAL MARKS` (number or `ABS`),
`WHETHER QUALIFIED` (`QUALIFIED` or `---`).
Optional (enable extra pages): `MEDIUM`, `SEX`, `INCOME`, `DATE OF BIRTH`.

## Project layout

```
app.py                 Streamlit UI
g05_analysis.py        Analysis engine (also a CLI)
tests/                 pytest suite (synthetic data)
requirements.txt       Runtime dependencies
requirements-dev.txt   + pytest, ruff
.streamlit/config.toml Theme / server settings
.streamlit/secrets.toml.example   Optional password
.github/workflows/ci.yml          Tests on every push
```

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

CLI (writes the Excel report): `python g05_analysis.py G05.xlsx`
Tests: `pip install -r requirements-dev.txt && pytest`

## Deploy via GitHub → Streamlit Community Cloud

1. Create a **private** GitHub repo and push:
   ```bash
   git init && git add . && git commit -m "G05 Analyzer"
   git branch -M main
   git remote add origin https://github.com/<you>/<repo>.git
   git push -u origin main
   ```
2. At <https://share.streamlit.io> → **Create app** → pick the repo, branch `main`,
   main file `app.py` → **Deploy**.
3. Recommended — **Settings → Secrets**:
   ```toml
   APP_PASSWORD = "your-strong-password"
   ```
4. Open the app and upload `G05.xlsx` in the sidebar.

## ⚠️ Privacy

The register holds candidate-level data of children (DOB, sex, income, marks).
`.gitignore` excludes `G05*.xlsx` and generated reports — **never commit them**.
Keep the repo private, upload data through the app, and set `APP_PASSWORD`.

## Notes

- Score-bracket labels (`1-9`, `11-19`, …) follow the original report so numbers
  stay comparable year to year; a mark of exactly 10 falls in `11-19`.
- "Qualified" uses the register's `WHETHER QUALIFIED` column; the cut-off mark shown
  is the lowest mark among qualified candidates.
