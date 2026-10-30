"""G05 Analyzer - ZEO Muthur (Grade 5 Scholarship) - Streamlit app."""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from g05_analysis import (BRACKET_ORDER, DEFAULT_EXCLUDE, DEFAULT_THRESHOLD,
                          MONTHS, SEX_LABEL_SETS, STUDENT_COLS, display_names,
                          report_workbook_bytes, run_analysis, students_workbook_bytes,
                          validate_columns)

st.set_page_config(page_title="G05 Analyzer - ZEO Muthur", page_icon="📘",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown(
    """<style>
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; padding-left: 20px; padding-right: 20px; }
    </style>""", unsafe_allow_html=True)

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ---------------------------------------------------------------- password
def check_password() -> bool:
    try:
        expected = st.secrets.get("APP_PASSWORD")
    except Exception:
        expected = None
    if not expected or st.session_state.get("authed"):
        return True
    st.title("🔒 G05 Analyzer - ZEO Muthur")
    pw = st.text_input("Password", type="password")
    if pw:
        if pw == expected:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


if not check_password():
    st.stop()


# ---------------------------------------------------------------- data
@st.cache_data(show_spinner="Reading file…")
def read_register(source) -> pd.DataFrame:
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    return pd.read_excel(source)


@st.cache_data(show_spinner="Analysing…")
def analyse(df, exclude, threshold, sex_key):
    return run_analysis(df, list(exclude), threshold, SEX_LABEL_SETS[sex_key])


st.sidebar.title("📘 G05 Analyzer")
st.sidebar.caption("ZEO Muthur · Grade 5 Scholarship")
st.sidebar.markdown("---")

uploaded = st.sidebar.file_uploader(
    "Upload G05 register (.xlsx)", type=["xlsx"],
    help="Processed in memory and not stored.")
local = sorted(Path(".").glob("G05*.xlsx"))
if uploaded is not None:
    raw = read_register(uploaded.getvalue())
elif local:
    raw = read_register(local[0])
    st.sidebar.caption(f"Using local file: {local[0].name}")
else:
    st.title("📘 G05 Analyzer - ZEO Muthur")
    st.info("👈 Upload the **G05 register (.xlsx)** in the sidebar to begin.")
    st.stop()

missing = validate_columns(raw)
if missing:
    st.error("The file is missing required column(s): " + ", ".join(missing))
    st.stop()

all_schools = sorted(raw["SCHNAME"].astype(str).str.strip().unique())
default_ex = [s for s in DEFAULT_EXCLUDE if s in all_schools]
with st.sidebar.expander("⚙️ Analysis settings", expanded=False):
    exclude = st.multiselect("Exclude schools", all_schools, default=default_ex)
    threshold = st.slider("Marks threshold", 30, 150, DEFAULT_THRESHOLD, 5,
                          help="Used for the 'Above threshold' % (default 70).")
    sex_key = st.selectbox("Sex code meaning", list(SEX_LABEL_SETS),
                           help="The register stores sex as 0/1. Pick the meaning.")

res = analyse(raw, tuple(exclude), threshold, sex_key)
stu, school, zone, T = res["students"], res["school"], res["zone"], res["totals"]
diag = res["diagnostics"]
t = res["threshold"]
PT, AT = f"P_{t}", f"Above_{t}"
sch_disp = display_names(school, t)

st.sidebar.markdown("---")
page = st.sidebar.radio("📊 Sections", [
    "Zone Overview", "School Performance", "School Drill-down", "Compare Schools",
    "Score Distributions", "Demographics", "Qualified Students", "Student Explorer",
    "Data Quality", "Downloads"])


def fmt(df, formats):
    return df.style.format({k: v for k, v in formats.items() if k in df.columns}, na_rep="–")


PCT = {PT: "{:.1f}%", "P_CutOff": "{:.1f}%", "Avg_Marks": "{:.1f}", "Median_Marks": "{:.1f}"}

def student_view(d: pd.DataFrame) -> pd.DataFrame:
    v = d[STUDENT_COLS].copy()
    v["DOB"] = v["DOB"].dt.date
    return v


def csv_button(label, df, name):
    st.download_button(label, df.to_csv(index=False).encode("utf-8-sig"), name, "text/csv")


# ================================================================ pages
if page == "Zone Overview":
    st.header("🌍 Zone Overview")
    st.caption(f"{T['Schools']} schools · threshold {t} marks"
               + (f" · {diag['excluded_rows']} excluded record(s)" if diag["excluded_rows"] else ""))
    c = st.columns(5)
    c[0].metric("Applicants", f"{T['APP']:,}")
    c[1].metric("Sat", f"{T['SAT']:,}")
    c[2].metric("Absent", f"{T['ABSENT']:,}")
    c[3].metric(f"≥ {t} marks", f"{T['Above_T']:,}", f"{T['P_T']:.1f}%", delta_color="off")
    c[4].metric("Qualified (cut-off)", f"{T['Qualified']:,}", f"{T['P_CutOff']:.1f}%", delta_color="off")
    c = st.columns(5)
    c[0].metric("Average marks", f"{T['Avg']:.1f}")
    c[1].metric("Median marks", f"{T['Median']:.0f}")
    c[2].metric("Highest", f"{T['Max']:.0f}")
    c[3].metric("Lowest", f"{T['Min']:.0f}")
    c[4].metric("Cut-off mark", f"{T['CutOff']:.0f}" if pd.notna(T["CutOff"]) else "–",
                help="Lowest mark among candidates marked QUALIFIED.")
    st.markdown("---")

    l, r = st.columns(2)
    with l:
        st.subheader("Score brackets")
        zd = res["zone_dist"].drop(columns="ZONE").iloc[0]
        fig = px.bar(x=BRACKET_ORDER, y=[int(zd[b]) for b in BRACKET_ORDER],
                     labels={"x": "Marks range", "y": "Candidates"})
        st.plotly_chart(fig, use_container_width=True)
    with r:
        st.subheader("Marks histogram")
        fig = px.histogram(stu.dropna(subset=["MARKS"]), x="MARKS", nbins=40,
                           labels={"MARKS": "Total marks"})
        fig.add_vline(x=t, line_dash="dash", line_color="orange", annotation_text=f"{t}")
        if pd.notna(T["CutOff"]):
            fig.add_vline(x=T["CutOff"], line_dash="dash", line_color="red",
                          annotation_text=f"Cut-off {T['CutOff']:.0f}")
        st.plotly_chart(fig, use_container_width=True)

    a, b, c3 = st.columns(3)
    for col, key, title in [(a, "SEX_LABEL", "Sex"), (b, "INCOME", "Income"), (c3, "MEDIUM", "Medium")]:
        counts = stu[key].fillna("Unknown").value_counts()
        col.plotly_chart(px.pie(names=counts.index, values=counts.values, hole=0.45, title=title),
                         use_container_width=True)

    st.subheader("🏆 Top & bottom schools")
    metric = st.radio("Rank by", [PT, "P_CutOff", "Avg_Marks"], horizontal=True,
                      format_func=lambda x: {PT: f"% ≥ {t}", "P_CutOff": "% qualified",
                                              "Avg_Marks": "Average marks"}[x])
    n = st.slider("Schools to show", 3, 15, 5)
    min_sat = st.number_input("Ignore schools with fewer candidates sat than", 0, 100, 5)
    ranked = sch_disp[sch_disp["SAT"] >= min_sat].sort_values(metric, ascending=False)
    cols = ["SCHNAME", "SAT", PT, "P_CutOff", "Avg_Marks"]
    t1, t2 = st.columns(2)
    t1.markdown("**Top**")
    t1.dataframe(fmt(ranked.head(n)[cols], PCT), hide_index=True, use_container_width=True)
    t2.markdown("**Bottom**")
    t2.dataframe(fmt(ranked.tail(n).iloc[::-1][cols], PCT), hide_index=True, use_container_width=True)

elif page == "School Performance":
    st.header("🏫 School Performance")
    st.sidebar.markdown("---")
    st.sidebar.subheader("Filters")
    min_sat = st.sidebar.number_input("Minimum candidates sat", 0, int(school["SAT"].max()), 0)
    name_q = st.sidebar.text_input("School name contains")
    only_q = st.sidebar.checkbox("Only schools with ≥1 qualified")
    f = sch_disp[sch_disp["SAT"] >= min_sat]
    if name_q:
        f = f[f["SCHNAME"].str.contains(name_q, case=False, na=False)]
    if only_q:
        f = f[f["Above_CutOff"] > 0]
    st.caption(f"Showing {len(f)} of {len(sch_disp)} schools")

    st.subheader(f"% above {t} vs % qualified")
    fig = px.scatter(f, x=PT, y="P_CutOff", size="SAT", color="Avg_Marks",
                     hover_name="SCHNAME", hover_data=["SAT", AT, "Above_CutOff"],
                     color_continuous_scale="Viridis",
                     labels={PT: f"% ≥ {t}", "P_CutOff": "% qualified"})
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Ranking")
    metric = st.radio("Rank by", [PT, "P_CutOff", "Avg_Marks", "Above_CutOff"], horizontal=True)
    rk = f.sort_values(metric)
    fig = px.bar(rk, x=metric, y="SCHNAME", orientation="h", color=metric,
                 color_continuous_scale="RdYlGn")
    fig.update_layout(height=max(400, 22 * len(rk)), yaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("School summary table")
    st.dataframe(fmt(f, PCT), hide_index=True, use_container_width=True)
    csv_button("⬇️ Download table (CSV)", f, "school_performance.csv")

elif page == "School Drill-down":
    st.header("🔎 School Drill-down")
    name = st.selectbox("School", sch_disp.sort_values("SCHNAME")["SCHNAME"])
    row = sch_disp[sch_disp["SCHNAME"] == name].iloc[0]
    sid = row["SCHID"]
    n_sch = len(sch_disp)
    c = st.columns(5)
    c[0].metric("Applicants", int(row["APP"]))
    c[1].metric("Sat", int(row["SAT"]))
    c[2].metric(f"% ≥ {t}", f"{row[PT]:.1f}%", f"Rank {row[PT + '_Rank']} / {n_sch}", delta_color="off")
    c[3].metric("% qualified", f"{row['P_CutOff']:.1f}%", f"Rank {row['P_CutOff_Rank']} / {n_sch}",
                delta_color="off")
    c[4].metric("Average marks", f"{row['Avg_Marks']:.1f}", f"{row['Avg_Marks'] - T['Avg']:+.1f} vs zone",
                delta_color="off")

    sd = res["school_dist"]
    srow = sd[sd["SCHID"] == sid].iloc[0]
    zrow = res["zone_dist"].iloc[0]
    s_pct = [srow[b] / max(srow[BRACKET_ORDER].sum(), 1) * 100 for b in BRACKET_ORDER]
    z_pct = [zrow[b] / max(zrow[BRACKET_ORDER].sum(), 1) * 100 for b in BRACKET_ORDER]
    fig = go.Figure()
    fig.add_bar(x=BRACKET_ORDER, y=s_pct, name="This school")
    fig.add_bar(x=BRACKET_ORDER, y=z_pct, name="Zone", marker_color="#bbbbbb")
    fig.update_layout(barmode="group", yaxis_title="% of candidates", xaxis_title="Marks range")
    st.plotly_chart(fig, use_container_width=True)

    sub = stu[stu["SCHID"] == sid]
    l, r = st.columns(2)
    hist = px.histogram(sub.dropna(subset=["MARKS"]), x="MARKS", nbins=20, title="Marks histogram")
    hist.add_vline(x=t, line_dash="dash", line_color="orange")
    l.plotly_chart(hist, use_container_width=True)
    mix = sub.groupby(["SEX_LABEL", "INCOME"]).agg(
        Candidates=("SERIAL", "size"), Qualified=("QUALIFIED", "sum")).reset_index()
    r.markdown("**Candidates by sex & income**")
    r.dataframe(mix, hide_index=True, use_container_width=True)

    st.subheader("Candidates")
    view = student_view(sub).sort_values("MARKS", ascending=False)
    st.dataframe(view, hide_index=True, use_container_width=True)
    csv_button("⬇️ Download candidates (CSV)", view, f"{sid}_candidates.csv")

elif page == "Compare Schools":
    st.header("⚖️ Compare Schools")
    names = st.multiselect("Select 2–6 schools", sorted(sch_disp["SCHNAME"]),
                           default=sch_disp.nsmallest(3, PT + "_Rank")["SCHNAME"].tolist(),
                           max_selections=6)
    if len(names) < 2:
        st.info("Pick at least two schools.")
    else:
        sub = sch_disp[sch_disp["SCHNAME"].isin(names)]
        long = sub.melt(id_vars="SCHNAME", value_vars=[PT, "P_CutOff"], var_name="Metric",
                        value_name="Percent")
        st.plotly_chart(px.bar(long, x="SCHNAME", y="Percent", color="Metric", barmode="group"),
                        use_container_width=True)
        sd = res["school_dist"][res["school_dist"]["SCHNAME"].isin(names)].set_index("SCHNAME")[BRACKET_ORDER]
        pct = sd.div(sd.sum(axis=1), axis=0) * 100
        long = pct.reset_index().melt(id_vars="SCHNAME", var_name="Range", value_name="%")
        st.plotly_chart(px.line(long, x="Range", y="%", color="SCHNAME", markers=True,
                                category_orders={"Range": BRACKET_ORDER}), use_container_width=True)
        st.dataframe(fmt(sub, PCT), hide_index=True, use_container_width=True)

elif page == "Score Distributions":
    st.header("📊 Score Distributions")
    tab1, tab2, tab3 = st.tabs(["Heatmap", "Stacked bars", "Tables"])
    sd = res["school_dist"].set_index(["SCHID", "SCHNAME"])
    mode = st.radio("Show", ["Counts", "% of school"], horizontal=True)
    mat = sd if mode == "Counts" else sd.div(sd.sum(axis=1).replace(0, 1), axis=0) * 100
    with tab1:
        fig = px.imshow(mat.values, x=BRACKET_ORDER, y=[n for _, n in mat.index], aspect="auto",
                        color_continuous_scale="YlOrRd", labels=dict(x="Marks range", y="School", color=mode))
        fig.update_layout(height=max(500, 20 * len(mat)))
        st.plotly_chart(fig, use_container_width=True)
    with tab2:
        top = st.slider("Number of schools (largest first)", 5, len(sd), min(15, len(sd)))
        sel = sd.assign(_n=sd.sum(axis=1)).nlargest(top, "_n").drop(columns="_n")
        sel = (sel if mode == "Counts" else sel.div(sel.sum(axis=1), axis=0) * 100)
        long = sel.reset_index().melt(id_vars=["SCHID", "SCHNAME"], var_name="Range", value_name="v")
        st.plotly_chart(px.bar(long, x="SCHNAME", y="v", color="Range",
                               category_orders={"Range": BRACKET_ORDER}), use_container_width=True)
    with tab3:
        st.markdown("**Zone**")
        st.dataframe(res["zone_dist"], hide_index=True, use_container_width=True)
        st.markdown("**Schools**")
        st.dataframe(res["school_dist"], hide_index=True, use_container_width=True)
        csv_button("⬇️ Download school distributions (CSV)", res["school_dist"], "school_distributions.csv")

elif page == "Demographics":
    st.header("👥 Demographics")
    if "Code 0" in set(stu["SEX_LABEL"]):
        st.info("Sex shows raw codes. Set the meaning under ⚙️ Analysis settings in the sidebar.")
    tabs = st.tabs(["Sex", "Income", "Medium", "Birth month / year"])
    demo = res["demo"]
    for tab, key, col in zip(tabs, ["sex", "income", "medium", "birth_month"],
                             ["SEX_LABEL", "INCOME", "MEDIUM", "BIRTH_MONTH"]):
        with tab:
            d = display_names(demo[key], t)
            long = d.melt(id_vars=col, value_vars=[PT, "P_CutOff"], var_name="Metric", value_name="%")
            order = {col: MONTHS} if key == "birth_month" else None
            l, r = st.columns(2)
            l.plotly_chart(px.bar(long, x=col, y="%", color="Metric", barmode="group",
                                  category_orders=order), use_container_width=True)
            bx = stu.dropna(subset=["MARKS"])
            r.plotly_chart(px.box(bx, x=col, y="MARKS", category_orders=order, points=False),
                           use_container_width=True)
            st.dataframe(fmt(d, PCT), hide_index=True, use_container_width=True)
            if key == "birth_month":
                st.caption("Compare early-year vs late-year births to see any relative-age effect.")
    yr = display_names(demo["birth_year"], t)
    st.subheader("By birth year")
    st.dataframe(fmt(yr, PCT), hide_index=True, use_container_width=True)

elif page == "Qualified Students":
    st.header("🎖️ Qualified Students")
    q = stu[stu["QUALIFIED"]]
    c = st.columns(4)
    c[0].metric("Qualified", len(q))
    c[1].metric("Cut-off mark", f"{T['CutOff']:.0f}" if pd.notna(T["CutOff"]) else "–")
    c[2].metric("Highest mark", f"{q['MARKS'].max():.0f}" if len(q) else "–")
    c[3].metric("Schools with ≥1 qualified", q["SCHID"].nunique())
    per = q.groupby("SCHNAME").size().sort_values(ascending=False).reset_index(name="Qualified")
    st.plotly_chart(px.bar(per.head(25), x="Qualified", y="SCHNAME", orientation="h",
                           title="Qualified candidates per school (top 25)")
                    .update_layout(yaxis=dict(autorange="reversed"), yaxis_title=None),
                    use_container_width=True)
    f1, f2, f3 = st.columns(3)
    s_f = f1.multiselect("School", sorted(q["SCHNAME"].unique()))
    i_f = f2.multiselect("Income", sorted(q["INCOME"].dropna().unique()))
    x_f = f3.multiselect("Sex", sorted(q["SEX_LABEL"].unique()))
    if s_f:
        q = q[q["SCHNAME"].isin(s_f)]
    if i_f:
        q = q[q["INCOME"].isin(i_f)]
    if x_f:
        q = q[q["SEX_LABEL"].isin(x_f)]
    view = student_view(q).sort_values("MARKS", ascending=False)
    st.caption(f"{len(view)} candidates")
    st.dataframe(view, hide_index=True, use_container_width=True)
    csv_button("⬇️ Download (CSV)", view, "qualified_students.csv")

elif page == "Student Explorer":
    st.header("🧑‍🎓 Student Explorer")
    st.warning("Shows individual candidate records. Protect public deployments with `APP_PASSWORD`.")
    c = st.columns(4)
    sch = c[0].multiselect("School", sorted(stu["SCHNAME"].unique()))
    rng = c[1].multiselect("Marks range", BRACKET_ORDER)
    qual = c[2].selectbox("Qualification", ["All", "Qualified", "Not qualified"])
    inc = c[3].multiselect("Income", sorted(stu["INCOME"].dropna().unique()))
    c = st.columns(3)
    sx = c[0].multiselect("Sex", sorted(stu["SEX_LABEL"].unique()))
    lo, hi = c[1].slider("Marks between", 0, 200, (0, 200))
    q = c[2].text_input("Search school / marks / DOB")
    f = stu
    if sch:
        f = f[f["SCHNAME"].isin(sch)]
    if rng:
        f = f[f["MARK_RANGE"].isin(rng)]
    if qual != "All":
        f = f[f["QUALIFIED"] == (qual == "Qualified")]
    if inc:
        f = f[f["INCOME"].isin(inc)]
    if sx:
        f = f[f["SEX_LABEL"].isin(sx)]
    if (lo, hi) != (0, 200):
        f = f[f["MARKS"].between(lo, hi)]
    view = student_view(f)
    if q:
        mask = view.astype(str).apply(lambda s: s.str.contains(q, case=False, na=False)).any(axis=1)
        view = view[mask]
    st.caption(f"{len(view):,} candidates match")
    st.dataframe(view, hide_index=True, use_container_width=True)
    csv_button("⬇️ Download (CSV)", view, "students_filtered.csv")

elif page == "Data Quality":
    st.header("🔍 Data Quality")
    c = st.columns(4)
    c[0].metric("Excluded records", diag["excluded_rows"])
    c[1].metric("Absent ('ABS')", T["ABSENT"])
    c[2].metric("Lowest qualified mark", f"{diag['cutoff_min_qualified']:.0f}")
    c[3].metric("Highest not-qualified mark", f"{diag['max_unqualified']:.0f}")

    checks = {
        "Marks that are not numbers and not ABS": diag["unexpected_marks"],
        f"Marks outside 0–200": diag["marks_out_of_range"],
        "Not qualified but marks ≥ cut-off": diag["cutoff_overlap"],
        "Qualified but absent": diag["qualified_absent"],
        "Missing / invalid date of birth": diag["missing_dob"],
        "Unknown sex code": diag["unknown_sex"],
        "Income not BELOW/ABOVE": diag["unknown_income"],
    }
    summary = pd.DataFrame({"Check": list(checks), "Records": [len(v) for v in checks.values()]})
    summary["Status"] = summary["Records"].map(lambda n: "✅ OK" if n == 0 else "⚠️ Review")
    st.dataframe(summary, hide_index=True, use_container_width=True)
    if diag["schid_multi_names"]:
        st.warning(f"SCHID with more than one school name: {diag['schid_multi_names']}")
    st.subheader("Non-numeric marks values")
    st.dataframe(diag["non_numeric_marks"], hide_index=True)
    if len(diag["qual_cut_by_income"]):
        st.subheader("Qualified marks by income group")
        st.dataframe(diag["qual_cut_by_income"], hide_index=True)
    for name, d in checks.items():
        if len(d):
            with st.expander(f"{name} ({len(d)})"):
                st.dataframe(student_view(d), hide_index=True, use_container_width=True)

elif page == "Downloads":
    st.header("⬇️ Downloads")
    st.markdown("Generated from the currently loaded file and settings.")
    c = st.columns(2)
    c[0].download_button("📊 Analysis report (.xlsx)", report_workbook_bytes(res),
                         "Mutur_Exam_Analysis_Report.xlsx", XLSX)
    c[1].download_button("🧑‍🎓 Candidate-level results (.xlsx)", students_workbook_bytes(res),
                         "G05_candidates.xlsx", XLSX)
    st.caption("The analysis report has the same four sheets as before "
               "(School_Performance, Zone_Performance, School_Score_Distributions, "
               "Zone_Score_Distributions) plus demographic sheets.")
