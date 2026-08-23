# ApplyEase 实现计划

## 1. MVP 目标

已经完成一个可演示的端到端产品：用户上传 CV，系统建立个人经历库；用户粘贴职位描述完成职位分析，粘贴申请页面文字或在明确同意后上传申请表截图完成字段识别；系统生成带证据来源的申请材料，并推荐补强资源与项目。

## 2. MVP 优先级

### P0：必须完成

1. React + TypeScript 基础界面和路由；
2. FastAPI 基础服务和 PostgreSQL 连接；
3. CV PDF/DOCX 上传与文字解析；
4. 规则或 LLM Structured Output 将 CV 转为结构化 Experience Bank；
5. 用户审核、编辑和确认个人经历；
6. 粘贴职位描述；
7. 提取技能、职责、资格和申请材料要求；
8. 生成匹配分数、匹配证据和技能缺口；
9. 生成定制 Resume、Cover Letter 和常见申请题答案；
10. 生成材料显示引用经历、claim/quote 和事实检查状态；
11. 根据技能缺口推荐资源和一个实战项目。

### P1：第二阶段

- 上传申请表截图并在明确同意后使用 Gemini OCR 识别字段；
- 自动识别申请表问题和字数限制；
- STAR、50/150/300 字等可选择答案模板（已实现；同时支持检测和执行字符/字数限制）；
- 申请状态、截止日期和材料版本追踪；
- 资源完成状态、链接健康检查与用户反馈（已实现）；完成项目自动回写经历库仍属于后续增强。

### P2：后续扩展

- 浏览器扩展与 Greenhouse/Lever/通用字段适配（已实现）；
- 用户预览并确认后的表单辅助填写（已实现；永不自动提交）；
- 招聘职位网页/截图导入（已实现）；
- 多份 CV 模板和 DOCX/PDF 导出（已实现）；
- 多语言材料生成（已实现）；
- Milvus 向量 Embedding/RAG（已实现；用于材料生成前检索用户确认经历与文档证据）；

## 3. 开发阶段

### 阶段一：项目骨架与数据模型

- 初始化 `frontend/` 和 `backend/`；
- 建立环境变量配置；
- 创建 Experience、Document、Job、Application、Resource 等核心数据表；阶段九再加入 User 与所有权模型；独立 Profile 模型尚未需要；
- 配置 PostgreSQL、SQLAlchemy 和 Alembic；
- 建立健康检查 endpoint 和基础页面。

验收：前后端可以启动，数据库迁移成功，`/health/live` 和 `/health/ready` 正常。

当前实现：前端、后端与 PostgreSQL 可通过 Docker Compose 统一启动；FastAPI 提供 `/health/live` 与包含数据库 revision 检查的 `/health/ready`。Alembic 管理初始 schema、legacy 外键修复和阶段九 owner 迁移，`python -m app.cli db upgrade/check/wait` 支持空数据库迁移、旧 MVP 数据库无损接管和启动前检查。配置层验证环境、数据库 URL、CORS、上传限制、认证密钥和 LLM 超时，生产模式拒绝 SQLite、通配符 CORS、默认开发数据库凭据和弱 `AUTH_SECRET`。阶段一当时采用单用户边界，已由阶段九认证与数据隔离覆盖。

### 阶段二：Experience Bank

- 实现文件上传；
- 解析 PDF/DOCX 文本；
- 设计结构化 LLM schema；
- 保存经历、技能、量化成果和来源；
- 提供用户审核与编辑界面。

验收：上传一份 CV 后，能得到可编辑的经历卡片；数字和公司名称不应被静默改写。

生产化补充验收：重复上传同一文件不会产生重复记录；空文件、损坏文件、超大文件和不支持格式返回明确错误；用户可删除错误经历；保存失败时事务回滚。

