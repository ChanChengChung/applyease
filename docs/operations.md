# ApplyEase 本地运行与数据库迁移

## 部署边界

当前版本具备可撤销数据库 Session、网页 HttpOnly Cookie + CSRF、扩展 Bearer、持久化登录限速、邮箱验证/密码重置、伪匿名安全审计和 `user_id` 数据隔离。本地 development/test 只有在完全没有凭证时才使用 `local@applyease.dev`；无效或过期凭证不会降级。应用能够强制 HTTPS，但不自行签发 TLS 证书：正式上线必须在受信云平台或反向代理终止 TLS，并确保它覆盖客户端传入的 `X-Forwarded-Proto`。

## 推荐启动：Docker Compose

首次运行前：

```bash
cp .env.example backend/.env
docker compose up --build -d
```

Compose 会按顺序启动 PostgreSQL、执行数据库迁移、启动 FastAPI，再启动前端。打开：

- 前端：`http://127.0.0.1:5173`
- API 文档：`http://127.0.0.1:8000/docs`
- Liveness：`http://127.0.0.1:8000/health/live`
- Readiness：`http://127.0.0.1:8000/health/ready`

Backend 容器会读取 `backend/.env` 中的 AI 开关、Ollama 模型和 Gemini key；Compose 只把 `OLLAMA_BASE_URL` 改为 Mac/宿主机可访问的 `host.docker.internal:11434`。

### 从本地兼容账号切换到正式登录

阶段九迁移会把旧数据归属到 `local@applyease.dev`。在启用 production 强制认证前，用交互命令为这个 owner 设置真实邮箱和密码；密码通过隐藏提示输入，不会出现在 shell history：

```bash
docker compose exec backend python -m app.cli auth claim-local --email you@example.com
```

然后设置安全的 `AUTH_SECRET`，以 `VITE_AUTH_REQUIRED=true docker compose up -d --build frontend` 重建登录界面。请先确认新账号能够登录并看到旧数据，再切换 `APP_ENV=production`。阶段十一上线后，旧签名 token 不再接受，用户和扩展需要重新登录；数据库内容不会丢失。

检查容器：

```bash
docker compose ps
docker compose logs backend
```

## 本机开发

```bash
make install
make db-upgrade
make dev-backend
```

另开终端运行：

```bash
make dev-frontend
```

`make dev-backend` 每次都会先升级数据库。FastAPI 不再在 import 或启动时调用 `create_all`，因此漏跑迁移时 readiness 会明确返回 503，而不会静默改变数据库。

## 数据库命令

```bash
cd backend
.venv/bin/python -m app.cli db wait --timeout 60
.venv/bin/python -m app.cli db upgrade
.venv/bin/python -m app.cli db check
```

`db upgrade` 支持两种情况：

1. 空数据库：从 Alembic revision 逐步创建完整 schema；
2. 旧 MVP 数据库：确认现有表和字段兼容、补充可安全补充的旧结构、保留数据、标记初始 revision，然后运行后续迁移。

如果旧数据库结构不兼容，命令会停止并输出具体缺失项，不会删除或重建数据库。

## 升级前备份与恢复

PostgreSQL 升级前建议：

```bash
pg_dump -h 127.0.0.1 -p 5433 -U applyease -Fc applyease -f applyease-before-migration.dump
```

SQLite 则在服务停止后复制数据库文件。出现迁移问题时优先恢复备份；不要在不了解数据迁移方向的情况下直接执行 downgrade。ApplyEase 的自动启动流程只会向前执行 `upgrade head`，不会自动降级或删除数据。

### 可验证备份

不要只依赖 Docker volume。仓库中的 `scripts/backup-postgres.sh` 会在数据库容器内执行 `pg_dump`，输出 PostgreSQL custom archive、解析验证 archive，并生成 SHA-256 校验文件；它不会读取或打印数据库密码。

```bash
# 本地完整备份（目标目录应位于加密磁盘或受控备份卷）
sh scripts/backup-postgres.sh --output-dir ./backups

# 不导出用户资料的 schema-only 冒烟验证
sh scripts/backup-postgres.sh --schema-only --output-dir /tmp/applyease-backup-check

# 生产服务器；.env.production 不会进入备份档案
sh scripts/backup-postgres.sh --production --output-dir /srv/applyease-backups
```

在正式環境把 archive 複製至受控備份位置後，先用完全隔離的暫存 PostgreSQL 容器演練實際還原：

```bash
sh scripts/verify-postgres-restore.sh --archive /srv/applyease-backups/applyease-full-<timestamp>.dump
```

