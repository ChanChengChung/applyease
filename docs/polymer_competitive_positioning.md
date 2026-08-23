# ApplyEase — Evidence-First Application OS

## The problem

Students do not merely lack application-writing speed. They repeatedly rewrite CVs,
cover letters and application forms, while generic AI can introduce claims they cannot
defend in an interview. This is especially risky for technical and quantitative roles,
where credibility and the ability to explain a decision matter.

## Competitive position

| Product category | Publicly promoted strength | ApplyEase distinction |
| --- | --- | --- |
| AIApply | High-volume auto-apply, tailored CVs and interview tools | ApplyEase deliberately keeps the applicant in control: it prepares fields but does not silently submit an application. |
| Teal | Job tracking and tailored resumes | ApplyEase starts with a confirmed, source-linked Experience Bank so downstream material has an auditable factual basis. |
| Jobscan | ATS keyword and match-rate optimisation | ApplyEase treats a match score as guidance, then converts missing skills into a time-bounded project plan with a CV evidence template. |

The positioning is **not** “another AI CV writer.” It is:

> **Evidence-First Application OS: AI drafts; confirmed experience proves.**

## Product proof points to show live

1. Upload or load the demo CV. Confirmed and unconfirmed experience are visibly distinct.
2. Analyse a target role. The match report shows evidence, missing skills and explanations.
3. Generate a resume or cover letter. Open **Application Integrity Gate**:
   - source count from confirmed experience;
   - fact-check outcome;
   - export is blocked if the fact check fails.
4. Open **Evidence tracing**. Each material source points to the experience used; this is an experience-level citation, not a misleading sentence-offset claim.
5. Load application questions. Sensitive fields remain manual; AI only suggests reviewable answers.
6. Open Resource Plan. A total time budget applies to the whole plan, and the chosen goal changes ranking and explanation.

## Honest safety boundary

ApplyEase does **not** claim to guarantee interviews or submit external applications without review. It stores a tracker entry as `saved` until the user chooses the real status. This is a deliberate product decision: applicant agency and factual integrity are more valuable than inflated application volume.

## 7-minute video arc

| Time | Story beat | Screen evidence |
| --- | --- | --- |
| 0:00–0:40 | One-line brand + student pain | “I turn scattered student experience into defensible applications.” |
| 0:40–1:20 | Why existing automation is insufficient | Competitive position table / simple product diagram. |
| 1:20–3:20 | Experience → job match | Confirmed Experience Bank and match report. |
| 3:20–4:45 | Core differentiator | Generate material, Integrity Gate, Evidence tracing, blocked unsafe export. |
| 4:45–5:45 | Application form | Detect questions; show sensitive questions require the user, while grounded answers are editable. |
| 5:45–6:30 | Growth loop | Resource Plan with a total budget and portfolio deliverable. |
| 6:30–7:00 | Reflection | Local Qwen + optional Gemini fallback; next improvement is more granular claim-to-span provenance and evaluation datasets. |

## AI implementation facts to say accurately

- Local default model: Ollama `qwen3:4b`; optional Gemini fallback is configuration-based.
- RAG uses Milvus with user-scoped retrieval and confirmed experience as the factual application layer.
- AI material citations are validated: the cited experience must be confirmed, its quoted evidence must exist in that experience, and its claim must appear in generated content.
- A rule-based fallback keeps the local demo usable if a model provider is unavailable.

## Public source references

- [Polymer Tech Expo 2026 requirements](https://events.polymercapital.com/tech-expo-2026)
- [AIApply](https://aiapply.co/)
- [Teal — how it works](https://www.tealhq.com/how-it-works)
- [Jobscan Resume Matcher](https://www.jobscan.co/resume-matcher)