当前实现（完整版本）：`GET /api/v1/experiences` 支持标题、组织和描述搜索、确认状态筛选及 `limit/offset` 分页；支持手动新增经历、标题+组织（忽略大小写和首尾空格）重复检测、更新时重复检测、批量确认并返回不存在的 ID。前端经历库提供搜索、状态筛选、手动新增、逐条勾选、批量确认和加载更多，并保留来源展示、编辑、删除和上传后刷新。阶段二后端专门测试覆盖 409 重复、分页筛选、批量确认缺失 ID、空批量输入和更新冲突；阶段九之后所有记录均按用户隔离。

### 阶段三：职位分析与匹配

- 实现职位描述输入页面；
- 提取必需技能、加分技能、职责和资格；
- 使用可复现的关键词/文本证据匹配；向量 embedding 保留为后续增强；
- 生成匹配报告和缺口清单；
- 为每一项匹配显示支持证据。

建议匹配分数：

```text
40% 技能匹配
25% 经历相关性
15% 量化成果
10% 教育背景
10% 语言、地点与资格要求
```

验收：对同一份 CV 输入 Quant、AI Research 和 Software Engineer 三个职位时，系统选择的重点经历明显不同。

当前实现（完整版本）：`POST /api/v1/jobs/analyze` 经过服务层调用 Ollama/Gemini Structured Output，并在 provider 失败时自动使用确定性规则 fallback；`GET /api/v1/jobs/{id}/match-report` 只检索已确认经历，支持必需/加分技能分离、非内置技能匹配、职责与资格展示、分数构成、无经历警告和逐项原文证据。AI 返回的 Experience ID、技能名称和证据 quote 都会经过白名单及原文校验，无法验证时降级为规则结果。前端展示技能缺口、分数构成、职责、资格、警告和证据。阶段三测试覆盖 AI 清洗、fallback、防幻觉证据、未确认经历隔离、非目录技能和必需/加分技能拆分。

### 阶段四：申请材料生成

- 建立 Resume、Cover Letter 和行为题 prompt；
- 使用检索增强生成，只检索用户已确认经历；
- 加入事实检查和字符数检查；
- 显示材料引用经历、claim/quote 和事实检查状态；逐句引用保留为后续增强；
- 支持重新生成、编辑和复制。

验收：不能从经历库中找到证据的数字、公司、技术或成就必须被标记，而不是直接生成。

当前实现（完整版本）：Resume、Cover Letter 和申请题答案统一经过 `material_service.generate_material`，API 路由不直接决定 provider；Ollama/Gemini 只接收已确认经历，AI 输出必须提供 Experience ID、生成文本中的 claim 和经历原文 evidence quote，任一引用无法验证就自动降级到规则生成。所有数字会与职位描述/已确认经历进行事实检查；答案的字符上限会随版本保存，人工编辑超限会返回 422，前端同时阻止保存。支持生成独立版本、按 material type 查询历史、人工编辑、来源展示、复制、空题目/无效职位/不存在历史的明确错误。阶段四测试覆盖 AI citation 白名单、未确认经历隔离、数字幻觉 fallback、人工编辑事实检查、字符上限、历史筛选和前端超限阻止。

### 阶段五：申请表问题识别

- 支持粘贴申请页面文本；
- 将问题分类为动机题、行为题、技术题、资格题和资料字段；
- 识别必填状态和字数限制；
- 为每道题检索相关经历并生成答案；
- 第一版只提供复制功能，不自动提交。

验收：至少识别 10 种常见申请题，并能正确输出问题类型和字数限制。

当前实现（完整版本）：申请表识别经过服务层统一编排 Ollama/Gemini Structured Output 与确定性规则 fallback，覆盖动机、公司兴趣、项目、团队协作、领导力、挑战、技术、教育、身份、联系方式、工作授权、薪资、人口统计、健康和可用时间等字段；服务端重新计算字段分类、必填状态、敏感/人工填写策略、字符限制和 word limit，不接受模型绕过敏感字段保护。支持单题生成、批量生成、跳过已保存答案、重新生成、人工编辑、字数/字符双重限制、答案来源和事实检查。截图 OCR 支持 PNG/JPEG/WebP、5 MB 上限、文件签名校验和显式云端同意，OCR 调用也经过独立服务边界；未确认经历不会用于 prompt 或人工答案事实验证。浏览器扩展已实现用户确认后的字段填充，但第三方网站自动提交明确不在产品范围内。

