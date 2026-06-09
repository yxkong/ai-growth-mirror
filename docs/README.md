---
title: AI Growth Mirror Docs Index
domain: growth_mirror
status: canonical
updated_at: 2026-06-09
---

# AI Growth Mirror 文档入口

English docs index: [docs/en/README.md](./en/README.md)

> 本目录作为 AI 成长镜（AI Growth Mirror）的设计、规范与配置文档库。通过结构化事实与六轴 Agentic 成熟度模型，帮助用户量化和提升与 AI 的协作水平。

## 核心真源索引

- **[ARCHITECTURE_PRINCIPLES.md](./design/ARCHITECTURE_PRINCIPLES.md)**（英文：[ARCHITECTURE_PRINCIPLES.md](./en/design/ARCHITECTURE_PRINCIPLES.md)）：唯一架构真源，规范分层设计、资源归属、稳定性硬规范。
- **[design/README.md](./design/README.md)**（英文：[design/README.md](./en/design/README.md)）：设计文档目录索引，提供快速阅读导览。
- **[OPEN_SOURCE_GOVERNANCE.md](./config/OPEN_SOURCE_GOVERNANCE.md)**（英文：[OPEN_SOURCE_GOVERNANCE.md](./en/config/OPEN_SOURCE_GOVERNANCE.md)）：仓库治理说明，规范脱敏规范、许可协议及开源边界。
- **[CONTRIBUTING.zh.md](../CONTRIBUTING.zh.md)**（英文：[CONTRIBUTING.md](../CONTRIBUTING.md)）：贡献指南，涵盖开发环境搭建、分支策略与提交规范。

## 阅读规则

1. **架构先行**：在修改任何核心代码前，须先对齐 **[ARCHITECTURE_PRINCIPLES.md](./design/ARCHITECTURE_PRINCIPLES.md)**，特别是 `Section 14` 的四大研发架构硬规范。
2. **真源原则**：活动区 canonical 文档以 `docs/design/` 和 `docs/config/` 为准；`docs/**/bak/` 为历史归档备份，不作为当前执行依据。
3. **保持同步**：所有功能迭代在实现时，均需确保文档中的计算公式与接口契约同步更新，严禁出现文档与实现脱节。
4. **中英双真源**：面向用户的设计文档分 `docs/design/`（中文）与 `docs/en/design/`（英文）两棵树；**发布或升版时必须同一次变更集内同步更新中英文**，禁止只改一侧。
