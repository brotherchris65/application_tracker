"""
ai_engine.py — All Anthropic API calls.
API key lives in st.secrets["anthropic"]["api_key"].
"""

import streamlit as st
import anthropic
import json
import db

RESUME = """
Name: Christopher Hill
Title: Data Engineering Manager & BI Lead
Location: Burleson, TX
Contact: 817-805-0832 | brotherchris65@gmail.com | linkedin.com/in/chris-hill02020

SUMMARY:
Results-driven Data Engineering leader who builds high-performing teams, earns executive
trust, and delivers enterprise-grade data infrastructure. Daily engagement with C-Suite and
VP-level stakeholders. Led migration to Snowflake Bronze/Silver/Gold medallion architecture.
Expert in the modern data stack.

SKILLS:
Platforms: Snowflake, Power BI, NetSuite, Zoho CRM, Infusionsoft, MySQL, Docker, Django
Languages: Python (Pandas, NumPy, Matplotlib, SQLAlchemy), SQL, HTML, JavaScript, CSS
Data Integration: Airbyte, Fivetran, Dagster, Rudderstack
AI Development: Snowflake Cortex AI, Streamlit, LLM Functions, Agent Development
Frameworks: dbt, Power Query, DAX, SQLAlchemy
Data Engineering: Medallion Architecture, Dev/Prod Environment Management,
  ETL/ELT Pipeline Design, Data Governance, Naming Conventions,
  Pipeline Monitoring, Data Integrity Testing
Analysis: Data Wrangling, Data Mining, Data Visualization, Executive Reporting
Certifications: Google Data Analytics Certification (2021), Google Certified Educator Level 2 (2020)

EXPERIENCE:

Brave Thinking Institute (2022–Present) — Data Engineering Manager & BI Lead
- Lead cross-functional team of data engineers, data scientists, and contractors
- Engage daily with C-Suite and VP-level leadership on strategy and insights
- Architected migration of disparate data sources into Snowflake with Bronze/Silver/Gold
  medallion architecture and separate dev/prod environments in Snowflake and dbt
- Established ETL governance policies, naming conventions, mandatory dbt schema tests,
  and a monitoring dashboard
- Ingest data from CRM (Zoho, Infusionsoft), financial (NetSuite), and marketing sources
  via Airbyte and Fivetran
- Manage customer profile and identity resolution via Rudderstack
- Build and orchestrate production ELT pipelines with Dagster and dbt
- Develop AI agents using Snowflake Cortex; build Streamlit executive dashboards
- Create and maintain Power BI reports with DAX and Power Query
- Track lead opt-in/conversion rates; calculate ROI across marketing channels

Vio Security (2021–2022) — Business Intelligence Analyst
- Extracted data from multiple sources; maintained Sales, Service, and Financial
  dashboards and reports in Power BI
- Created Sales and Service reports that drove significant operational changes
- Produced Residual Monthly Revenue Reports and weekly/monthly maintenance logs

Texas Public Schools (2007–2021) — Computer Science & Robotics Instructor | Mathematics Teacher
- Pioneered district's first Computer Science program (Python, HTML, CSS) — 97% success rate
- Led faculty data literacy initiative; trained 50+ educators — 100% adoption
- Led district-level data analysis project producing a new student intervention program
- Served as curriculum lead for Mathematics department

EDUCATION:
- Master of Education, Educational Leadership — Lamar University (2010)
- Master of Divinity with Biblical Languages — Southwestern Baptist Theological Seminary (2002)
- BS, Occupational Education (Russian, Religion & Crypto-Linguistics) — Wayland Baptist University (1999)
- US Air Force — Airborne Russian Cryptologic Linguist, Worldwide (1983–1999)
"""


def _client():
    return anthropic.Anthropic(api_key=st.secrets["anthropic"]["api_key"])


def analyze(job_id: str, title: str, company: str, jd: str) -> bool:
    """
    Run full AI analysis: match score, skills, tailored resume, cover letter.
    Saves everything to Snowflake. Returns True on success.
    """
    prompt = f"""You are an expert resume writer and job-match analyst.
Return ONLY valid JSON — no markdown fences, no commentary, just the raw JSON object.

{{
  "score": <integer 0-100 match percentage>,
  "summary": "<2 sentence overall match summary>",
  "matched_skills": ["skill1", "skill2"],
  "gap_skills": ["skill1", "skill2"],
  "nice_to_have": ["skill1", "skill2"],
  "tailored_resume": {{
    "summary": "<3-4 sentence professional summary rewritten to mirror this job's language and priorities — 100% truthful to actual experience>",
    "skills": {{
      "platforms": "<comma-separated, reordered to prioritize what matches this job>",
      "languages": "<comma-separated>",
      "data_integration": "<comma-separated>",
      "ai_development": "<comma-separated>",
      "frameworks": "<comma-separated>",
      "data_engineering": "<comma-separated>",
      "analysis": "<comma-separated>"
    }},
    "experience": [
      {{
        "company": "Brave Thinking Institute",
        "title": "Data Engineering Manager & BI Lead",
        "dates": "2022 – Present",
        "bullets": ["<rewritten bullet using job keywords where truthful — 6 bullets>"]
      }},
      {{
        "company": "Vio Security",
        "title": "Business Intelligence Analyst",
        "dates": "2021 – 2022",
        "bullets": ["<rewritten bullet — 3 bullets>"]
      }},
      {{
        "company": "Texas Public Schools",
        "title": "Computer Science & Robotics Instructor | Mathematics Teacher",
        "dates": "2007 – 2021",
        "bullets": ["<rewritten bullet — 3 bullets>"]
      }}
    ]
  }},
  "cover_letter": "<full professional cover letter ~350 words, To Hiring Manager, signed Christopher Hill, referencing the specific role and company, highlighting most relevant achievements>"
}}

CANDIDATE RESUME:
{RESUME}

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
