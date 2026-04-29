import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

# Ensure sibling modules (db, geocode) are importable when run via
# `streamlit run dashboard/app.py` from the repo root.
sys.path.insert(0, str(Path(__file__).parent))

import folium
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from folium.plugins import HeatMap, MarkerCluster
from streamlit_folium import st_folium

from db import query_df
from geocode import load_cache

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# First-2-digit PLZ prefix → federal state (approximate; border areas may differ)
PLZ_TO_STATE: dict[str, str] = {
    "01": "Sachsen", "02": "Sachsen", "03": "Brandenburg", "04": "Sachsen",
    "06": "Sachsen-Anhalt", "07": "Thüringen", "08": "Sachsen", "09": "Sachsen",
    "10": "Berlin", "12": "Berlin", "13": "Berlin", "14": "Brandenburg",
    "15": "Brandenburg", "16": "Brandenburg", "17": "Mecklenburg-Vorpommern",
    "18": "Mecklenburg-Vorpommern", "19": "Mecklenburg-Vorpommern",
    "20": "Hamburg", "21": "Niedersachsen", "22": "Hamburg",
    "23": "Schleswig-Holstein", "24": "Schleswig-Holstein",
    "25": "Schleswig-Holstein", "26": "Niedersachsen",
    "27": "Niedersachsen", "28": "Bremen", "29": "Niedersachsen",
    "30": "Niedersachsen", "31": "Niedersachsen", "32": "Nordrhein-Westfalen",
    "33": "Nordrhein-Westfalen", "34": "Hessen", "35": "Hessen",
    "36": "Hessen", "37": "Niedersachsen", "38": "Niedersachsen",
    "39": "Sachsen-Anhalt",
    "40": "Nordrhein-Westfalen", "41": "Nordrhein-Westfalen",
    "42": "Nordrhein-Westfalen", "44": "Nordrhein-Westfalen",
    "45": "Nordrhein-Westfalen", "46": "Nordrhein-Westfalen",
    "47": "Nordrhein-Westfalen", "48": "Nordrhein-Westfalen",
    "49": "Niedersachsen",
    "50": "Nordrhein-Westfalen", "51": "Nordrhein-Westfalen",
    "52": "Nordrhein-Westfalen", "53": "Nordrhein-Westfalen",
    "54": "Rheinland-Pfalz", "55": "Rheinland-Pfalz",
    "56": "Rheinland-Pfalz", "57": "Nordrhein-Westfalen",
    "58": "Nordrhein-Westfalen", "59": "Nordrhein-Westfalen",
    "60": "Hessen", "61": "Hessen", "63": "Hessen", "64": "Hessen",
    "65": "Hessen", "66": "Saarland", "67": "Rheinland-Pfalz",
    "68": "Baden-Württemberg", "69": "Baden-Württemberg",
    "70": "Baden-Württemberg", "71": "Baden-Württemberg",
    "72": "Baden-Württemberg", "73": "Baden-Württemberg",
    "74": "Baden-Württemberg", "75": "Baden-Württemberg",
    "76": "Baden-Württemberg", "77": "Baden-Württemberg",
    "78": "Baden-Württemberg", "79": "Baden-Württemberg",
    "80": "Bayern", "81": "Bayern", "82": "Bayern",
    "83": "Bayern", "84": "Bayern", "85": "Bayern",
    "86": "Bayern", "87": "Bayern", "88": "Baden-Württemberg",
    "89": "Baden-Württemberg",
    "90": "Bayern", "91": "Bayern", "92": "Bayern",
    "93": "Bayern", "94": "Bayern", "95": "Bayern",
    "96": "Bayern", "97": "Bayern", "98": "Thüringen", "99": "Thüringen",
}

# ICD chapter → English chapter name (used to enrich dynamic labels)
ICD_CHAPTER_EN: dict[str, str] = {
    "A": "Infectious & parasitic diseases",
    "B": "Infectious & parasitic diseases",
    "C": "Neoplasms / cancer",
    "D": "Blood & immune disorders",
    "E": "Endocrine & metabolic diseases",
    "F": "Mental & behavioural disorders",
    "G": "Nervous system",
    "H": "Eye & ear diseases",
    "I": "Circulatory system – heart & vessels",
    "J": "Respiratory system",
    "K": "Digestive system",
    "L": "Skin & subcutaneous tissue",
    "M": "Musculoskeletal system",
    "N": "Genitourinary system",
    "O": "Pregnancy & childbirth",
    "P": "Perinatal conditions",
    "Q": "Congenital malformations",
    "R": "Symptoms & abnormal findings",
    "S": "Injuries & trauma",
    "T": "Poisoning & adverse effects",
    "Z": "Factors influencing health status",
}

# OPS top-level digit → English description
OPS_CHAPTER_EN: dict[str, str] = {
    "1": "Diagnostics & examinations",
    "3": "Imaging procedures",
    "5": "Surgical operations",
    "6": "Medication procedures",
    "8": "Non-surgical therapeutic procedures",
    "9": "Supplementary procedures",
}

