# app.py — unified UI (no tabs), Google Sheets as the shared dataset

# app.py — unified UI (no tabs), Google Sheets as the shared dataset

import streamlit as st
import pandas as pd
from rapidfuzz import fuzz

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(
    page_title="Fuzzy Name Search – In iure",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# -------------------------------------------------
# Styling (background, header, basic tweaks)
# -------------------------------------------------
st.markdown(
    """
    <style>
        /* Page background */
        .stApp {
            background-color: #9ac288;
        }

        /* Header: logo + title row */
        .header-title-wrapper {
            display: flex;
            align-items: center;
            height: 100%;
        }

        .main-header {
            font-size: 38px;
            font-weight: 800;
            color: #0d3436;
            margin: 0;
            padding: 0;
        }

        /* Make table header slightly tinted */
        table thead tr th {
            background-color: #f0f6f0;
        }

        /* Hide anchor link icons on headings */
        .block-container h1 a,
        .block-container h2 a,
        .block-container h3 a {
            display: none !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------
# Logo + Title
# -------------------------------------------------
col_logo, col_title, col_spacer = st.columns([1, 4, 1])

with col_logo:
    # logo file must exist in repo root
    st.image("in_iure_logo.jpg", width=260)

with col_title:
    st.markdown(
        '<div class="header-title-wrapper">'
        '<div class="main-header">PROJEKTAS: archyvų skaitmeninimas</div>'
        "</div>",
        unsafe_allow_html=True,
    )

st.write("")  # small spacing


# -------------------------------------------------
# Data loading
# -------------------------------------------------
GOOGLE_SHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "17LgN7oWAxjLf620y96HM2Yeda4J8FgCe/gviz/tq?tqx=out:csv"
)


@st.cache_data(show_spinner="Kraunamas duomenų rinkinys iš Google Sheets...")
def load_data() -> pd.DataFrame:
    df = pd.read_csv(GOOGLE_SHEET_CSV_URL)
    return df


def clear_data_cache():
    load_data.clear()


# Load data
try:
    df = load_data()
except Exception as e:
    st.error(
        "Nepavyko įkelti duomenų iš Google Sheets. "
        "Patikrinkite nuorodą ir ar lentelė dalinamasi kaip "
        "„Anyone with the link → Viewer“."
    )
    st.exception(e)
    st.stop()

# Top-right "Refresh data" button
top_left, top_right = st.columns([6, 1])
with top_right:
    if st.button("🔄 Refresh data"):
        clear_data_cache()
        st.experimental_rerun()

# -------------------------------------------------
# Sidebar – settings
# -------------------------------------------------
with st.sidebar:
    st.header("Nustatymai")

    scorer_name = st.selectbox(
        "Panašumo metodas",
        options=["WRatio (subalansuotas)", "Token set ratio", "Partial ratio"],
        index=0,
    )

    min_score = st.slider("Minimalus panašumo balas", 0, 100, 70, 1)
    max_results = st.slider("Rodomų rezultatų skaičius", 1, 200, 25, 1)

    st.markdown(
        """
        **Pastaba:**  
        - *WRatio* – labiausiai subalansuotas bendras metodas  
        - *Token set ratio* – atlaidesnis su skiemenimis / žodžių tvarka  
        - *Partial ratio* – kai ieškoma tik dalies vardo/pavardės
        """
    )

# Map scorer choice to RapidFuzz function
if scorer_name.startswith("WRatio"):
    scorer_func = fuzz.WRatio
elif scorer_name.startswith("Token"):
    scorer_func = fuzz.token_set_ratio
else:
    scorer_func = fuzz.partial_ratio

# -------------------------------------------------
# Main search controls
# -------------------------------------------------
st.subheader("Choose search columns")

cols1, cols2 = st.columns([1, 2])

with cols1:
    all_columns = list(df.columns)
    default_search_cols = []

    # try to guess a default column like "Pavardė"
    for candidate in ["Pavardė", "Pavarde", "Pavardė", "Pavardė "]:
        if candidate in all_columns:
            default_search_cols = [candidate]
            break

    search_cols = st.multiselect(
        "Columns to match against",
        options=all_columns,
        default=default_search_cols or all_columns[:1],
    )

with cols2:
    query = st.text_input("Type a name (e.g., Urjasevitz)", "")

st.write("")
st.caption(f"Search will run against {len(df)} records.")
st.write("")


# -------------------------------------------------
# Fuzzy search implementation
# -------------------------------------------------
def run_fuzzy_search(
    df: pd.DataFrame,
    query_text: str,
    search_cols: list[str],
    scorer,
    max_results: int,
    min_score: int,
) -> pd.DataFrame:
    """Run fuzzy search over the chosen columns and return a result DataFrame."""
    records: list[dict] = []

    if not query_text:
        return pd.DataFrame()

    for _, row in df.iterrows():
        combined = " ".join(
            str(row[c]) for c in search_cols if c in df.columns and pd.notna(row[c])
        )

        # Fuzzy score
        score = scorer(query_text, combined)
        score = int(round(score))  # ✅ round to whole number

        if score >= min_score:
            rec = row.to_dict()
            rec["score"] = score
            records.append(rec)

        if len(records) >= max_results:
            break

    if not records:
        return pd.DataFrame()

    results_df = pd.DataFrame(records)
    results_df = results_df.sort_values("score", ascending=False).reset_index(drop=True)
    return results_df


# -------------------------------------------------
# Run search and display results
# -------------------------------------------------
if query:
    results_df = run_fuzzy_search(
        df,
        query,
        search_cols,   # columns chosen in multiselect
        scorer_func,   # similarity method
        max_results,   # ✅ correct variable
        min_score,
    )

    if not results_df.empty:
        st.write(f"Showing {len(results_df)} result(s).")

        # Remove "Dokumentas" column if present
        cleaned_df = results_df.copy()
        if "Dokumentas" in cleaned_df.columns:
            cleaned_df = cleaned_df.drop(columns=["Dokumentas"])

        # Replace NaN with "-" for display and download
        display_df = cleaned_df.fillna("-")

        # Show as a normal Streamlit table
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
        )

        # Download button (same cleaned data)
        csv_bytes = display_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "Download results as CSV",
            data=csv_bytes,
            file_name="fuzzy_search_results.csv",
            mime="text/csv",
        )
    else:
        st.info(
            "No matches found at this threshold. "
            "Try lowering **Minimum score** or choosing a different **Similarity method**."
        )
else:
    st.caption("Start typing above to see matches.")
