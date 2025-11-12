# app.py — unified UI (no tabs), Google Sheets as the shared dataset

import io
import os
import pandas as pd
import streamlit as st
from rapidfuzz import process, fuzz
from unidecode import unidecode

# ---------- Page setup ----------
st.set_page_config(page_title="Fuzzy Name Search", page_icon="🔎", layout="wide")

# Optional: small CSS tidy-up (hide Streamlit chrome)
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ---------- Helpers ----------
def normalize_text(s: str) -> str:
    if pd.isna(s):
        return ""
    s = str(s).strip().lower()
    s = unidecode(s)  # Š→S, Ł→L, etc.
    for ch in [",", ".", ";", ":", "_", "/", "\\", "(", ")", "[", "]", "{", "}", "'", '"']:
        s = s.replace(ch, " ")
    return " ".join(s.split())

SCORERS = {
    "WRatio (balanced)": fuzz.WRatio,
    "Token sort ratio": fuzz.token_sort_ratio,
    "Token set ratio": fuzz.token_set_ratio,
    "Partial ratio": fuzz.partial_ratio,
}

@st.cache_data(show_spinner=False)
def load_google_sheet(url: str) -> pd.DataFrame:
    # Loads a public (view-only) Google Sheet published as CSV.
    return pd.read_csv(url)

def build_choices(df: pd.DataFrame, search_cols):
    records = df.copy()
    if len(search_cols) == 1:
        records["_display"] = records[search_cols[0]].astype(str)
    else:
        records["_display"] = records[search_cols].astype(str).agg(" | ".join, axis=1)
    records["_norm"] = records["_display"].map(normalize_text)
    choices = records["_norm"].tolist()
    meta = records.drop(columns=["_norm"])
    return choices, meta

def do_search(query, choices, meta, scorer, limit, min_score):
    qn = normalize_text(query)
    if not qn:
        return pd.DataFrame(columns=["score", "match", *meta.columns])
    results = process.extract(qn, choices, scorer=scorer, limit=limit)  # (string, score, idx)
    rows = []
    for _, score, idx in results:
        if score >= min_score:
            row = meta.iloc[idx]
            rows.append({"score": int(score), "match": row["_display"], **row.to_dict()})
    if rows:
        out = pd.DataFrame(rows).sort_values("score", ascending=False, kind="mergesort").reset_index(drop=True)
        # Keep score + match first
        cols = ["score", "match"] + [c for c in out.columns if c not in ("score", "match")]
        return out[cols]
    return pd.DataFrame(columns=["score", "match", *meta.columns])

# ---------- Sidebar (settings) ----------
with st.sidebar:
    st.header("Settings")
    scorer_name = st.selectbox("Similarity method", list(SCORERS.keys()), index=0,
                               help="Try 'Token set ratio' if word order varies; 'Partial' for substrings.")
    min_score = st.slider("Minimum score", 0, 100, 70)
    limit = st.slider("Max results", 1, 100, 25)
    st.caption("Diacritics normalized automatically (e.g., Š→S, Ł→L).")

# ---------- Data source (Google Sheets) ----------
URL = "https://docs.google.com/spreadsheets/d/17LgN7oWAxjLf620y96HM2Yeda4J8FgCe/gviz/tq?tqx=out:csv"

# Load Google Sheet silently + optional refresh button
colA, colB = st.columns([4, 1])
with colA:
    try:
        df = load_google_sheet(URL)
    except Exception as e:
        st.error("Could not load the Google Sheet. Check the link and sharing (Anyone with the link → Viewer).")
        st.exception(e)
        st.stop()
with colB:
    if st.button("🔄 Refresh data"):
        load_google_sheet.clear()
        st.rerun()

# ---------- Main controls (columns selector + search box side by side) ----------
cols = list(df.columns)
default_cols = [c for c in cols if str(c).lower() in ["name", "names", "full_name"]] or cols[:1]

left, right = st.columns([1, 2], vertical_alignment="bottom")
with left:
    st.subheader("Choose search columns", anchor=False)
    search_cols = st.multiselect("Columns to match against", cols, default=default_cols)

with right:
    q = st.text_input("Type a name (e.g., *Urjasevitz*)", "")

if not search_cols:
    st.caption("Select at least one column to search against.")
    st.stop()

# Build search space
choices, meta = build_choices(df, search_cols)
st.caption(f"Search will run against {len(choices):,} records.")

# ---------- Results ----------
if q:
    results_df = do_search(q, choices, meta, SCORERS[scorer_name], limit, min_score)
    st.write(f"Showing {len(results_df):,} results.")
    if not results_df.empty:
        st.dataframe(results_df, use_container_width=True, hide_index=True)
        csv = results_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("Download results as CSV", csv, file_name="fuzzy_search_results.csv")
    else:
        st.info("No matches at this threshold. Try lowering **Minimum score** or switch to **Token set ratio**.")
else:
    st.caption("Start typing above to see matches.")
