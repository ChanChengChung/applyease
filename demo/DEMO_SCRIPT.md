# ApplyEase 五分钟 Demo

这套演示只通过用户界面操作，不需要手动修改数据库。为保持演示结果稳定，建议准备一个全新测试数据库，或使用一个没有历史数据的测试环境。

## 演示前

1. 启动 PostgreSQL、FastAPI、React 前端和 Ollama `qwen3:4b`。
2. 打开 ApplyEase，确认 Dashboard 能加载。
3. 将 `demo/chen_demo_cv.txt`、`demo/polymer_ai_internship_job.txt` 和 `demo/polymer_application_questions.txt` 放在容易访问的位置。
4. Chrome 中重新加载 `browser-extension/dist`，展开扩展“后端设置”并测试连接。

## 0:00–1:00：事实基础层

1. Dashboard 显示“上传你的 CV”。
2. 进入经历库，上传 `chen_demo_cv.txt`。
3. 展示结构化 Experience Cards、来源和待确认状态。
4. 快速检查每张卡，点击“确认经历”。
5. 所有经历确认后点击“返回工作台”。

讲解重点：后续 AI 只能使用已确认经历，避免虚构公司、数字和技能。

## 1:00–2:00：职位匹配

1. Dashboard 的下一步变为“分析目标职位”。
2. 打开职位分析，填写标题 `AI and Quantitative Technology Intern`、公司 `Polymer Capital`。
3. 粘贴 `polymer_ai_internship_job.txt` 内容并分析。
4. 展示匹配分数、技能缺口和每项证据来源。
5. 点击“返回工作台”。

## 2:00–3:15：材料生成

1. Dashboard 自动带入最新 Job ID。
2. 依次生成 Resume 与 Cover Letter。
3. 展示事实检查、引用经历和历史版本。
4. 两份材料齐全后点击“返回工作台”。

## 3:15–4:15：申请问题

1. 进入申请表助手，Job ID 已自动填写。
2. 粘贴 `polymer_application_questions.txt` 并识别。
3. 点击“生成所有可回答问题”。
4. 强调工作授权、邮箱等个人/敏感字段需要本人填写；AI 只生成叙事答案。
5. 人工填写必填敏感字段并保存，点击“返回工作台”。

## 4:15–5:00：安全填表与追踪

1. 用 Greenhouse/Lever fixture 或真实申请页展示扩展的字段预览与用户确认填充。
2. 强调扩展不会上传 Cookie、填写文件/验证码/敏感字段或点击 Submit。
3. 进入申请追踪，最新职位和公司已自动填入；选择截止日期、状态和 Follow-up 日期并添加。
4. 添加成功后自动回到 Dashboard，完整工作流显示完成；近期日期区分“截止日期”和“待跟进”，逾期记录会标红并显示“已逾期”。

## Demo 失败恢复

- LLM 超时：页面保留用户输入并显示错误，可直接重试；后端规则 fallback 仍能保证核心流程。
- 后端未启动：Dashboard 和扩展都会给出连接错误；启动后点击重新加载/测试连接。
- OCR 不可用：直接粘贴 `polymer_application_questions.txt`，不影响主流程。
- 浏览器适配器遇到未知字段：保留人工填写，不进行猜测或自动提交。