此腳本不讀取 `.env.production`、不連線至任何 Compose service，且以 `--network none`、無 published ports、唯讀 archive mount 啟動一次性的 PostgreSQL container；完成或失敗都會移除它。請在確定暫存磁碟容量足夠時執行，archive 本身仍屬敏感個資，不可上傳至第三方或在 shell/log 中打印內容。

生产备份目录必须位于受访问控制、加密且异机复制的存储，不应位于可被前端、Nginx 或 Docker bind mount 公开读取的位置。建议每日完整备份、至少保留 30 天，并定期检查 `.sha256`。恢复是破坏性操作，必须先停止 backend、在隔离数据库中用 `pg_restore --clean --if-exists --no-owner` 演练，确认数据后才切换生产流量；不要把未经验证的 archive 直接还原到正在服务的生产数据库。

## 环境配置校验

应用在启动前通过 Pydantic 校验数据库 URL、CORS、大小限制、超时和运行环境。`APP_ENV=production` 会额外拒绝：

- SQLite；
- 通配符 CORS；
- 示例中的默认 PostgreSQL 用户名和密码组合。

生产环境必须通过部署平台注入独立强密码和 Gemini API key，不要把密钥写进镜像或提交到版本库。

## 生产安全变量

至少设置：

```env
APP_ENV=production
AUTH_SECRET=<至少32字符、由secrets manager生成>
AUTH_COOKIE_SECURE=true
ENFORCE_HTTPS=true
ALLOWED_HOSTS=api.example.com
CORS_ORIGINS=https://app.example.com
DATABASE_URL=postgresql+psycopg://<独立用户>:<强密码>@<数据库>/applyease
AUTH_MAX_FAILED_ATTEMPTS=5
AUTH_MAX_FAILED_IP_ATTEMPTS=25
AUTH_RATE_LIMIT_WINDOW_SECONDS=900
AUTH_REQUIRE_VERIFIED_EMAIL=true
FRONTEND_BASE_URL=https://app.example.com
MAIL_DELIVERY_MODE=smtp
MAIL_FROM=ApplyEase <no-reply@example.com>
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=<由secrets manager注入>
SMTP_PASSWORD=<由secrets manager注入>
SMTP_STARTTLS=true
AI_GENERATION_MAX_REQUESTS=30
AI_GENERATION_RATE_LIMIT_WINDOW_SECONDS=900
CLOUD_OCR_MAX_REQUESTS=10
CLOUD_OCR_RATE_LIMIT_WINDOW_SECONDS=3600
JOB_IMPORT_MAX_REQUESTS=20
JOB_IMPORT_RATE_LIMIT_WINDOW_SECONDS=3600
```

反向代理必须：

- 只把 HTTPS 流量转发给应用，并将 `X-Forwarded-Proto` 固定为真实协议；
- 丢弃或覆盖客户端提交的 forwarding headers；Caddy 必须覆写 `X-Real-IP` / `X-Forwarded-For`，内部 Nginx 只透传该受信值，以便按真实客户端 IP 登录与寄信限流；
- 只允许 `ALLOWED_HOSTS` 中的域名；
- 不缓存 `/api/`、登录响应或包含 `Set-Cookie` 的响应；
- 将数据库、Ollama 和管理端口放在私网，不直接暴露公网。

普通网页登录不会在 JSON 返回 token，也不会写入 localStorage。扩展登录通过专用 client header 取得 Bearer；扩展只允许 loopback HTTP，远程后端必须 HTTPS。改变 `AUTH_SECRET` 会立即使所有现有 Session、CSRF 绑定和历史审计 HMAC 关联失效，因此应把它作为计划内的全员登出操作。

本地 `MAIL_DELIVERY_MODE=file` 会把验证/重置邮件写入 `backend/dev-mailbox/`。这些文件含一次性链接，目录权限为 `0700`、文件为 `0600` 且已被 Git 忽略；只用于开发，不应同步、分享或挂载到公开静态目录。`disabled` 只适合自动化测试。生产配置会拒绝 file/disabled 模式，并要求 SMTP、HTTPS 前端 URL 和已验证邮箱。

当前仍需由部署平台承担的外部能力：TLS 证书和自动续期、SMTP 服务、secret manager、数据库加密/备份、集中日志告警、WAF/DDoS 防护。产品层已实现 TOTP MFA 与恢复码；公开使用前应至少完成一次真实 SMTP 验证、备份恢复演练与外部安全扫描。WebAuthn/passkey 可作为下一项认证增强，不能用人工读取密码或直接修改生产数据库代替。