SIZE_LABELS = ["Small (<100)", "Medium (100–299)", "Large (300–599)", "Very Large (600+)"]
SIZE_BINS = [0, 99, 299, 599, float("inf")]

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="German Hospital Dashboard",
    page_icon="🏥",
    layout="wide",
)

st.title("🏥 German Hospital Dashboard")
st.caption(
    "Data: Gemeinsamer Bundesausschuss (G-BA) "
)

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Hospital Size vs. Stay Types",
    "🗺️ Geographical Density",
    "🫀 Surgery & Diagnosis Map",
    "📅 Year Comparison",
])

# ─────────────────────────────────────────────────────────────────────────────
# Cached data loaders
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=600)
def _hospitals_deduped() -> pd.DataFrame:
    """One row per hospital site, latest report year wins."""
    return query_df("""
        WITH latest AS (
            SELECT DISTINCT ON (ik, standortnummer)
                hospital_name, city, postal_code, report_year,
                beds_count,
                inpatient_case_count,
                partial_inpatient_case_count,
                outpatient_case_count
            FROM hospital_locations
            ORDER BY ik, standortnummer, report_year DESC
        )
        SELECT * FROM latest
        WHERE beds_count IS NOT NULL AND beds_count > 0
    """)


@st.cache_data(ttl=600)
def _location_density() -> pd.DataFrame:
    """Hospital count and total beds per postal code (deduped)."""
    return query_df("""
        WITH latest AS (
            SELECT DISTINCT ON (ik, standortnummer)
                city, postal_code, beds_count
            FROM hospital_locations
            WHERE postal_code IS NOT NULL
            ORDER BY ik, standortnummer, report_year DESC
        )
        SELECT postal_code, city,
               COUNT(*)                        AS hospital_count,
               SUM(COALESCE(beds_count, 0))    AS total_beds
        FROM latest
        GROUP BY postal_code, city
        ORDER BY hospital_count DESC
    """)


@st.cache_data(ttl=600)
def _top_hospitals(code_prefix: str, source: str, limit: int) -> pd.DataFrame:
    """Top hospitals by aggregated case count for a given ICD or OPS prefix."""
    if source == "icd":
        sql = """
            WITH latest_locs AS (
                SELECT DISTINCT ON (ik, standortnummer)
                    ik, standortnummer, report_year,
                    hospital_name, postal_code, city
                FROM hospital_locations
                WHERE postal_code IS NOT NULL
                ORDER BY ik, standortnummer, report_year DESC
            ),
            cases AS (
                SELECT hd.ik, hd.standortnummer, hd.report_year,
                       SUM(COALESCE(hdd.case_count, 0)) AS total_cases
                FROM hospital_departments hd
                JOIN hospital_department_diagnoses hdd
                  ON hd.department_id = hdd.department_id
                WHERE hdd.icd_code LIKE %s
                  AND hdd.case_count IS NOT NULL
                GROUP BY hd.ik, hd.standortnummer, hd.report_year
            )
            SELECT ll.hospital_name, ll.postal_code, ll.city,
                   c.total_cases
            FROM latest_locs ll
            JOIN cases c
              ON ll.ik = c.ik
             AND ll.standortnummer = c.standortnummer
             AND ll.report_year = c.report_year
            WHERE c.total_cases > 0
            ORDER BY c.total_cases DESC
            LIMIT %s
        """
    else:
        sql = """
            WITH latest_locs AS (
                SELECT DISTINCT ON (ik, standortnummer)
                    ik, standortnummer, report_year,
                    hospital_name, postal_code, city
                FROM hospital_locations
                WHERE postal_code IS NOT NULL
                ORDER BY ik, standortnummer, report_year DESC
            ),
            cases AS (
                SELECT hd.ik, hd.standortnummer, hd.report_year,
                       SUM(COALESCE(hdp.case_count, 0)) AS total_cases
                FROM hospital_departments hd
                JOIN hospital_department_procedures hdp
                  ON hd.department_id = hdp.department_id
                WHERE hdp.ops_code LIKE %s
                  AND hdp.case_count IS NOT NULL
                GROUP BY hd.ik, hd.standortnummer, hd.report_year
            )
            SELECT ll.hospital_name, ll.postal_code, ll.city,
                   c.total_cases
            FROM latest_locs ll
            JOIN cases c
              ON ll.ik = c.ik
             AND ll.standortnummer = c.standortnummer
             AND ll.report_year = c.report_year
            WHERE c.total_cases > 0
            ORDER BY c.total_cases DESC
            LIMIT %s
        """
    return query_df(sql, (code_prefix + "%", limit))


