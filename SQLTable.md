# 数据库表设计说明（SQLTable.md）

数据库：SQLite，数据库文件统一位于 `db/sourcelink.db`，使用 SQLModel（SQLAlchemy + Pydantic）以 ORM 方式操作。
所有时间字段以 UTC 时区感知时间存储。

---

## 1. user（用户表）

保存管理员与普通注册用户。普通用户使用手机号或邮箱注册登录；管理员使用固定用户名 `admin` 登录并绑定手机号。

| 字段名 | 类型 | 约束 | 含义 |
| --- | --- | --- | --- |
| id | INTEGER | 主键，自增 | 用户唯一标识 |
| username | VARCHAR(64) | 唯一索引，可空 | 登录用户名；普通用户为空，管理员为 admin |
| phone | VARCHAR(20) | 唯一索引，可空 | 手机号，短信注册时写入，也是登录账号之一 |
| email | VARCHAR(128) | 唯一索引，可空 | 邮箱，邮箱注册时写入，也是登录账号之一 |
| password_hash | VARCHAR(255) | 非空 | 二次哈希后的密码密文（SHA-256(pepper+密码) 再 PBKDF2-SHA256） |
| is_admin | BOOLEAN | 非空，默认 0 | 是否管理员 |
| is_active | BOOLEAN | 非空，默认 1 | 账号是否启用（预留封禁能力） |
| created_at | DATETIME | 非空 | 创建时间（UTC） |
| updated_at | DATETIME | 非空 | 最近更新/登录时间（UTC） |

**设计理由**

- 账号支持用户名/手机号/邮箱三种形态登录，三者都建唯一索引以保证不重复并加速登录查询；SQLite 中唯一列允许出现多个 NULL，因此普通用户 username 为空不冲突。
- 密码不明文存储，采用服务端 pepper 的 SHA-256 + 每用户随机盐的 PBKDF2 二次哈希，即使数据库泄露也无法直接还原密码。
- is_admin 用布尔标记区分角色，需求只有“管理员/普通用户”两类，无需引入额外角色表。

---

## 2. resource_block（资源块表）

商业化虚拟资源块，由管理员新建、编辑、删除；普通用户输入正确的资源块密码后才能看到网盘链接。

| 字段名 | 类型 | 约束 | 含义 |
| --- | --- | --- | --- |
| id | INTEGER | 主键，自增 | 资源块唯一标识 |
| name | VARCHAR(128) | 非空，索引 | 资源名称 |
| description | TEXT | 可空 | 资源描述（卡片展示用，可选） |
| pan_url | VARCHAR(512) | 非空 | 资源网盘链接，解锁后才返回给前端 |
| purchase_url | VARCHAR(512) | 非空 | 第三方购买链接（直接对外可见） |
| block_password_hash | VARCHAR(255) | 非空 | 资源块密码的二次哈希密文 |
| is_published | BOOLEAN | 非空，默认 1，索引 | 是否上架；下架后普通用户列表不可见 |
| created_at | DATETIME | 非空 | 创建时间（UTC） |
| updated_at | DATETIME | 非空 | 更新时间（UTC） |

**设计理由**

- 对应需求中的四个核心元素：资源名称、资源网盘链接、资源块密码、资源购买链接；description/is_published 为便于运营的最小增强。
- 资源块密码同样以二次哈希存储，接口永不返回该哈希，避免绕过“输密码才能看链接”的业务规则。
- pan_url 在普通列表接口中不输出，只有解锁接口校验密码成功后才返回，做到数据层面的保护。
- **过期状态不落库**：`expired` 由后端根据 `created_at` 与 `site_config` 中的资源有效期配置实时计算，避免“有效期修改后需批量刷新旧数据”的问题；列表接口返回前自动把过期资源下架。

---

## 3. verification_code（验证码表）

注册时下发的短信/邮箱验证码，两类渠道共用一张表。

