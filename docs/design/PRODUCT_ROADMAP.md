# AI Growth Mirror — 产品长期规划

> 本文档定义产品的核心定位、当前阶段、中长期路线图。

## 1. 产品定位

**一句话**：帮助 AI coding 用户发现自己的使用短板，并给出可执行的训练方案。

**目标用户**：使用 Cursor / Claude Code / Codex / Copilot 等 AI 编程工具的中高级程序员，希望：
- 知道自己是否"用对了" AI
- 发现提需求的盲区（而非代码本身的问题）
- 获得具体的、可练习的改进路径

**核心价值**：
1. **诊断** — 你的 Prompt 哪里弱？（不是代码弱，是"提需求"弱）
2. **训练** — 给一个两周可执行的练习方案
3. **追踪** — 下次再跑，看看你有没有进步

**不是什么**：
- 不是代码质量检查工具
- 不是 AI 工具的使用教程
- 不是通用的编程能力评估

## 2. 当前状态（v0.3）

### 已完成
- 多工具 session 采集（Cursor / Claude Code / Codex / QCoder / CodeBuddy）
- LLM + Heuristic 双通道 session read 提取
- 五轴能力评分（intent_clarity / execution_driving / implementation_depth / delivery_closure / adaptive_recovery）
- Prompt Quality 五维评分（context_provision / request_specificity / information_timing / scope_management / correction_quality）
- 成长教练：deficit 诊断 + 改写卡片 + friction_synthesis
- 对比报告（快照 compare）
- 趋势分析（30 天轨迹线）
- 缓存机制（session_read 不重复提取）

### 当前问题
1. **信息过载** — 报告 13 个 section，用户读不完
2. **UI 过度设计** — 适合营销页，不适合数据报告
3. **核心价值被稀释** — "你的问题在哪 + 怎么练"被埋在大量辅助信息里
4. **indexed_prompt 用户误判** — 使用 skill 触发词的高级用户被错误标为"缺上下文"

## 3. 短期规划（v0.4 — 当前迭代）

### 目标：精简 + 闭环 + 程序员审美

| 改动 | 状态 | 说明 |
|------|------|------|
| deficit 排序考虑 prompt_style | ✅ done | indexed_prompt 用户的 missing-context 降权 |
| deficit label override | ✅ done | 对索引用户显示"任务变量未前置"而非"缺少必要上下文" |
| 报告 section 重排 | ✅ done | Prompt Coach + Growth Plan 前置到最高位 |
| Hero 区精简 | ✅ done | 去掉 overview-band 三卡片，改为单行摘要 |
| CSS 去花哨 | ✅ done | 恢复精致 UI；去除多余光晕；sidebar sticky + 滚动高亮 |
| 导航与正文对齐 | ✅ done | sidebar 顺序与 DOM 一致；滚动时高亮跟随 |
| 会话范围过滤 scope | ✅ done | `--repo` / `--dir` / `--keyword` + config.yaml |
| 五轴迷你趋势图比例 | ✅ done | axis 系列独立 viewBox 64px，避免拉伸失真 |
| min_quality / advanced_features / has_data | ✅ done | 质量门、高级特性、无数据展示 — |
| evaluation_status 体系 | ✅ done | 4 种评估状态如实披露 |
| friction_synthesis | ✅ done | LLM 优先 + 规则兜底 |
| closure_guidance.mode | ✅ done | 区分 open_ended vs engineered |

### v0.4 验收标准
- [x] 报告首屏能在 5 秒内让用户知道"我哪里弱 + 怎么练"（Prompt Coach / Growth Plan 前置；Hero 单行摘要）
- [x] 侧栏导航与正文区块一一对应，滚动时当前章节高亮同步
- [x] 所有 appendix section 默认折叠
- [x] indexed_prompt 用户不会看到"缺少必要上下文"标签（降权 + 文案 override）
- [x] `--min-quality` 与 scope 过滤可在 CLI / config 配置

## 4. 中期规划（v0.5 ~ v0.7）

### v0.5：交互式报告
- 报告从静态 HTML 改为带 JS 交互的 SPA
- 用户可以点击 deficit 直接跳转到对应的改写卡片
- 雷达图可交互（hover 显示每个轴的详情）
- 暗色模式支持

### v0.6：个性化训练路径
- 基于用户历史 N 次报告，生成个性化的训练序列
- 每周推送一个"本周训练 Prompt"
- 训练完成后自动对比前后数据
- 引入"习惯养成"机制（连续 N 天/N 周）

### v0.7：团队版
- 团队聚合视图（匿名化）
- 团队平均 vs 个人对比
- 团队常见短板 Top 3
- Manager Dashboard（不看个人数据，只看聚合趋势）

## 5. 长期规划（v1.0+）

### v1.0：AI Coding 教练平台
- 开放 API：第三方 AI 工具可接入
- 插件市场：用户可自定义评分维度
- 社区基准：匿名对标（"你的 context_provision 处于前 30%"）

### v1.5：实时反馈
- IDE 插件：在用户发送 Prompt 前给出实时建议
- "发送前自检"自动弹出
- 基于历史数据预测本次 session 的潜在摩擦

## 6. 设计原则（长期不变）

1. **诊断先于评分** — 用户不关心 65 分还是 70 分，关心"我哪里不好"
2. **可执行先于全面** — 每次只给 2 个训练重点，不要信息轰炸
3. **如实披露** — 代理结果标注来源，不伪装为 LLM 深度分析
4. **程序员审美** — 信息密度 > 视觉冲击，代码块 > 花哨卡片
5. **数据自主** — 所有数据本地处理，不上传到服务端
6. **增量进化** — 每个版本专注解决 1-2 个核心问题

## 7. 技术债清理计划

| 项目 | 优先级 | 说明 |
|------|--------|------|
| i18n key 去重 | P1 | template_labels / guidance_labels / view_model 有重叠 |
| 模板拆分 | P1 | 1700行单文件 → partials 组件化 |
| 测试覆盖 | P2 | prompt_coach 逻辑缺少端到端测试 |
| session_read schema 迁移 | P2 | v1.0 → v1.1 的向后兼容性 |
| 报告渲染引擎 | P3 | Jinja2 → React/Vue SSR（为 v0.5 交互化铺路） |

## 修订记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-06-03 | v0.4 | 导航/DOM 对齐、滚动 spy、scope 配置化、五轴图比例、质量门与高级特性 |
| 2026-06-02 | v0.1 | 初版产品规划 |
