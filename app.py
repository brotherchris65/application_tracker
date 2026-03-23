import streamlit as st
import json
from datetime import date, timedelta
import db
import ai_engine
import docx_builder

st.set_page_config(
    page_title="JobTrack — Chris Hill",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    [data-testid="stSidebar"] { background-color: #16181c; }
    .metric-card { background:#16181c; border:1px solid rgba(255,255,255,0.08); border-radius:12px; padding:18px 20px; text-align:center; }
    .metric-card .num { font-size:2rem; font-weight:600; color:#f0ede8; }
    .metric-card .lbl { font-size:0.75rem; color:#5e5d5a; text-transform:uppercase; letter-spacing:1px; }
    .score-high { color:#4caf7d; font-weight:600; }
    .score-mid  { color:#c8a96e; font-weight:600; }
    .score-low  { color:#e05c5c; font-weight:600; }
    .tag-match { background:rgba(76,175,125,0.15); color:#4caf7d; padding:2px 10px; border-radius:20px; font-size:0.8rem; margin:2px; display:inline-block; }
    .tag-gap   { background:rgba(224,92,92,0.15);  color:#e05c5c; padding:2px 10px; border-radius:20px; font-size:0.8rem; margin:2px; display:inline-block; }
    .tag-nice  { background:rgba(91,155,213,0.15); color:#5b9bd5; padding:2px 10px; border-radius:20px; font-size:0.8rem; margin:2px; display:inline-block; }
    .reminder-overdue { color:#e05c5c; font-weight:600; }
    .reminder-soon    { color:#c8a96e; font-weight:600; }
    .reminder-ok      { color:#4caf7d; }
</style>
""", unsafe_allow_html=True)

db.init()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📋 JobTrack")
    st.caption("Chris Hill · Data Engineering")
    st.divider()
    page = st.radio("Navigate", ["🏠 Dashboard","➕ Add Job","⚡ Pipeline","📄 All Jobs","⏰ Reminders"], label_visibility="collapsed")
    st.divider()
    stats = db.get_stats()
    st.markdown(f"**Total tracked:** {stats['total']}")
    st.markdown(f"**Applied:** {stats['applied']}")
    st.markdown(f"**Interviews:** {stats['interviews']}")
    st.markdown(f"**Follow-ups due:** <span style='color:#e05c5c'>{stats['followups_due']}</span>", unsafe_allow_html=True)


# ── Job detail renderer (defined before page routing) ─────────────────────────
def render_job_detail(j):
    tab_overview, tab_analysis, tab_resume, tab_cover, tab_notes = st.tabs(
        ["Overview", "AI Analysis", "Tailored Resume", "Cover Letter", "Notes"]
    )

    with tab_overview:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Status:** `{j['status'].upper()}`")
            st.markdown(f"**Salary:** {j.get('salary') or '—'}")
            st.markdown(f"**Applied:** {j.get('app_date') or '—'}")
            st.markdown(f"**Follow-up:** {j.get('follow_date') or '—'}")
            if j.get("url"):
                st.markdown(f"[View posting ↗]({j['url']})")
        with c2:
            if j.get("match_score") is not None:
                sc = j["match_score"]
                color = "#4caf7d" if sc >= 75 else "#c8a96e" if sc >= 50 else "#e05c5c"
                st.markdown(f"<div style='font-size:2.5rem;font-weight:700;color:{color}'>{sc}%</div>", unsafe_allow_html=True)
                st.caption(j.get("match_summary") or "")
            else:
                st.info("No analysis yet.")
                if j.get("jd") and st.button("⚡ Run Analysis", key=f"ov_analyze_{j['job_id']}"):
                    with st.spinner("Analyzing…"):
                        ai_engine.analyze(j["job_id"], j["title"], j["company"], j["jd"])
                    st.rerun()
        st.markdown("---")
        st.markdown("**Update Status**")
        status_opts = ["saved","applied","interview","offer","rejected"]
        new_status = st.selectbox("Status", status_opts,
                                  index=status_opts.index(j["status"]),
                                  key=f"status_{j['job_id']}", label_visibility="collapsed")
        if new_status != j["status"]:
            db.update_status(j["job_id"], new_status)
            st.success("Status updated.")
            st.rerun()

    with tab_analysis:
        analysis = db.get_analysis(j["job_id"])
        if not analysis:
            if not j.get("jd"):
                st.warning("No job description on file.")
            elif st.button("⚡ Run AI Analysis", key=f"run_an_{j['job_id']}", type="primary"):
                with st.spinner("Analyzing against your resume…"):
                    ai_engine.analyze(j["job_id"], j["title"], j["company"], j["jd"])
                st.rerun()
        else:
            sc = analysis["match_score"]
            color = "#4caf7d" if sc >= 75 else "#c8a96e" if sc >= 50 else "#e05c5c"
            st.markdown(f"<span style='font-size:2rem;font-weight:700;color:{color}'>{sc}% Match</span>", unsafe_allow_html=True)
            st.markdown(analysis.get("match_summary",""))
            st.markdown("---")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("**✅ Skills You Match**")
                for s in (analysis.get("matched_skills") or []):
                    st.markdown(f'<span class="tag-match">{s}</span>', unsafe_allow_html=True)
            with c2:
                st.markdown("**❌ Gaps to Address**")
                for s in (analysis.get("gap_skills") or []):
                    st.markdown(f'<span class="tag-gap">{s}</span>', unsafe_allow_html=True)
            with c3:
                st.markdown("**💡 Nice to Have**")
                for s in (analysis.get("nice_to_have") or []):
                    st.markdown(f'<span class="tag-nice">{s}</span>', unsafe_allow_html=True)
            if st.button("↺ Re-analyze", key=f"reanalyze_{j['job_id']}"):
                with st.spinner("Re-analyzing…"):
                    ai_engine.analyze(j["job_id"], j["title"], j["company"], j["jd"])
                st.rerun()

    with tab_resume:
        doc = db.get_document(j["job_id"], "resume")
        if not doc:
            if not j.get("jd"):
                st.warning("No job description on file.")
            elif st.button("⚡ Generate Tailored Resume", key=f"gen_res_{j['job_id']}", type="primary"):
                with st.spinner("Generating tailored resume…"):
                    ai_engine.analyze(j["job_id"], j["title"], j["company"], j["jd"])
                st.rerun()
        else:
            resume_data = json.loads(doc["content"])
            st.markdown(f"*Tailored for* **{j['title']}** *at* **{j['company']}**")
            with st.expander("📄 Preview Resume", expanded=True):
                st.markdown("### Christopher Hill")
                st.caption("Data Engineering Manager · BI Lead · Burleson, TX")
                st.markdown("---")
                st.markdown("**PROFESSIONAL SUMMARY**")
                st.write(resume_data.get("summary",""))
                st.markdown("**PROFESSIONAL EXPERIENCE**")
                for exp in resume_data.get("experience",[]):
                    st.markdown(f"**{exp['company']}** — *{exp['title']}* · {exp['dates']}")
                    for b in exp.get("bullets",[]):
                        st.markdown(f"- {b}")
            docx_bytes = docx_builder.build(resume_data, j["title"], j["company"])
            safe_name = f"ChrisHill_Resume_{'_'.join(j['company'].split())[:20]}_{'_'.join(j['title'].split())[:20]}.docx"
            st.download_button("⬇ Download .docx", data=docx_bytes, file_name=safe_name,
                               mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                               key=f"dl_{j['job_id']}", type="primary")
            if st.button("↺ Regenerate Resume", key=f"regen_{j['job_id']}"):
                with st.spinner("Regenerating…"):
                    ai_engine.analyze(j["job_id"], j["title"], j["company"], j["jd"])
                st.rerun()

    with tab_cover:
        doc = db.get_document(j["job_id"], "cover_letter")
        if not doc:
            if not j.get("jd"):
                st.warning("No job description on file.")
            elif st.button("⚡ Generate Cover Letter", key=f"gen_cl_{j['job_id']}", type="primary"):
                with st.spinner("Writing cover letter…"):
                    ai_engine.analyze(j["job_id"], j["title"], j["company"], j["jd"])
                st.rerun()
        else:
            st.text_area("Cover Letter", value=doc["content"], height=420, key=f"cl_{j['job_id']}")

    with tab_notes:
        new_notes  = st.text_area("Notes", value=j.get("notes") or "", height=120, key=f"notes_{j['job_id']}")
        new_follow = st.date_input("Follow-up Date", value=j.get("follow_date") or date.today() + timedelta(days=7), key=f"follow_{j['job_id']}")
        new_app    = st.date_input("Application Date", value=j.get("app_date") or date.today(), key=f"app_{j['job_id']}")
        if st.button("💾 Save Notes", key=f"savenotes_{j['job_id']}"):
            db.update_notes(j["job_id"], new_notes, new_follow, new_app)
            st.success("Saved!")
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Dashboard
# ══════════════════════════════════════════════════════════════════════════════
if page == "🏠 Dashboard":
    st.title("Dashboard")
    st.caption("Your job search at a glance")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="num">{stats["total"]}</div><div class="lbl">Total Tracked</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="num">{stats["applied"]}</div><div class="lbl">Applications Sent</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="num">{stats["interviews"]}</div><div class="lbl">Interviews</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="metric-card"><div class="num" style="color:#e05c5c">{stats["followups_due"]}</div><div class="lbl">Follow-ups Due</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("⏰ Follow-up Reminders")
        reminders = db.get_reminders()
        if not reminders:
            st.info("No follow-up reminders set.")
        else:
            today = date.today()
            for r in reminders[:8]:
                diff = (r["follow_date"] - today).days
                if diff < 0:
                    label, cls = f"🔴 Overdue by {abs(diff)}d", "reminder-overdue"
                elif diff <= 3:
                    label, cls = f"🟡 Due in {diff}d", "reminder-soon"
                else:
                    label, cls = f"🟢 {r['follow_date'].strftime('%m/%d/%y')}", "reminder-ok"
                st.markdown(f"**{r['title']}** · {r['company']} — <span class='{cls}'>{label}</span>", unsafe_allow_html=True)

    with col_r:
        st.subheader("🕐 Recent Activity")
        recent = db.get_recent_jobs(6)
        if not recent:
            st.info("No jobs tracked yet.")
        else:
            for j in recent:
                sc = j.get("match_score")
                score_html = ""
                if sc is not None:
                    cls = "score-high" if sc >= 75 else "score-mid" if sc >= 50 else "score-low"
                    score_html = f' <span class="{cls}">{sc}%</span>'
                st.markdown(f"**{j['title']}** · {j['company']}{score_html} — `{j['status'].upper()}`", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Add Job
# ══════════════════════════════════════════════════════════════════════════════
elif page == "➕ Add Job":
    st.title("Add New Job")
    st.caption("Paste a job description and save, or run AI analysis immediately")

    with st.form("add_job_form"):
        c1, c2 = st.columns(2)
        with c1:
            title    = st.text_input("Job Title *", placeholder="e.g. Data Engineering Manager")
            url      = st.text_input("Job URL", placeholder="https://linkedin.com/jobs/...")
            salary   = st.text_input("Salary Range", placeholder="e.g. $130k – $160k")
            app_date = st.date_input("Application Date", value=date.today())
        with c2:
            company     = st.text_input("Company *", placeholder="Company name")
            location    = st.text_input("Location", placeholder="City, ST or Remote")
            status      = st.selectbox("Status", ["saved","applied","interview","offer","rejected"])
            follow_date = st.date_input("Follow-up Reminder", value=date.today() + timedelta(days=7))
        jd    = st.text_area("Job Description * (paste full text for AI analysis)", height=200,
                             placeholder="Paste the complete job description here…")
        notes = st.text_area("Notes", height=80)

        col_s, col_a, _ = st.columns([1,2,3])
        with col_s:
            save_only    = st.form_submit_button("💾 Save Job", use_container_width=True)
        with col_a:
            save_analyze = st.form_submit_button("⚡ Save + Analyze with AI", type="primary", use_container_width=True)

    if save_only or save_analyze:
        if not title or not company:
            st.error("Please enter at least a Job Title and Company.")
        else:
            job_id = db.insert_job(title=title, company=company, url=url, location=location,
                                   salary=salary, status=status, app_date=app_date,
                                   follow_date=follow_date, jd=jd, notes=notes)
            st.success(f"✓ Saved: **{title}** at **{company}**")
            if save_analyze:
                if not jd:
                    st.warning("No job description — AI analysis skipped.")
                else:
                    with st.spinner("Analyzing against your resume…"):
                        ok = ai_engine.analyze(job_id, title, company, jd)
                    if ok:
                        st.success("✓ AI analysis complete! Find this job under All Jobs.")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Pipeline
# ══════════════════════════════════════════════════════════════════════════════
elif page == "⚡ Pipeline":
    st.title("Pipeline")
    statuses = ["saved","applied","interview","offer"]
    colors   = {"saved":"#9b7fe8","applied":"#5b9bd5","interview":"#c8a96e","offer":"#4caf7d"}
    cols = st.columns(4)

    for col, status in zip(cols, statuses):
        jobs = db.get_jobs_by_status(status)
        with col:
            st.markdown(f"<div style='color:{colors[status]};font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px'>{status.upper()} ({len(jobs)})</div>", unsafe_allow_html=True)
            if not jobs:
                st.caption("No jobs")
            for j in jobs:
                score_str = f" · {j['match_score']}%" if j.get("match_score") is not None else ""
                with st.expander(f"{j['company'][:18]} — {j['title'][:20]}{score_str}"):
                    if j.get("app_date"):
                        st.caption(f"Applied: {j['app_date']}")
                    if j.get("follow_date"):
                        diff = (j["follow_date"] - date.today()).days
                        if diff < 0:
                            st.markdown(f"<span class='reminder-overdue'>⚠ Follow-up overdue</span>", unsafe_allow_html=True)
                        elif diff <= 3:
                            st.markdown(f"<span class='reminder-soon'>⏰ Follow-up in {diff}d</span>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: All Jobs
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📄 All Jobs":
    st.title("All Jobs")

    fc1, fc2 = st.columns([3,2])
    with fc1:
        search = st.text_input("Search", placeholder="Search by title or company…", label_visibility="collapsed")
    with fc2:
        status_filter = st.selectbox("Status", ["All","saved","applied","interview","offer","rejected"], label_visibility="collapsed")

    jobs = db.get_all_jobs(search=search, status=status_filter if status_filter != "All" else None)

    if not jobs:
        st.info("No jobs found. Add your first job using the sidebar.")
    else:
        for j in jobs:
            sc = j.get("match_score")
            score_str = f" · {sc}%" if sc is not None else ""
            with st.expander(f"**{j['title']}** · {j['company']}{score_str}  —  `{j['status'].upper()}`"):
                render_job_detail(j)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Reminders
# ══════════════════════════════════════════════════════════════════════════════
elif page == "⏰ Reminders":
    st.title("Follow-up Reminders")

    reminders = db.get_reminders()
    if not reminders:
        st.info("No follow-up reminders set. Add a follow-up date when saving a job.")
    else:
        today = date.today()
        overdue  = [r for r in reminders if (r["follow_date"] - today).days < 0]
        upcoming = [r for r in reminders if 0 <= (r["follow_date"] - today).days <= 7]
        later    = [r for r in reminders if (r["follow_date"] - today).days > 7]

        if overdue:
            st.markdown("### 🔴 Overdue")
            for r in overdue:
                diff = abs((r["follow_date"] - today).days)
                st.markdown(f"**{r['title']}** · {r['company']} — <span class='reminder-overdue'>Overdue by {diff} day{'s' if diff!=1 else ''}</span>", unsafe_allow_html=True)

        if upcoming:
            st.markdown("### 🟡 This Week")
            for r in upcoming:
                diff = (r["follow_date"] - today).days
                msg = "Today" if diff == 0 else f"In {diff} day{'s' if diff!=1 else ''}"
                st.markdown(f"**{r['title']}** · {r['company']} — <span class='reminder-soon'>{msg}</span>", unsafe_allow_html=True)

        if later:
            st.markdown("### 🟢 Upcoming")
            for r in later:
                st.markdown(f"**{r['title']}** · {r['company']} — {r['follow_date'].strftime('%b %d, %Y')}")