字段填充 MVP：`browser-extension/` 扫描当前网页的 input/textarea/select，将不含用户输入值的字段元数据发送到 `POST /api/v1/applications/{id}/fill-preview`；用户在扩展弹窗中查看匹配、来源和警告，只有勾选的 `ready` 字段会被填充。密码、验证码、文件、敏感字段和 Submit/Apply 按钮始终排除。扩展已完成 Greenhouse 与 Lever 专用适配器、通用 fallback、可配置后端地址和连接检查；自动化测试覆盖普通字段、动态字段、select、radio、maxlength、React/Vue 事件和禁止填充边界。按当前产品范围不再继续开发其他网站适配器。

### 阶段六：资源与行动计划

- 建立人工审核的资源数据库；
- 为资源添加主题、难度、时长、费用和官方链接；
- 根据缺口、用户水平和可用时间排序；
- 为每个资源绑定一个可展示的实战任务；
- 提供完成标准和可写入 CV 的成果模板。

示例资源：Kaggle Competitions、Kaggle Learn、QuantConnect Learning Center、fast.ai、PyTorch Tutorials、Hugging Face Learn、FastAPI Documentation、Docker Get Started、GitHub Skills。

验收：输入“缺少量化研究项目”，系统应给出至少一个学习资源、一个实战任务、预计时长和完成标准，而不是只返回泛泛的学习建议。

当前实现（完整版本）：资源目录包含 Kaggle Learn/Competitions、QuantConnect、PyTorch、fast.ai、Hugging Face、FastAPI、Docker 和 GitHub Skills 等官方链接；目录采用幂等补种，已有数据库也会自动补齐新增资源。`GET /api/v1/resources/recommendations` 根据职位缺口、用户水平、最多可投入小时、免费筛选和数量限制排序，返回匹配分数、命中技能和推荐理由；每个资源绑定学习时长、难度、项目任务、交付物、完成标准和 CV bullet 模板。`POST /api/v1/resources/{id}/complete` 支持完成/撤销并按用户持久化状态，前端显示总预计时间和项目行动计划。

### 阶段七：申请进度追踪

当前实现（完整版本）：支持创建、列表、编辑、删除投递记录，字段包括公司、职位、可选关联 Job ID、截止日期、面试日期、follow-up 日期和备注；状态包括 saved、applied、assessment、interview、offer、rejected、withdrawn。后端通过 `api/v1/tracker.py` → `crud/tracker.py` → `models/tracker.py` 分层访问数据库，并校验同一用户下的关联职位存在性。列表支持状态、日期区间、排序、limit/offset；每条记录返回逾期、待跟进和下一步行动标记，`/tracker/applications/summary` 返回总数、各状态、进行中、逾期和待跟进汇总。Dashboard 同步展示未来 14 天及逾期的截止/跟进事件。前端提供创建、编辑、状态筛选、排序、加载/空/错误状态和删除确认，用户可在提交前核对关键日期。

### 阶段八：端到端产品整合与 Demo 质量

- 将“上传 CV → 确认经历 → 分析职位 → 生成材料 → 回答申请题 → 浏览器辅助填充 → 更新申请状态”串成一个明确工作流；
- Dashboard 显示下一步行动、材料完成度、缺失信息和申请状态；
- 建立固定评估数据集，量化字段识别、证据引用、字数限制和事实一致性；
- 增加统一 loading、重试、空状态和错误恢复体验；
- 完成一条可重复演示的 Polymer Capital 展示脚本与示例数据。

验收：新用户能够从 CV 上传开始，在 5 分钟内完成一次有证据来源、可人工确认的实习申请准备流程；演示不依赖临时手工修改数据库。

