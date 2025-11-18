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
        '</div>',
        unsafe_allow_html=True,
    )

st.write("")  # small spacing


# -------------------------------------------------
# Data loading
# -------------------------------------------------
GOOGLE_SHEET_CSV_URL = (
    "https://docs.google.com/spreadsheets/d/17LgN7oWAxjLf620y96HM2Yeda4J8FgCe/export?format=cvs"
    # ^ change here if you switch to another sheet
)


@st.cache_data(show_spinner="Kraunamas duomenų rinkinys iš Google Sheets...")
def load_data(url: str) -> pd.DataFrame:
    df = pd.read_csv(url)
    return df


def clear_data_cache():
    load_data.clear()


# Load data
try:
    df = load_data(GOOGLE_SHEET_CSV_URL)
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
    st.caption("Columns to match against")
    all_columns = list(df.columns)
    default_search_cols = []

    # try to guess a default column like "Pavardė"
    for candidate in ["Pavardė", "Pavarde", "Pavardė", "Pavardė "]:
        if candidate in all_columns:
            default_search_cols = [candidate]
            break

    search_cols = st.multiselect(
        "",
        options=all_columns,
        default=default_search_cols or all_columns[:1],
    )

with cols2:
    st.caption("Type a name (e.g., Urjasevitz)")
    query = st.text_input("", "")

st.write("")
st.caption(f"Search will run against {len(df)} records.")
st.write("")


# -------------------------------------------------
# Fuzzy search implementation
# -------------------------------------------------
def run_fuzzy_search(
    data: pd.DataFrame,
    query_text: str,
    columns: list[str],
    scorer,
    min_score: int,
    limit: int,
) -> pd.DataFrame:
    if not query_text.strip():
        return pd.DataFrame()

    records = []
    for _, row in data.iterrows():
        combined = " ".join(
            str(row[c]) for c in columns if c in row and pd.notna(row[c])
        )
        if not combined.strip():
            continue

        score = scorer(query_text, combined)
        if score >= min_score:
            rec = row.to_dict()
            rec["score"] = score
            records.append(rec)

    if not records:
        return pd.DataFrame()

    res = pd.DataFrame(records)
    res = res.sort_values("score", ascending=False)
    res = res.head(limit)
    # move score to the first column
    cols_order = ["score"] + [c for c in res.columns if c != "score"]
    return res[cols_order]


# -------------------------------------------------
# Run search and display results
# -------------------------------------------------
if query:
    results_df = run_fuzzy_search(
        df,
        query_text=query,
        columns=search_cols,
        scorer=scorer_func,
        min_score=min_score,
        limit=max_results,
    )

    if not results_df.empty:
        st.write(f"Showing {len(results_df)} result(s).")

        # If "Dokumentas" column exists, turn it into clickable eye icons
        display_df = results_df.copy()
        if "Dokumentas" in display_df.columns:
            def to_eye_link(url: str) -> str:
                if isinstance(url, str) and url.strip():
                    return f'<a href="{url}" target="_blank">👁️</a>'
                return ""

            display_df["Dokumentas"] = display_df["Dokumentas"].apply(to_eye_link)

        # Render as HTML to allow clickable icons
        html_table = display_df.to_html(escape=False, index=False)
        st.write(html_table, unsafe_allow_html=True)

        # Download button
        csv_bytes = results_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "Download results as CSV",
            data=csv_bytes,
            file_name="fuzzy_search_results.csv",
            mime="text/csv",
        )
    else:
        st.info(
            "Pagal pasirinktą minimalų balą atitikmenų nerasta. "
            "Pabandykite sumažinti **Minimalus panašumo balas** nustatymą "
            "arba pakeisti panašumo metodą."
        )
else:
    st.caption("Start typing above to see matches.")