@st.cache_data(ttl=3600)
def _load_icd_options() -> pd.DataFrame:
    """All 3-char ICD prefixes that appear in hospital data, sorted by code."""
    return query_df("""
        WITH prefixes AS (
            SELECT SUBSTRING(icd_code, 1, 3) AS prefix,
                   SUM(COALESCE(case_count, 0)) AS total_cases
            FROM hospital_department_diagnoses
            WHERE icd_code IS NOT NULL
              AND case_count IS NOT NULL
              AND case_count > 0
            GROUP BY SUBSTRING(icd_code, 1, 3)
        ),
        best_desc AS (
            SELECT DISTINCT ON (SUBSTRING(code, 1, 3))
                   SUBSTRING(code, 1, 3) AS prefix,
                   description_de
            FROM icd_reference
            ORDER BY SUBSTRING(code, 1, 3), LENGTH(code) ASC, code ASC
        )
        SELECT p.prefix,
               COALESCE(d.description_de, p.prefix) AS description_de,
               p.total_cases
        FROM prefixes p
        LEFT JOIN best_desc d ON p.prefix = d.prefix
        ORDER BY p.prefix ASC
    """)


@st.cache_data(ttl=3600)
def _load_ops_options() -> pd.DataFrame:
    """All 4-char OPS prefixes (e.g. '5-36') that appear in hospital data, sorted by code."""
    return query_df("""
        WITH prefixes AS (
            SELECT SUBSTRING(ops_code, 1, 4) AS prefix,
                   SUM(COALESCE(case_count, 0)) AS total_cases
            FROM hospital_department_procedures
            WHERE ops_code IS NOT NULL
              AND case_count IS NOT NULL
              AND case_count > 0
            GROUP BY SUBSTRING(ops_code, 1, 4)
        ),
        best_desc AS (
            SELECT DISTINCT ON (SUBSTRING(code, 1, 4))
                   SUBSTRING(code, 1, 4) AS prefix,
                   description_de
            FROM ops_reference
            ORDER BY SUBSTRING(code, 1, 4), LENGTH(code) ASC, code ASC
        )
        SELECT p.prefix,
               COALESCE(d.description_de, p.prefix) AS description_de,
               p.total_cases
        FROM prefixes p
        LEFT JOIN best_desc d ON p.prefix = d.prefix
        ORDER BY p.prefix ASC
    """)


def _build_option_map(df: pd.DataFrame, chapter_en: dict[str, str]) -> dict[str, str]:
    """Build {label: prefix} dict sorted by code with basic English hint and cases."""
    result: dict[str, str] = {}
    for _, row in df.iterrows():
        prefix: str = str(row["prefix"])
        desc_de: str = str(row["description_de"] or prefix)
        desc: str = desc_de
        if len(desc) > 60:
            desc = desc[:59] + "…"
        en_hint = chapter_en.get(prefix[0].upper(), "")
        en_part = f" ({en_hint})" if en_hint else ""
        case_count = int(row["total_cases"]) if pd.notna(row["total_cases"]) else 0
        label = f"{prefix} – {desc}{en_part}  [{case_count:,} cases]"
        result[label] = prefix
    return result


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 – Hospital Size vs. Stay Types
# ─────────────────────────────────────────────────────────────────────────────