当前实现（第一部分）：新增 `/api/v1/dashboard/summary` 只读聚合接口，并保持 `api/dashboard.py`、`crud/dashboard.py`、`services/dashboard_service.py` 解耦。前端以 Dashboard 为默认首页，显示经历、职位、材料和追踪指标，根据数据库真实状态计算唯一的“下一步行动”，并串联经历库、职位分析、材料生成、申请问题和申请追踪。最新 Job ID、公司和职位会随导航自动带入下游页面；Dashboard 同时覆盖 loading、错误重试、空状态和未来 14 天截止日期。资源计划保留在主导航中，但不作为阻塞申请主流程的步骤。

当前实现（第二部分）：新增统一 `PageFeedback` 成功/错误/信息反馈；关键页面在完成审核后提供“返回工作台”，申请追踪创建成功后自动返回 Dashboard 并重新读取数据库状态。职位、材料、表单和追踪页面保留用户输入，失败时可以原地重试。录屏演示使用参赛者自己的 CV、目标职位与真实工作流，不会向账户写入演示种子数据。

当前实现（阶段八完成）：Dashboard 现在区分截止日期、Follow-up 和逾期事件，提供“刷新状态”操作，并在无日期时给出明确的截止/跟进空状态。新增 `backend/tests/test_stage8_e2e.py`，以固定 CV → 确认经历 → 分析 Polymer 职位 → 生成 Resume/Cover Letter → 识别申请题 → 生成答案/人工保存敏感字段 → 创建关联申请 → Dashboard 聚合的顺序验证核心工作流契约。前端新增 Dashboard 日期事件测试，浏览器扩展和前后端构建均纳入阶段八发布门槛。当前阶段八的验收重点是模块整合和可重复 Demo，不包含认证、多用户隔离或自动提交第三方网站。

## 4. 推荐页面

1. Dashboard：申请进度、近期任务和技能缺口；
2. Profile：个人经历库；
3. Job Analysis：职位输入和匹配报告；
4. Application Builder：材料和申请题生成；
5. Resource Plan：学习资源和实战计划；
6. Application Tracker：截止日期、状态和面试记录。

## 5. 测试方案

- 单元测试：解析器、匹配分数、字数限制和事实检查；
- API 测试：上传、职位分析、材料生成和资源推荐；
- 前端测试：经历审核、材料编辑和复制操作；
- 人工评估：使用 3 个不同岗位，检查经历选择是否合理（尚未形成版本化人工评分记录）；
- 安全测试：确认未确认经历不会进入最终生成结果。

## 6. Demo 验收指标（目标，尚未全部自动量化）

- 一份申请材料生成时间：目标低于 2 分钟；
- 10 个职位关键词中至少覆盖 8 个相关关键词；
- 所有量化成果均有来源；
- 申请题字数限制通过率达到 100%；
- 用户可以在 3 分钟内完成一次“职位分析 → 生成材料”；
- 对经验不足的用户至少生成一个可在 7–14 天完成的补强项目。

## 7. 风险与边界

- 不编造经历、成绩、公司名称或技术成果；
- 不保证录取或面试结果；
- 不自动替用户作最终提交；
- CV 和身份资料默认私密，并提供删除功能；
- 外部学习资源优先使用官方链接，并记录最后验证时间；
- 生成内容必须经过用户审核。

### 阶段九：认证与多用户数据隔离

当前实现：新增 User 模型、PBKDF2-SHA256 密码哈希及 `/api/v1/auth/register`、`/login`、`/me`。Alembic `0003_auth_ownership` 将既有数据安全归属到 legacy owner，为所有用户业务表增加非空 `user_id` 外键和索引，并把文档去重改为用户内 SHA-256 唯一、资源进度改为用户+资源唯一。SQLAlchemy Session 统一应用 owner 查询条件并自动写入 owner，防止 CRUD 漏加过滤。阶段九最初使用网页 Bearer/localStorage；阶段十一已经将网页认证替换为 HttpOnly Cookie + CSRF，并将扩展 Bearer 改为可撤销数据库 Session。development/test 仅在完全无凭证时映射到 `local@applyease.dev`，无效凭证不会降级。

