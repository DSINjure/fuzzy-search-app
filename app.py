import io
import pandas as pd
import streamlit as st
from rapidfuzz import process, fuzz
from unidecode import unidecode

st.set_page_config(page_title="Fuzzy Name Search", page_icon="🔎", layout="wide")

def normalize_text(s: str) -> str:
    if pd.isna(s):
        return ""
    s = str(s).strip().lower()
    s = unidecode(s)
    for ch in [",", ".", ";", ":", "_", "/", "\\", "(", ")", "[", "]", "{", "}", "'", '"']:
        s = s.replace(ch, " ")
    s = " ".join(s.split())
    return s

SCORERS = {
    "WRatio (balanced)": fuzz.WRatio,
    "Token sort ratio": fuzz.token_sort_ratio,
    "Token set ratio": fuzz.token_set_ratio,
    "Partial ratio": fuzz.partial_ratio,
}

@st.cache_data(show_spinner=False)
def load_excel(file_bytes: bytes, sheet_name=None):
    with io.BytesIO(file_bytes) as f:
        xl = pd.ExcelFile(f)
        use_sheet = sheet_name or xl.sheet_names[0]
        df = xl.parse(use_sheet)
    return df, xl.sheet_names

@st.cache_data(show_spinner=False)
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
    results = process.extract(qn, choices, scorer=scorer, limit=limit)
    rows = []
    for _, score, idx in results:
        if score >= min_score:
            row = meta.iloc[idx]
            rows.append({"score": int(score), "match": row["_display"], **row.to_dict()})
    if rows:
        return pd.DataFrame(rows).sort_values("score", ascending=False, kind="mergesort").reset_index(drop=True)
    return pd.DataFrame(columns=["score", "match", *meta.columns])

st.title("🔎 Fuzzy Name Search")
st.caption("Upload your Excel/CSV and search for near-matches (diacritics and minor spelling differences tolerated).")

with st.sidebar:
    st.header("⚙️ Settings")
    scorer_name = st.selectbox("Similarity method", list(SCORERS.keys()), index=0)
    min_score = st.slider("Minimum score", 0, 100, 70)
    limit = st.slider("Max results", 1, 100, 25)

tab1, tab2 = st.tabs(["🔼 Upload & Configure", "🔍 Search"])

with tab1:
    URL = "https://docs.google.com/spreadsheets/d/17LgN7oWAxjLf620y96HM2Yeda4J8FgCe/gviz/tq?tqx=out:csv"

st.info("Loading shared dataset from Google Sheets...")

@st.cache_data(show_spinner=True)
def load_google_sheet(url: str):
    import pandas as _pd
    return _pd.read_csv(url)
if st.button("🔄 Refresh data"):
    load_google_sheet.clear()  # clear only this function's cache
    st.toast("Reloading data…")
    st.rerun()                 # restart the script so it fetches fresh data
try:
    df = load_google_sheet(URL)
    st.success(f"Loaded {len(df):,} rows from shared Google Sheet.")
    sheet_names = None  # keep API compatibility below

    st.subheader("Choose search columns")
    cols = list(df.columns)
    default_cols = [c for c in cols if str(c).lower() in ["name", "names", "full_name"]] or cols[:1]
    search_cols = st.multiselect("Columns to match against", cols, default=default_cols)

    if not search_cols:
        st.warning("Select at least one column to search against.")
    else:
        choices, meta = build_choices(df, search_cols)
        st.info(f"Search will run against {len(choices):,} records.")
        st.session_state["choices"] = choices
        st.session_state["meta"] = meta
        st.session_state["ready"] = True
except Exception as e:
    st.error("Could not load the Google Sheet. Check that the link is correct and the sheet is shared as 'Anyone with the link → Viewer'.")
    st.exception(e)
    st.session_state["ready"] = False

with tab2:
    if st.session_state.get("ready"):
        q = st.text_input("Type a name (e.g., *Urjasevitz*)", "")
        if q:
            results_df = do_search(q, st.session_state["choices"], st.session_state["meta"],
                                   SCORERS[scorer_name], limit, min_score)
            st.write(f"Showing {len(results_df):,} results.")
            st.dataframe(results_df, use_container_width=True, hide_index=True)
            if len(results_df):
                csv = results_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button("Download results as CSV", csv, file_name="fuzzy_search_results.csv")
        else:
            st.caption("Enter a query to see matches.")
    else:
        st.warning("Upload and configure your dataset in the first tab.")
