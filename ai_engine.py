"""
ai_engine.py — All Anthropic API calls.
API key lives in st.secrets["anthropic"]["api_key"].
"""

import streamlit as st
import anthropic
import json
import base64
import db
import pdf_builder


def _client():
    return anthropic.Anthropic(api_key=st.secrets["anthropic"]["api_key"])


def _base_resume_text() -> str | None:
    saved = db.get_base_resume()
    if not saved:
        return None
    saved_text = str(saved).strip()
    return saved_text if saved_text else None


def analyze(job_id: str, title: str, company: str, jd: str) -> bool:
    """
    Run full AI analysis: match score, skills, tailored resume, cover letter.
    Saves everything to Snowflake. Returns True on success.
    """
    base_resume = _base_resume_text()
    if not base_resume:
        st.error("No active resume found. Upload your resume in Resume Manager before running AI analysis.")
        return False

    prompt = f"""You are an expert resume writer and job-match analyst.
Return ONLY valid JSON — no markdown fences, no commentary, just the raw JSON object.

{{
  "score": <integer 0-100 match percentage>,
  "summary": "<2 sentence overall match summary>",
  "matched_skills": ["skill1", "skill2"],
  "gap_skills": ["skill1", "skill2"],
  "nice_to_have": ["skill1", "skill2"],
  "tailored_resume": {{
    "name": "<candidate full name from resume if available, else empty string>",
    "headline": "<candidate title/headline from resume if available, else empty string>",
    "contact": "<single line contact info from resume if available, else empty string>",
    "summary": "<3-4 sentence professional summary rewritten to mirror this job's language and priorities — 100% truthful to actual experience>",
    "skills": {{
      "core": "<comma-separated skills prioritized for this role>"
    }},
    "experience": [
      {{
        "company": "<company>",
        "title": "<title>",
        "dates": "<date range>",
        "bullets": ["<2-6 rewritten bullets using job keywords where truthful>"]
      }}
    ],
    "education": ["<optional education line>", "<optional education line>"],
    "certifications": ["<optional certification>", "<optional certification>"]
  }},
  "cover_letter": "<full professional cover letter ~350 words, addressed To Hiring Manager, signed with candidate name from resume, referencing the specific role and company, highlighting most relevant achievements>"
}}

CANDIDATE RESUME:
{base_resume}

TARGET JOB: {title} at {company}
{jd}"""

    try:
        message = _client().messages.create(
            model="claude-opus-4-5",
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        # Strip accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        parsed = json.loads(raw)

        # ── Save analysis ────────────────────────────────────────────────────
        db.save_analysis(
            job_id=job_id,
            score=int(parsed.get("score", 0)),
            summary=parsed.get("summary", ""),
            matched=parsed.get("matched_skills", []),
            gaps=parsed.get("gap_skills", []),
            nice=parsed.get("nice_to_have", []),
        )

        # ── Save tailored resume ─────────────────────────────────────────────
        tr = parsed.get("tailored_resume")
        if tr:
            db.save_document(job_id, "resume", json.dumps(tr))
            pdf_bytes = pdf_builder.build(tr, title, company)
            db.save_document(job_id, "resume_pdf", base64.b64encode(pdf_bytes).decode("utf-8"))

        # ── Save cover letter ────────────────────────────────────────────────
        cl = parsed.get("cover_letter", "")
        if cl:
            db.save_document(job_id, "cover_letter", cl)

        return True

    except json.JSONDecodeError as e:
        st.error(f"AI returned invalid JSON: {e}")
        return False
    except anthropic.AuthenticationError:
        st.error("Invalid Anthropic API key. Check your secrets.toml.")
        return False
    except Exception as e:
        st.error(f"AI analysis failed: {e}")
        return False
