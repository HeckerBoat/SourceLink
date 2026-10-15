# 项目文件架构说明（architecture.md）

商业化虚拟资源托管平台，前后端分离：**Flask（后端 API）+ Vue 3（前端页面）**，SQLite 存储。
后端代码在 `backend/`，前端代码在 `Frontend/`，根目录 `app.py` 为统一启动入口（启动后同时提供 API 与前端页面）。

---

## 顶层文件

| 文件 | 作用 |
| --- | --- |
| `app.py` | 项目统一启动入口，创建 Flask 应用并监听 `0.0.0.0:5000`，首次启动自动建库与初始化管理员 |
| `requirements.txt` | Python 依赖清单（uv pip 安装） |
| `.env.example` | 环境变量模板（密钥、SMTP、短信厂商配置），复制为 `.env` 后使用 |
| `.env` | 实际环境变量（含密钥，已被 .gitignore 忽略，不入库） |
| `.python-version` | 固定 Python 3.12（uv python pin） |
| `.gitignore` | Git 忽略规则（虚拟环境、db、.env、node_modules、dist、权重等） |
| `SQLTable.md` | 数据库表结构设计说明（表名/字段/含义/设计理由），共 8 张表 |
| `finish_req.md` | 已完成功能需求清单（对照基本需求逐条验收） |
| `architecture.md` | 本文件，全部文件作用索引 |
| `CloudConfig.md` | 云主机反向代理配置指南（113.46.196.84 → 100.93.80.112:5000-6000） |
| `README.md` | 英文项目说明与运行指南 |
| `README_zh.md` | 中文项目说明与运行指南 |

---

## `backend/` —— Flask 后端

| 文件 | 作用 |
| --- | --- |
| `backend/app.py` | Flask 应用工厂：加载配置、初始化数据库、注册蓝图、CORS（暴露 X-Refresh-Token 头）、全局异常处理（堆栈打印后端）、托管前端 `dist` 产物 |
| `backend/config.py` | 全局配置：从 `.env` 读取端口、密钥、会话空闲时长（SESSION_IDLE_MINUTES）、管理员账户、SMTP、短信渠道等 |
| `backend/database.py` | SQLModel 引擎/会话：`init_db()` 建表，`get_session()` 提供会话 |
| `backend/init_db.py` | 启动初始化：先执行配置/数据库迁移（migrate_env + migrate_db），再建表、写入默认站点配置、创建管理员 admin（绑定 11111111111），并在密钥变更导致旧哈希失效时按配置密码自动重置管理员哈希 |

### `backend/models/` —— 数据库表模型（SQLModel）

| 文件 | 作用 |
| --- | --- |
| `models/user.py` | 用户表 `user`：用户名/手机号/邮箱、二次哈希密码、管理员标记 |
| `models/resource.py` | 资源块表 `resource_block`：名称、描述、网盘链接、购买链接、块密码哈希、上下架 |
| `models/verification.py` | 验证码表 `verification_code`：短信/邮箱验证码哈希、有效期、一次性消费标记 |
| `models/site_config.py` | 站点配置表 `site_config`：键值对存储前端可调参数 |
| `models/access_log.py` | 访问记录表 `access_log`：用户解锁资源块的成功/失败审计 |
| `models/trusted_device.py` | 可信设备表 `trusted_device`：用户成功登录过的设备（设备 ID + UA 摘要 + 首次/最近登录时间），异地登录风控依据 |
| `models/feedback.py` | 用户反馈表 `feedback`：提交者、内容（≤2000 字）、提交时间 |
| `models/captcha_record.py` | 滑动验证码表 `captcha_record`：拼图挑战（含正确坐标）与一次性放行凭证，5 分钟过期 |
| `models/__init__.py` | 集中导出全部模型，供建表时注册元数据 |

### `backend/services/` —— 业务逻辑层

| 文件 | 作用 |
| --- | --- |
| `services/security.py` | 密码二次哈希（SHA-256+pepper → PBKDF2-SHA256）、JWT 签发（有效期=会话空闲时长）与校验、SHA-256 工具 |
| `services/auth.py` | 注册（验证码校验+查重+建用户）、登录（用户名/手机/邮箱）、绑定/更换手机号（格式+唯一占用校验，无需短信验证码）、可信设备判定与登记、用户序列化、发 token |
| `services/verification.py` | 验证码生成（6 位数字）、60 秒限频、手机号/邮箱格式校验、一次性校验 |
| `services/captcha.py` | 滑动拼图验证码：Pillow 生成随机背景与缺口/滑块图、坐标容差校验（±6px）、一次性 ticket 签发与消费 |
| `services/notifier.py` | 通知渠道：短信（默认 console 打印终端，预留阿里云/腾讯云）、邮件（SMTP 真实发送/console）、新设备登录风险提醒邮件 |
| `services/resource.py` | 资源块 CRUD、上下架、解锁校验、访问记录写入/联表查询/单条删除/全量清空；过期资源自动下架、禁止上架/解锁 |
| `services/feedback.py` | 反馈提交（≤2000 字）、按角色查询（管理员全部/普通用户仅自己的，管理员附提交者账号）、管理员单条删除/全量清空 |
| `services/site_config.py` | 站点配置默认值、启动加载到内存缓存、公开配置、管理员更新、`session_idle_minutes()` 会话空闲时长读取（签发/续期令牌实时使用，5-10080 分钟）、`resource_ttl()` 资源有效期读取（月/天/小时）、`is_resource_expired()` 过期判定（三项均为 0 则永久有效） |
| `services/migrate.py` | 迁移（需求 16）：`migrate_env()` 按 .env.example 补齐 .env 缺失键（旧值不覆盖，改前备份）；`migrate_db()` 给已存在的表 ALTER 补齐缺失列（旧数据保留，变更前备份 db 到 db/backups/），启动时自动执行 |
| `services/__init__.py` | 服务层包标识 |

