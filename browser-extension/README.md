# ApplyEase Field Preview Extension

这是一个安全的浏览器扩展 MVP：扫描当前招聘页面的表单字段，调用 ApplyEase 生成字段预览，用户勾选后才填充。当前网站专用适配器为 Greenhouse 和 Lever。

## Greenhouse 适配器

- 通过 Greenhouse 域名（例如 `boards.greenhouse.io`、`job-boards.greenhouse.io`）或页面的 `#grnhse_app` 标记自动识别。
- 优先使用 Greenhouse 表单中的 `label`、`fieldset/legend`、`data-qa` 和字段容器提取问题名称。
- 将同名 radio 选项合并成一个可预览字段，并在用户确认后选择对应选项。
- 仍然遵守通用安全边界：不会填充密码、文件、checkbox、验证码、敏感字段，也不会点击提交按钮。
- 本地验证页面为 `fixtures/greenhouse-application.html`；真实招聘页面的字段由其实际 DOM 动态决定，未匹配字段会保留为人工填写。

## Lever 适配器

- 自动识别 `jobs.lever.co`、`jobs.eu.lever.co` 和嵌入了 Lever application form 标记的企业招聘页。
- 支持基础字段、自定义问题、textarea、select 和 radio group；每次扫描都重新读取动态 DOM。
- Resume 等文件字段及 data consent checkbox 只在预览中提示人工处理，扩展不会填写或勾选。
- 本地验证页面为 `fixtures/lever-application.html`。扩展不会调用 Lever 的提交 API，也不会自动提交申请。

## 安全边界

- 不会自动点击 Submit/Apply/Confirm。
- 不会填充密码、验证码、文件上传、隐藏字段或敏感字段。
- 只填充状态为 `ready` 的字段；`needs_review`、`manual_required`、`no_match` 必须人工处理。
- 使用当前浏览器标签页，不上传 Cookie、密码或网页表单值到后端。
- 后端只接收字段元数据和用户在扩展中选择的申请记录；内部 ID 不会显示给用户。
- 更换后端地址前必须先取得该 origin 的 Chrome 权限；地址成功变更后，扩展会立即清除旧地址的 access token，要求重新登录，避免 token 被发送到新主机。

## 构建

```bash
npm install
npm run build
```

## 本地测试表单

`fixtures/application-form.html` 是本地招聘表单 fixture，包含普通文本框、textarea、select、密码、文件上传、敏感字段和提交按钮。字段扫描与填充模块自动化测试覆盖：

- label/name/id/placeholder 识别；
- `maxlength` 限制；
- select option 匹配；
- React/Vue 兼容的 native value setter 与 `input/change` 事件；
- 密码、文件、提交按钮永不填充；
- 超过网页限制的答案跳过。

运行：

```bash
npm test
```

如需手动检查 fixture，可在项目根目录运行：

```bash
python3 -m http.server 4173 --directory browser-extension/fixtures
```

然后访问 `http://127.0.0.1:4173/application-form.html`，在 Chrome 加载 `dist/` 扩展并按下方步骤操作。

## Chrome 加载

1. 打开 `chrome://extensions`。
2. 打开右上角 Developer mode。
3. 点击 Load unpacked。
4. 选择 `browser-extension/dist`。
5. 确保 ApplyEase FastAPI 运行在 `http://127.0.0.1:8000`。
6. 在 ApplyEase 申请表助手中先识别问题并生成答案。
7. 生产/多用户模式下，先在扩展“后端设置与账号”登录；扩展仅保存 access token，不保存密码。
8. 打开招聘网页，点击扩展图标，选择「公司 · 职位」申请记录，点击“扫描当前网页”。
9. 检查预览并勾选字段，点击“填充已勾选字段”。
10. 在网页中人工核对后手动提交。

## 后端地址与连接检查

扩展默认连接 `http://127.0.0.1:8000`。在弹窗展开“后端设置”可以修改地址、授予该地址的最小访问权限并点击“测试连接”。输入地址时可以填写服务根地址，也可以误填 `/api/v1` 后缀，扩展会自动规范化并将配置保存在 Chrome 本地存储中。

如果扫描失败，扩展会分别提示：后端不可达、尚未选择申请记录、当前页面无法注入扩展、没有识别到字段或后端接口错误。动态加载的表单可以等待加载完成后重新点击扫描。

当前已支持 Greenhouse 和 Lever 专用适配器，其余网站继续使用通用字段匹配。本项目暂不继续开发其他网站适配器。
