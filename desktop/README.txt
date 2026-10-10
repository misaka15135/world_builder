World Builder 0.1.0 — Windows x64 便携应用

用途：Agent 主导的游戏场景搭建原型，当前是固定 A—F、建筑场地导向的流程。
源码产品主线为 main；旧规则与本地验证对照保留在 codex/local-validation。
便携包是构建时的源码快照，不会随分支更名或源码文档更新自动升级。

双击 WorldBuilder.exe。请保持整个文件夹完整，_internal 是应用资源与运行环境。
不需要安装 Python；系统需要 Microsoft Edge WebView2 Runtime 和 .NET Framework 4.6.2+。
本机已验收的系统含 WebView2；未提供运行库安装器。

先选择“离线样例”，点击“开始构建”，即可测试完整流程。
“我的 API”需要填写自己的 HTTPS API 地址、模型和密钥。
密钥只用于下次运行，不保存在应用配置中。

数据目录：%LOCALAPPDATA%\WorldBuilder
  runs\              运行历史与产物
  preferences.json   非密钥设置
  webview\           浏览器运行数据
  desktop.log        应用错误日志

更新时退出应用，替换整个应用文件夹；用户数据目录保持原样。
关闭时若正在生成，会先请求取消并等待已发出的请求结束；窗口标题显示保存进度。
离线样例是人工响应，预览只读，真实模型质量和游戏内通行尚未验收。
动态任务调度、自然资产、用户修改/撤销及新游戏平台属于后续规划，未包含在本版。
导出 GLB/schematic 不等于目标软件已加载或角色已能通行；没有自动线上投稿功能。
源码中的 docs/07_desktop_application.md 提供使用、构建与验收说明。
