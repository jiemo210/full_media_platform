# 全媒体聚合平台

> 参考原「热点荟 NewsHub」项目重构的新项目（保留原有前后端代码结构），聚焦三大核心业务：
> **热点新闻挖掘展示 → AI 改写/创作 → 全媒体平台发布**

---

## 一、核心功能

### 1. 热点新闻挖掘展示
- 13 大可用新闻源实时聚合（详见下方源清单），一键抓取、去重入库
- 热度排行、来源/分类筛选、按热度/时间排序
- 新闻正文抓取，供 AI 改写使用

### 2. AI 改写与全媒体发布
- 点击热点新闻 → AI 流式生成改写文章（风格/平台/补充提示词可配）
- 生成内容自动进入**富文本编辑器**，Markdown 格式自动渲染（编辑/预览双视图、工具栏）
- 一键创建发布任务到头条/百家号/公众号/知乎/微博/小红书/B站/微头条
- 半自动发布包一键复制 + 模拟直发（真实平台 API 待资质接入）

### 3. AI 创作 + 富文本编辑器
- 自定义主题、风格、字数、平台 AI 创作，流式输出
- 生成结果直接进入富文本编辑器，Markdown 自动匹配展示格式，可保存到文章库

### 4. 新闻源管理
- 后台一键健康探测，停用/启用/移除新闻源
- 已剔除失效源：微博、知乎、36氪、澎湃、抖音、浙江新闻（2026-08 实测不可用）

### 5. 后台管理（完整管理端）
- 数据统计、用户管理、新闻管理、文章管理、新闻源管理、日志查看
- 发布任务支持预览 / 编辑 / 删除 / 复制发布包 / 模拟直发

### 6. 界面换肤
- 颜色模式：深色 / 浅色；背景方案：极光之夜 / 深海 / 暮色紫 / 宣纸白
- 选择持久化到 localStorage，刷新保留

### 7. 日志记录
- 请求访问日志（方法/路径/状态码/耗时）与业务日志统一输出到 `backend/logs/app.log`
- 后台「日志查看」实时查看，按大小轮转、保留 7 天

### 8. AI 模型与写作风格（后台可维护）
- **多 AI 模型配置**：后台「AI 模型」增删改（模型 ID/接口地址/独立 API Key/默认模型），AI 改写与创作可选择模型
- **写作风格库**：后台「写作风格」增删改；AI 改写与创作的风格下拉以维护数据为准
- **AI 改写建议**：改写前可一键生成 4 条建议，勾选后自动带入补充提示词

### 9. 页面配置
- 后台「页面配置」可修改：新闻列表每页数量（默认 10）、自动抓取间隔、启动自动抓取、默认 AI 模型

### 10. 发布平台管理
- 后台「发布平台」配置 8 大平台：名称、字数范围、**规范性要求/约束**、**发布跳转链接**、启用状态、排序
- AI 创作 / AI 改写的发布平台下拉取自维护数据，选择后显示该平台规范提示
- 「发布」改为**发布跳转**：一键标记发布并在新窗口自动打开对应平台发布页

### 11. 文章能力增强
- AI 创作 / AI 改写支持**导出 PDF**（打印另存）
- AI 生成内容自动**拆分标题**：标题进入编辑器上方标题框，正文不再重复包含标题
- 发布成功/失败弹出**全局显著提示**（顶部 Toast，含“前往发布/打开平台”快捷操作）

### 12. 发布与热点细节优化
- 发布管理：任务**预览/编辑**展示完整正文；「发布跳转」同步打开新标签（避免弹窗拦截）并跳转平台发布页；回执链接指向平台发布页（非模拟地址）
- 平台规范性要求自动作为**提示词**传给模型（含在生成请求中）
- 热点新闻默认**按时间排序**、默认展示**最近 3 天**热点（可传 days 调整），每条标注**首次抓取时间**
- 「复制发布包」改为复制**富文本预览正文**（Markdown 已转纯文本），并兼容无剪贴板 API 环境

