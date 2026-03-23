"""
db.py — Snowflake connection and all database operations.
All credentials come from st.secrets (never hardcoded).
"""

import streamlit as st
from snowflake.connector import connect, DictCursor
import json
from datetime import date, datetime
import uuid
import base64
import binascii
from cryptography.hazmat.primitives import serialization


# ── Connection ────────────────────────────────────────────────────────────────

@st.cache_resource
def get_conn():
    """Return a cached Snowflake connection."""
    s = st.secrets["snowflake"]
    private_key = s["private_key"]
    passphrase = s.get("private_key_passphrase", "")

    placeholder_fields = [
        "account",
        "user",
        "private_key",
        "warehouse",
    ]
    for field in placeholder_fields:
        value = str(s.get(field, ""))
        if "<your-" in value or "<paste-" in value:
            raise ValueError(
                "Snowflake secrets are placeholders. Update .streamlit/secrets.toml with real values."
            )

    if isinstance(private_key, str):
        normalized = private_key.strip()
        if "\\n" in normalized and "BEGIN" in normalized:
            normalized = normalized.replace("\\n", "\n")

        if "BEGIN" in normalized:
            try:
                key_obj = serialization.load_pem_private_key(
                    normalized.encode("utf-8"),
                    password=passphrase.encode("utf-8") if passphrase else None,
                )
            except ValueError as exc:
                raise ValueError(
                    "Invalid snowflake.private_key in Streamlit secrets. Use a valid PEM private key and correct passphrase."
                ) from exc
            private_key = key_obj.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        else:
            try:
                private_key = base64.b64decode("".join(normalized.split()), validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ValueError(
                    "Invalid snowflake.private_key in Streamlit secrets. Provide PEM text (with BEGIN/END) or a base64-encoded DER key."
                ) from exc

    return connect(
        account=s["account"],
        user=s["user"],
        private_key=private_key,
        warehouse=s["warehouse"],
        database=s.get("database", "JOB_TRACKER"),
        schema=s.get("schema", "PUBLIC"),
        role=s.get("role", ""),
    )


def run(sql, params=None, fetch=False):
    """Execute SQL, optionally returning rows as dicts."""
    conn = get_conn()
    with conn.cursor(DictCursor) as cur:
        cur.execute(sql, params or ())
        if fetch:
            rows = cur.fetchall()
            # Lowercase all keys for consistent access
            return [{k.lower(): v for k, v in row.items()} for row in rows]
        return None


# ── Bootstrap ─────────────────────────────────────────────────────────────────

def init():
    """Create database, schema, and tables if they don't exist."""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("CREATE DATABASE IF NOT EXISTS JOB_TRACKER")
        cur.execute("USE DATABASE JOB_TRACKER")
        cur.execute("CREATE SCHEMA IF NOT EXISTS PUBLIC")
        cur.execute("USE SCHEMA PUBLIC")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS JOBS (
                JOB_ID        VARCHAR(40)   PRIMARY KEY,
                TITLE         VARCHAR(200)  NOT NULL,
                COMPANY       VARCHAR(200)  NOT NULL,
                LOCATION      VARCHAR(200),
                URL           VARCHAR(2000),
                SALARY        VARCHAR(100),
                STATUS        VARCHAR(20)   DEFAULT 'saved',
                APP_DATE      DATE,
                FOLLOW_DATE   DATE,
                JD            TEXT,
                NOTES         TEXT,
                MATCH_SCORE   INTEGER,
                MATCH_SUMMARY TEXT,
                CREATED_AT    TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS JOB_ANALYSIS (
                JOB_ID          VARCHAR(40)  PRIMARY KEY REFERENCES JOBS(JOB_ID),
                MATCH_SCORE     INTEGER,
                MATCH_SUMMARY   TEXT,
                MATCHED_SKILLS  VARIANT,
                GAP_SKILLS      VARIANT,
                NICE_TO_HAVE    VARIANT,
                ANALYZED_AT     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS JOB_DOCUMENTS (
                DOC_ID      VARCHAR(40)   PRIMARY KEY,
                JOB_ID      VARCHAR(40)   REFERENCES JOBS(JOB_ID),
                DOC_TYPE    VARCHAR(20),   -- 'resume' | 'cover_letter'
                CONTENT     TEXT,
                CREATED_AT  TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (JOB_ID, DOC_TYPE)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS APP_SETTINGS (
                SETTING_KEY   VARCHAR(100) PRIMARY KEY,
                SETTING_VALUE TEXT,
                UPDATED_AT    TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP
            )
        """)
    conn.commit()


# ── Job CRUD ──────────────────────────────────────────────────────────────────

def insert_job(*, title, company, url, location, salary, status,
               app_date, follow_date, jd, notes):
    job_id = str(uuid.uuid4())
    run("""
        INSERT INTO JOBS
            (JOB_ID, TITLE, COMPANY, LOCATION, URL, SALARY, STATUS,
             APP_DATE, FOLLOW_DATE, JD, NOTES)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (job_id, title, company, location or None, url or None,
          salary or None, status,
          app_date or None, follow_date or None,
          jd or None, notes or None))
    get_conn().commit()
    return job_id


def get_all_jobs(search=None, status=None):
    where_parts = []
    params = []
    if search:
        where_parts.append("(LOWER(TITLE) LIKE %s OR LOWER(COMPANY) LIKE %s)")
        params += [f"%{search.lower()}%", f"%{search.lower()}%"]
    if status:
        where_parts.append("STATUS = %s")
        params.append(status)
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    rows = run(f"""
        SELECT j.*, a.MATCH_SCORE, a.MATCH_SUMMARY,
               a.MATCHED_SKILLS, a.GAP_SKILLS, a.NICE_TO_HAVE
        FROM JOBS j
        LEFT JOIN JOB_ANALYSIS a USING (JOB_ID)
        {where}
        ORDER BY j.CREATED_AT DESC
    """, params, fetch=True)
    return _parse_jobs(rows)


def get_jobs_by_status(status):
    rows = run("""
        SELECT j.*, a.MATCH_SCORE
        FROM JOBS j
        LEFT JOIN JOB_ANALYSIS a USING (JOB_ID)
        WHERE j.STATUS = %s
        ORDER BY j.CREATED_AT DESC
    """, (status,), fetch=True)
    return _parse_jobs(rows)


def get_recent_jobs(n=6):
    rows = run("""
        SELECT j.JOB_ID, j.TITLE, j.COMPANY, j.STATUS, a.MATCH_SCORE
        FROM JOBS j
        LEFT JOIN JOB_ANALYSIS a USING (JOB_ID)
        ORDER BY j.CREATED_AT DESC
        LIMIT %s
    """, (n,), fetch=True)
    return rows or []


def get_stats():
    jobs = run("SELECT STATUS FROM JOBS", fetch=True) or []
    today = date.today()
    followups = run(
        "SELECT COUNT(*) AS CNT FROM JOBS WHERE FOLLOW_DATE <= %s AND STATUS NOT IN ('offer','rejected')",
        (today,), fetch=True
    )
    total = len(jobs)
    applied = sum(1 for j in jobs if j["status"] in ("applied", "interview", "offer"))
    interviews = sum(1 for j in jobs if j["status"] == "interview")
    due = followups[0]["cnt"] if followups else 0
    return {"total": total, "applied": applied, "interviews": interviews, "followups_due": due}


def get_reminders():
    rows = run("""
        SELECT JOB_ID, TITLE, COMPANY, FOLLOW_DATE
        FROM JOBS
        WHERE FOLLOW_DATE IS NOT NULL
          AND STATUS NOT IN ('offer','rejected')
        ORDER BY FOLLOW_DATE ASC
    """, fetch=True)
    return rows or []


def update_status(job_id, status):
    run("UPDATE JOBS SET STATUS = %s WHERE JOB_ID = %s", (status, job_id))
    get_conn().commit()


def update_job_details(job_id, *, title, company, url, location, salary, jd):
    run("""
        UPDATE JOBS
        SET TITLE = %s,
            COMPANY = %s,
            URL = %s,
            LOCATION = %s,
            SALARY = %s,
            JD = %s
        WHERE JOB_ID = %s
    """, (
        title,
        company,
        url or None,
        location or None,
        salary or None,
        jd or None,
        job_id,
    ))
    get_conn().commit()


def delete_job(job_id):
    run("DELETE FROM JOB_DOCUMENTS WHERE JOB_ID = %s", (job_id,))
    run("DELETE FROM JOB_ANALYSIS WHERE JOB_ID = %s", (job_id,))
    run("DELETE FROM JOBS WHERE JOB_ID = %s", (job_id,))
    get_conn().commit()


def update_notes(job_id, notes, follow_date, app_date):
    run("""
        UPDATE JOBS SET NOTES = %s, FOLLOW_DATE = %s, APP_DATE = %s
        WHERE JOB_ID = %s
    """, (notes, follow_date, app_date, job_id))
    get_conn().commit()


# ── Analysis ──────────────────────────────────────────────────────────────────

def save_analysis(job_id, score, summary, matched, gaps, nice):
    run("""
        MERGE INTO JOB_ANALYSIS AS t
        USING (SELECT %s AS JOB_ID) AS s ON t.JOB_ID = s.JOB_ID
        WHEN MATCHED THEN UPDATE SET
            MATCH_SCORE = %s, MATCH_SUMMARY = %s,
            MATCHED_SKILLS = PARSE_JSON(%s), GAP_SKILLS = PARSE_JSON(%s),
            NICE_TO_HAVE = PARSE_JSON(%s), ANALYZED_AT = CURRENT_TIMESTAMP
        WHEN NOT MATCHED THEN INSERT
            (JOB_ID, MATCH_SCORE, MATCH_SUMMARY, MATCHED_SKILLS, GAP_SKILLS, NICE_TO_HAVE)
            VALUES (%s,%s,%s, PARSE_JSON(%s), PARSE_JSON(%s), PARSE_JSON(%s))
    """, (
        job_id,
        score, summary, json.dumps(matched), json.dumps(gaps), json.dumps(nice),
        job_id, score, summary, json.dumps(matched), json.dumps(gaps), json.dumps(nice),
    ))
    # Also denormalize score/summary onto JOBS for quick access
    run("UPDATE JOBS SET MATCH_SCORE = %s, MATCH_SUMMARY = %s WHERE JOB_ID = %s",
        (score, summary, job_id))
    get_conn().commit()


def get_analysis(job_id):
    rows = run("""
        SELECT MATCH_SCORE, MATCH_SUMMARY,
               MATCHED_SKILLS, GAP_SKILLS, NICE_TO_HAVE
        FROM JOB_ANALYSIS WHERE JOB_ID = %s
    """, (job_id,), fetch=True)
    if not rows:
        return None
    r = rows[0]
    return {
        "match_score":    r["match_score"],
        "match_summary":  r["match_summary"],
        "matched_skills": _parse_variant(r.get("matched_skills")),
        "gap_skills":     _parse_variant(r.get("gap_skills")),
        "nice_to_have":   _parse_variant(r.get("nice_to_have")),
    }


# ── Documents ─────────────────────────────────────────────────────────────────

def save_document(job_id, doc_type, content):
    """Upsert a resume or cover letter (stored as text/JSON string)."""
    run("""
        MERGE INTO JOB_DOCUMENTS AS t
        USING (SELECT %s AS JOB_ID, %s AS DOC_TYPE) AS s
              ON t.JOB_ID = s.JOB_ID AND t.DOC_TYPE = s.DOC_TYPE
        WHEN MATCHED THEN UPDATE SET CONTENT = %s, CREATED_AT = CURRENT_TIMESTAMP
        WHEN NOT MATCHED THEN INSERT (DOC_ID, JOB_ID, DOC_TYPE, CONTENT)
            VALUES (%s, %s, %s, %s)
    """, (job_id, doc_type, content, str(uuid.uuid4()), job_id, doc_type, content))
    get_conn().commit()


def get_document(job_id, doc_type):
    rows = run("""
        SELECT CONTENT, CREATED_AT FROM JOB_DOCUMENTS
        WHERE JOB_ID = %s AND DOC_TYPE = %s
    """, (job_id, doc_type), fetch=True)
    return rows[0] if rows else None


def set_setting(key, value):
    run("""
        MERGE INTO APP_SETTINGS AS t
        USING (SELECT %s AS SETTING_KEY) AS s ON t.SETTING_KEY = s.SETTING_KEY
        WHEN MATCHED THEN UPDATE SET SETTING_VALUE = %s, UPDATED_AT = CURRENT_TIMESTAMP
        WHEN NOT MATCHED THEN INSERT (SETTING_KEY, SETTING_VALUE)
            VALUES (%s, %s)
    """, (key, value, key, value))
    get_conn().commit()


def get_setting(key):
    rows = run("""
        SELECT SETTING_VALUE, UPDATED_AT
        FROM APP_SETTINGS
        WHERE SETTING_KEY = %s
    """, (key,), fetch=True)
    return rows[0] if rows else None


def save_base_resume(resume_text):
    set_setting("base_resume", resume_text)


def get_base_resume():
    row = get_setting("base_resume")
    if not row:
        return None
    return row.get("setting_value")


def clear_base_resume():
    run("DELETE FROM APP_SETTINGS WHERE SETTING_KEY = %s", ("base_resume",))
    get_conn().commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_variant(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    try:
        return json.loads(v)
    except Exception:
        return []


def _parse_jobs(rows):
    if not rows:
        return []
    result = []
    for r in rows:
        r["matched_skills"] = _parse_variant(r.get("matched_skills"))
        r["gap_skills"]     = _parse_variant(r.get("gap_skills"))
        r["nice_to_have"]   = _parse_variant(r.get("nice_to_have"))
        result.append(r)
    return result