## 公网发布（Caddy + Docker Compose）

仓库提供 `docker-compose.production.yml`：只有 Caddy 对外暴露 80/443；Caddy 仅接入 `edge` network 并只能到 frontend。frontend 同时接入 `edge` 和 `app` network，作为唯一 API relay；PostgreSQL、Milvus 与 FastAPI 只接入 `app`，不暴露数据库/API port，也不会出现跨站 Cookie 问题。

Backend 容器以非 root 用户运行，并启用唯读根文件系统、`/tmp` tmpfs、`cap_drop: ALL` 与 `no-new-privileges`。production Compose 还限制 Caddy/frontend 为最多 128 processes、backend/PostgreSQL/Milvus 为最多 256 processes，降低异常 fork／子进程耗尽 VM 的风险；并限制 Caddy/frontend 各 256 MiB、backend/PostgreSQL 各 768 MiB、Milvus 1024 MiB，避免单一解析、索引或异常流量耗尽整台 VM。如需调整必须先做实际并发压测，并同时保留足够的 OS/Docker headroom，不能无上限移除。上传解析在内存和 `/tmp` 内完成；生产邮件必须走 SMTP，不能依赖本地文件 mailbox。

CV 上传除 10 MB 原始文件限制外，默认还限制 PDF 为 50 页、可抽取文字为 200,000 字符、DOCX 解压后内容为 25 MB，以防止压缩炸弹和异常解析消耗资源。必要时可用 `MAX_DOCUMENT_PAGES`、`MAX_DOCUMENT_TEXT_CHARACTERS`、`MAX_DOCX_UNCOMPRESSED_BYTES` 调低这些限制；不要因单一文件放宽为无上限。

frontend Nginx 也会在请求进入 FastAPI 前拒绝大于 10 MB 的 body，并对 header/body 读取设置 15 秒超时（response send 为 30 秒），以限制 oversized upload 与 slow-client 资源占用。每个真实 client IP 最多 20 条并发连接；一般 API 为 60 requests/min（burst 30），认证路由为 10 requests/min（burst 15），超过时由 edge 回 `429`。AI 路由仍另有帐户级、持久化 PostgreSQL 配额，不能只依赖 IP 限流。Nginx 的 IP 是由 Caddy 覆写 `X-Real-IP` 后传入，frontend 在 production 不公开端口；不要将 frontend 单独暴露到公网，否则这项信任边界会失效。若未来调低 `MAX_UPLOAD_BYTES`，也必须同步调低 Nginx `client_max_body_size`；不要把 proxy 限制设得高于 application 限制。

所有可能调用模型的动作在发出 provider 请求前都使用 PostgreSQL 的按帐户配额：一般 AI 生成默认每 15 分钟 30 次，明确同意后才会执行的 Gemini OCR 默认每小时 10 次。上限命中时 API 返回 `429` 和 `Retry-After`；provider 失败也会计入额度，避免攻击者透过重复失败耗尽免费层。可通过 `AI_GENERATION_MAX_REQUESTS`、`AI_GENERATION_RATE_LIMIT_WINDOW_SECONDS`、`CLOUD_OCR_MAX_REQUESTS`、`CLOUD_OCR_RATE_LIMIT_WINDOW_SECONDS` 调低，生产环境不应任意放宽。

公开职位 URL 导入也有独立的每帐户默认每小时 20 次上限（`JOB_IMPORT_MAX_REQUESTS` / `JOB_IMPORT_RATE_LIMIT_WINDOW_SECONDS`）。服务只访问 standard HTTPS/443、初次 DNS 和实际已连接 peer 都必须是 public IP，拒绝 redirect 和环境代理，并维持 10 秒／2 MB 串流限制；不要把它改成通用网页抓取器。

截图 OCR 唯一使用 Gemini（不是 Ollama）。因此 production 配置若设置 `SCREENSHOT_OCR_ENABLED=true`，启动校验会要求非空 `GEMINI_API_KEY`；没有 key 时应保持该开关为 `false`，而不是让用户同意上传截图后才收到 provider 错误。

production Compose 对 Caddy、PostgreSQL、Milvus、backend 和 frontend 使用 Docker `local` log driver，并保留最多 5 个、每个 10 MB 的日志档，避免默认 JSON log 无限增长写满 VM 磁碟。這不是集中化觀測的替代品；仍需在外部平台設定集中 logs 與告警。

### 固定的 container image 與更新流程

