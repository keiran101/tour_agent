# 技术栈选型决策记录

> 决策时间：2026-05-07
> 项目：Tour Agent - AI旅游行程规划助手

---

## 一、骨架层

### 1. Web框架 → FastAPI

**对比：** FastAPI vs Flask vs Django

| | FastAPI | Flask | Django |
|--|---------|-------|--------|
| 异步支持 | 原生async/await | 需扩展 | 3.1+支持但生态未跟上 |
| API文档 | 自动生成Swagger/OpenAPI | 需flask-restx | 需DRF |
| 类型校验 | Pydantic内置 | 无 | Serializer |
| 流式响应 | SSE/WebSocket原生支持 | 需扩展 | 不优雅 |

**选择理由：** AI Agent后端核心需求是API服务+流式输出+异步工具调用，FastAPI三项全满足。Pydantic校验省大量样板代码，且和LLM结构化输出天然配合。面试AI岗FastAPI是默认期望。

---

### 2. 数据库 → PostgreSQL

**对比：** PostgreSQL vs MySQL vs SQLite

| | PostgreSQL | MySQL | SQLite |
|--|-----------|-------|--------|
| 向量搜索 | pgvector扩展原生支持 | 无 | 无 |
| JSON支持 | JSONB可索引查询 | 功能弱 | 无 |
| 并发能力 | 强，MVCC | 强 | 差 |

**选择理由：** pgvector直接做景点语义搜索，不需额外引入向量数据库，架构更简单。JSONB适合存行程半结构化数据。面试体现工程能力。

---

### 3. ORM → SQLModel

**对比：** SQLModel vs SQLAlchemy vs Tortoise ORM vs Prisma

| | SQLModel | SQLAlchemy | Tortoise ORM |
|--|---------|------------|-------------|
| 和FastAPI配合 | 同一作者，无缝集成 | 需手动转Pydantic | 需适配 |
| 类型提示 | 天然，基于Pydantic | 2.0+支持 | 支持 |
| 复杂查询 | 可回退SQLAlchemy | 最强 | 中 |

**选择理由：** 一个类同时是数据库模型和Pydantic Schema，省掉model↔schema转换的大量样板代码。底层就是SQLAlchemy，复杂查询可随时回退。

---

### 4. 数据库迁移 → Alembic

**对比：** Alembic vs 手动SQL vs Django Migrations

**选择理由：** SQLModel/SQLAlchemy生态下唯一正经选择。行程规划项目表结构会频繁迭代，没有迁移工具维护成本极高。面试体现工程成熟度。

---

### 5. 缓存 → Redis（第二阶段接入）

**对比：** Redis vs Memcached vs 不加缓存

| | Redis | Memcached | 不加 |
|--|-------|-----------|------|
| 数据结构 | 丰富 | 仅Key-Value | - |
| 发布订阅 | 支持 | 不支持 | - |
| 持久化 | 支持 | 不支持 | - |

**选择理由：** LLM响应缓存可省钱提速，会话状态存Redis比内存可靠，速率限制依赖Redis。但MVP阶段流量小，第二阶段再接入。骨架模板已有内存fallback机制。

---

### 6. 认证 → JWT（OAuth2后期可选加）

**对比：** JWT vs Session+Cookie vs OAuth2 vs 不加

**选择理由：** 前后端分离架构下JWT是标准选择。旅游Agent需区分用户（行程/对话/偏好不同），认证必须。OAuth2后期做产品打磨时加。

---

### 7. 监控 → 结构化日志为主，Prometheus配置保留

**对比：** Prometheus+Grafana vs 简单日志 vs Sentry vs 不加

**选择理由：** 面试项目无真实流量，Prometheus仪表板全是平线展示效果差。结构化日志（loguru）记录每次LLM调用的耗时/token/工具链路才是实际排查工具。Prometheus中间件代码保留，面试时讲"预埋了指标采集"。

---

### 8. 链路追踪 → Langfuse

**对比：** Langfuse vs LangSmith vs Phoenix (Arize) vs OpenTelemetry+Jaeger