### 12.5 内容风控（AI 风控检查）
- AI 创作 / AI 改写完成后可点击「🛡 风控检查」，由 AI 按**法律法规、社会主义核心价值观、平台风控要求**审查标题与正文
- 返回结果含：通过状态、风险级别（低/中/高）、风险点列表、修改建议；高风险会给出红色警告
- 后台「页面配置」可开关风控检查（`RISK_CHECK_ENABLED`）并配置补充要求（`RISK_CHECK_EXTRA`，如“需标注 AI 生成内容”）
- 后台「发布平台」可为每个平台单独配置**平台风控要求**（`risk_rules`），风控检查自动带入；留空复用规范性要求

### 12.6 资料搜索
- 顶部导航新增「🔎 资料搜索」：输入任意主题/问题，AI 自动扩展检索词
- 支持**时间范围筛选**（不限 / 近 24 小时 / 3 天 / 7 天 / 30 天），网页结果与本地热点库同步限时
- 网页检索（360 搜索，Bing 兜底）**仅保留新闻/文章类**：自动剔除百科词条、词典、问答、视频与网站首页
- 本地热点库按所选时间窗检索，再由 AI 精选：综合摘要、相关性说明、热点标注、延伸搜索词
- 每条资料可直接「✍️ 以此主题创作」，一键带入 AI 创作页

### 13. 最新增强
- **发布跳转**：点击「发布跳转」使用任务自带平台地址同步打开新标签（彻底避免弹窗拦截）；已移除回执链接入口
- **富文本复制**：发布包 / 文章 / 创作 / 改写的复制均改为复制**带格式 HTML**（ClipboardItem，含纯文本降级与兼容回退）
- **富文本导入图片**：编辑器工具栏新增 🖼 图片按钮（本地选择/直接粘贴），图片以 Markdown 语法保存并回显
- **导出 PDF**：文章库与发布管理页均支持导出 PDF（打印另存）
- **发布编辑弹窗**：与文章库一致，使用富文本编辑器（标题 + 富文本正文）
- **热点新闻搜索**：首页新增搜索框，按标题/摘要关键词过滤

### 14. 缺陷修复
- **发布跳转不再出现 about:blank**：改为点击瞬间同步锚点点击打开任务自带的真实平台地址
- **富文本图片保存/回显修复**：①HTML→Markdown 转换改为递归遍历子节点，图片不再被段落节点吞掉；②文章/任务正文字段升级为 LONGTEXT，容纳 base64 图片（此前 TEXT 64KB 上限会导致保存失败）
- **发布编辑弹框加宽**：编辑弹窗宽度提升至 880px（96vw 自适应），富文本浏览编辑更舒适

### 15. 二次加固（针对仍复现的两项）
- **发布跳转多层保障**：点击瞬间 `window.open` 打开真实平台地址；被浏览器拦截时自动弹出「打开平台发布页」可点击按钮，同时顶部 Toast 提供「打开平台」操作，确保任何情况下都有可见的跳转入口（不再出现无反应的 about:blank）
- **发布管理预览支持图片**：发布任务预览由本地简易渲染改为统一 Markdown→HTML 渲染，富文本中的图片在预览中正常展示
- 提示：若浏览器标签页是修复前打开的，请 **Ctrl+F5 强制刷新** 加载新代码

### 16. 上线加固（P0 落地）
- **本地素材库（可配置）**：新增 `storage.py` 本地对象存储抽象与 `media_assets` 素材表；上传接口 `POST /api/media/upload`（jpg/png/gif/webp/bmp/svg，≤10MB）返回 URL；`/media` 静态访问；富文本编辑器插图/粘贴图片**自动上传为 URL**（上传失败才降级 base64）；素材目录 `MEDIA_DIR` 可配置（config.json/.env/后台页面配置）
- **异步爬虫**：`POST /api/news/crawl` 立即返回（4ms），后台线程抓取；`GET /api/news/crawl/status` 查询进度（各源条数/总数/新增）；首页与后台新闻页按钮自动轮询进度
- **AI 限流与模型自动切换**：`AI_RATE_LIMIT`（默认每用户 50 次/小时，可配窗口）超限返回 429；`ai_service` 按启用模型列表失败自动切换（首选模型优先）
- **发布频率与任务上限**：`PUBLISH_RATE_LIMIT`（默认 50 任务/小时/用户）、`PUBLISH_TASK_LIMIT`（默认 500 总任务）超限返回 429
- 后台「页面配置」新增：素材目录、AI 限流、发布限流等可配置项

