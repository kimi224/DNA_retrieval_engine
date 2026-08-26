# DNA Retrieval Engine 前端调研与原型说明

更新时间：2026-08-26

## 1. 调研目标

本项目是数据结构课程设计中的生物信息学工具，不是营销页面。界面需要帮助使用者回答三个问题：

1. 索引是否已经建立，K-mer 参数是什么。
2. 本次批量检索扫描了多少 Reads，命中了哪些参考基因组位置。
3. 每个命中区域允许了哪些错配，算法在哪里提前剪枝。

因此原型采用白色、低饱和、数据密集型科研工作台：以轨道视图承载参考序列和 Read 对齐，以右侧检查器展示单条命中的可追溯细节。

## 2. GitHub 高 star 项目参考

以下数据通过 GitHub CLI（`gh api` / `gh repo view`）读取，star 数为本次调研时的仓库公开值。

| 项目 | Stars | 许可证 | 可借鉴的界面模式 | 本项目的取舍 |
|---|---:|---|---|---|
| [igvteam/igv.js](https://github.com/igvteam/igv.js) | 733 | MIT | 顶部基因组坐标导航、纵向堆叠轨道、可选中局部特征 | 复用轨道和坐标语言，收窄到参考序列、Reads 和错配标注 |
| [GMOD/jbrowse-components](https://github.com/GMOD/jbrowse-components) | 292 | Apache-2.0 | 现代化的多轨工作区、侧栏检查器、桌面端可部署思路 | 复用“主视图 + Inspector”结构，不引入其 React 依赖 |
| [higlass/higlass](https://github.com/higlass/higlass) | 341 | MIT | 多视图同步、连续缩放和平移、轨道之间共享坐标 | 在原型中保留缩放按钮、窗口坐标和命中带联动 |
| [Edinburgh-Genome-Foundry/DnaFeaturesViewer](https://github.com/Edinburgh-Genome-Foundry/DnaFeaturesViewer) | 700 | MIT | 长序列上的清晰特征带、序列标签和局部放大 | 复用简洁特征带表达，用黄色/红色专门表达容错错配 |

## 3. 视觉与交互决策

- **背景**：纯白 `#FFFFFF`，次级工作区使用接近白色的 `#F8FAFC`，保证科研软件的明亮感和打印可读性。
- **主色**：深蓝灰用于文字和结构，科研蓝用于主操作和命中区域；绿色只表示已完成，琥珀色/红色只表示错配告警。
- **布局**：左侧运行参数，中间参考基因组沙盘，右侧命中详情；避免把所有信息压缩成 KPI 卡片。
- **序列显示**：参考序列和 Read 使用等宽字体并共享坐标。允许的错配字符使用实心色块和 `Mismatch` 文案同时表达，不依赖颜色本身。
- **动效**：运行检索时展示短暂进度动画；点击命中时使用 150-250ms 的高亮过渡；遵循 `prefers-reduced-motion`。
- **pywebview**：HTML 不依赖前端构建工具即可双击运行。运行按钮预留 `window.pywebview.api.run_search`，没有 Python bridge 时使用内置样例数据演示。

## 4. 原型内置展示数据

- 参考基因组：`chr-demo-01`，3,200 bp（展示窗口 400-470）。
- K-mer：`K = 6`，手写拉链法哈希表状态显示为 `1,962 buckets / 3,195 windows`。
- 批量读取：50 条 Reads，示例视图展示 6 条代表性结果，摘要显示 47 条容错命中。
- 容错阈值：`k = 2`，示例命中包含 0、1、2 个错配；错配发生时展示参考碱基、Read 碱基和 Hamming distance。
- 运行结果：命中位置、候选数、比较字符数、剪枝次数和耗时均为可替换的展示数据。

## 5. 实现边界

本文件夹中的 HTML 是界面原型，不替代课程设计中的底层实现。生产实现时，Python 侧应继续手写哈希表、单链表和比对逻辑，再通过 pywebview bridge 将结构化结果传给界面。