| | Langfuse | LangSmith | Phoenix | OTel+Jaeger |
|--|---------|-----------|---------|-------------|
| 定位 | LLM应用专用 | LangChain专用 | LLM可观测 | 通用分布式追踪 |
| 框架绑定 | 不绑定 | 强绑LangChain | 不绑定 | 不绑定 |
| 自部署 | Docker一键起 | 不支持 | 支持 | 支持 |
| LLM语义理解 | Prompt/Token/成本/链路树 | 类似 | 类似 | 不懂LLM语义 |

**选择理由：** 专为LLM应用设计，链路树展示Agent完整决策过程（用户提问→工具调用→生成行程），每步的Prompt/Response/耗时/Token一目了然。不绑定LangChain，自研Agent用SDK手动打Trace即可。Docker自部署，面试演示不依赖外网。

---

### 9. 记忆系统 → 纯pgvector自实现

**对比：** mem0+pgvector vs 纯pgvector vs ChromaDB vs Redis

| | mem0+pgvector | 纯pgvector | ChromaDB | Redis |
|--|-------------|-----------|----------|-------|
| 实现方式 | LLM自动提取事实 | 手动Embedding+存储+检索 | 独立服务 | Key-Value |
| 额外依赖 | mem0库 | 无（已有PostgreSQL） | 独立服务 | 已有 |
| 面试价值 | 容易被问"只是调库" | 最高，每步能讲原理 | 中 | 低 |

**选择理由：** 本项目记忆场景明确（用户偏好+历史行程），不需要mem0的自动事实提取。自实现Embedding→pgvector存储→相似度检索链路，面试时每个环节都能讲清原理，不引入额外依赖。

---

### 10. 包管理 → uv

**对比：** uv vs poetry vs pip+requirements.txt vs conda

| | uv | poetry | pip | conda |
|--|---|--------|-----|-------|
| 速度 | 极快（Rust实现） | 中 | 慢 | 慢 |
| 依赖锁定 | 自动 | 自动 | 需手动freeze | 自动 |
| pyproject.toml | 原生 | 原生 | 不支持 | 不支持 |

**选择理由：** 速度碾压级优势，命令和pip高度兼容零学习成本。面试体现跟进Python工具链最新演进。

---

### 11. 部署 → Docker Compose

**对比：** Docker Compose vs 单机直跑 vs Kubernetes vs 云平台托管

**选择理由：** 本项目至少4个服务（FastAPI+PostgreSQL+Redis+Langfuse），手动逐个启动是灾难。面试官git clone后一条`docker compose up`就能看到完整运行的项目，拉开差距。K8s对demo项目是过度设计。

---

## 二、业务层

### 12. LLM提供商 → 默认MiMo，保留DeepSeek/Qwen可切换

**对比：** GPT-4o / Claude Sonnet / Gemini 2.5 / GPT-4.1 / MiMo-V2.5 / DeepSeek-V3 / Qwen-Plus

| 旗舰级 | 价格($/1M token) | Tool Calling | 国内访问 |
|--------|-----------------|-------------|---------|
| GPT-4o | $2.5/$10 | 最成熟 | 需代理 |
| Claude Sonnet 4.5 | $3/$15 | 质量高 | 需代理 |
| Gemini 2.5 Pro | $1.25/$10 | 一致性稍弱 | 需代理 |

| 性价比 | 价格($/1M token) | Tool Calling | 国内访问 |
|--------|-----------------|-------------|---------|
| MiMo-V2.5-Flash | $0.10/$0.30 | 专为Agent设计 | 直连 |
| DeepSeek-V3 | $0.28/$1.10 | 支持 | 直连 |
| Qwen-Plus | $0.11/$0.28 | 支持 | 直连 |

**架构决策：**
- LLM抽象层统一封装OpenAI兼容协议，换模型只改配置
- 默认MiMo-V2.5-Flash：专攻Agent场景、价格最低、国内直连
- 备选DeepSeek-V3、Qwen-Plus：中文质量对比和fallback
- 演示可切GPT-4o：最稳定的tool calling
- 不选Claude/Gemini：需代理、价格高、本项目无独特优势

---

### 13. 景点数据API → 高德地图（国内）+ Google Places（海外）

