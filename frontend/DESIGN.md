# Tour Agent 前端设计方案

## Context

前端还是空项目（仅有 CLAUDE.md）。这是一个面试展示项目，需要在视觉和交互上体现 AI Agent 的深度。后端 API 已完成，前端需要从零搭建。

---

## 1. 技术栈（最终确认）

| 项目 | 选型 | 理由 |
|------|------|------|
| 框架 | Next.js 14+ App Router + TypeScript | 面试主流，路由清晰 |
| 样式 | Tailwind CSS + shadcn/ui（自定义暖色主题） | 开发效率高，可定制 |
| 状态 | zustand | 轻量好讲 |
| 动画 | Framer Motion | 聊天气泡、阶段切换、卡片交互 |
| 拖拽 | @dnd-kit/core + @dnd-kit/sortable | group_days 阶段 |
| 地图 | Leaflet + React Leaflet | 免费，POI 标点+路线 |
| 图标 | Lucide React | shadcn 默认图标库 |
| 包管理 | pnpm | 快 |

---

## 2. 设计风格：Warm Minimal

**核心调性**：温暖、有呼吸感、有出行向往感。不是冷灰色 SaaS 工具。

- 背景用暖白（cream），不是纯白
- 阴影带暖色调，不是纯黑阴影
- Glassmorphism 仅用于浮动面板（输入栏、阶段指示器、modal 遮罩）
- 圆角偏大（卡片 12px，按钮 8px，pill 按钮 9999px）

---

## 3. 配色系统

### 核心色

| Token | 浅色模式 | 深色模式 | 用途 |
|-------|---------|---------|------|
| background | `#FAF8F5` 暖白 | `#1C1917` 暖黑 | 页面底色 |
| surface | `#FFFFFF` | `#252220` | 卡片、面板 |
| surface-raised | `#FBF9F7` | `#2D2A27` | 侧栏 |
| surface-sunken | `#F3F0EC` | `#161412` | 输入框背景 |
| border | `#E8E4DF` | `#3A3633` | 边框 |
| border-subtle | `#EEECEA` | `#302D2A` | 分割线 |

### 主色 & 辅助色

| Token | 浅色 | 深色 | 用途 |
|-------|------|------|------|
| primary | `#E8722A` 暖橙 | `#F0883E` | CTA、active |
| primary-hover | `#D4651F` | `#F59B58` | 悬停 |
| primary-subtle | `#FDF0E7` | `#2E2118` | 浅背景 |
| accent | `#3B9ECF` 天蓝 | `#5BB5DE` | 地图、链接 |

### 文本层次

| Token | 浅色 | 深色 | 用途 |
|-------|------|------|------|
| text-primary | `#1C1917` | `#F5F2EF` | 正文 |
| text-secondary | `#57534E` | `#A8A29E` | 次要文本 |
| text-muted | `#A8A29E` | `#78716C` | 占位符 |

### POI 类别色（用于卡片色标和地图标记）

| 类别 | 颜色 | 浅背景 |
|------|------|-------|
| attraction 景点 | `#D97706` amber | `#FFFBEB` |
| restaurant 餐厅 | `#DC2626` red | `#FEF2F2` |
| hotel 住宿 | `#7C3AED` violet | `#F5F3FF` |
| shopping 购物 | `#E85D8A` pink | `#FDF2F8` |
| activity 活动 | `#059669` emerald | `#ECFDF5` |

### Day 主题色（时间线、分天标签）

| Day 1 | Day 2 | Day 3 | Day 4 | Day 5 |
|-------|-------|-------|-------|-------|
| `#E8722A` 橙 | `#3B9ECF` 蓝 | `#059669` 绿 | `#7C3AED` 紫 | `#D97706` 琥珀 |

### 语义色

| success | warning | error | info |
|---------|---------|-------|------|
| `#16A34A` | `#CA8A04` | `#DC2626` | `#3B9ECF` |

---

## 4. 字体

```css
--font-sans: "Inter", "Noto Sans SC", system-ui, sans-serif;
```

