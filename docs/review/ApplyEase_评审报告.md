# ApplyEase（polymer project）评审报告
> 评审方式：读 README → 从用户视角模拟每条功能链路（后端 route → service → AI/crud → 前端页面）→ 找优化点。所有结论均带 `文件:行号` 依据。

---

## 一、项目是什么

ApplyEase — Evidence-First AI 申请 OS（Polymer Capital 竞赛作品）。
- **前端**：React + TS + Vite，~20k 行，lazy 路由 + i18n（中简/中繁/英）
- **后端**：FastAPI + SQLAlchemy + PostgreSQL，~16k 行，22 个 Alembic migration
- **AI**：默认全关（`AI_*_ENABLED=false`，config.py:38-42），开启后走 Ollama Qwen3:4B → DashScope/Gemini fallback
- **RAG**：Milvus + Ollama embedding，本地 bag-of-words cosine 兜底
- **质量**：150 backend + 84 frontend tests passed（自述），安全设计（HttpOnly+CSRF、SSRF 校验、配额、审计）远超同类学生项目

## 二、用户功能链路模拟（默认配置 = AI 全关）

| 步骤 | 用户操作 | 真实发生的事 |
|---|---|---|
| 1. 上传 CV | `/documents/upload` | pdf/docx 解析 → `mock_extractor` 正则切 section → 经历卡片（未确认）。**走的是正则解析器，不是 AI** |
| 2. 确认证据 | `/experiences/bulk-confirm` | 只改 `confirmed` 标志位，**不做 embedding、不建索引** |
| 3. 职位分析 | `/jobs/analyze-preview`（先预览不落库） | JD 按 **31 个硬编码技能**关键词匹配 → 与 confirmed 经历做子串匹配 → match report |
| 4. 保存职位 | `/jobs/save-analyzed` | 落库，解锁 workspace |
| 5. 生成材料 | `/materials/resume/generate` 等 | **RAG 只在 AI 开启时运行**。AI 关 = 模板拼接（material_service.py）；AI 开 = RAG 检索 + LLM + 引用校验，失败**静默降级**回模板 |
| 6. 学习计划 | `/resources/recommendations` | 10 条人工目录 + 分数排序；时间预算贪心装包 |
| 7. 追踪申请 | `/tracker/*` + `/jobs/{id}/readiness` | Integrity Gate：hold/prepare/review/ready 四态判定，设计很好 |

## 三、优化点（按优先级）

### P0 — 评委/用户 5 分钟内就会撞上的

1. **默认 demo 完全没有 AI，"RAG" 卖点是休眠的**
   `.env.example:6-9` 四个开关全 false；`retrieve_context` 仅 2 个调用点（material_generator.py:279、job_analyzer.py:318），都被 AI 开关挡住。评委按 Quick Start 跑起来看到的是纯正则+模板系统，却读着 README 里的 "retrieval-augmented generation"。
   **改法**：demo 模式默认开 `AI_MATERIAL_GENERATION_ENABLED` + 检测 Ollama 可用性并在 UI 明示「当前 deterministic / AI 模式」徽章；或干脆在生成页标出 `generation_method`。

2. **Fact-check 在规则路径恒绿 → 虚假安全感**
   `generate_resume/cover_letter/answer` 的文本 100% 由证据拼出，`_fact_check`（material_service.py:74-108）必然通过 → "✅ Fact check passed" 徽章是装饰性的。AI 路径的校验也只查**数字子串**（material_validation_service.py:92-94）：AI 写 "three" 查不出、"40%" 只要 JD 里出现过 40 就放行。
   **改法**：校验升级为实体+数字+日期三类 claim 级检查；规则路径输出标注「trivially grounded」，不显示同款徽章。

3. **AI 输出因一次校验失败就静默丢给模板，无重试反馈**
   `validate_ai_citations` 抛 ProviderError（material_validation_service.py:56,62,76）→ `_safe`（material_generator.py:304-314）捕获 → 直接 fallback 到规则模板。引用 quote 差一个标点就整份报废，且用户不知道自己拿到的是模板。llm.generate_json 也没有「带着校验错误重试」的机制。
   **改法**：把校验错误作为反馈注入 prompt 重试 1 次（比直接放弃便宜得多）；fallback 时在 UI 明确显示「AI 未通过证据校验，已回退模板」。

4. **Evidence 引用常常不构成"证明"**
   规则路径的 `claim` = 描述第一行（material_service.py:68-71）；match report 的 `_evidence_quote` 匹配不到就退回第一条描述（job_analysis_service.py:267-270）。Evidence Tracing UI 展示的是「来源存在」，不是「这句话被这句证据支持」。README 自己承认 claim-span provenance 是 next step——这是产品差异化的最大欠账。