with tab1:
    st.header("Hospital Size vs. Type of Stay")
    st.info(
        "**Deduplication strategy:** hospitals appearing in both the 2023 and 2024 "
        "quality reports are deduplicated by keeping only the **latest year's** entry. "
        "This prevents double-counting while using the most current data available.",
        icon="ℹ️",
    )

    df = _hospitals_deduped()
    for col in ["beds_count", "inpatient_case_count",
                "partial_inpatient_case_count", "outpatient_case_count"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["size_category"] = pd.cut(df["beds_count"], bins=SIZE_BINS, labels=SIZE_LABELS)

    # ── KPI row ──────────────────────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Unique hospital sites", f"{len(df):,}")
    k2.metric("Avg beds / site", f"{df['beds_count'].mean():.0f}")
    k3.metric("Total beds (Germany)", f"{df['beds_count'].sum():,.0f}")
    k4.metric("Largest single site", f"{df['beds_count'].max():.0f} beds")

    st.divider()

    STAY_COLOR = {
        "Inpatient": "#2563eb",
        "Partial Inpatient": "#7c3aed",
        "Outpatient": "#059669",
    }
    STAY_COL_MAP = {
        "Inpatient": "inpatient_case_count",
        "Partial Inpatient": "partial_inpatient_case_count",
        "Outpatient": "outpatient_case_count",
    }

    # ── Aggregation ───────────────────────────────────────────────────────────
    agg = (
        df.dropna(subset=["size_category"])
        .groupby("size_category", observed=True)
        .agg(
            Inpatient=("inpatient_case_count", "mean"),
            Partial_Inpatient=("partial_inpatient_case_count", "mean"),
            Outpatient=("outpatient_case_count", "mean"),
            n=("beds_count", "count"),
        )
        .reset_index()
    )

    # ── Grouped column chart ──────────────────────────────────────────────────
    fig_col = px.bar(
        agg.melt(
            id_vars=["size_category", "n"],
            value_vars=["Inpatient", "Partial_Inpatient", "Outpatient"],
            var_name="stay_type",
            value_name="avg_cases",
        ).assign(stay_type=lambda d: d["stay_type"].str.replace("_", " ")),
        x="size_category",
        y="avg_cases",
        color="stay_type",
        barmode="group",
        title="Average Cases per Hospital by Size Category",
        labels={
            "size_category": "Hospital Size",
            "avg_cases": "Avg. Cases / Hospital",
            "stay_type": "Stay Type",
        },
        category_orders={"size_category": SIZE_LABELS},
        color_discrete_map=STAY_COLOR,
        text_auto=".0f",
    )
    fig_col.update_traces(textposition="outside")
    fig_col.update_layout(height=420, legend=dict(orientation="h", yanchor="bottom", y=-0.2))
    st.plotly_chart(fig_col, width="stretch")

    # ── Scatter + summary table ───────────────────────────────────────────────
    col_l, _ = st.columns(2)

    with col_l:
        stay_choice = st.radio(
            "Y-axis: case type",
            list(STAY_COL_MAP.keys()),
            horizontal=True,
        )
        y_col = STAY_COL_MAP[stay_choice]
        df_sc = df.dropna(subset=[y_col, "beds_count"])
        fig_sc = px.scatter(
            df_sc,
            x="beds_count",
            y=y_col,
            color="size_category",
            hover_data=["hospital_name", "city"],
            opacity=0.6,
            title=f"Beds vs. {stay_choice} Cases",
            labels={
                "beds_count": "Number of Beds",
                y_col: f"{stay_choice} Cases",
                "size_category": "Size",
            },
            category_orders={"size_category": SIZE_LABELS},
        )
        x_v = df_sc["beds_count"].to_numpy(dtype=float)
        y_v = df_sc[y_col].to_numpy(dtype=float)
        mask = ~(np.isnan(x_v) | np.isnan(y_v))
        if mask.sum() > 1:
            m, b = np.polyfit(x_v[mask], y_v[mask], 1)
            x_line = np.linspace(x_v[mask].min(), x_v[mask].max(), 200)
            fig_sc.add_trace(go.Scatter(
                x=x_line, y=m * x_line + b,
                mode="lines", name="Linear trend",
                line=dict(color="black", width=2, dash="dash"),
                showlegend=True,
            ))
        fig_sc.update_layout(height=440, legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_sc, width="stretch")

    with st.expander("Summary statistics table"):
        display = agg.copy()
        display.columns = [
            "Size Category", "Avg Inpatient", "Avg Partial Inpatient", "Avg Outpatient", "N Hospitals",
        ]
        for c in ["Avg Inpatient", "Avg Partial Inpatient", "Avg Outpatient"]:
            display[c] = display[c].round(0).astype("Int64")
        st.dataframe(display, width="stretch", hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 – Geographical Density
# ─────────────────────────────────────────────────────────────────────────────

with tab2:
    st.header("Geographical Density of Hospitals")

    df_locs = _location_density()
    df_locs["state"] = df_locs["postal_code"].str[:2].map(PLZ_TO_STATE).fillna("Other / Unknown")

    state_agg = (
        df_locs.groupby("state")
        .agg(hospital_count=("hospital_count", "sum"), total_beds=("total_beds", "sum"))
        .reset_index()
        .sort_values("hospital_count", ascending=False)
    )
    state_agg["beds_per_hospital"] = (
        state_agg["total_beds"] / state_agg["hospital_count"]
    ).round(1)
    known = state_agg[state_agg["state"] != "Other / Unknown"]

    # ── State bar chart (no geocoding needed) ─────────────────────────────────
    col_chart, col_info = st.columns([3, 2])

    with col_chart:
        fig_state = px.bar(
            known,
            x="hospital_count",
            y="state",
            orientation="h",
            color="total_beds",
            color_continuous_scale="Blues",
            text="hospital_count",
            title="Hospital Locations per Federal State",
            labels={
                "hospital_count": "Hospital Locations",
                "state": "Federal State",
                "total_beds": "Total Beds",
            },
        )
        fig_state.update_traces(textposition="outside")
        fig_state.update_layout(
            height=620,
            yaxis={"categoryorder": "total ascending"},
        )
        st.plotly_chart(fig_state, width="stretch")

    with col_info:
        st.subheader("Top 10 States")
        st.dataframe(
            known.head(10).rename(columns={
                "state": "State",
                "hospital_count": "Hospitals",
                "total_beds": "Total Beds",
                "beds_per_hospital": "Avg Beds/Site",
            }),
            width="stretch",
            hide_index=True,
        )
        st.caption(
            "State assignment uses the first two digits of the postal code (PLZ). "
            "Border areas may fall under a neighbouring state."
        )

        fig_beds = px.bar(
            known.sort_values("beds_per_hospital", ascending=False).head(10),
            x="beds_per_hospital",
            y="state",
            orientation="h",
            title="Avg Beds per Hospital Site (top 10)",
            labels={"beds_per_hospital": "Avg Beds", "state": ""},
            color="beds_per_hospital",
            color_continuous_scale="Oranges",
        )
        fig_beds.update_layout(
            height=320,
            yaxis={"categoryorder": "total ascending"},
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig_beds, width="stretch")

    st.divider()

    # ── Interactive map (offline cache lookup) ─────────────────────────────────
    st.subheader("Interactive Hospital Map")

    cached = load_cache()
    all_pcs = df_locs["postal_code"].dropna().unique().tolist()
    n_ok = sum(1 for pc in all_pcs if cached.get(pc, (None, None))[0] is not None)
    n_unmapped = len(all_pcs) - n_ok

    st.info(
        f"**Map coverage from local cache:** ✅ {n_ok} mapped · "
        f"⬜ {n_unmapped} unmapped (total: {len(all_pcs)} unique postal codes)\n\n"
        "Coordinates are read from the committed `dashboard/geocache.csv` file.",
        icon="📍",
    )

    # Build map from whatever is cached
    df_map = df_locs.copy()
    df_map["lat"] = df_map["postal_code"].map(lambda pc: cached.get(pc, (None, None))[0])
    df_map["lon"] = df_map["postal_code"].map(lambda pc: cached.get(pc, (None, None))[1])
    df_map_valid = df_map.dropna(subset=["lat", "lon"])

    if len(df_map_valid) > 0:
        map_mode = st.radio("Map style", ["Heatmap", "Clusters"], horizontal=True)

        m = folium.Map(location=[51.1657, 10.4515], zoom_start=6, tiles="CartoDB positron")

        if map_mode == "Heatmap":
            HeatMap(
                [[r["lat"], r["lon"], r["hospital_count"]] for _, r in df_map_valid.iterrows()],
                radius=15, blur=25, min_opacity=0.4,
            ).add_to(m)
        else:
            cluster = MarkerCluster().add_to(m)
            for _, r in df_map_valid.iterrows():
                folium.CircleMarker(
                    location=[r["lat"], r["lon"]],
                    radius=max(4, min(18, int(r["hospital_count"]) * 2)),
                    popup=folium.Popup(
                        f"<b>{r['city']}</b> ({r['postal_code']})<br/>"
                        f"Hospitals: {int(r['hospital_count'])}<br/>"
                        f"Total beds: {int(r['total_beds'])}",
                        max_width=200,
                    ),
                    color="#1d4ed8",
                    fill=True,
                    fill_opacity=0.65,
                ).add_to(cluster)

        st.caption(
            f"Showing **{len(df_map_valid)}** of {len(df_map)} postal-code areas on the map."
        )
        st_folium(m, height=560, width="stretch")
    else:
        st.warning(
            "No mapped locations found in `dashboard/geocache.csv` yet. "
            "Run the geocache sync/update workflow and commit coordinates."
        )


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 – Surgery & Diagnosis Map
# ─────────────────────────────────────────────────────────────────────────────

with tab3:
    st.header("Where Are Specific Treatments Carried Out?")
    st.markdown(
        "Select a **diagnosis category (ICD)** or a **procedure category (OPS)** to see which "
        "hospitals treat the most patients.  \n"
        "*ICD codes* describe what a patient **has**; *OPS codes* describe what was **done**."
    )

    col_src, col_sel, col_n = st.columns([1, 3, 1])

    with col_src:
        data_source = st.radio("Source", ["Diagnoses (ICD)", "Procedures (OPS)"])

    with col_sel:
        if data_source == "Diagnoses (ICD)":
            icd_opts = _build_option_map(_load_icd_options(), ICD_CHAPTER_EN)
            icd_labels = list(icd_opts.keys())
            icd_default = next((i for i, l in enumerate(icd_labels) if icd_opts[l].startswith("I")), 0)
            chapter_label = st.selectbox(
                "Diagnosis (type to search)",
                icd_labels, index=icd_default,
                help="All ICD-10-GM 3-character codes found in hospital data, sorted by code.",
            )
            code_prefix = icd_opts[chapter_label]
            source_key = "icd"
        else:
            ops_opts = _build_option_map(_load_ops_options(), OPS_CHAPTER_EN)
            ops_labels = list(ops_opts.keys())
            ops_default = next((i for i, l in enumerate(ops_labels) if ops_opts[l].startswith("5-3")), 0)
            chapter_label = st.selectbox(
                "Procedure (type to search)",
                ops_labels, index=ops_default,
                help="All OPS 4-character prefixes found in hospital data, sorted by code.",
            )
            code_prefix = ops_opts[chapter_label]
            source_key = "ops"

    with col_n:
        top_n = st.number_input("Top N", min_value=5, max_value=2000, value=2000, step=5)

    with st.spinner("Querying database …"):
        df_top = _top_hospitals(code_prefix, source_key, int(top_n))

    if df_top.empty:
        st.warning("No data found for this selection.")
        st.stop()

    df_top["total_cases"] = pd.to_numeric(df_top["total_cases"], errors="coerce")

    # Resolve map points from committed local cache
    cached = load_cache()

    df_top["lat"] = df_top["postal_code"].map(
        lambda pc: cached.get(str(pc), (None, None))[0] if pd.notna(pc) else None
    )
    df_top["lon"] = df_top["postal_code"].map(
        lambda pc: cached.get(str(pc), (None, None))[1] if pd.notna(pc) else None
    )
    df_map_top = df_top.dropna(subset=["lat", "lon"])

    col_map, col_right = st.columns([3, 2])

    with col_map:
        m2 = folium.Map(location=[51.1657, 10.4515], zoom_start=6, tiles="CartoDB positron")
        max_cases = float(df_map_top["total_cases"].max()) if len(df_map_top) > 0 else 1.0

        for rank, (_, row) in enumerate(df_map_top.iterrows(), start=1):
            radius = 6 + 22 * float(row["total_cases"]) / max_cases
            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=radius,
                popup=folium.Popup(
                    f"<b>#{rank} {row['hospital_name']}</b><br/>"
                    f"{row['city']} &nbsp;({row['postal_code']})<br/>"
                    f"Cases: <b>{int(row['total_cases']):,}</b>",
                    max_width=300,
                ),
                tooltip=f"{row['hospital_name']} – {int(row['total_cases']):,} cases",
                color="#dc2626",
                fill=True,
                fill_color="#dc2626",
                fill_opacity=0.55,
            ).add_to(m2)

        st.caption(
            f"**{chapter_label}** · {len(df_map_top)} hospitals mapped · "
            "circle size ∝ case count · click for details"
        )
        st_folium(m2, height=590, width="stretch")

    with col_right:
        # Horizontal bar chart – top 15
        fig_top = px.bar(
            df_top.head(15),
            x="total_cases",
            y="hospital_name",
            orientation="h",
            title=f"Top 15 Hospitals",
            labels={"total_cases": "Cases", "hospital_name": ""},
            color="total_cases",
            color_continuous_scale="Reds",
            text="total_cases",
        )
        fig_top.update_traces(texttemplate="%{text:,}", textposition="outside")
        fig_top.update_layout(
            height=460,
            yaxis={"categoryorder": "total ascending"},
            coloraxis_showscale=False,
            margin={"r": 70},
        )
        st.plotly_chart(fig_top, width="stretch")

        with st.expander(f"Full table – top {len(df_top)}"):
            st.dataframe(
                df_top[["hospital_name", "city", "postal_code", "total_cases"]]
                .rename(columns={
                    "hospital_name": "Hospital",
                    "city": "City",
                    "postal_code": "PLZ",
                    "total_cases": "Cases",
                })
                .assign(Cases=lambda d: d["Cases"].astype("Int64")),
                width="stretch",
                hide_index=True,
            )


@st.cache_data(ttl=600)
def _available_years() -> list[int]:
    df = query_df("SELECT DISTINCT report_year FROM hospital_locations ORDER BY report_year")
    return [int(r) for r in df["report_year"]]


@st.cache_data(ttl=600)
def _year_summary(year: int) -> dict:
    df = query_df("""
        SELECT COUNT(*)                                        AS hospital_count,
               SUM(COALESCE(beds_count, 0))                   AS total_beds,
               SUM(COALESCE(inpatient_case_count, 0))         AS total_inpatient,
               SUM(COALESCE(partial_inpatient_case_count, 0)) AS total_partial,
               SUM(COALESCE(outpatient_case_count, 0))        AS total_outpatient
        FROM hospital_locations
        WHERE report_year = %s
    """, (year,))
    return {k: int(v) for k, v in df.iloc[0].items()}


@st.cache_data(ttl=600)
def _hospitals_both_years(year_a: int, year_b: int) -> pd.DataFrame:
    """Hospitals present in both years with side-by-side metrics."""
    return query_df("""
        SELECT a.hospital_name, a.city, a.postal_code,
               a.beds_count                                                             AS beds_a,
               b.beds_count                                                             AS beds_b,
               COALESCE(b.beds_count, 0) - COALESCE(a.beds_count, 0)                   AS beds_delta,
               a.inpatient_case_count                                                   AS inpatient_a,
               b.inpatient_case_count                                                   AS inpatient_b,
               COALESCE(b.inpatient_case_count, 0) - COALESCE(a.inpatient_case_count, 0) AS inpatient_delta,
               a.outpatient_case_count                                                  AS outpatient_a,
               b.outpatient_case_count                                                  AS outpatient_b,
               COALESCE(b.outpatient_case_count, 0) - COALESCE(a.outpatient_case_count, 0) AS outpatient_delta
        FROM hospital_locations a
        JOIN hospital_locations b
          ON a.ik = b.ik AND a.standortnummer = b.standortnummer
        WHERE a.report_year = %s AND b.report_year = %s
        ORDER BY ABS(COALESCE(b.inpatient_case_count, 0) - COALESCE(a.inpatient_case_count, 0)) DESC
    """, (year_a, year_b))


@st.cache_data(ttl=600)
def _hospitals_only_in(target_year: int, other_year: int) -> pd.DataFrame:
    """Hospitals that exist in target_year but NOT in other_year."""
    return query_df("""
        SELECT hospital_name, city, postal_code,
               beds_count, inpatient_case_count, outpatient_case_count
        FROM hospital_locations t
        WHERE t.report_year = %s
          AND NOT EXISTS (
              SELECT 1 FROM hospital_locations o
              WHERE o.ik = t.ik AND o.standortnummer = t.standortnummer
                AND o.report_year = %s
          )
        ORDER BY COALESCE(beds_count, 0) DESC
    """, (target_year, other_year))


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 – Year-on-Year Comparison
# ─────────────────────────────────────────────────────────────────────────────

with tab4:
    st.header("Year-on-Year Comparison")
    st.markdown(
        "Select any two report years to compare hospital capacity and activity. "
        "New years are picked up automatically from the database as data is ingested."
    )

    years = _available_years()
    if len(years) < 2:
        st.warning("At least two report years are needed for a comparison.")
        st.stop()

    col_ya, col_yb, _ = st.columns([1, 1, 3])
    with col_ya:
        year_a = st.selectbox("Base year", years, index=0, key="y5_a")
    with col_yb:
        remaining = [y for y in years if y != year_a]
        year_b = st.selectbox("Compare year", remaining,
                              index=len(remaining) - 1, key="y5_b")

    if year_a == year_b:
        st.warning("Please select two different years.")
        st.stop()

    with st.spinner("Loading comparison data …"):
        sa = _year_summary(year_a)
        sb = _year_summary(year_b)
        df_both = _hospitals_both_years(year_a, year_b)
        df_new = _hospitals_only_in(year_b, year_a)
        df_gone = _hospitals_only_in(year_a, year_b)

    numeric_cols = [
        "beds_a", "beds_b", "beds_delta",
        "inpatient_a", "inpatient_b", "inpatient_delta",
        "outpatient_a", "outpatient_b", "outpatient_delta",
    ]
    for col in numeric_cols:
        if col in df_both.columns:
            df_both[col] = pd.to_numeric(df_both[col], errors="coerce")

    # ── KPI row with deltas ───────────────────────────────────────────────────
    st.subheader(f"{year_a}  →  {year_b}")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Hospitals", f"{sb['hospital_count']:,}",
              delta=sb["hospital_count"] - sa["hospital_count"])
    k2.metric("Total Beds", f"{sb['total_beds']:,}",
              delta=sb["total_beds"] - sa["total_beds"])
    k3.metric("Inpatient Cases", f"{sb['total_inpatient']:,}",
              delta=sb["total_inpatient"] - sa["total_inpatient"])
    k4.metric("Partial Inpatient", f"{sb['total_partial']:,}",
              delta=sb["total_partial"] - sa["total_partial"])
    k5.metric("Outpatient Cases", f"{sb['total_outpatient']:,}",
              delta=sb["total_outpatient"] - sa["total_outpatient"])

    st.divider()

    # ── Side-by-side bar chart ────────────────────────────────────────────────
    metrics_df = pd.DataFrame({
        "Metric": ["Hospitals", "Beds (÷10)", "Inpatient (÷1000)",
                   "Partial Inp. (÷1000)", "Outpatient (÷1000)"],
        str(year_a): [
            sa["hospital_count"],
            sa["total_beds"] // 10,
            sa["total_inpatient"] // 1000,
            sa["total_partial"] // 1000,
            sa["total_outpatient"] // 1000,
        ],
        str(year_b): [
            sb["hospital_count"],
            sb["total_beds"] // 10,
            sb["total_inpatient"] // 1000,
            sb["total_partial"] // 1000,
            sb["total_outpatient"] // 1000,
        ],
    }).melt(id_vars="Metric", var_name="Year", value_name="Value")

    fig_compare = px.bar(
        metrics_df, x="Metric", y="Value", color="Year",
        barmode="group",
        title=f"Key Metrics: {year_a} vs {year_b}  (beds ÷10, cases ÷1000 for scale)",
        color_discrete_map={str(year_a): "#2563eb", str(year_b): "#f59e0b"},
        text_auto=True,
    )
    fig_compare.update_traces(textposition="outside")
    fig_compare.update_layout(height=380, legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig_compare, width="stretch")

    st.divider()

    # ── Scatter + new/gone tables ─────────────────────────────────────────────
    col_sc, col_tbl = st.columns([3, 2])

    with col_sc:
        df_sc5 = df_both.dropna(subset=["beds_a", "beds_b"]).copy()
        df_sc5["beds_a"] = pd.to_numeric(df_sc5["beds_a"])
        df_sc5["beds_b"] = pd.to_numeric(df_sc5["beds_b"])
        df_sc5["beds_delta"] = pd.to_numeric(df_sc5["beds_delta"])

        fig_sc5 = px.scatter(
            df_sc5,
            x="beds_a", y="beds_b",
            color="beds_delta",
            color_continuous_scale="RdYlGn",
            hover_data=["hospital_name", "city", "beds_delta"],
            title=f"Beds per Hospital: {year_a} (x) vs {year_b} (y)",
            labels={
                "beds_a": f"Beds {year_a}",
                "beds_b": f"Beds {year_b}",
                "beds_delta": "Δ Beds",
            },
            opacity=0.7,
        )
        # Diagonal = no change
        max_b = float(max(df_sc5["beds_a"].max(), df_sc5["beds_b"].max(), 1))
        fig_sc5.add_trace(go.Scatter(
            x=[0, max_b], y=[0, max_b],
            mode="lines", name="No change",
            line=dict(color="gray", width=1, dash="dash"),
            showlegend=True,
        ))
        fig_sc5.update_layout(height=460)
        st.plotly_chart(fig_sc5, width="stretch")

        # Top movers by inpatient delta
        st.subheader("Biggest Changes in Inpatient Cases")
        df_movers = df_both.dropna(subset=["inpatient_delta"]).copy()
        df_movers["inpatient_delta"] = pd.to_numeric(df_movers["inpatient_delta"])

        top_gain = df_movers.nlargest(8, "inpatient_delta")[
            ["hospital_name", "city", "inpatient_a", "inpatient_b", "inpatient_delta"]
        ]
        top_loss = df_movers.nsmallest(8, "inpatient_delta")[
            ["hospital_name", "city", "inpatient_a", "inpatient_b", "inpatient_delta"]
        ]
        combined = pd.concat([top_gain, top_loss])
        combined["inpatient_delta"] = pd.to_numeric(combined["inpatient_delta"])

        fig_movers = px.bar(
            combined,
            x="inpatient_delta",
            y="hospital_name",
            orientation="h",
            color="inpatient_delta",
            color_continuous_scale="RdYlGn",
            title=f"Top 8 Gainers & Losers (Inpatient Cases {year_a}→{year_b})",
            labels={"inpatient_delta": "Δ Cases", "hospital_name": ""},
            hover_data=["city", "inpatient_a", "inpatient_b"],
        )
        fig_movers.update_layout(
            height=420,
            yaxis={"categoryorder": "total ascending"},
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig_movers, width="stretch")

    with col_tbl:
        inner_tab_new, inner_tab_gone, inner_tab_both = st.tabs([
            f"🆕 New in {year_b} ({len(df_new)})",
            f"❌ Gone in {year_b} ({len(df_gone)})",
            f"🔄 In both ({len(df_both)})",
        ])

        with inner_tab_new:
            st.caption(f"Hospitals in {year_b} not present in {year_a}.")
            if df_new.empty:
                st.info("No new hospitals.")
            else:
                st.dataframe(
                    df_new[["hospital_name", "city", "beds_count", "inpatient_case_count"]]
                    .rename(columns={
                        "hospital_name": "Hospital", "city": "City",
                        "beds_count": "Beds", "inpatient_case_count": "Inpatient",
                    }),
                    width="stretch", hide_index=True, height=520,
                )

        with inner_tab_gone:
            st.caption(f"Hospitals in {year_a} not present in {year_b}.")
            if df_gone.empty:
                st.info("No removed hospitals.")
            else:
                st.dataframe(
                    df_gone[["hospital_name", "city", "beds_count", "inpatient_case_count"]]
                    .rename(columns={
                        "hospital_name": "Hospital", "city": "City",
                        "beds_count": "Beds", "inpatient_case_count": "Inpatient",
                    }),
                    width="stretch", hide_index=True, height=520,
                )

        with inner_tab_both:
            st.caption(f"Hospitals present in both {year_a} and {year_b}.")
            st.dataframe(
                df_both[["hospital_name", "city", "beds_a", "beds_b",
                          "beds_delta", "inpatient_a", "inpatient_b", "inpatient_delta"]]
                .rename(columns={
                    "hospital_name": "Hospital", "city": "City",
                    "beds_a": f"Beds {year_a}", "beds_b": f"Beds {year_b}",
                    "beds_delta": "Δ Beds",
                    "inpatient_a": f"Inp. {year_a}", "inpatient_b": f"Inp. {year_b}",
                    "inpatient_delta": "Δ Inpatient",
                }),
                width="stretch", hide_index=True, height=520,
            )
