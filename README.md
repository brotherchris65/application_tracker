# JobTrack — Chris Hill

A Streamlit job application tracker with AI-powered resume tailoring,
cover letter generation, and Snowflake-backed storage.

---

## Features

- **Add & track jobs** — paste job URLs and descriptions, set status, follow-up dates
- **AI Analysis** — match score, matched skills, skill gaps, nice-to-haves
- **Tailored Resume** — full rewritten resume generated per job, downloadable as `.docx`
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
└── .streamlit/
    └── secrets.toml    # Your credentials (never commit this)
```

---

## Setup

### 1. Clone / create a GitHub repo

Push all files **except** `.streamlit/secrets.toml` to a GitHub repository.
The `.gitignore` already excludes it.

### 2. Fill in your secrets

Edit `.streamlit/secrets.toml`:

```toml
[anthropic]
api_key = "sk-ant-api03-..."        # From console.anthropic.com → API Keys

[snowflake]
account   = "abc12345.us-east-1"   # From Snowflake: Admin → Accounts → copy identifier
user      = "CHRIS"
password  = "your_password"
warehouse = "COMPUTE_WH"
database  = "JOB_TRACKER"          # Created automatically on first run
schema    = "PUBLIC"
role      = "SYSADMIN"
```

**Finding your Snowflake account identifier:**
1. Log into app.snowflake.com
2. Click your name (bottom left) → hover your account
3. Copy the account identifier (format: `orgname-accountname` or `accountname.region`)

### 3. Deploy to Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click **New app** → connect your GitHub repo
3. Set **Main file path** to `app.py`
4. Go to **Advanced settings → Secrets**
5. Paste the contents of your `secrets.toml` (without the comment block at the top)
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

- Your Anthropic API key and Snowflake credentials live **only** in Streamlit secrets
- They are never stored in the code or committed to GitHub
- Streamlit Community Cloud encrypts secrets at rest
- The `.docx` is generated in memory and sent directly to your browser — nothing is written to disk