5. **技能表硬编码 ×2 份且不一致**
   `mock_extractor.py:3-24`（21 项）vs `job_analysis_service.py:12-44`（31 项，多出 Risk Management/Market Making/Quantitative Research 等）。后果：CV 里的 Market Making 不会进经历 skills，JD 要求它必判 gap。JD 里 Kubernetes/AWS/Go/Spark 等完全识别不到 → 报「未识别到明确技能要求」。
   **改法**：抽成单一 `data/skills.yaml`，两处共用；中期让 LLM 抽取不依赖白名单。

6. **CV 解析正则只为一份 CV 调过参**
   `SECTION_RE`（mock_extractor.py:25-28）要求 "WORK(ING) EXPERIENCE"/"INTERNSHIP"/"QUANT INSIGHT EXPERIENCE" 等精确标题；纯 "EXPERIENCE"、"PROFESSIONAL EXPERIENCE"、中文 CV 全部落进 GENERAL 被丢弃（:207-209），最后只剩一条 "Uncategorized Experience"。评委上传自己的 CV 很可能触发。
   **改法**：放宽 section 匹配 + GENERAL 兜底不要整段丢弃；对无日期行做「公司名在前」的通用回退。

### P1 — 性能与健壮性

7. **Milvus 每次检索全量重嵌+重写索引**（最贵的实现细节）
   `_milvus_search`（rag_service.py:203-269）每次调用：embed 全部 passages + query 16384 条已知 id + upsert 全量 + flush。100 条经历 = 每次生成材料 100+ 次 Ollama HTTP 调用。
   **改法**：confirm/编辑/删除时增量索引（现有 upsert+purge 基建都在），检索只 search； passages 可加 hash 缓存避免重复 embed。

8. **generate-all 在一个 HTTP 请求里串行跑 N 个 LLM 调用**
   applications.py:344-370 循环调 `_generate`，每个 30s 超时 ×3 次重试 ×2 provider，10 题 = 最坏几分钟，必然撞网关超时。且无进度、无部分结果。
   **改法**：改后台任务 + SSE/轮询，或前端逐题请求（已有单题端点）。

9. **重试用同步 `time.sleep` 阻塞 worker**（providers.py:411），且对「invalid JSON」这类确定性失败也做无差别重试。FastAPI `def` 路由跑线程池（默认 40 线程），几个并发生成就可能占满。

10. **Tracker 页 N+1**：TrackerPage.tsx:183-188，list + 每条 application 一个 workspace 请求（50 条 = 51 个请求，虽是并行）。该出 `GET /tracker/workspaces?ids=` 批量端点。

11. **材料版本无上限**：每次生成 `_save` 新版本（materials.py），`list_materials` 全量返回。长期需分页/保留策略。

12. **前端 `request()` 无超时、无 AbortController**（request.ts）→ 长生成不能取消，关页也不中止后端任务。后端还应支持请求取消传递（httpx 已支持）。

13. **匹配分数失真**：`_relevance_score` 取单条经历最高值、分母是整个 JD 的 token 数（job_analysis_service.py:309-324）→ `experience_relevance` 恒接近 0；`qualification_coverage` 恒 0（:366）。score_breakdown 五个维度里两个是死的。`_matched` 用整句子串匹配，AI 返回短语级 requirement 时会全 miss。

### P2 — 打磨

14. **两条建目标的路径不一致**：ApplicationBuilderPage.tsx:266-292 用 `analyzeJob`（直接落库）而 JobAnalysis 用 preview→save → Builder 里取消创建也会留下孤儿 job 记录，绕过了「用户确认后才保存」的产品主张。
15. `"Loading workspace…"` 硬编码英文（App.tsx:100-110），i18n 覆盖 4k 行却漏了这句。
16. `POST /materials/resume/generate?job_id=1` 用 query 传参，应改 JSON body。
17. 生成只取 `list_all` 前 100 条经历（limit=100 默认），>100 条静默丢失；resume 固定取前 6 条按 created_at 排序而非相关度（AI 路径有 select_relevant_experiences，规则路径没有）。
18. readiness 的 "latest material" 依赖传入列表已按时间排序（application_readiness_service.py:9-16），排序变了判定就错。

## 四、做得好的（不需要动）

- 会话级 `with_loader_criteria` 全局 ownership 过滤（db/session.py）+ RAG 双重租户过滤——多租户隔离是认真做的
- Integrity Gate 的 hold/prepare/review/ready 四态 + 敏感字段永不自动填——产品原则贯彻到了代码
- SSRF 防护（内网/redirect/DNS race）、配额先扣后用、demo seed 不泄漏真实 CV——安全意识远超学生项目
- Demo/评审动线（90 秒导览、latest-job 竞态修复）显示对现场演示的重视

## 五、建议动手顺序

**如果比赛/提交在即（只修评委可见的）**：#1（AI 模式徽章或默认开启）→ #6（CV 解析兜底）→ #3（fallback 显式提示）。三个都是小改动、大观感。

**下一周**：#7（RAG 增量索引）→ #2（claim 级 fact-check）→ #8（generate-all 后台化）→ #5（统一技能表）。

**长期**：#4 claim-span provenance（README 已承诺的 next step，也是和所有"AI 简历工具"真正拉开差距的地方）。