| 字段名 | 类型 | 约束 | 含义 |
| --- | --- | --- | --- |
| id | INTEGER | 主键，自增 | 记录唯一标识 |
| target | VARCHAR(128) | 非空，索引 | 接收目标：手机号或邮箱地址 |
| channel | VARCHAR(10) | 非空，索引 | 渠道：sms（短信）/ email（邮箱） |
| purpose | VARCHAR(32) | 非空，默认 register，索引 | 用途：register（注册）/ bind_email（绑定邮箱），预留找回密码等场景 |
| code_hash | VARCHAR(64) | 非空 | 验证码的 SHA-256 哈希，明文不落库 |
| expires_at | DATETIME | 非空 | 过期时间（默认 5 分钟） |
| consumed_at | DATETIME | 可空 | 被使用（作废）的时间，为空表示未使用 |
| created_at | DATETIME | 非空 | 发送时间（UTC） |

**设计理由**

- 短信与邮箱验证码结构完全一致，用 channel 字段区分，避免两张重复的表。
- 验证码只存哈希且一次性（校验成功立即写 consumed_at），并带过期时间，防止重放与撞库。
- 按 (target, channel, purpose, created_at) 查询最新一条，用于“60 秒内不得重发”的限频。

---

## 4. site_config（站点配置表）

管理后台可调整、需要持久化并在程序启动时同步给前端的参数，键值对存储。

| 字段名 | 类型 | 约束 | 含义 |
| --- | --- | --- | --- |
| id | INTEGER | 主键，自增 | 配置项唯一标识 |
| config_key | VARCHAR(64) | 唯一索引，非空 | 配置键 |
| config_value | TEXT | 非空，默认空串 | 配置值（统一以字符串存储，使用时转换） |
| updated_at | DATETIME | 非空 | 最近修改时间（UTC） |

**内置配置项**

| config_key | 默认值 | 含义 |
| --- | --- | --- |
| site_name | SourceLink 资源托管平台 | 站点名称（前端标题/导航/邮件模板使用） |
| register_enabled | true | 是否开放注册 |
| sms_channel_enabled | true | 是否开放短信注册渠道 |
| email_channel_enabled | true | 是否开放邮箱注册渠道 |
| code_ttl_seconds | 300 | 验证码有效期（秒） |
| code_resend_interval | 60 | 同一目标重发验证码的最小间隔（秒） |
| session_idle_minutes | 60 | 会话空闲失效时长（分钟），管理员后台可改（5-10080），签发/续期令牌实时读取；`.env` 的 SESSION_IDLE_MINUTES 仅为首次启动的种子值 |
| resource_ttl_months | 0 | 资源有效期-月（0-120），与天数、小时数累加计算 |
| resource_ttl_days | 0 | 资源有效期-天（0-3650） |
| resource_ttl_hours | 0 | 资源有效期-小时（0-87600）；三项均为 0 表示永久有效 |

**设计理由**

- 用键值对而非宽表，新增配置项无需改表结构，符合“前端参数更改后同步保存到配置数据库、启动时读取同步到前端”的要求。
- 敏感信息（SMTP 密码、短信厂商密钥）放在服务端 `.env` 而不是本表，避免通过管理界面泄露；表中只存非敏感的业务开关与参数。

---

## 5. access_log（资源访问记录表）

记录用户解锁资源块的尝试，便于管理员审计异常解锁行为。

| 字段名 | 类型 | 约束 | 含义 |
| --- | --- | --- | --- |
| id | INTEGER | 主键，自增 | 记录唯一标识 |
| user_id | INTEGER | 非空，索引 | 尝试解锁的用户 ID |
| resource_id | INTEGER | 非空，索引 | 被解锁的资源块 ID |
| success | BOOLEAN | 非空 | 本次密码校验是否成功 |
| created_at | DATETIME | 非空 | 尝试时间（UTC） |

**设计理由**

- 成功与失败都记录，管理员可从后台观察是否有人暴力尝试资源块密码。
- 成功记录同时作为“解锁过一次即直接展示网盘链接”的判定依据：资源列表接口按 (user_id, resource_id, success=1) 标记 unlocked，解锁接口允许历史成功用户传空密码直接放行，免密放行不再重复写日志。
- 仅存 ID 外键值（SQLite 不强制外键约束也能工作），展示时由服务层联表带出账号与资源名称，保持表结构精简。

---