### `backend/api/` —— HTTP 接口层（Flask 蓝图，统一前缀 `/api`）

| 文件 | 作用 |
| --- | --- |
| `api/common.py` | 统一 JSON 响应 `{code,msg,data}`、`require_auth(admin)` 登录/管理员鉴权装饰器 + 会话滑动续期（剩余不足一半时响应头下发 X-Refresh-Token） |
| `api/auth.py` | 公开配置 `GET /config/public`、注册 `POST /auth/register`（需滑动凭证）、登录 `POST /auth/login`（新设备需滑动凭证，业务码 4011，成功后登记设备+发风险邮件）、当前用户 `GET /auth/me`、绑定手机号 `POST /auth/bind-phone`（需登录）、绑定邮箱 `POST /auth/bind-email`（需登录，校验 bind_email 邮箱验证码） |
| `api/captcha.py` | 滑动验证码：获取拼图 `POST /captcha/new`、校验坐标签发凭证 `POST /captcha/verify` |
| `api/verification.py` | 发送验证码 `POST /verification/send`（purpose=register 公开；purpose=bind_email 需登录） |
| `api/resources.py` | 资源列表 `GET /resources`、解锁查看 `POST /resources/<id>/unlock`（需登录） |
| `api/feedback.py` | 提交反馈 `POST /feedback`、按角色查看 `GET /feedback`（需登录）、管理员删除 `DELETE /feedback/<id>` 与清空 `DELETE /feedback` |
| `api/admin.py` | 管理员接口：资源块 CRUD、站点配置读写（含 session_idle_minutes 与 resource_ttl_* 范围校验）、访问记录查询 `GET /admin/logs`、单条删除 `DELETE /admin/logs/<id>` 与全量清空 `DELETE /admin/logs`（均需管理员） |
| `api/__init__.py` | 接口层包标识 |

---

## `Frontend/` —— Vue 3 前端（Vite + Element Plus + Pinia + Vue Router）

| 文件 | 作用 |
| --- | --- |
| `Frontend/package.json` | 前端依赖与脚本（dev/build/preview） |
| `Frontend/vite.config.js` | Vite 配置：`@` 别名、dev 端口 5173、`/api` 代理到 5000、构建到 `dist` |
| `Frontend/index.html` | SPA 入口 HTML（含站点 favicon） |
| `Frontend/.gitignore` | 前端忽略 node_modules/dist |

### `Frontend/src/`

