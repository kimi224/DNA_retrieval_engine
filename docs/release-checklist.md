# 发布检查表

- [ ] 使用 CPython 3.13.15 x64 干净环境安装 `requirements.lock`。
- [ ] `scripts/check.ps1` 中 Ruff、20+ 测试和覆盖率门槛全部通过。
- [ ] CLI `demo` 完成生成、索引、检索、JSON/CSV 导出。
- [ ] `onedir` 版本完成生成、三种输入、索引重建、检索和导出。
- [ ] `onefile` 版本启动无控制台黑窗，根目录 `icon.ico` 显示正确。
- [ ] 断网后 Lucide 图标、四个页面和全部业务可用。
- [ ] 中文路径、空格路径、取消对话框、只读目录均有可见反馈。
- [ ] 四个页面的 Read、坐标、K、阈值和汇总计数一致。
- [ ] 生成数据的错配范围为 0-3，四类数量随种子变化且报告按 50 条 Reads 计算比例。
- [ ] 任务运行、桥接未就绪或缺少前置数据时，索引/检索/导出等按钮均不可点击，任务结束后自动恢复。
- [ ] 被阈值拒绝但错配不超过 3 的 Read 在坐标图和对比沙盘中显示红色近似对齐。
- [ ] 重复启动时只保留一个实例并显示提示。
- [ ] 在未安装 Python 的 Windows 10/11 x64 干净机器双击验收。
- [ ] 记录测试机 WebView2 版本和最终 EXE SHA-256。

Windows 10 目标机若缺少 Evergreen WebView2 Runtime，需要先安装官方 Runtime。项目不内置 250 MB 以上的 Fixed Version Runtime。