### 18. 安全与运维加固（P0/P1 落地）
- **密钥环境变量化**：`api_key` 不再写入 config.json（内存中保留，重启后从 `.env`/环境变量读取）；后台模型列表返回脱敏 Key，编辑留空表示保持不变
- **强制改密**：默认管理员不再固定 `admin/admin123`——首次创建随机生成初始密码（登录后强制修改），存量默认口令账号自动标记强制改密；`FMP_ADMIN_PASSWORD` 可指定初始密码
- **弱密钥防护**：检测到弱 JWT 密钥时自动生成随机密钥；请通过 `FMP_JWT_SECRET` 配置强密钥
- **上传安全**：图片上传按魔数校验真实类型（不再信任客户端 Content-Type），已禁用 SVG 上传
- **XSS 防护**：Markdown 链接/图片统一协议白名单（仅 http/https/mailto、/media、base64 图片），富文本粘贴内容自动净化（移除脚本/事件属性/危险 URL）
- **日志脱敏**：数据库连接串不再打印口令
- **数据库迁移**：新增 `schema_migrations` 轻量迁移机制（`backend/migrations.py`），替代启动时裸 ALTER
- **爬虫去重优化**：`news.title_hash` 索引 + 批量查重入库（替代逐条查询）
- **中文全文搜索**：MySQL FULLTEXT(ngram) 索引，关键词搜索自动走全文索引，其他引擎回退 LIKE
- **权限实时校验**：角色/禁用状态改为每次请求查库，降权/禁用立即生效
- **发布状态机**：`pending → jumped（已跳转）→ published（确认已发布）`，跳转不再直接标记已发布
- **定时抓取生效**：`CRAWL_INTERVAL` 由调度线程按间隔循环抓取（此前为死配置）
- **日志保留**：`LOG_RETENTION_DAYS` 按天清理过期日志

### 17. 短篇小说创作（v2.2 已落地）
- **创作向导**：题材/篇幅（1万/3万/5万）/写作风格/参考作品 → 生成设定（梗概/世界观/角色卡）→ 生成分章大纲 → 进入编辑器
- **小说编辑器**：章节树 + 富文本编辑器 + AI 逐章生成（SSE 流式、自动落库）+ 断点续写
- **本地小说库**：创作完成或本地导入（按段落自动分章）入库；列表/搜索/题材筛选
- **AI 大纲总结**：一键生成并分栏展示——人物介绍（姓名/身份/性格/作用）、情节大纲（开端→发展→高潮→结局）、题材分类（主题材+标签）
- **参考创作**：新建小说可多选库内作品，注入其大纲总结作为参考（仅结构/人物设定逻辑，输出原创）
- **发布集成**：整本小说一键转发布任务（复用发布中台，平台规范注入）
- 数据模型：`novel_projects`（设定/大纲/总结 JSON/参考/入库标记）+ `novel_chapters`（正文 LONGTEXT）
- 复用：多模型+失败切换、AI 限流、富文本、素材库、发布中台、后台管理

---

## 二、新闻源清单（2026-08-26 实测）

| 来源 Key | 名称 | 状态 |
|----------|------|------|
| baidu | 百度新闻 | ✅ 可用 |
| toutiao | 今日头条 | ✅ 可用 |
| tencent | 腾讯新闻 | ✅ 可用 |
| cctv | 央视网 | ✅ 可用 |
| sina_finance | 新浪财经 | ✅ 可用 |
| nanfang | 南方+ | ✅ 可用 |
| people | 人民网 | ✅ 可用 |
| xinhua | 新华网 | ✅ 可用 |
| dahe | 大河网 | ✅ 可用（新增） |
| zynews | 中原网 | ✅ 可用（新增） |
| thepaper | 澎湃新闻 | ✅ 可用（新增） |
| hntv | 大象新闻 | ✅ 可用（新增） |
| zhengzhou_fabu | 郑州发布（政府新闻频道） | ✅ 可用（新增） |