| 文件 | 作用 |
| --- | --- |
| `src/main.js` | 前端入口：挂载 Vue、Pinia、Router、Element Plus（中文语言包）、全局图标、全局样式 |
| `src/App.vue` | 根组件（仅 router-view） |
| `src/api/http.js` | axios 实例：baseURL=/api、Bearer token 注入、X-Refresh-Token 滑动续期落盘、统一拆包、401 跳登录、业务码 4011（需滑动验证）静默透传 |
| `src/router/index.js` | Hash 路由表（含 /feedback 与 /admin/feedback）与全局守卫（未登录跳登录、管理员页鉴权、登录后访问登录页自动跳转） |
| `src/stores/auth.js` | Pinia 认证状态：token/user、登录态与管理员判定、设备 ID 生成与持久化（sl_device_id）、localStorage 持久化、setUser 更新用户、退出 |
| `src/stores/site.js` | Pinia 站点状态：启动拉取公开配置（站名、注册/渠道开关）并同步标题 |
| `src/styles/main.css` | 全局样式：主题色、渐变背景、认证页、头部、资源卡片、管理后台布局、768px 移动端响应式适配 |
| `src/utils/format.js` | ISO 时间转本地显示文本 |
| `src/layouts/MainLayout.vue` | 主框架：顶部导航（站名、管理入口、用户下拉：资源市场/我的/意见反馈/管理后台/退出）+ 内容区 |
| `src/layouts/AdminLayout.vue` | 管理后台框架：左侧菜单（资源管理/站点配置/访问记录/用户反馈）+ 内容区 |
| `src/components/ResourceCard.vue` | 资源卡片：名称、描述、前往购买（外链）、查看资源按钮 |
| `src/components/UnlockDialog.vue` | 解锁弹窗：输入块密码 → 成功后展示网盘链接并支持复制（含非安全上下文降级） |
| `src/components/SliderCaptcha.vue` | 滑动拼图验证码组件：canvas 渲染背景缺口与滑块、指针拖动（支持触屏）、坐标按显示比例换算提交、成功 emit 一次性 ticket、失败自动刷新 |
| `src/views/Login.vue` | 登录页（用户名/手机号/邮箱 + 密码）；新设备登录返回 4011 时内嵌滑动验证码，验证通过自动重试 |
| `src/views/Register.vue` | 注册页：短信/邮箱选项卡、发送验证码 60s 倒计时、两次密码一致性校验、必填滑动验证码、携带设备 ID |
| `src/views/Market.vue` | 资源市场首页：Hero 区 + 资源卡片网格 + 解锁弹窗 |
| `src/views/Feedback.vue` | 意见反馈页：提交反馈 + 反馈列表（管理员显示全部并附提交者账号，普通用户仅自己的）；管理员可单条删除/一键清空全部反馈（二次确认） |
| `src/views/Profile.vue` | 「我的」页：账号信息展示（用户名/邮箱/手机号/注册时间）、绑定邮箱（未绑邮箱时显示：发码 60s 倒计时 + bind_email 验证码校验）、绑定/更换手机号（前端格式校验，无需短信验证码，绑定后可手机号登录） |
| `src/views/admin/Resources.vue` | 管理-资源块：表格（含创建日期、过期状态）、新建/编辑（密码留空不改，弹窗宽度 min(560px,94vw)）、上下架（已过期资源禁止上架）、删除确认 |
| `src/views/admin/Settings.vue` | 管理-站点配置：站名、注册与渠道开关、验证码有效期/重发间隔、会话空闲失效时长（分钟）、资源有效期（X月X天X小时，全 0 表示永久有效），保存后同步前端；移动端标签置顶 |
| `src/views/admin/Logs.vue` | 管理-访问记录：解锁成功/失败记录表格，支持单条删除与一键清空（二次确认） |

构建产物目录 `Frontend/dist/` 由 `npm run build` 生成，由 Flask 直接托管（已忽略入库）。

---

## `db/` —— SQLite 数据库

| 文件 | 作用 |
| --- | --- |
| `db/sourcelink.db` | SQLite 数据库文件（首次启动自动创建，已忽略入库），共 8 张表，详见 [SQLTable.md](SQLTable.md) |
| `db/backups/` | 迁移自动备份目录：结构变更前的数据库副本、.env 补齐前的副本（时间戳命名，已忽略入库） |

---

## `test/` —— 测试脚本

| 文件 | 作用 |
| --- | --- |
| `test/smoke_test.py` | 后端接口冒烟测试（85 项检查），覆盖滑动验证码、新设备登录风控、登录/注册/验证码/资源 CRUD/解锁与免密直显/权限/配置（含会话空闲时长）/绑定手机号/绑定邮箱（bind_email 验证码）/反馈/访问记录与反馈删除/令牌续期 |
| `test/migrate_test.py` | 迁移机制测试（13 项检查，独立运行无需服务）：.env 缺失键补齐/旧值保留/自动备份/幂等/按模板生成；旧库缺列 ALTER 补齐/旧数据保留/备份/幂等 |
| `test/test_email.py` | 163 邮箱 SMTP 发信实测：调用 notifier.send_email 向发件箱自身发一封测试验证码邮件，验证授权码与链路 |
| `test/e2e/diagnose-message.mjs` | 诊断解锁错误提示 DOM 状态的 puppeteer 脚本 |
| `test/e2e/ab-message.mjs` / `ab-message2.mjs` | ElMessage 生命周期对比实验（旧/新版 headless） |
| `test/e2e/timing.mjs` | 测量 API 耗时、JS 心跳、消息挂载精确时序 |
| `test/e2e/dialog-shot.mjs` | dialog 内错误提示截图验证 |
| `test/e2e/admin-ui.mjs` | 管理后台 UI 端到端流程（新建/删除/配置/记录） |
| `test/e2e/slider-captcha.mjs` | 滑动验证码端到端测试（CDP 真实拖动：错误坐标提示 / 白盒读库精确拖动通过 / 登录页新设备触发） |
| `test/e2e/package.json` | E2E 测试依赖（puppeteer-core，驱动系统 Edge） |

---

## 启动与请求链路

```
浏览器 http://100.93.80.112:5000
        │  静态资源（Frontend/dist）
        ├── Flask(app.py → backend/app.py)
        │
        └── /api/*  →  api 蓝图 → services 业务层 → models(SQLModel) → SQLite(db/sourcelink.db)
```

开发模式下也可分别启动：Flask `python app.py`（5000）+ Vite `npm run dev`（5173，/api 自动代理）。