阶段九测试覆盖注册、重复账号、登录错误、`/me`、生产无 token 401、两个用户访问同一 Job ID 的越权阻断、空数据库迁移和旧数据库数据保留。

### 阶段十：AI 质量评估与可观测性

当前实现：所有 Ollama/Gemini Structured Output 调用统一产生 `provider_attempt` 事件，记录功能、Provider、模型、Prompt 版本、尝试次数、耗时、输入/输出字符数量、状态、错误类别和 fallback 来源；业务层完成 schema、证据与事实校验后再产生 `feature_outcome`，因此“模型响应成功但验证失败后使用规则”会正确计为 `rule_fallback`。截图 OCR 也使用相同口径。`ai_invocations` 不含 Prompt、模型输出、CV/职位正文、申请答案、截图、邮箱或 API Key，并带非空 `user_id`，沿用阶段九 Session 所有权过滤。

新增 Alembic `0004_ai_observability`、`GET /api/v1/ai/metrics?days=1..90` 及前端“AI 质量”页面，按用户展示端到端成功率、规则降级率、最终失败、Provider 平均/P95 延迟和功能结果。观测写入失败只记录服务端错误类别，不阻断申请工作流。

`backend/evals/stage10_cases.json` 是版本化固定评估集；`python -m app.cli ai eval --provider rules|ollama|gemini` 可比较规则、本地 Qwen 和 Gemini。Gemini 必须带 `--confirm-external`，同一评估运行复用限速器以遵守 Free Tier；默认门槛 100%，低于门槛退出码 2。评估覆盖职位技能/职责、表单类型和敏感字段人工填写策略：离线规则基线 4/4，本机 Ollama `qwen3:4b` 实测 4/4。阶段十测试覆盖内容不落库、Ollama→Gemini 降级链、指标聚合、跨用户隔离、日期边界、离线评估和前端 loading/empty/指标交互。

### 阶段十一：生产部署安全加固

当前实现：原本不可撤销的 HMAC Bearer 已替换为数据库 `auth_sessions`。随机 token 和 CSRF secret 只在签发时交给客户端，数据库只保存用 `AUTH_SECRET` 计算的 HMAC；Session 支持过期、单会话撤销、`POST /auth/logout-all` 全部撤销和 `GET /auth/sessions` 活跃会话检查。普通网页登录只返回 `access_token=null`，凭证仅通过 HttpOnly、SameSite=Strict Cookie 传递；所有 Cookie 认证的非安全方法必须同时提供与 Session 绑定的 CSRF Cookie/Header。浏览器扩展必须发送 `X-ApplyEase-Client: browser-extension` 才取得 Bearer，Bearer 不需要 CSRF但同样可撤销；扩展远程 API 地址强制 HTTPS。

新账号密码至少 12 字符，PBKDF2-SHA256 使用 310,000 rounds；旧账号仍可登录，并在成功验证后自动升级旧 hash。登录失败按 email HMAC 与直接连接 IP HMAC 双维度进行数据库持久化限速，默认 15 分钟内单账号 5 次、单 IP 25 次；错误响应不区分账号不存在、密码错误或停用。`security_audits` 只保存事件、结果、可选 user ID 与 email/IP/User-Agent 的 HMAC，不保存原值、密码或 token。

生产配置必须启用 `AUTH_COOKIE_SECURE=true`、`ENFORCE_HTTPS=true`、显式 `ALLOWED_HOSTS`、至少 32 字符 `AUTH_SECRET`、严格 CORS 和非默认 PostgreSQL 凭据，否则启动失败。FastAPI 生产模式关闭 OpenAPI/Swagger，拒绝未知 Host 和非 HTTPS 请求，并加入 HSTS、CSP、frame、MIME、referrer、permissions 与 API no-store 响应头；Nginx 静态前端也配置 CSP 和相同基础头。应用负责强制和验证 HTTPS，但 TLS 证书仍应由云平台/受信反向代理终止。

