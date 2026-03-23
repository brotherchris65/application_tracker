# JobTrack — Chris Hill

A Streamlit job application tracker with AI-powered resume tailoring,
cover letter generation, and Snowflake-backed storage.

---

## Features

- **Add & track jobs** — paste job URLs and descriptions, set status, follow-up dates
- **Resume Manager** — upload your current resume (`.txt` or `.docx`), replace with a different version, or edit the active resume text
- **AI Analysis** — match score, matched skills, skill gaps, nice-to-haves
- **Tailored Resume** — full rewritten resume generated per job, downloadable as `.docx` and `.pdf`
- **Cover Letter** — AI-written, tailored to each specific role
- **Pipeline view** — Kanban-style board by status
- **Reminders** — overdue and upcoming follow-up alerts
- **Snowflake storage** — all data persists in your own Snowflake account

---

## Project Structure

```
jobtracker/
├── app.py              # Main Streamlit app & all UI
├── db.py               # Snowflake connection & all queries
├── ai_engine.py        # Anthropic API calls (analysis, resume, cover letter)
├── docx_builder.py     # Builds formatted .docx from resume data
├── requirements.txt    # Python dependencies
├── .gitignore          # Keeps secrets.toml out of git
├── secrets.example.toml # Safe template for local setup
└── secrets.toml        # Your local credentials (never commit this)
```

---

## Setup

### 1. Clone / create a GitHub repo

Push all files to a GitHub repository except your local `secrets.toml`.
The `.gitignore` already excludes `secrets.toml`.

### 2. Fill in your secrets

Create your local secrets file from the template:

```bash
cp secrets.example.toml secrets.toml
```

Then edit `secrets.toml` with your Anthropic and Snowflake values.

**Finding your Snowflake account identifier:**
1. Log into app.snowflake.com
2. Click your name (bottom left) → hover your account
3. Copy the account identifier (format: `orgname-accountname` or `accountname.region`)

### 3. Deploy to Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click **New app** → connect your GitHub repo
3. Set **Main file path** to `app.py`
4. Go to **Advanced settings → Secrets**
5. Paste the contents of your `secrets.toml`
6. Click **Deploy**

### 4. Run locally (optional)

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## First Run

On first launch the app automatically creates:
- `JOB_TRACKER` database
- `PUBLIC` schema
- `JOBS`, `JOB_ANALYSIS`, and `JOB_DOCUMENTS` tables

No manual SQL required.

---

## Security Notes

- Keep real credentials only in local `secrets.toml` and in your Streamlit Cloud Secrets panel
- Commit only `secrets.example.toml`; never commit `secrets.toml`
- Streamlit Community Cloud encrypts secrets at rest
- The `.docx` is generated in memory and sent directly to your browser — nothing is written to disk
