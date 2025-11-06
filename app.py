import io
import pandas as pd
import streamlit as st
from rapidfuzz import process, fuzz
from unidecode import unidecode

st.set_page_config(page_title="Fuzzy Name Search", page_icon="🔎", layout="wide")

# ——————————————————————————————————————————————————————————————
# Helpers
# ——————————————————————————————————————————————————————————————

def normalize_text(s: str) -> str:
    if pd.isna(s):
        return ""
    s = str(s).strip().lower()
    s = unidecode(s)  # remove diacritics: Š → S, Ł → L, etc.
    # normalize punctuation to spaces
    for ch in [",", ".", ";", ":", "_", "/", "\\", "(", ")", "[", "]", "{", "}", "'", '"']:
        s = s.replace(ch, " ")
    # collapse multiple spaces
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
    # If sheet_name is None, load first sheet
    with io.BytesIO(file_bytes) as f:
        xl = pd.ExcelFile(f)
        use_sheet = sheet_name or xl.sheet_names[0]
        df = xl.parse(use_sheet)
    return df, xl.sheet_names

@st.cache_data(show_spinner=False)
def build_choices(df: pd.DataFrame, search_cols):
    # Build display value and normalized value for matching
    records = df.copy()
    # Coalesce selected columns into one search key
    if len(search_cols) == 1:
        records["_display"] = records[search_cols[0]].astype(str)
    else:
        records["_display"] = records[search_cols].astype(str).agg(" | ".join, axis=1)

    records["_norm"] = records["_display"].map(normalize_text)
    # Choices for RapidFuzz must be a list; keep index mapping
    choices = records["_norm"].tolist()
    meta = records.drop(columns=["_norm"])
    return choices, meta

def do_search(query, choices, meta, scorer, limit, min_score):
    qn = normalize_text(query)
    if not qn:
        return pd.DataFrame(columns=["score", "match", *meta.columns])
    # RapidFuzz returns list of tuples: (matched_string, score, index)
    results = process.extract(qn, choices, scorer=scorer, limit=limit)
    rows = []
    for _, score, idx in results:
        if score >= min_score:
            row = meta.iloc[idx]
            rows.append({"score": int(score), "match": row["_display"], **row.to_dict()})
    if rows:
        return pd.DataFrame(rows).sort_values("score", ascending=False, kind="mergesort").reset_index(drop=True)
    return pd.DataFrame(columns=["score", "match", *meta.columns])

# ——————————————————————————————————————————————————————————————
# UI
# ——————————————————————————————————————————————————————————————

st.title("🔎 Fuzzy Name Search")
st.caption("Upload your Excel/CSV and search for near‑matches (diacritics and minor spelling differences tolerated).")

with st.sidebar:
    st.header("⚙️ Settings")
    scorer_name = st.selectbox("Similarity method", list(SCORERS.keys()), index=0,
                               help="Try 'Token set' for reordered tokens, or 'Partial' for substrings.")
    min_score = st.slider("Minimum score", 0, 100, 70, help="Show only matches with score ≥ this value.")
    limit = st.slider("Max results", 1, 100, 25)

    st.markdown("---")
    st.write("**Tips**")
    st.write("- Normalize your data columns (first+last name in one column is ok).")
    st.write("- Diacritics are removed automatically (e.g., *Š* → *S*).")
    st.write("- Use 'Token set ratio' if word order often changes.")

tab1, tab2 = st.tabs(["🔼 Upload & Configure", "🔍 Search"])

with tab1:
    uploaded = st.file_uploader("Upload Excel (.xlsx) or CSV", type=["xlsx", "csv"])
    if uploaded is not None:
        file_bytes = uploaded.read()
        is_csv = uploaded.name.lower().endswith(".csv")
        if is_csv:
            df = pd.read_csv(io.BytesIO(file_bytes))
            sheet_names = None
        else:
            df, sheet_names = load_excel(file_bytes)
        st.success(f"Loaded **{uploaded.name}** ({len(df):,} rows).")
        if sheet_names:
            st.caption("Sheets found: " + ", ".join(sheet_names))

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
    else:
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