**对比：** 高德 vs Google Places vs 大众点评 vs TripAdvisor vs OpenStreetMap

| | 高德 | Google Places |
|--|------|--------------|
| 覆盖范围 | 国内最全 | 全球最全 |
| 路线规划 | 步行/驾车/公交全支持 | 全支持 |
| 距离耗时 | 支持 | 支持 |
| 免费额度 | 5000次/天 | $200/月 |

**架构决策：** 接口抽象层封装两个数据源，根据目的地自动切换国内/海外API。大众点评无官方API，爬虫有法律风险，不碰。

---

### 14. UGC内容获取 → Tavily搜索API（间接获取小红书/马蜂窝等）

**对比：** Tavily vs SerpAPI vs Bing Search vs Google Custom Search vs Brave Search

| | Tavily | SerpAPI | Bing Search |
|--|-------|---------|-------------|
| AI适配 | ★★★★★ 返回清洗后文本 | ★★★ 原始JSON | ★★★ 原始JSON |
| 免费额度 | 1000次/月 | 100次/月 | 1000次/月 |
| 国内访问 | 直连 | 需代理 | 直连 |

**架构决策：** 不直接爬取各平台（法律风险），通过Tavily搜索引擎API间接获取UGC内容。搜索时用`site:xiaohongshu.com`等限定平台。Tavily专为AI Agent设计，返回LLM友好的文本摘要，省掉网页解析环节。

---

### 15. 天气API → 和风天气

**对比：** 和风天气 vs 高德天气 vs OpenWeatherMap vs AccuWeather

| | 和风天气 | 高德天气 | OpenWeatherMap |
|--|--------|--------|---------------|
| 预报天数 | 7天（免费） | 仅3天 | 5天（免费） |
| 旅游生活指数 | 穿衣/紫外线/运动/舒适度共16项 | 无 | 无 |
| 海外覆盖 | 全球 | 仅中国 | 全球最广 |
| 免费额度 | 1000次/天 | 5000次/天 | 1000次/天 |

**选择理由：** 高德天气只能预报3天且无生活指数，不满足5-7天行程规划需求。和风天气的旅游舒适度指数是差异化数据，Agent可据此调整行程（"明天下雨，建议室内景点"）。

---

### 16. 前端 → MVP用Chainlit，正式版换Next.js

**对比：** Streamlit vs Gradio vs Chainlit vs Next.js vs Mesop

| | Chainlit | Streamlit | Next.js |
|--|---------|----------|---------|
| 聊天界面 | 原生 | 有组件 | 需自己写 |
| 工具调用Step展示 | 原生可展开步骤卡片 | 需自己拼 | 需自己写 |
| 流式输出 | 原生打字机效果 | 支持 | 需接WebSocket |
| SaaS扩展性 | 有限 | 有限 | 最强 |

**架构决策：** MVP阶段Chainlit几十行出专业聊天界面，工具调用Step自动可视化，面试演示效果好。正式版换Next.js支撑登录页/行程管理/地图展示等SaaS功能。

---

## 三、技术栈全景

```
┌─────────────────────────────────────────────────┐
│                    前端层                         │
│   MVP: Chainlit (Python)                        │
│   正式版: Next.js + React                        │
├─────────────────────────────────────────────────┤
│                    API层                         │
│   FastAPI + JWT认证 + Pydantic校验               │
├─────────────────────────────────────────────────┤
│                   Agent层                        │
│   自研Agent循环（参考LightAgent设计）              │
│   工具：高德/Google Places/和风天气/Tavily         │
│   LLM：MiMo(默认) / DeepSeek / Qwen (可切换)     │
├─────────────────────────────────────────────────┤
│                   服务层                         │
│   LLM抽象层(OpenAI兼容) + 记忆服务(pgvector)     │
├─────────────────────────────────────────────────┤
│                  基础设施层                       │
│   PostgreSQL + pgvector | Redis(二期)            │
│   Alembic迁移 | Langfuse链路追踪                  │
│   结构化日志 | Docker Compose部署                  │
├─────────────────────────────────────────────────┤
│                  工具链                           │
│   uv包管理 | Docker | Prometheus(预埋)           │
└─────────────────────────────────────────────────┘
```