| 级别 | 大小 | 行高 | 字重 | 用途 |
|------|------|------|------|------|
| xs | 12px | 16px | 400 | 标签、badge |
| sm | 14px | 20px | 400 | 次要文本 |
| base | 16px | 24px | 400 | 正文、消息 |
| lg | 18px | 28px | 500 | 小标题 |
| xl | 20px | 28px | 600 | 区域标题 |
| 2xl | 24px | 32px | 600 | 页面标题 |

---

## 5. 布局

```
Desktop (≥1024px):
┌──────────┬──────────────────────────────────────────┐
│ Sidebar  │              Chat Area                   │
│  280px   │        (max-width: 768px, 居中)           │
│          │                                          │
│          │  [当 Builder 有地图时，右侧出现 Map 面板]    │
│          │  Chat ~60%  |  Map ~40%                   │
└──────────┴──────────────────────────────────────────┘

Tablet (768-1023px):
┌────┬─────────────────────────────────────────────────┐
│ 60 │                 Chat Area                        │
│ px │        (sidebar 收起为 icon 栏)                   │
└────┴─────────────────────────────────────────────────┘

Mobile (<768px):
┌──────────────────────────────────────────────────────┐
│ [☰]  标题                                            │
│                 Chat Area (全屏)                      │
│    Sidebar 作为 overlay 抽屉                          │
│    Map 作为底部面板 (300px 高)                         │
└──────────────────────────────────────────────────────┘
```

---

## 6. 核心页面与组件

### 6.1 登录/注册
- 居中卡片（max-width 400px），暖色渐变背景
- 输入框 48px 高，圆角 8px
- 主按钮 48px 高，`--primary` 色

### 6.2 侧栏
- 顶部: Logo + 品牌名"如途"
- 新建对话按钮（虚线边框，hover 变橙）
- 会话列表（44px 行高，当前项左侧 3px 橙色竖条）
- 分割线
- 行程列表（带状态小圆点：draft=黄，confirmed=绿）
- 底部: 设置 + 暗色模式切换

### 6.3 聊天区域
- **Assistant 气泡**: 左对齐，白底，圆角 `12px 12px 12px 4px`，带浅阴影
- **User 气泡**: 右对齐，橙色底，白字，圆角 `12px 12px 4px 12px`
- **打字指示器**: 三个圆点脉冲动画
- **输入栏**: 底部 sticky，毛玻璃背景，44px 圆形发送按钮

### 6.4 阶段指示器（Phase Indicator）
```
● 收集需求 ─ ○ 选景点 ─ ○ 分天 ─ ○ 安排 ─ ○ 确认
```
- 浮动在聊天区顶部，毛玻璃 pill 形状
- 当前步骤：橙色圆点 + 脉冲动画
- 手机端只显示圆点，不显示文字

### 6.5 Gathering — 问题卡片
- 嵌入聊天流中（作为 assistant 消息的附属组件）
- 选项渲染为 pill 按钮（圆角 9999px），点击变橙色
- 多选时显示"(可多选)"提示
- 底部"确认选择"按钮，点击后将选项拼接为自然语言消息发送

### 6.6 Select POIs — POI 卡片
- 卡片 280px 宽，网格布局（3/2/1 列自适应）
- 左上角：类别色 icon（48x48）
- 右上角：勾选框（勾选后卡片边框变橙）
- 卡片内容：名称、简介（2行截断）、推荐理由（浅蓝底 info 框）、元数据行（评分/价格/时长）
- "推荐"和"备选"分组，备选默认折叠
- **右侧地图面板**：POI 标记按类别着色，hover 卡片 ↔ 地图标记联动高亮

### 6.7 Group Days — 分天拖拽
- 横向排列的 Day 列（flex，每列 min-width 260px）
- 每列顶部：Day 主题色 header（"第1天: 西湖经典游"）
- POI 标签可跨列拖拽（@dnd-kit）
- 底部虚线放置区（"拖拽景点到这里"）
- 手机端改为纵向手风琴

