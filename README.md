# 🔎 Fuzzy Name Search (Streamlit + RapidFuzz)

A ready‑to‑run web app for fuzzy searching names from an Excel/CSV list.
It tolerates minor spelling differences and diacritics (Š→S, Ł→L, etc.).

## Features
- Upload **Excel (.xlsx)** or **CSV**
- Choose which columns to search (e.g., full name)
- Adjustable similarity threshold and method
- Ranked results with scores
- Download matches as CSV
- Works offline if self‑hosted; easy to deploy online

## One‑click deploy (Streamlit Community Cloud)
1. Create a **new GitHub repo** and add these files: `app.py`, `requirements.txt`, `.streamlit/config.toml` (optional), `README.md`.
2. Go to **share.streamlit.io** → **New app** → select your repo and set **Main file path** to `app.py`.
3. Click **Deploy**. Your app gets a public URL you can share.

## Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```
The app will open in your browser at http://localhost:8501

## Notes
- For very large files (e.g., >200k rows), consider pre‑filtering by first letter or splitting files.
- Try different scorers: **WRatio** (balanced), **Token set ratio** (good for re‑ordered words), **Partial ratio** (substrings).