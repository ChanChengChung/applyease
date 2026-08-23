# ApplyEase 公網上線清單

本清單只涵蓋需要擁有者帳戶、付款或外部平台授權的工作。程式碼、Docker production 拓撲、preflight、測試與本機驗收已在倉庫中完成。

## 1. 伺服器與網域

- [ ] 建立 Linux VM（建議 Ubuntu LTS、至少 2 vCPU / 8 GB RAM；Compose 對應服務已有約 3 GiB 的合計 memory ceilings，仍必須保留 OS、Docker cache 與尖峰 headroom。若要在同機跑 Ollama，請依模型額外配置 RAM，或改用 private remote endpoint）。
- [ ] 安裝 Docker Engine 與 Docker Compose plugin；只讓受信管理員可 SSH。
- [ ] 購買或使用現有網域，建立 `APP_DOMAIN` 的 A/AAAA 記錄指向 VM 公網 IP。
- [ ] 在雲端 firewall / security group 只開 TCP 80、443 與管理用 SSH；**不要**開 PostgreSQL 5432、Milvus 19530 或 FastAPI 8000。
- [ ] 確認沒有其他服務佔用 80/443；Caddy 會用這兩個連接埠自動取得與續期 TLS 憑證。

## 2. 郵件與 AI 外部服務

- [ ] 選擇 SMTP 供應商，完成寄件網域的 SPF、DKIM、DMARC 設定，建立只具發信權限的 SMTP credential。這是註冊驗證與重設密碼所必需的。
- [ ] 若使用 Gemini：在 Google AI Studio 建立受限制的 API key，設定配額警示；只把 key 放進伺服器的 `.env.production` 或 secret manager。
- [ ] 若使用 Ollama：部署一個只供 private network 存取的 Ollama endpoint；不要把 11434 對公網開放。若不使用它，讓 `OLLAMA_BASE_URL` 留空，系統會採 Gemini／規則 fallback。
- [ ] 選擇加密的異機備份位置（雲端 bucket、受控 NAS 或備份服務），並設定最少 30 天保留策略。

## 3. 建立 production secrets

在伺服器專案根目錄執行：

```bash
cp .env.production.example .env.production
chmod 600 .env.production
openssl rand -base64 48
```

將輸出填入 `AUTH_SECRET`（至少 32 字元），並填入自己的 `APP_DOMAIN`、不可變 Git tag／commit 形式的 `APP_VERSION`、至少 16 字元的 PostgreSQL 密碼、啟用 STARTTLS 的 SMTP 資訊與可選 AI key。不要把 `.env.production` 上傳到 Git、聊天訊息、截圖或共享磁碟。

## 4. 部署與首次驗收

```bash
sh scripts/preflight-production.sh
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
docker compose --env-file .env.production -f docker-compose.production.yml ps
sh scripts/smoke-production.sh https://<APP_DOMAIN>
```

- [ ] 確認 `https://<APP_DOMAIN>/health/ready` 回傳成功，且 `version` 等於本次部署的 immutable release（驗證 backend、資料庫與 migration）；HTTP 會自動轉至 HTTPS。
- [ ] 從無痕視窗註冊一個測試帳戶；確認驗證信可收到、連結只能使用一次。
- [ ] 用新帳戶登入、啟用 MFA、保存恢復碼，再驗證第二次登入流程。
- [ ] 上傳一份非敏感測試 CV，分析測試 JD，產生一份材料，確認所有資料只對該帳戶可見。
- [ ] 檢查 Caddy、backend 的 logs 沒有 secret、CV 原文、密碼或 token。驗證／重設 email link 應使用 `#verify_token=` 或 `#reset_token=` fragment，而非 query string。
- [ ] 執行 `docker inspect` 確認容器使用 `local` log driver 與 rotation；仍須監控 VM 磁碟使用量。
- [ ] 執行完整備份，並用 `sh scripts/verify-postgres-restore.sh --archive <backup.dump>` 在**隔離、無網路的暫存 PostgreSQL**完成一次實際 restore 演練；不要把未驗證備份直接還原到正式資料庫。
- [ ] 閱讀並照 [Release 與 Rollback Runbook](release_runbook.md) 執行 immutable release 發布；只有在 migration 相容性已證明時才能 rollback application，**不要**直接執行未演練的 database downgrade。

## 5. 持續營運

- [ ] 將 GitHub Actions CI 設為受保護分支的必要檢查。
- [ ] 建立 Docker image／容器可用性、磁碟、資料庫備份成功率、SMTP 失敗率與 AI fallback 比例的告警。
- [ ] 每月更新系統與 Docker base image；每次更新先通過 CI、preflight 與 staging 驗收。
- [ ] 每季實際演練一次密碼重設、帳戶刪除、備份復原與 MFA 恢復碼流程；帳戶刪除若回 503，代表衍生向量尚未安全清除，應待 Milvus 恢復後重試，不能把它視為刪除成功。

## 不在本次自動化範圍內

這些項目必須由服務擁有者在外部平台執行，程式不能代替你授權：購買／管理網域、雲端 VM、DNS、TLS 網路可達性、SMTP 帳戶與寄件網域驗證、Gemini API key、Ollama 主機、異機備份與監控告警。未完成上述項目前，不要將服務公開給真實使用者。