production Dockerfile 與 Compose 對 Python、Node、Nginx、Caddy、PostgreSQL、Milvus 都固定到 SHA-256 manifest digest，避免同一 tag 在上游變動後悄悄改變已審核的部署內容。CI 的 `verify-production-image-pins.sh` 會拒絕移除 digest 的變更。

更新 base image 時不要只改 tag：先取得官方供應商的新 digest，更新相應 Dockerfile、`docker-compose.production.yml` 與 `scripts/verify-postgres-restore.sh` 的同一 PostgreSQL digest，接著執行完整 CI、production image build、Caddy validate 及一次隔離 restore rehearsal。確認 CV 解析、登入、MFA、資料隔離與備份都正常後才部署到 staging，再發布 production。digest 固定不取代定期安全更新；至少每月審閱一次上游 CVE 與新版 image。

前端将带内容哈希的 `/assets/` 静态文件缓存一年；HTML 与所有 SPA 路由则返回 `Cache-Control: no-cache`，使浏览器在每次发布后重新取得入口文件，避免旧入口引用已替换的 JavaScript chunk。即使发生极少数延迟页面加载失败，客户端也只显示可恢复的重新载入动作，不会显示可能含个人资料的技术错误。

所有浏览器与 API 回应均设置 `nosniff`、拒绝嵌入、no-referrer、最小 Permissions Policy、COOP `same-origin`、CORP `same-origin`、关闭 DNS prefetch 与 Flash cross-domain policy。production CSP 禁止 object/embed，且 `connect-src` 只允许同一 HTTPS origin；如未来加入第三方脚本、字体、分析或 CDN，必须先进行隐私与 CSP 审查，不能改为通配符。

驗證和密碼重設 email link 的一次性 token 使用 `#verify_token=` / `#reset_token=` URL fragment，而不是 HTTP query string；fragment 不會傳到 Caddy/Nginx/backend。production frontend Nginx 與 backend Uvicorn 也關閉原始 access log，避免日後不慎新增的敏感 query 被記錄。維持此邊界時，應依賴既有的去識別安全 audit、AI telemetry 與外部 uptime/metrics 監控，不要為方便而重新開啟會記錄完整 URL/payload 的 access log。

1. 准备一台已安装 Docker Compose 的 Linux 服务器，并把域名的 A/AAAA 记录指向该服务器；防火墙仅开放 TCP 80 和 443。
2. 在服务器根目录复制 `.env.production.example` 为 `.env.production`，替换所有密码、`AUTH_SECRET`、域名、SMTP 和 AI provider 配置，并把 `APP_VERSION` 设为正在部署的不可变 Git tag 或 commit。`AUTH_SECRET` 至少 32 个字符，PostgreSQL 密码至少 16 个字符；SMTP 必须启用 STARTTLS。该文件被 Git 忽略，权限应设为 `600`。
3. 确认 `APP_DOMAIN` 可从公网解析且未被另一个反向代理占用 80/443，然后执行：

```bash
chmod 600 .env.production
sh scripts/preflight-production.sh
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
docker compose --env-file .env.production -f docker-compose.production.yml ps
sh scripts/smoke-production.sh https://<APP_DOMAIN>
```

4. Caddy 会自动申请和续期 TLS 证书。部署完成后，从公网检查 `https://<APP_DOMAIN>/health/ready`（路径经唯一的 frontend relay 到 backend，验证数据库、migration 与 `version`，而不是只验证静态前端）；确认 response 的 `version` 正是本次 release，再注册测试账号、完成验证邮件、登录、启用 MFA、上传测试 CV，并确认 `/api/v1` 不可经 HTTP 明文访问。

仓库还提供不需要 DNS/SMTP 的本机 production 整合检查：`sh scripts/verify-production-stack.sh`。它只使用 `localhost`、假凭证和独立 Compose project/volumes，验证 HTTPS、redirect、health、API 认证边界及 edge/app network 分段，结束后自动删除测试资料；它不能替代真实域名、真实 TLS 与 SMTP 的公网验收。

`smoke-production.sh` 会读取 readiness JSON、HTTPS 的 HSTS/CSP header，并确认 HTTP 自动跳转 HTTPS；它不创建账号、不上传文件，也不会读取或显示 secrets。须在 DNS 与 TLS 已就绪的外部网络执行。

不要使用 `.env.production.example` 的示例值启动服务；production 配置会拒绝弱 `AUTH_SECRET`、HTTP、默认数据库凭据、未验证邮箱与非 SMTP 邮件模式。首次发布前也应单独备份数据库卷，并实际演练一次恢复。
