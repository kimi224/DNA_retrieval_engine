# DNA Retrieval Engine

当前版本：v2.0

同济大学数据结构课程设计题目 X：面向 DNA Reads 的 K-mer 局部哈希索引与汉明距离容错检索桌面程序。

核心索引没有使用 Python `dict`、`defaultdict` 或 `set` 代替课程要求的数据结构。参考序列存放在连续 `bytearray` 中；K-mer 索引使用固定桶数组、手写拉链法冲突链和手写位置单链表。

## 目录

- [1. 项目结构](#1-项目结构)
- [2. 环境](#2-环境)
- [3. 命令行调试](#3-命令行调试)
- [4. 桌面端](#4-桌面端)
- [5. 检查与打包](#5-检查与打包)
- [6. 自动化回归测试](#6-自动化回归测试)
- [7. 许可证](#7-许可证)

## 1. 项目结构

```text
DNA_retrieval_engine/
├── app.py                         # PyInstaller 与源码运行入口，仅负责启动桌面应用
├── pyproject.toml                 # Python 包元数据、依赖和 pytest/Ruff 配置
├── requirements.lock              # 可复现的运行与构建依赖版本
├── icon.ico                       # Windows 程序图标
├── README.md                      # 项目使用、构建和维护说明
├── LICENSE                        # MIT 许可证
├── 技术路径调研.md                 # 技术选型、架构决策和稳定性调研
├── docs/                          # 面向开发与交付的详细文档
│   ├── architecture.md            # 数据流、核心结构、算法和复杂度
│   ├── data-format.md              # FASTA/FASTQ/真值文件格式与校验规则
│   ├── release-checklist.md        # 发布前检查表
│   └── stability-investigation.md  # 卡死、内存增长和压力测试报告
├── packaging/
│   └── DNA_Retrieval_Engine.spec   # PyInstaller onedir/onefile 打包配置
├── scripts/                       # 自动检查、构建和稳定性压力测试脚本
│   ├── bootstrap.ps1               # 初始化开发环境
│   ├── check.ps1                   # Ruff、pytest、覆盖率和前端语法检查
│   ├── build.ps1                   # 构建 onedir 与 onefile 程序
│   ├── stress_navigation.py        # 8 步视图路由内存压力测试
│   └── stress_startup.py           # 多轮冷启动与前端握手测试
├── src/dna_retrieval_engine/      # 生产 Python 包
│   ├── config.py                   # 业务常量和版本号
│   ├── models.py                   # Read、Hit、批次结果等数据模型
│   ├── paths.py                    # 源码与 PyInstaller 资源路径
│   ├── cli.py                      # 命令行生成、校验、索引、检索和导出
│   ├── core/                       # 课程要求的手写核心数据结构与算法
│   │   ├── genome_buffer.py         # bytearray 参考基因组
│   │   ├── hash_table.py            # 拉链法哈希表和位置链
│   │   ├── kmer_index.py            # K-mer 滑动窗口索引
│   │   ├── linked_list.py           # 位置单链表节点
│   │   └── matcher.py               # 种子检索、汉明距离和剪枝
│   ├── services/                   # 数据集、检索、报告和生成业务服务
│   │   ├── dataset_generator.py     # 生成 50 条 0-3 错配 Reads
│   │   ├── dataset_service.py       # 数据加载、校验和当前数据集状态
│   │   ├── search_service.py        # 索引、批量检索和结果快照
│   │   └── report_service.py        # JSON/CSV 报告导出
│   ├── storage/                    # FASTA、FASTQ、真值和导出文件读写
│   ├── desktop/                    # pywebview 窗口、API 和后台任务控制器
│   │   ├── main.py                  # WebView2 窗口和本地 HTTP Server 启动
│   │   ├── api.py                   # 私有服务边界和公开 Bridge 方法
│   │   ├── task_controller.py       # 单任务、取消和线程安全状态
│   │   └── single_instance.py       # Windows 单实例保护
│   └── resources/web/              # 离线桌面前端资源
│       ├── index.html               # 运行工作台
│       ├── app.js                   # 工作台数据展示和交互
│       ├── pages.js                 # 索引、Reads、报告视图逻辑
│       ├── bridge-client.js         # Bridge 单飞轮询、超时和生命周期
│       ├── state-store.js           # 前端共享状态
│       ├── ui-state.js              # capability 权限矩阵
│       ├── ui-actions.js            # 帮助、菜单、弹窗和本地操作
│       ├── router.js                # 单文档多视图路由
│       ├── styles.css                # 工作台样式
│       ├── pages.css                 # 次级页面样式
│       ├── pages/                   # 索引状态、Reads、运行报告模板
│       └── vendor/lucide.min.js      # 离线图标库
└── tests/                          # 不依赖 Playwright 的自动化回归测试
    ├── unit/                       # 核心结构、匹配器和文件格式单测
    └── integration/                # 生成检索流程、Bridge、UI 契约测试
```

`prd/` 保留为原始设计基线，生产前端位于 `src/dna_retrieval_engine/resources/web/`。

## 2. 环境

- Windows 10/11 x64
- CPython 3.13.15 x64
- WebView2 Runtime
- 项目已有 `.venv` 时可直接使用；重建环境运行 `scripts\bootstrap.ps1`

## 3. 命令行调试

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

## 4. 桌面端

```powershell
.\.venv\Scripts\python.exe .\app.py
```

工作台支持随机生成、完整数据集文件夹导入和分别选择 FASTA/FASTQ 三种输入方式。索引页、Reads 页和报告页均以 Python 服务中的当前数据集、当前索引和最近运行结果为唯一数据源。

桌面端使用 pywebview 的本地 HTTP Server 加载内置页面，避免 `file://` 对 JS Bridge 的限制。桥接采用 `pywebviewready`、单飞状态轮询、超时和退避；后台任务只更新线程安全状态，不直接从工作线程调用 WebView。帮助、菜单、视图缩放、坐标复制和算法追踪均为本地 UI 操作，不依赖数据集。

生成器固定输出 50 条 Reads，但每条 Read 的错配数随机取 0-3，并保证四类至少各出现一条；因此四类错配的数量会随随机种子变化，不再固定为每类 10 条。检索阈值、详情中的“>x 拒绝”和运行报告分布均使用同一 0-3 配置。

长任务（生成、加载、重建索引、检索、导出）通过后台任务控制器执行。任务运行或桥接未就绪时，依赖数据的按钮会自动锁定；任务完成、失败或取消后由状态轮询恢复界面，避免重复点击造成窗口假死。索引状态页用于查看 K-mer 窗口、桶和链表节点统计，重建索引仅在参考序列变化或需要切换 K-mer 时使用。

右侧命中详情可通过面板按钮收起；被阈值拒绝但实际错配不超过 3 的 Read 会在坐标图和对比沙盘中以红色显示，成功命中保持蓝色。

按钮权限按前置条件区分：参数和生成/导入标签在无数据时仍可配置；索引、Reads 和报告页在无数据时锁定业务按钮；任务运行中只保留取消任务、帮助和本地视图操作。

程序启动时会先显示可用的本地界面，等待 `pywebviewready` 后再启用文件对话框和任务按钮。帮助、用户菜单、项目菜单和视图菜单即使没有数据也可以打开；“索引状态”“Reads 列表”“运行报告”在没有数据时只展示空状态，打印、导出、重建和导入快捷操作保持禁用。

## 5. 检查与打包

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\check.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

构建脚本先生成 `onedir` 便于排错，再生成无控制台的单文件 EXE。最终交付前仍须按 [发布检查表](docs/release-checklist.md) 在未安装 Python 的干净 Windows 机器上验收。

## 6. 自动化回归测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

测试覆盖随机错配分布、0-3 阈值边界、未命中近似对齐、后台任务立即返回/状态同步、非法 API 调用拒绝，以及前端资源中的按钮锁定和侧栏收起接线；不依赖耗时的 Playwright 流程。

前端稳定性压力测试同样不依赖 Playwright：

```powershell
.\.venv\Scripts\python.exe .\scripts\stress_navigation.py --rounds 160
.\.venv\Scripts\python.exe .\scripts\stress_startup.py --runs 12 --timeout 20
```

根因、修复和实测数据见 [前端卡死与内存增长调研报告](docs/stability-investigation.md)。

## 7. 许可证

本项目基于 [MIT License](LICENSE) 开源，可自由使用、复制、修改与再分发。

软件按“原样”提供，不作任何明示或暗示的担保，详见 [LICENSE](LICENSE) 全文。

第三方依赖与前端资源的许可证如下：

| 组件 | 许可证 |
|---|---|
| [pywebview](https://github.com/r0x0r/pywebview) | BSD-3-Clause |
| [pythonnet](https://github.com/pythonnet/pythonnet) | MIT |
| [PyInstaller](https://github.com/pyinstaller/pyinstaller) | GPLv2-or-later（含允许分发非自由程序的特殊例外） |
| [lucide](https://github.com/lucide-icons/lucide) | ISC（见 `src/dna_retrieval_engine/resources/web/vendor/LUCIDE-LICENSE.txt`） |
