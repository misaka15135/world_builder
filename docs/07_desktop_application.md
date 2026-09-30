# Windows 桌面应用 0.1.0

## 启动与使用

本机构建输出为 `dist/WorldBuilder/WorldBuilder.exe`。双击打开独立窗口；分享时使用 `dist/WorldBuilder-0.1.0-win-x64.zip`，先完整解压再启动。必须保留 `_internal` 文件夹，里面包含 Python、网页、JSON 契约、六份 agent skill 和运行资源。

1. 选择「离线样例」并点击「开始构建」，验证 A—F、几何预览和导出流程。
2. 在「连接与运行设置」填写自己的 HTTPS API 地址、模型，选择「我的 API」后输入密钥运行。密钥只在当前进程中用于单次任务，不写入设置文件。
3. 在运行档案中打开历史；交付区可通过原生另存为对话框下载 `.worldpkg`、GLB、schematic 或诊断文件。

初版预览支持旋转、缩放、剖切和构件查看，尚无世界编辑功能。离线样例由人工响应驱动；真实 API 生成质量、目标游戏加载和通行由 024 工单验收。

## 系统与数据

Windows x64；无需另装 Python。系统需有 Microsoft Edge WebView2 Runtime 和 .NET Framework 4.6.2 或更新版本。本轮在 Windows 11、WebView2 154.0.4258.37 上验收；未在干净系统中验证运行库安装。

数据独立于程序目录，默认位于 `%LOCALAPPDATA%/WorldBuilder`：

| 路径 | 内容 |
|---|---|
| `runs/` | 历史、阶段响应、WIR 与导出产物 |
| `preferences.json` | API 地址、模型、预算等非密钥设置 |
| `webview/` | WebView2 浏览器运行数据 |
| `desktop.log` | 启动及宿主错误 |
| `session.json` | 最近启动的 PID、端口与版本；进程退出后该文件不代表仍在运行 |

关闭窗口会关闭本地 HTTP 服务；若有生成任务，则先请求取消并等待当前请求返回，标题显示停止进度。相同数据目录只允许一个应用实例。更新时先退出，再替换完整应用目录，用户数据保留。本版为未签名便携包，尚无安装器、自动更新和跨版本数据迁移流程。

## 模块边界

`desktop/app.py` 管窗口、用户目录和服务生命周期；`workbench/server.py` 管 HTTP API；`workbench/jobs.py` 管运行队列、历史和设置；`agents/` 管 A—F 调用；`web/features/` 管前端功能。源码与打包环境的资源路径统一由 `resources.py` 解析。

桌面宿主绑定随机 loopback 端口，沿用测试台 Host/Origin/token 校验。设置通过 `/api/v1/preferences` 写入用户目录，所以重开换端口后仍可读取。网页版继续使用浏览器本地设置。两种入口共用前端和后端功能模块，后续更新可独立修改这些模块。

## 开发与构建

在项目根目录使用 Windows x64 Python。本次构建使用 Python 3.13.9，全部依赖版本记录于 `desktop/requirements-build.txt`。

```powershell
python -m venv .venv-desktop
.\.venv-desktop\Scripts\python.exe -m pip install -r desktop/requirements-build.txt
.\.venv-desktop\Scripts\python.exe tools/run_desktop.py
.\.venv-desktop\Scripts\python.exe tools/build_desktop.py
```

构建脚本拒绝覆盖现有 `dist/WorldBuilder`；应先退出旧版并将其移至备份目录。构建输出目录包、ZIP 及 SHA-256 摘要 `dist/build-info.json`。锁定版本用于复建同一依赖组合，不保证 ZIP 字节级可复现。

打包程序自检（使用新的测试数据目录）：

```powershell
.\dist\WorldBuilder\WorldBuilder.exe --self-test --data-dir artifacts/agent-runs/my-desktop-check
```

它执行包内人工样例与回放，写 `self-test.json`。源码测试命令与实际结果见 [026 工单](../work_order/026_windows_desktop_application.md)；验证摘要见 [validation.json](../artifacts/desktop-026/validation.json)。

## 实现依据

访问日期均为 2026-09-30。

- [pywebview 打包说明](https://pywebview.flowrl.com/guide/freezing)：PyInstaller 冻结路径与 GUI 后端裁剪，适用于本版打包方案。
- [pywebview Windows 引擎](https://pywebview.flowrl.com/guide/web_engine.html)：EdgeChromium、WebView2 和 .NET 前置条件。明确指定该引擎，未采用旧 IE 回退。
- [pywebview API](https://pywebview.flowrl.com/api/)：窗口关闭事件、持久化浏览器目录与下载开关；应用数据持久化和本地服务关闭策略由项目实现。
