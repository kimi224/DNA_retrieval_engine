# 前端卡死与内存增长调研报告

版本：v2.0

## 结论

截图中接近 1.45 GB 且持续增长的问题不是 DNA 算法在无数据时死循环，而是 pywebview JS API 暴露边界与 WebView2 多页面导航共同导致的生命周期泄漏。

## 已确认根因

1. `DesktopApi` 曾把 `window`、`datasets`、`search`、`tasks` 等内部对象作为公开属性挂在 `js_api` 实例上。pywebview 会递归检查不以下划线开头的属性来生成 JavaScript API，最终遍历到 `window.native` 和 WebView2 原生控件。压力测试直接捕获到 `maximum recursion depth exceeded`、`AccessibilityObject.Bounds.Empty.Empty...` 和“CoreWebView2 can only be accessed from the UI thread”。这是偶发启动卡死和异常内存增长的主要根因。
2. 四个页面原先使用真实文档导航。即使使用 `location.replace`，WebView2 仍会在快速切换时保留一部分旧渲染上下文。旧实现 80 次导航的进程树工作集从约 845.5 MB 增到 1,294.4 MB，接近用户截图现象。
3. Bridge 探测和状态轮询缺少完整的单飞、超时、退避与页面生命周期模型，启动注入边界可能出现重入。
4. `get_state()` 曾反复生成索引统计和结果字典，增加轮询分配压力；缓存索引时还遗漏 `built: true`，造成索引页有数据却显示空状态。
5. 文件夹卡片只对主标题设置省略号，路径文本没有固定宽度和溢出规则。

## 实施方案

- `DesktopApi` 所有内部状态改为 `_window`、`_datasets`、`_search` 等私有属性，只暴露明确的桥接方法。
- 页面使用 pywebview 内置 HTTP Server，不使用 `file://`。
- 后台线程只修改锁保护状态，不直接调用 `evaluate_js`。
- Bridge 使用一个串行轮询 Promise；运行中 250 ms、空闲 1 s、隐藏页面 3 s，支持超时、退避、停止和恢复。
- 四个真实视图一次加载到同一文档，由 `router.js` 切换显示状态，不再产生新的 WebView2 文档、历史项或 Bridge 实例。
- 启动遮罩等待 `pywebviewready`、首次 `get_state()` 和四视图装载全部完成；8 秒后显示恢复入口。
- 索引页改为只读，索引在生成、导入或检索时自动构建。
- 索引和检索结果保存不可变快照，状态轮询不再遍历核心结构。
- 窗口默认最大化，减少启动后窗口操作。

## 验证数据

### 导航内存压力

命令：

```powershell
.\.venv\Scripts\python.exe .\scripts\stress_navigation.py --rounds 160
```

采用 8 步非线性切换序列，覆盖工作台、索引、Reads、报告及反向重复切换。重构后 160 次切换：

- 初始：854.1 MB
- 短时峰值：960.9 MB
- 第 160 次：907.1 MB
- 等待回收后：886.9 MB
- 暖机后净增长：`-39.8 MB`

内存进入平台波动区间并回落，不再随切换次数线性增长。

### 冷启动握手压力

命令：

```powershell
.\.venv\Scripts\python.exe .\scripts\stress_startup.py --runs 12 --timeout 20
```

12/12 成功。首次冷启动约 4.7 秒，其余约 1.77-1.99 秒。每轮均确认 HTTP 协议、四个视图、Bridge 和首次状态同步完成，而不仅是检查进程存活。

## WebView2 内存说明

WebView2 会创建浏览器、渲染器、GPU 等多个子进程。测试机空闲启动的整个进程树通常在 750-900 MB，GPU 进程本身可占约 250 MB；这是平台基线，不等于 Python 算法内存。判断泄漏应看多轮操作后是否持续线性增长、能否回落，而不是只看单个瞬时总量。

Microsoft 将 `--disable-gpu` 等浏览器参数定义为诊断/开发用途，并明确不建议生产应用依赖这些参数。本项目没有用禁用 GPU 掩盖问题，而是消除了实际对象递归和页面上下文累积。

## 参考资料

- [pywebview JavaScript-Python bridge](https://github.com/r0x0r/pywebview/blob/master/docs/guide/interdomain.md)
- [pywebview Application Architecture](https://github.com/r0x0r/pywebview/blob/master/docs/guide/architecture.md)
- [WebView2 Threading Model](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/threading-model)
- [WebView2 browser flags](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/webview-features-flags)
