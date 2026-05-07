# 项目骨架选型决策记录

> 决策时间：2026-05-07
> 项目：Tour Agent - AI旅游行程规划助手
> 目标：面试导向，展示Agent深度 + SaaS产品形态

---

## 一、需求分析

### 项目目标
- 做一个对话式AI旅游行程规划Agent
- 用户输入目的地/天数/预算/偏好，Agent输出结构化每日行程
- 最终形态为可展示的SaaS产品

### 对骨架的要求
- 架构设计优秀，值得学习
- 能在上面做减法（去掉不需要的）+ 做加法（加入旅游Agent核心逻辑）
- 面试时每个模块都能讲清楚

---

## 二、候选方案调研

### 调研范围
从GitHub搜索了三类项目：轻量Agent框架、Agent后端模板、全栈AI SaaS模板。
最终筛选出三个候选：

### 候选A：LightAgent
- 地址：https://github.com/wanxingai/LightAgent
- 定位：超轻量Agent引擎（核心~1000行）
- 优势：Agent循环设计精炼，支持多LLM/多Agent/记忆/工具调用，零依赖
- 劣势：只有Agent核心，无Web层/数据库/认证等基础设施

### 候选B：FastAPI + LangGraph Agent Template
- 地址：https://github.com/wassim249/fastapi-langgraph-agent-production-ready-template
- 定位：生产级Agent后端模板（2.2k stars）
- 优势：分层架构标准（API→Service→Agent→Tools），自带PostgreSQL/JWT/Redis/Prometheus/mem0
- 劣势：无前端，Agent部分绑定LangGraph

### 候选C：Full-Stack AI Agent Template
- 地址：https://github.com/vstorm-co/full-stack-ai-agent-template
- 定位：全栈AI SaaS模板（1.2k stars）
- 优势：前后端齐全（FastAPI + Next.js），支持6种AI框架，SaaS功能完整
- 劣势：模块过多（6框架+4向量库+3任务队列+多集成），做减法成本高，面试难全掌握

---

## 三、对比评估

| 评估维度 | LightAgent | FastAPI+LangGraph | Full-Stack Template |
|---------|-----------|-------------------|-------------------|
| Agent深度 | ★★★★★ | ★★★★ | ★★★ |
| 工程架构 | ★★ | ★★★★★ | ★★★★★ |
| 产品完整度 | ★ | ★★★ | ★★★★★ |
| 代码掌控度 | ★★★★★ | ★★★★ | ★★ |
| 做减法难度 | 无需 | 轻松 | 重 |

---

## 四、最终决策

**不是三选一，而是各取所长：**

### 代码骨架：FastAPI + LangGraph Agent Template
选它作为实际开发的起点。理由：
1. 分层架构（API→Service→Agent→Tools）是业界标准，面试可讲设计思路
2. 基础设施现成：PostgreSQL + Alembic迁移、JWT认证、Redis缓存、Prometheus监控
3. 代码量适中，能全部读完理解
4. 做减法简单：去掉LangGraph，替换为自研Agent核心

### Agent设计：参考LightAgent
去掉LangGraph后，参考LightAgent的设计自建Agent循环。理由：
1. 面试时"自研Agent核心"比"套框架"高一个档次
2. LightAgent的工具调用、记忆系统、多Agent协作设计值得借鉴
3. 核心仅~1000行，可以完全理解后选择性吸收

### 产品形态：参考Full-Stack AI Agent Template
前端和SaaS功能参考它的设计。理由：
1. 它的Next.js前端 + WebSocket流式响应是成熟的SaaS交互模式
2. 认证、对话管理、暗黑模式等产品细节可参考
3. 不直接用它的代码，避免引入过重的依赖

### 改造路径
```
克隆 FastAPI+LangGraph Template
  → 理解其分层架构
  → 去掉LangGraph，在core/下自建Agent循环（参考LightAgent）
  → 实现旅游行程规划的工具链（景点搜索/路线优化/天气等）
  → 保留基础设施（FastAPI/PostgreSQL/JWT/监控）
  → 加前端（先Streamlit MVP，后期可换Next.js）
```

---

## 五、参考资源

- LightAgent: https://github.com/wanxingai/LightAgent
- FastAPI+LangGraph Template: https://github.com/wassim249/fastapi-langgraph-agent-production-ready-template
- Full-Stack AI Agent Template: https://github.com/vstorm-co/full-stack-ai-agent-template
- FastAPI官方全栈模板: https://github.com/fastapi/full-stack-fastapi-template
- FastAPI最佳实践: https://github.com/zhanymkanov/fastapi-best-practices
