# SourceLink 资源托管平台

商业化虚拟资源托管平台。管理员在后台维护资源块（资源名称、网盘链接、资源块密码、第三方购买链接），用户注册登录后，在资源市场点击资源并输入正确的资源块密码即可查看网盘链接。

- 后端：Python Flask（SQLModel 操作 SQLite，Cookie + 服务端会话鉴权）
- 前端：Vue 3 + Vite + Element Plus + Pinia
- 前后端分离开发，生产环境由 Flask 统一托管前端构建产物，一个入口即可运行

English: [README.md](README.md)

---

## 功能特性

- **管理员**：使用 `admin` 账户登录，进入后台新建 / 编辑 / 删除资源块，管理上下架、站点配置、查看解锁访问记录、查阅全部用户反馈；访问记录与用户反馈均支持单条删除与一键清空。
- **资源块四要素**：资源名称、资源网盘链接、资源块密码、资源购买链接，管理员均可编辑。
- **普通用户**：手机号或邮箱注册（短信验证码 / 邮箱验证码任选其一验证通过即可），登录后浏览资源市场。
- **滑动拼图验证码**：注册及陌生设备首次登录均需拖动拼图补全缺口（后端 Pillow 随机生成，挑战与凭证 5 分钟有效、一次性使用，对齐一半即验证成功），验证通过后前端即移除验证码组件，防人机批量注册与撞库。
- **忘记密码**：登录页「忘记密码」可通过注册邮箱接收验证码重置密码，重置成功后所有设备强制重新登录。
- **用户管理**：管理员在后台可新建、查看、编辑、删除客户账户（登录账号、初始密码、停用/启用、重置密码），重置密码或停用后该用户所有设备强制下线；内置管理员账户受保护不可被操作。
- **异地设备保护**：陌生设备首次登录必须先通过滑动验证，登录成功后自动发送账户风险邮件（时间 / IP / 设备信息）；同设备再次登录免验证（可信设备表）。
- **会话空闲失效**：采用 Cookie 存储登录信息（HttpOnly Cookie 保存随机会话标识，服务端 `user_session` 表校验，不采用登录令牌校验）。会话有效期即站点配置 `session_idle_minutes`（默认 60 分钟，管理员后台「站点配置」可改为 5-10080 分钟并即时生效，`.env` 的 `SESSION_IDLE_MINUTES` 仅为首次启动种子值）；活跃会话剩余有效期不足一半时自动滑动续期并刷新 Cookie，活跃用户不掉线；超时后下一次任意请求返回 401，前端自动退出登录态并跳转登录页。
- **我的页面**：登录用户可查看账号信息；输入手机号无需短信验证码即可绑定/更换（前端格式校验 + 后端占用校验），绑定后支持手机号登录；未绑定邮箱的账号可通过邮箱验证码绑定邮箱，绑定后支持邮箱登录。
- **用户反馈**：登录用户可提交反馈并查看自己提交的记录；管理员在后台可查看全部用户反馈（含提交者账号）。
- **密码解锁**：用户点击资源块后必须输入资源块密码，校验通过才返回网盘链接；可一键复制。
- **解锁一次终身直显**：用户成功解锁过的资源块，再次点击无需重复输入密码，直接展示网盘链接（依据访问记录中的成功日志判定）。
- **购买引流**：资源卡片提供第三方购买链接按钮，新窗口打开。
- **注册校验**：短信、邮箱两条渠道可在后台独立开关；验证码 5 分钟有效、60 秒限频、一次性使用。
- **站点配置持久化**：站名、注册开关、渠道开关、验证码参数存数据库，启动时加载并同步前端。
- **资源有效期与过期自动下架**：管理员在后台以“X 月 X 天 X 小时”统一配置资源有效期（三项均为 0 表示永久有效）；资源创建日期自动记录，过期状态实时判定，过期资源自动下架、禁止上架且无法解锁。
- **升级迁移保护**：服务启动时自动迁移——`.env` 按 `.env.example` 补齐缺失配置键（已有值绝不覆盖），SQLite 已存在的表自动 ALTER 补齐缺失列（旧数据完整保留）；两类变更执行前都会先把原文件备份到 `db/backups/`。
- **移动端适配**：768px 断点响应式布局——资源卡片单列、头部收紧、后台菜单横向滚动、表单顶部标签，滑动验证码支持触屏拖动。
- **安全**：密码二次哈希（SHA-256+服务端 pepper → PBKDF2-SHA256 随机盐）；Cookie + 服务端会话；网盘链接仅解锁后下发。
- **错误处理**：所有异常堆栈打印在后端终端，前端只做轻提示，不弹错误窗。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3、Vue Router 4、Pinia、Element Plus、Axios、Vite 6 |
| 后端 | Flask 3、SQLModel / SQLAlchemy、Flask-Cors、python-dotenv、Pillow |
| 数据库 | SQLite（文件位于 `db/sourcelink.db`） |
| 环境管理 | uv（Python 3.12）、npm |

