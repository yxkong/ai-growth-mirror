## 背景

<!-- 为什么要改？用户/产品/技术现象是什么？链接相关 Issue / 设计文档（如有）。 -->

## 问题定义

<!-- 用可验证的语言描述「错在哪 / 缺什么」，避免只写实现动作。 -->

## 方案

<!-- 说明真源、边界与取舍；若有多方案，写为什么选当前方案。 -->

## 改动范围

<!-- 白名单：列出会改动的模块/文件类型；便于 reviewer 快速对齐 scope。 -->

- [ ] `application/` 报告组装
- [ ] `domain/` 领域逻辑
- [ ] `infra/readers/` 数据源
- [ ] `assets/i18n/` 可见文案
- [ ] `assets/templates/` 报告模板
- [ ] `tests/unit/` 单元测试
- [ ] `docs/` 设计/规范文档

**本 PR 实际涉及：**

（在此填写具体路径或模块，例如 `report_view.py`、`view_model_zh.yaml`）

## 非目标

<!-- 明确这次不做什么，防止 scope creep。 -->

- 

## 验证

<!-- 必须贴可复现命令与结果；报告类改动补充产物检查点。 -->

```bash
# 示例
pytest tests/unit/test_xxx.py -q
```

**结果：**

- [ ] 单元测试通过
- [ ] 报告/summary/sidecar 扫描通过（如适用）
- [ ] 无个人路径、密钥、生成物进入 diff

## 风险与回滚

<!-- 兼容性、数据/schema、i18n、用户可见行为变化；如何快速回滚。 -->

| 项 | 说明 |
|---|---|
| 用户可见变化 | |
| 兼容性 | |
| 回滚方式 | `git revert <commit>` 或关闭功能开关 |

## 提交信息

<!-- 本 PR 的 commit 是否遵循 `type(scope): 动机`；若多 commit，简述各自职责。 -->

## Checklist

- [ ] 遵循 [`ARCHITECTURE_PRINCIPLES.md`](../docs/design/ARCHITECTURE_PRINCIPLES.md) 分层与主编排真源
- [ ] 用户可见文案在 `assets/i18n/`，domain 层无硬编码文案
- [ ] 无 `config.yaml`、个人 HTML/JSON、本机绝对路径
- [ ] 缺数据时不使用误导性 fallback（报告类改动）
- [ ] 改动范围与「非目标」一致
