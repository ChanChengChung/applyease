# ApplyEase Release 與 Rollback Runbook

這份 runbook 只應在受控的 production VM 上由已授權管理員執行。它不取代
[上線清單](launch_checklist.md)：DNS、SMTP、異機備份與監控仍需先完成。

## 發布前的不可省略檢查

1. 在 staging 或另一個受控環境先通過 CI、`sh scripts/preflight-production.sh`、登入、MFA、CV upload 與 smoke 測試。
2. 建立完整 PostgreSQL backup，將 archive 與 checksum 放到加密的異機位置；使用隔離容器執行一次 restore rehearsal。不要只做 schema backup。
3. 記錄目前 release：

```bash
curl --fail --silent https://<APP_DOMAIN>/health/ready
git rev-parse HEAD
git status --short
```

若 working tree 有未預期的 tracked changes，先停止。不要在臨時修改過的 production source 上發布。

## 發布 immutable release

假設 `<RELEASE>` 是已審核的 immutable Git tag 或完整 commit（例如 `v1.0.0`）。

```bash
git fetch --tags
git checkout --detach <RELEASE>

# 在 .env.production 將 APP_VERSION 設為同一個 <RELEASE>。
chmod 600 .env.production
sh scripts/preflight-production.sh
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
docker compose --env-file .env.production -f docker-compose.production.yml ps
sh scripts/smoke-production.sh https://<APP_DOMAIN>
curl --fail --silent https://<APP_DOMAIN>/health/ready
```

最後一個 response 的 `version` 必須完全等於 `<RELEASE>`，且 `database` 為
`ok`、migration 為目前 head。然後在無痕瀏覽器完成一個非敏感測試帳戶的註冊、
email verification、登入、MFA、文件 upload 及登出。若上述任一步失敗，不要把
流量導入或宣告發布完成。

## 安全 rollback 原則

不要直接執行 `alembic downgrade`，也不要把舊 application image 接到未知的新
schema。資料庫 migration 通常是 forward-only；錯誤的 schema downgrade 可能造成
不可逆資料遺失。

先判斷新 release 是否引入 migration：

```bash
curl --fail --silent https://<APP_DOMAIN>/health/ready
git diff <PREVIOUS_RELEASE>..<FAILED_RELEASE> -- backend/migrations
```

- **沒有 migration，或已在 staging 證明舊版與新 schema 相容**：可回到
  `<PREVIOUS_RELEASE>`，同步把 `APP_VERSION` 改為該 release，重新跑 preflight、
  Compose build、smoke 和 readiness version 驗證。
- **有未證明相容性的 migration**：不要冒險部署舊程式。優先做 forward fix；若必須
  災難復原，停止服務並由已驗證、加密的完整 backup 還原到隔離環境演練後，再由資料
  擁有者批准復原 production。此過程可能遺失 backup 之後的資料，必須明確溝通。

可相容 rollback 的指令如下：

```bash
git checkout --detach <PREVIOUS_RELEASE>
# 編輯 .env.production：APP_VERSION=<PREVIOUS_RELEASE>
chmod 600 .env.production
sh scripts/preflight-production.sh
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
sh scripts/smoke-production.sh https://<APP_DOMAIN>
```

確認 readiness `version` 為 `<PREVIOUS_RELEASE>` 後，重新驗證登入與一個不含敏感
資料的讀寫流程。保留 failed release 的 container logs（不得含 secrets/CV 原文）與
時間線，供後續事件檢討。

## 發布後監控

發布後至少觀察 30 分鐘：HTTPS uptime、readiness、container restart count、VM
memory/disk、PostgreSQL backup 狀態、SMTP delivery failure、AI provider fallback / quota
429 比例。異常時先停止自動化部署，再依上面 migration 相容性原則處理。