## 目录结构

```
SourceLink/
├── app.py                 # 统一启动入口
├── backend/               # Flask 后端（api / services / models）
├── Frontend/              # Vue 前端源码
│   └── dist/              # 前端构建产物（npm run build 生成）
├── db/                    # SQLite 数据库文件
├── test/                  # 接口冒烟测试 + E2E 脚本
├── SQLTable.md            # 数据库表设计
├── CloudConfig.md         # 云主机反向代理配置指南
└── architecture.md        # 每个文件的作用说明
```

完整文件索引见 [architecture.md](architecture.md)，数据库设计见 [SQLTable.md](SQLTable.md)。

---

## 快速开始

### 1. 环境要求

- Python 3.12（已用 `uv python pin 3.12` 固定）
- Node.js 18+（已在 Node 22 验证）
- [uv](https://docs.astral.sh/uv/) 包管理器

### 2. 创建虚拟环境并安装后端依赖

PowerShell：

```powershell
uv venv
uv pip install -r requirements.txt
# 若默认镜像拉取失败，可临时指定镜像：
# $env:UV_DEFAULT_INDEX='https://pypi.mirrors.ustc.edu.cn/simple'; uv pip install -r requirements.txt
```

### 3. 配置环境变量

复制模板并按需修改（首次运行也会自动生成一份带随机密钥的 `.env`）：

```powershell
Copy-Item .env.example .env
```

`.env` 关键项：`SECRET_KEY`、`PASSWORD_PEPPER`（生产环境务必修改）、`SESSION_IDLE_MINUTES`（会话空闲过期分钟数种子值，默认 60，之后以管理后台「站点配置」修改为准）、SMTP 邮箱配置、短信渠道配置。

### 4. 安装并构建前端

```powershell
cd Frontend
npm install --registry=https://registry.npmmirror.com
npm run build
cd ..
```

> 开发模式可另开终端执行 `npm run dev`（5173 端口，自动代理 `/api` 到 5000）。

### 5. 启动

```powershell
.\.venv\Scripts\python.exe app.py
```

首次启动自动建表、写入默认站点配置、创建管理员账户。访问：

- 本机：<http://127.0.0.1:5000>
- 公网：<http://100.93.80.112:5000>（请确认防火墙/安全组放行 5000 端口）

### 默认账户

| 账户 | 密码 | 说明 |
| --- | --- | --- |
| admin | `1q2w3e4r` | 管理员，已绑定手机号 11111111111 |

普通用户请在注册页自行注册。

---

## 短信 / 邮箱验证码说明

注册时两种渠道**任选其一**验证通过即可：

- **短信**：默认 `console` 模式——验证码直接打印在后端终端窗口（形如 `[SMS-console] 向手机号 138... 发送验证码: 246810`），便于无厂商凭证时联调。接入真实短信时，在 `.env` 设置 `SMS_PROVIDER` 并在 `backend/services/notifier.py` 中实现阿里云/腾讯云调用。
- **邮箱**：`.env` 已预置 163 邮箱 SMTP（`smtp.163.com:465`，使用 POP3/SMTP 授权码）并开启 `SMTP_ENABLED=true`，真实发送 HTML 验证码邮件；将 `SMTP_ENABLED` 置 false 则回退为终端打印。可用 `.\.venv\Scripts\python.exe test\test_email.py` 实测发信链路。

## 接口一览（前缀 `/api`）

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/config/public` | 公开 | 站点公开配置 |
| POST | `/captcha/new` | 公开 | 获取滑动拼图验证码（背景图 + 滑块图 + 挑战 ID） |
| POST | `/captcha/verify` | 公开 | 提交拖动坐标，通过后签发一次性 `ticket` |
| POST | `/auth/register` | 公开 | 注册（channel=sms/email + target + code + password + captcha_ticket + device_id） |
| POST | `/auth/login` | 公开 | 登录；陌生设备需先携带 `captcha_ticket`（返回业务码 `4011` 表示需要滑动验证） |
| GET | `/auth/me` | 登录 | 当前用户信息 |
| POST | `/auth/bind-phone` | 登录 | 绑定/更换手机号（无需短信验证码） |
| POST | `/auth/bind-email` | 登录 | 邮箱验证码校验通过后绑定邮箱 |
| POST | `/verification/send` | 混合 | 发送验证码（`purpose=register` 公开；`purpose=bind_email` 需登录） |
| GET | `/resources` | 登录 | 已上架资源块列表（不含网盘链接，含 `unlocked` 已解锁标记） |
| POST | `/resources/<id>/unlock` | 登录 | 校验块密码返回网盘链接；历史已解锁用户传空密码直接返回 |
| GET/POST/PUT/DELETE | `/admin/resources[...]` | 管理员 | 资源块 CRUD |
| GET/PUT | `/admin/config` | 管理员 | 站点配置读写 |
| GET | `/admin/logs` | 管理员 | 资源解锁访问记录 |
| DELETE | `/admin/logs/<id>`、`/admin/logs` | 管理员 | 单条删除 / 全量清空访问记录 |
| GET/POST | `/feedback` | 登录 | 提交反馈 / 反馈列表（普通用户仅见自己的，管理员见全部） |
| DELETE | `/feedback/<id>`、`/feedback` | 管理员 | 单条删除 / 全量清空用户反馈 |

统一响应格式：`{"code": 0, "msg": "success", "data": ...}`，`code != 0` 表示业务失败。

## 测试

接口冒烟测试（需先启动服务，自动创建并清理测试数据，共 85 项检查）：

```powershell
.\.venv\Scripts\python.exe test\smoke_test.py
```

迁移机制测试（独立运行无需服务，13 项检查：.env 补齐与数据库列迁移，含备份）：

```powershell
.\.venv\Scripts\python.exe test\migrate_test.py
```

163 邮箱 SMTP 发信实测（向发件箱自身发送一封测试验证码邮件）：

```powershell
.\.venv\Scripts\python.exe test\test_email.py
```

浏览器端到端脚本（puppeteer-core 驱动系统 Edge，无需另外下载浏览器）：

```powershell
cd test/e2e
npm install --registry=https://registry.npmmirror.com
node admin-ui.mjs        # 管理后台流程
node dialog-shot.mjs     # 解锁错误提示验证
node slider-captcha.mjs  # 滑动验证码：错误拖动 / 白盒精确拖动 / 登录新设备流程
cd ../..
```

## 安全建议

- 上线前修改 `.env` 中的 `SECRET_KEY`、`PASSWORD_PEPPER`、管理员默认密码。
- 生产建议用 waitress / gunicorn 部署，并放在 Nginx HTTPS 反向代理之后。
- `.env`、`db/*.db`、`.venv/`、`node_modules/`、`dist/` 均已在 `.gitignore` 中忽略。
