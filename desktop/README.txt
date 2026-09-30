World Builder 0.1.0 — Windows x64 便携应用

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
