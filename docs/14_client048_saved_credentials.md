# 048 保存API密钥与移除TXT导入

日期：2026-10-16；工单：[048](../work_order/048_client_saved_api_credentials.md)；桌面 `0.1.2-client048`，包名 `WorldBuilder048`。继续使用[启动入口](../start_client047.cmd)，优先新版；旧包不自动更新。

## 从GitHub源码启动

049只推源码与[精选证据](../examples/client048_delivery/README.md)，不上传dist/EXE/运行历史/完整场景。已有本地便携包可继续双击；新克隆必须先准备Python环境，不会自动下载安装包。

网页预览（无需Unity、Minecraft、Node或API密钥）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe tools/run_workbench.py --open
```

选择本周山谷的“离线样例”可重建已发布参考参数。网页不支持DPAPI密钥持久化；需要记住密钥时使用Windows桌面源码或自行构建，建议与原验收相同的Windows x64 Python3.12：

```powershell
py -3.12 -m venv .venv-desktop
.\.venv-desktop\Scripts\python.exe -m pip install -r desktop/requirements-build.txt
.\.venv-desktop\Scripts\python.exe tools/run_desktop.py
# 可选：构建便携包，目标目录不存在时运行
.\.venv-desktop\Scripts\python.exe tools/build_desktop.py --name WorldBuilder048
```

系统需WebView2与.NET，见[桌面依赖说明](07_desktop_application.md)。不自动导入Unity；045/046历史脚本引用的作者本地原始运行不随Git上传。047/048旧截图和摘要在精选目录可查，不把本机路径当公共下载链接。

## 使用

在“连接设置”粘贴密钥，勾选“记住API密钥（Windows当前用户加密，重启可用）”，点击保存设置。之后重开同一数据目录的新版程序，密钥框留空即可使用已保存的密钥；不读回星号占位或真实密钥，状态文字显示是否已保存。

完整API地址改变后不会沿用另一地址的密钥；输入新密钥并保存可替换。取消勾选再保存，会清除该地址已保存的密钥，新输入仅用于下一次运行；“清除当前API地址已保存的密钥”按钮需确认，不影响场景历史或外部环境变量。清除/取消记住不等于撤销已发送请求。

TXT首行导入的控件和文件读取逻辑已经移除，不删除用户原 `api.txt`。旧版只保存非密钥设置，所以升级后仍需手动粘贴并保存一次；本轮不会擅自从TXT迁移真实密钥。网页入口/非Windows平台不能安全保存时明确提示仅临时使用，不回退明文存储。

## 存储与接口

加密数据保存在应用数据目录的 `credentials/<endpoint-sha256>.dpapi`；默认是 `%LOCALAPPDATA%/WorldBuilder/credentials`，与preferences/runs分离并忽略Git。DPAPI使用当前用户保护，不使用LOCAL_MACHINE标志；本机同用户权限下运行的程序仍可能解密，不宣称抵抗账户失陷。保存先生成密文再原子替换，不写明文临时文件。[Microsoft CryptProtectData说明](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)（访问2026-10-16）支持这一当前用户/资源释放设计；不涉及额外账户或云端密钥托管。

HTTP v1新增受同一Host/Origin/token约束的POST `/credentials/status|save|clear`。status/clear接受 `{endpoint}`，save接受 `{endpoint,api_key}`，只返回supported/saved及脱敏错误，不提供密钥读取接口。保存要求先保存同一endpoint的配置。bootstrap仅声明 `credential_storage=windows_dpapi` 或null。API运行优先临时显式密钥，其次取该endpoint已保存密钥，最后沿用已有环境变量规则；离线/调整/回放不读保存密钥。

凭据损坏会明确要求重新保存/清除，不能静默当成密钥缺失。密钥不写preferences、任务、worldpkg、导出日志或浏览器localStorage。047原记录仍描述当时一次性TXT导入；048显式覆盖客户端凭据生命周期，模型/生成器/profile契约不变。047登记中jobs/server源码摘要属于原快照，本轮更改后不再宣称这些文件哈希未变，不改写原登记或验证报告。

## “受限参数调整不调用API”的含义

例如把树数388改410：用户已经给出明确数值，不需要模型再决定数值；本地执行046既有参数化构建、道路/房间检查、WIR和GLB导出。费用为0次模型调用，仍需全图重建，不是即时改画面。API生成则由模型理解范围内偏好并提出B/D参数和F审查；二者共享本地构建与硬验证。用自然语言要求自由局部修改仍不是当前能力。

## 验证

新增15项合成密钥测试和既有回归，共168 passed：实际当前用户DPAPI加密、独立Python进程解密、桌面会话关闭重开、完整endpoint隔离、临时密钥优先、回放不读取密钥、损坏显式失败/恢复、非法字段/HTTP/用户信息地址拒绝、CSRF、无密钥读回及移除TXT控件。无付费网络调用，未验证真实密钥余额/有效性。打包及窗口结果见048工单；不提交或推送GitHub。

最终包内旧样例/回放自检通过；真实exe合成凭据保存、独立进程重开和清除三阶段均pass，证据在 `artifacts/client048/`。原生设置窗口已核对保存标记及空密码框，[实际截图](../artifacts/client048/settings-reopened.png)只含测试地址与合成模型名，不含真实密钥；合成密钥已清除，不留作用户API配置。
