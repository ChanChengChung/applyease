# ApplyEase — Polymer Capital submission assets

This document is intentionally tied to the implemented product. Do not claim
automatic third-party submission, sentence-offset citations, guaranteed
interviews, or an AI capability that has not been demonstrated on screen.

## One-page write-up draft

### ApplyEase: Evidence-First Application OS for technical students

Hong Kong students repeatedly tailor CVs, cover letters and online application
forms, but generic AI can create claims they cannot defend in an interview.
ApplyEase turns a student's scattered CV projects into an **Experience Bank**:
editable facts that the student must explicitly confirm before the AI may use
them. For every role, it maps requirements to that confirmed evidence, makes
gaps visible, and then produces reviewable material rather than silently
submitting an application.

**How it works.** A FastAPI backend parses PDF/DOCX CVs into PostgreSQL records.
React/TypeScript presents an editable Experience Bank. A job-analysis service
extracts required and preferred skills, then matches only confirmed records.
For generation, ApplyEase retrieves user-scoped evidence through Milvus RAG;
the local default is Ollama `qwen3:4b`, with optional Gemini fallback and a
deterministic rule fallback for reliable demos. Every generated material carries
experience-level source citations. Validation checks that the cited experience
is confirmed, the quote exists in that experience, and the cited claim appears
in the generated material. Unsupported numerical claims fail the fact check and
block Resume export.

**Why it is different.** Existing application tools optimise volume, tracking or
keyword scores. ApplyEase optimises **defensibility**: a requirement is shown as
either supported by a confirmed source or a learning gap. Sensitive fields such
as work authorisation, identity and salary remain explicitly manual. The product
does not auto-submit third-party applications. Missing skills become a
time-bounded resource/project plan with a CV outcome template.

**Impact and next step.** The result is a complete loop: evidence → role proof
map → grounded Resume/Cover Letter/form answers → user-confirmed filling →
tracking and gap-closing plan. Next, I will extend claim provenance from
experience-level sources to granular spans and evaluate it with a larger student
CV/JD benchmark.

## 7-minute video script and screen route

| Time | Say | Show |
| --- | --- | --- |
| 0:00–0:35 | “I am Chen, and I build AI systems that make student experience defensible—not merely better worded. My own application pain was rewriting the same facts for every role.” | ApplyEase title + one-line positioning. |
| 0:35–1:10 | “Students already have projects, courses and activities, but not every fact fits every job. Generic AI can also write claims that fail in an interview.” | Dashboard → open **90-second judge walkthrough**. |
| 1:10–1:50 | “I start with a human-confirmed Experience Bank. Unconfirmed content never becomes application evidence.” | Walkthrough step 1 / Profile. Point at confirmed state and editable source. |
| 1:50–2:40 | “For a Quant/AI role, ApplyEase extracts requirements and makes a Proof Map. Green is supported; amber is a visible gap. A score alone cannot hide missing evidence.” | Job Analysis → match report + Proof Map. |
| 2:40–3:45 | “The generation layer uses user-scoped retrieval. My local default is Qwen through Ollama; Gemini is optional fallback; rules keep the system usable when a provider fails.” | Application Builder generation states → Integrity Gate. |
| 3:45–4:30 | “This is the differentiator: each material cites confirmed experience. I can challenge a claim before an interviewer does. A failed fact check blocks export.” | Evidence Tracing → click challenge → Integrity Gate. |
| 4:30–5:10 | “AI helps with application questions, but sensitive fields are deliberately manual. The user previews and confirms any fill; ApplyEase never submits.” | Form Assistant demo questions, including work-authorisation manual field. |
| 5:10–5:45 | “When evidence is missing, the system does not fabricate it. It turns the gap into a time-bounded project plan and Quant/AI interview rehearsal.” | Resource Plan + Quant/AI Readiness Pack. |
| 5:45–6:25 | “The Tracker connects the real state: materials, answers, evidence, gaps and next action. Version observations are labelled as observations—not fake causal A/B results.” | Tracker workspace / Dashboard role command center. |
| 6:25–7:00 | “ApplyEase is not an auto-apply bot. It is an Evidence-First Application OS: AI drafts; confirmed experience proves. Next I will improve claim-level provenance and benchmark quality across diverse student applications.” | Return to dashboard; show boundary statement. |

## Recording checklist

1. Start Docker and open `http://localhost:5173` in a private browser window.
2. Use the **Load demo data** button. It now seeds confirmed experiences, a
   Quant/AI target role, deterministic fact-checked Resume/Cover Letter,
   answerable + manual application questions, and a saved tracker record.
3. Avoid showing real email addresses, API keys, browser tabs, or raw CV PII.
4. Record the local deterministic demo rather than relying on a live model call.
5. Keep the two honest caveats in the spoken reflection: experience-level—not
   sentence-offset—citations, and no automated external submission.
