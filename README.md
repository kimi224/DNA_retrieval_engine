# DNA Retrieval Engine

同济大学数据结构课程设计题目 X：面向 DNA Reads 的 K-mer 局部哈希索引与汉明距离容错检索桌面程序。

核心索引没有使用 Python `dict`、`defaultdict` 或 `set` 代替课程要求的数据结构。参考序列存放在连续 `bytearray` 中；K-mer 索引使用固定桶数组、手写拉链法冲突链和手写位置单链表。

## 环境

- Windows 10/11 x64
- CPython 3.13.15 x64
- WebView2 Runtime
- 项目已有 `.venv` 时可直接使用；重建环境运行 `scripts\bootstrap.ps1`

## 命令行调试

安装项目后可直接运行：

```powershell
.\.venv\Scripts\dna-retrieval.exe --help
```

一键完成“生成 -> 索引 -> 检索 -> 导出”：

```powershell
.\.venv\Scripts\dna-retrieval.exe demo `
  --output D:\课程设计数据 `
  --seed 104729 `
  --reference-length 3200 `
  --k 6 `
  --mismatches 2
```

也可以分别运行：

```powershell
.\.venv\Scripts\dna-retrieval.exe validate --dataset D:\课程设计数据\dna_demo_xxx
.\.venv\Scripts\dna-retrieval.exe index --dataset D:\课程设计数据\dna_demo_xxx --k 6
.\.venv\Scripts\dna-retrieval.exe search --dataset D:\课程设计数据\dna_demo_xxx --k 6 --mismatches 2
```

命令输出为 UTF-8 JSON。PowerShell 旧版控制台若中文显示异常，可先执行 `chcp 65001`。

## 桌面端

```powershell
.\.venv\Scripts\python.exe .\app.py
```

工作台支持随机生成、完整数据集文件夹导入和分别选择 FASTA/FASTQ 三种输入方式。索引页、Reads 页和报告页均以 Python 服务中的当前数据集、当前索引和最近运行结果为唯一数据源。

生成器固定输出 50 条 Reads，但每条 Read 的错配数随机取 0-3，并保证四类至少各出现一条；因此四类错配的数量会随随机种子变化，不再固定为每类 10 条。检索阈值、详情中的“>x 拒绝”和运行报告分布均使用同一 0-3 配置。

长任务（生成、加载、重建索引、检索、导出）通过后台任务控制器执行。任务运行或桥接未就绪时，依赖数据的按钮会自动锁定；任务完成、失败或取消后由状态轮询恢复界面，避免重复点击造成窗口假死。索引状态页用于查看 K-mer 窗口、桶和链表节点统计，重建索引仅在参考序列变化或需要切换 K-mer 时使用。

右侧命中详情可通过面板按钮收起；被阈值拒绝但实际错配不超过 3 的 Read 会在坐标图和对比沙盘中以红色显示，成功命中保持蓝色。

## 检查与打包

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

构建脚本先生成 `onedir` 便于排错，再生成无控制台的单文件 EXE。最终交付前仍须按 [发布检查表](docs/release-checklist.md) 在未安装 Python 的干净 Windows 机器上验收。

详细设计见 [架构说明](docs/architecture.md)、[数据格式](docs/data-format.md) 和 [答辩演示脚本](docs/demo-script.md)。`prd/` 保留为原始设计基线，生产前端位于 `src/dna_retrieval_engine/resources/web/`。

## 自动化回归测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

测试覆盖随机错配分布、0-3 阈值边界、未命中近似对齐、后台任务立即返回/状态同步、非法 API 调用拒绝，以及前端资源中的按钮锁定和侧栏收起接线；不依赖耗时的 Playwright 流程。
