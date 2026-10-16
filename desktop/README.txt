World Builder 0.1.2-client048 — Windows x64 便携应用

用途：Agent 主导的游戏场景搭建原型，包含本周768米山谷生成/受限参数调整和旧A—F实验入口。
源码产品主线为 main；旧规则与本地验证对照保留在 codex/local-validation。
便携包是构建时的源码快照，不会随分支更名或源码文档更新自动升级。

双击 WorldBuilder048.exe（自定义构建名时使用对应exe）。请保持整个文件夹完整，_internal 是应用资源与运行环境。
不需要安装 Python；系统需要 Microsoft Edge WebView2 Runtime 和 .NET Framework 4.6.2+。
本机已验收的系统含 WebView2；未提供运行库安装器。

本周山谷“离线样例”按已录制参数重建，不调用API；受限参数调整也为零API全图重建。
“我的 API”需要填写自己的 HTTPS API 地址、模型和密钥。
Windows桌面可勾选记住密钥，按完整API地址用当前用户DPAPI加密保存在本机，重启复用。
密钥不写非密钥配置、运行历史或浏览器存储；可清除。未勾选时只供下次运行，已移除TXT导入。

数据目录：%LOCALAPPDATA%\WorldBuilder
  runs\              运行历史与产物
  preferences.json   非密钥设置
  credentials\       当前Windows用户加密凭据，不随代码分享
  webview\           浏览器运行数据
  desktop.log        应用错误日志

更新时退出应用，替换整个应用文件夹；用户数据目录保持原样。
关闭时若正在生成，会先请求取消并等待已发出的请求结束；窗口标题显示保存进度。
旧32米离线样例使用人工响应；山谷使用046录制参数和045真实模型配方，预览均只读。
已有真实模型限定样本、源/目标测试分开记录；新参数变体没有自动继承目标实走证据。
动态任务调度、通用自然资产、稳定世界局部修改/撤销及新游戏平台属于后续规划。
导出 GLB/schematic 不等于目标软件已加载或角色已能通行；没有自动线上投稿功能。
源码中的 docs/14_client048_saved_credentials.md 提供最新源码启动、密钥、构建与验收说明。