### 6.8 Arrange — 时间线
- 左侧时间标签（mono 字体），竖线连接
- 右侧活动卡片（类别色 icon + 名称 + 描述 + 元数据）
- 活动之间的交通连接（图标 + "步行15分钟"）
- 顶部 Day tabs 切换
- **右侧地图**：显示当天路线

### 6.9 Confirm — 确认面板
- 行程摘要卡片（目的地/天数/预算）
- 每日概览（单行：Day主题色标签 + 景点链 A → B → C）
- 小贴士列表
- "返回修改" + "确认保存" 双按钮（确认用 success 绿色）

### 6.10 Trip 详情页
- 复用 Arrange 时间线 + 地图（只读模式）
- 顶部 header：标题/目的地/状态 badge
- 操作栏：编辑/删除

---

## 7. 动画规格（Framer Motion）

| 场景 | 属性 | 时长 | 缓动 |
|------|------|------|------|
| 消息入场 | opacity 0→1, y 12→0 | 300ms | easeOut |
| 选项 chip 入场 | 交错 50ms，scale 0.8→1 | 250ms | easeOut |
| POI 卡片入场 | 交错 60ms，y 20→0 | 400ms | easeOut |
| POI hover | translateY -2px, shadow 增强 | 200ms | CSS ease |
| 选中勾选 | scale 0→1 | spring(500, 25) | spring |
| 阶段切换退出 | opacity→0, x→-30 | 250ms | easeIn |
| 阶段切换进入 | opacity 0→1, x 30→0 | 350ms | easeOut |
| 拖拽拿起 | scale 1.02, shadow-lg | 150ms | ease |
| 时间线入场 | 交错 120ms，x -20→0 | 400ms | easeOut |
| 按钮点击 | scale 0.97 | 100ms | ease |
| Toast 入场 | y 16→0, opacity | 200ms | easeOut |

所有动画尊重 `prefers-reduced-motion`，匹配时 duration 设为 0。

---

## 8. 交互模式

### 用户操作 → 聊天消息的转化
- Gathering 选项点击 → "我选择了：自然风光、美食体验"
- POI 勾选确认 → "我选这几个：西湖、灵隐寺、楼外楼"
- 拖拽分组确认 → "确认这个分组方案" 或描述调整 "把灵隐寺挪到第二天"
- Confirm 确认 → "就这样，保存行程"

### SSE 流式显示
- answer 事件：逐字追加显示（typewriter）
- gathering/builder 事件：立即完整渲染结构化组件
- [DONE]：结束 loading 状态

### 错误处理
- 网络错误：Toast 提示 + 重试按钮
- 401：清除 token，跳转登录
- 429：Toast 显示限流提示

---

## 9. 地图集成

| 阶段 | 地图行为 |
|------|---------|
| Gathering | 不显示 |
| Select POIs | 显示，POI 标记按类别着色，hover 联动 |
| Group Days | 可选显示，按天切换标记颜色 |
| Arrange | 显示，当天路线连线 |
| Confirm | 不显示（摘要卡片足够） |
| Trip 详情 | 显示，按天切换路线 |

---

## 10. 实施顺序

1. **脚手架** — Next.js 初始化 + Tailwind + shadcn/ui + 自定义主题色
2. **Auth** — 登录/注册页 + token 管理 store
3. **Shell** — 侧栏 + 布局 + 路由
4. **Chat 基础** — 消息气泡 + 输入栏 + zustand store + API 对接
5. **SSE** — 流式对接
6. **Gathering** — 问题卡片 + 选项交互
7. **Select POIs** — POI 卡片 + 地图联动
8. **Group Days** — 拖拽分组
9. **Arrange** — 时间线 + 地图路线
10. **Confirm** — 确认面板
11. **Trip** — 行程列表 + 详情页
12. **打磨** — 动画、暗色模式、响应式、loading 骨架屏

---

## 验证方式

- `pnpm dev` 启动后手动测试各页面
- 对接后端 `http://localhost:8000/api/v1` 走完整流程
- Chrome DevTools 检查响应式（375px / 768px / 1024px / 1440px）
- Lighthouse 跑分确认无障碍和性能
