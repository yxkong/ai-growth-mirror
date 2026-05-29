# AI Growth Mirror Logo 草案

设计关键词：镜面反思、五轴能力雷达、成长轨迹、AI 节点、本地优先的可信分析。

文件：
- ai-growth-mirror-logo-primary.svg：主图标，适合 App 图标、GitHub README、报告页顶部。
- ai-growth-mirror-logo-horizontal.svg：横向字标，适合官网/文档页头。
- ai-growth-mirror-logo-mono.svg：单色版，适合 favicon、深色底、印刷或低成本场景。
- PNG 文件：由 SVG 导出的预览图，如环境支持已一并生成。

建议品牌色：
- Reflection Purple: #7C3AED
- Growth Green: #10B981
- Insight Blue: #3B82F6
- Ink: #0F172A
- Canvas: #FAF8FF / #EEF2FF

模板接入（SVG 直引，报告 HTML 可离线打开）：
- 渲染：`application/html_render.py` / `infra/snapshots.py` 为 Jinja 增加 `assets/` 搜索路径
- 主报告 `report.html.j2`：桌面端把 `primary` 放到侧栏品牌区；移动端在 Hero 顶部保留紧凑品牌条
- 分享卡 / 快照对比：页头使用 `horizontal`