Alembic revision 为 `0005_security_hardening`。阶段十一自动化测试覆盖 HttpOnly/SameSite Cookie、网页不暴露 token、CSRF 阻断/通过、扩展 Bearer、logout/logout-all、无效 token 不降级、持久化限速、审计脱敏、旧 hash 升级、生产配置、Host/HTTPS 和安全头；完成时后端 85 passed、前端 44 passed 且 build 成功、扩展 15 passed 且 build 成功。

### 阶段十二：账号生命周期与恢复（已完成）

当前实现：`users.email_verified_at` 保存验证状态，`account_tokens` 保存邮箱验证/密码重置 token 的 HMAC、用途、有效期和一次性消费状态；旧账号迁移时标为已验证，新账号从未验证开始。同用户同用途重新申请会使旧 token 失效，过期、错误用途或已使用 token 均被拒绝。生产环境要求邮箱已验证才能登录或访问业务 API；development/test 保持本地 Demo 兼容。

新增 `/auth/email-verification/request`、`/confirm`、`/password/forgot` 和 `/password/reset`。公开请求对存在和不存在邮箱返回相同 202 响应；发送请求按邮箱/IP 的 HMAC 限速，无效确认按 IP 限速。密码重置成功后重新使用 PBKDF2-SHA256 哈希并撤销该用户所有 Session，所有设备必须重新登录。安全审计只保存事件、结果、用户 ID 和伪匿名 HMAC，不保存 token、邮箱或正文。

`email_service.py` 提供 file/SMTP/disabled adapter：本地 Docker 将权限 `0600` 的邮件写到 Git 忽略的 `backend/dev-mailbox/`，生产配置强制 SMTP、HTTPS `FRONTEND_BASE_URL` 和 `AUTH_REQUIRE_VERIFIED_EMAIL=true`。前端 AuthPage 支持注册后的验证提示、重发、忘记密码、重置密码、密码一致性、自动确认验证链接和过期/错误反馈。

验收：后端阶段十二测试覆盖 token 不落明文、旧 token 失效、过期、一次性消费、统一防枚举响应、请求/确认限速、生产验证门槛、密码重置撤销多个 Session、本地邮箱权限和生产配置；真实 PostgreSQL smoke test 验证注册 201、验证 200、重置请求 202、重置 200、旧 Session 401、新密码登录 200。完成时后端 92 passed、前端 49 passed 且 build 成功、扩展 15 passed 且 build 成功，Alembic revision 为 `0006_account_lifecycle`。

### 阶段十三：多模板 Resume 与 DOCX/PDF 导出（已完成）

当前实现：Application Builder 在用户选择事实检查通过的 Resume 版本后，要求填写导出姓名，可选填写 email/phone/LinkedIn/GitHub 等单行联系方式，并提供 Classic ATS、Modern navy、Compact dense 三种模板。导出服务使用当前材料文本，不重新调用 LLM，也不修改或保存姓名/联系方式；DOCX 使用 `python-docx`，PDF 使用 ReportLab，均为 Letter 页面、明确边距/字号/行距，并支持中英文混排。可选 Evidence Appendix 独立分页并明确提示提交前移除。

安全与边界：导出使用 POST JSON，个人资料不进入 URL；记录按当前用户隔离，跨用户 ID 返回 404；非 Resume、空材料、无效格式/模板、空白姓名和事实检查失败均返回明确错误。文件名经过安全字符清洗，响应标记正确 MIME、attachment 和 `nosniff`，CORS 只额外暴露 `Content-Disposition` 供前端读取下载文件名。

验收：三种模板分别生成可打开的 DOCX/PDF；测试验证 ZIP/PDF 签名、Letter 几何、姓名/联系方式、来源附录、格式/模板校验、事实检查门槛、材料类型和所有权隔离。PDF 三套模板的正文页及来源页均经实际渲染视觉检查；本机缺少 LibreOffice，因此 DOCX 完成 OOXML、页面、边距、样式和内容结构校验。完成时后端 95 passed、前端 54 passed 且 build 成功、扩展 15 passed 且 build 成功。