已移除（原项目有但失效）：weibo / zhihu / 36kr / pengpai / douyin / zhejiang

---

## 三、技术架构（沿用原项目结构）

```
full_media_platform/
├─ backend/                  # FastAPI 后端
│  ├─ main.py                # 入口（建表、种子管理员、路由注册）
│  ├─ config.py / config.json / .env   # 配置（8 源 + 平台 + AI）
│  ├─ database.py / models.py / schemas.py
│  ├─ auth_utils.py / deps.py          # JWT + 角色
│  ├─ spider.py               # 13 源爬虫 + 健康探测
│  ├─ ai_service.py           # DeepSeek 改写/创作（流式/同步）+ Markdown→HTML
│  ├─ search_service.py       # 资料搜索（360/Bing 检索 + AI 扩词/精选）
│  ├─ article_fetcher.py      # 新闻正文抓取
│  ├─ publish_service.py      # 发布包生成 + 模拟直发
│  ├─ cache.py                # Redis 缓存（可选）
│  └─ routers/                # auth / news / article / publish / admin
└─ frontend/                  # Vue 3 + Vite
   └─ src/
      ├─ components/          # NavBar / Login / Home / NewsPreview / Create / MaterialSearch
      │                       # RichEditor（富文本+Markdown） / Articles / Publish / AdminSources
      ├─ views/               # （路由直接挂组件）
      ├─ router/ api/ store/ assets/
```

数据存储：MySQL（库名 `full_media`），Redis 可选（`FMP_REDIS_URL`）。

---

## 四、启动方式

### 后端（端口 8012）

```powershell
cd E:\project\ai_project\chat_gpt\news_hub\full_media_platform\backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8012
```

### 前端（端口 5174，已代理 /api → 8012）

```powershell
cd E:\project\ai_project\chat_gpt\news_hub\full_media_platform\frontend
npm run dev
```

访问 `http://localhost:5174`，默认账号：**admin / admin123**。

> 安全提示：初始管理员密码为首次创建时随机生成（登录后强制修改），或通过环境变量 `FMP_ADMIN_PASSWORD` 指定；已不再使用固定默认口令。

### 生产构建

```powershell
cd frontend && npm run build   # 产物在 frontend/dist
```

---

## 五、环境变量（backend/.env）

| 变量 | 说明 |
|------|------|
| FMP_MYSQL_HOST/PORT/USER/PASSWORD/DB | MySQL 连接（默认 full_media 库） |
| FMP_REDIS_URL | Redis 连接（可留空） |
| FMP_JWT_SECRET | JWT 密钥 |
| FMP_AI_API_KEY / BASE_URL / MODEL | AI 服务（DeepSeek） |
| FMP_ADMIN_PASSWORD | 初始管理员密码（缺省则随机生成并强制改密） |
| FMP_DB_PATH | SQLite 兜底时的数据库文件路径 |
| FMP_AUTO_CRAWL | 启动是否自动抓取 |

---

## 六、API 一览

| 模块 | 接口 | 说明 |
|------|------|------|
| 认证 | POST /api/auth/login、GET /api/auth/me | JWT 登录 |
| 新闻 | GET /api/news、/api/news/top、/api/news/{id}、POST /api/news/crawl | 列表/排行/详情/抓取 |
| 文章 | POST /api/articles/rewrite/stream、/create/stream | AI 改写/创作（SSE） |
| 文章 | POST /api/articles/rewrite、/create、/save | 同步生成/编辑器保存 |
| 文章 | GET/PUT/DELETE /api/articles/* | 文章库 |
| 发布 | GET /api/publish/platforms、POST /api/publish/tasks | 平台/任务创建 |
| 发布 | GET /api/publish/tasks、POST /tasks/{id}/publish | 任务列表/模拟直发 |
| 后台 | GET/PUT /api/admin/sources、POST /admin/sources/health | 源管理与健康探测 |

---

**说明**：本 README 与后端接口文档（`http://localhost:8012/docs`）配套使用。