## 6. trusted_device（可信设备表）

记录用户成功登录过的设备（浏览器端生成并持久化的匿名设备 ID），用于实现“异地设备首次登录需要滑动验证码 + 邮件风险提醒，之后同设备登录免验证”。

| 字段名 | 类型 | 约束 | 含义 |
| --- | --- | --- | --- |
| id | INTEGER | 主键，自增 | 记录唯一标识 |
| user_id | INTEGER | 非空，索引 | 用户 ID |
| device_id | VARCHAR(64) | 非空，索引 | 前端生成并持久化在 localStorage 的匿名设备 ID |
| device_name | VARCHAR(160) | 可空 | 首次登录时的 User-Agent 摘要（风险邮件中展示） |
| first_login_at | DATETIME | 非空 | 该设备首次登录成功时间（UTC） |
| last_login_at | DATETIME | 非空 | 该设备最近一次登录时间（UTC） |

**设计理由**

- (user_id, device_id) 建唯一约束，天然防重复登记，一条记录即代表“该用户在该设备上登录过”。
- 设备 ID 由前端生成（UUID）而非取 IP/UA 指纹：同一网络下多台设备不会互相误伤，隐私性更好；device_name 仅存 UA 摘要供邮件提醒展示。
- 注册成功即登记当前设备，避免“注册后同浏览器再次登录还要过滑动验证”的糟糕体验；登录成功才写表，未通过的尝试不产生记录。

---

## 7. feedback（用户反馈表）

用户提交的意见反馈。普通用户只能查看自己提交的反馈，管理员可查看全部。

| 字段名 | 类型 | 约束 | 含义 |
| --- | --- | --- | --- |
| id | INTEGER | 主键，自增 | 反馈唯一标识 |
| user_id | INTEGER | 非空，索引 | 提交者用户 ID |
| content | VARCHAR(2000) | 非空 | 反馈内容（前端限制 2000 字） |
| created_at | DATETIME | 非空，索引 | 提交时间（UTC） |

**设计理由**

- 结构最小化：需求只要求提交与按角色查看，不引入标题/状态/回复等冗余字段，后续若需要“已处理”状态可无损加列。
- user_id 建索引，普通用户“只看自己”与管理员“看全部（联表带账号）”都走该索引；按 created_at 倒序返回最新反馈。

---

## 8. captcha_record（滑动验证码记录表）

滑动拼图验证码的“挑战”与校验通过后签发的“一次性凭证”，统一存储。

| 字段名 | 类型 | 约束 | 含义 |
| --- | --- | --- | --- |
| token | VARCHAR(64) | 主键 | 挑战 ID 或凭证 token（UUID hex，不重复） |
| kind | VARCHAR(16) | 非空，索引 | 类型：challenge（拼图挑战）/ ticket（放行凭证） |
| answer_x | INTEGER | 可空 | challenge 的缺口正确横坐标；ticket 为空 |
| expires_at | DATETIME | 非空，索引 | 过期时间（挑战与凭证均为 5 分钟） |
| consumed_at | DATETIME | 可空 | 被消费（作废）时间，为空表示未使用 |
| created_at | DATETIME | 非空 | 创建时间（UTC） |

**设计理由**

- 挑战与凭证结构一致（一个 key + 一次性消费语义），用 kind 区分，避免两张结构雷同的表。
- 正确坐标 answer_x 只存服务端，前端永远拿不到答案；校验容差 ±6 逻辑像素在服务层实现。
- 落库而非内存缓存：服务重启后未过期的挑战/凭证仍然有效，同时便于测试脚本白盒读取正确坐标；过期记录在生成新挑战时惰性清理。
- 一次性消费（consumed_at）：挑战校验即作废（无论对错），防止同一题反复试坐标；ticket 消费后作废，防重放。

---

## 表关系概览

```
user ──(1:N)──> access_log <──(N:1)── resource_block
user ──(1:N)──> trusted_device        （同一设备+用户唯一）
user ──(1:N)──> feedback
verification_code（独立，按 target 关联注册流程）
site_config（独立键值配置）
captcha_record（独立，挑战/凭证一次性消费）
```