### 阶段十六：申请提醒与 Calendar 导出（已完成）

Tracker 新增提醒中心，按 7/14/30/90 天窗口汇总**进行中**申请的截止日、follow-up 与面试日期；已拒绝和撤回记录不会产生提醒。逾期、当天和近期事件以稳定优先级排列。`GET /tracker/applications/reminders?days=14` 使用既有 Session owner filter，因此不会返回其他用户的记录。

每条申请可从 `GET /tracker/applications/{id}/calendar` 下载 `.ics`：有日期时将截止、跟进和面试分别生成 RFC 5545 全天事件，正确转义逗号、分号、反斜杠和换行，不杜撰时间/时区；没有任何日期返回 422，跨用户 ID 返回 404。前端读取安全文件名并触发浏览器下载，用户再自行导入 Apple Calendar、Google Calendar 或 Outlook。没有直接写第三方日历，也没有新增数据库表或 migration。

验收：后端测试覆盖提醒窗口、进行中状态过滤、RFC 5545 CRLF/转义、无日期与用户隔离；前端交互测试覆盖提醒显示、窗口切换和导出按钮。完成时后端 102 passed、前端 58 passed/build 成功；下一阶段建议为公开部署前的 TOTP/WebAuthn MFA 与恢复码，或在明确 OAuth 授权后再做日历同步。

### 阶段十七：TOTP MFA 与恢复码（已完成）

新增 TOTP 认证器设置、确认启用、恢复码轮换、关闭 MFA 与登录二次验证。首次设置只返回 provisioning URI/手动密钥，用户以 6 位 TOTP 确认后才启用；恢复码只在生成时返回一次，数据库仅存 HMAC。密码校验成功且 MFA 已启用时，服务器只创建 5 分钟、一次性的 `mfa_login` challenge；验证 TOTP 或恢复码成功后才会发放网页 Cookie/扩展 Bearer Session。

安全边界：无效挑战/验证码不会创建 Session；已使用或过期 challenge 不可重放；恢复码单次消费；轮换恢复码和关闭 MFA 要求当前 factor，并写入脱敏审计。新增 migration `0008_mfa`、Security 页面和登录验证码界面。验收：后端 104 passed，前端 59 passed/build 成功；下一阶段建议实现 WebAuthn/passkey 或用户授权的 Calendar OAuth。

### 阶段十四：Resume 预览与个人抬头资料（已完成）

当前实现：新增每用户 `ApplicantProfile`，用户在 Application Builder 明确选择后才保存姓名和单行联系方式，并可随时删除。Resume 预览按当前文本区块、模板、资料、显示开关和顺序实时更新；DOCX/PDF 导出接收相同 `section_order`/`hidden_sections`，避免预览与文件不一致。预览提示估算的一页溢出，用户可切换 Compact、隐藏不相关区块或编辑材料。

验收：资料 API 覆盖格式化、空白拒绝、用户隔离和删除；导出测试覆盖区块重排和全隐藏阻断；前端测试覆盖标题分段、隐藏与顺序预览。新增 Alembic `0007_applicant_profile`。完成时后端 97 passed、前端 56 passed 且 build 成功。

### 阶段十五：职位网页与截图导入（已完成）

当前实现：Job Analysis 新增“从链接导入”和“从截图导入”两条路径。公开链接只接受 HTTPS、无用户凭据、DNS 为全局地址、非跳转、HTML 响应；服务端采用 10 秒超时、2 MB 流式字节上限并清理网页标签，生成标题、公司、JD、地点、截止日期和来源 URL 草稿。截图复用 Gemini OCR，必须先勾选明确云端同意，并保留 PNG/JPEG/WebP、签名和 5 MB 限制。

安全与验收：导入草稿不落库、不直接触发 AI 匹配；用户必须审核可编辑字段后点击“分析职位”。测试覆盖非 HTTPS/私有地址阻断、跳转阻断、网页草稿提取和前端草稿回填。完成时后端 100 passed、前端 57 passed、扩展 15 passed，前端与扩展构建成功。
