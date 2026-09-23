# 开发与目标环境基线

初始冻结日期：2026-09-22；Unity 目标修订日期：2026-09-23。对应工单：005、008、009。状态：开发基准已实测；Unity 手工样件已在目标编辑器批处理和图形界面导入，Minecraft 已在目标游戏加载并粘贴；两者连续玩家通行待验。

## 基准主机

统一基准主机为 `MISAKA`，历史 SSH 别名 `tx5`。2026-09-23 用户确认当前已直接在这台 Windows 本机运行，不再从 Mac 经 SSH 操作；后续命令和测试直接在本机 PowerShell 执行。其他机器的结果不能冒充该主机的验收数据。

| 项目 | `tx5` 实测值 |
|---|---|
| 主机名 | `MISAKA` |
| 操作系统 | Windows 11 专业版 10.0.26200，build 26200，64 位 |
| CPU | Intel Core i9-14900HX，24 核、32 逻辑处理器 |
| 内存 | 68,319,457,280 bytes，约 63.6 GiB |
| GPU | NVIDIA GeForce RTX 4070 Laptop GPU，8188 MiB；驱动 616.92 |
| Python | 3.13.9 |
| Node.js | 24.18.0 |
| Java | Microsoft OpenJDK 21.0.11 LTS |
| 磁盘采集时可用空间 | C: 约 443 GiB；D: 约 185 GiB |

上表为 2026-09-22 经 `ssh tx5` 采集的历史记录。硬件和驱动可能变化；每次性能基准必须把重新采集的环境快照随结果保存。

2026-09-23 本机复核：主机名 MISAKA、i9-14900HX、68,319,457,280 bytes 内存、RTX 4070 Laptop GPU；当前 Python 3.13.9 位于 `D:/Soft/anaconda3`，实测 `jsonschema==4.25.0`、`pytest==8.4.2`。`requirements-dev.txt` 仍保留 005 的 `jsonschema==4.26.0`，本轮未修改全局环境或冒称与历史依赖完全相同。006 报告携带实际依赖和实现哈希，完整验收前需重新冻结环境。

本机默认 pytest 临时目录存在 WinError 5；测试改用项目 `artifacts/` 下新的专属临时目录。生成器不依赖该临时目录，命令示例见 [006 运行说明](generation-v0.1.md)。

## 冻结的首批目标组合

| 目标 | 版本组合 | 当前状态 |
|---|---|---|
| Unity | Unity `6000.3.24f1`（6.3 LTS）、URP `17.3.0`、glTFast `6.20.0` | 本机安装及签名有效；手工两层 GLB 已在目标编辑器导入并目视，26 个对象 ID/碰撞和不对称东窗坐标通过；控制器漫游待验 |
| Minecraft | Java Edition `1.21.11`、Fabric Loader `0.19.5`、WorldEdit `7.3.19`、Sponge Schematic v3、Java 21 | 目标游戏已运行并用 WorldEdit 加载、粘贴 1365 个非空气方块；连续玩家通行待验 |
| IFC | IFC4 ADD2 TC1；IfcOpenShell 版本由 011 安装后固定 | schema 已冻结，工具版本待验证 |

Unity 原候选 `6000.3.0f1` 在 Hub 存档中显示警告标记；用户报告官方签名警告并停止安装。该原候选及现有 WIR 样例 profile 保留为历史记录，不作为后续 008 的安装目标。修订后的 `6000.3.24f1` 见 [Unity 官方发布记录](https://unity.com/releases/editor/whats-new/6000.3.24f1)（2026-09-10 发布）；2026-09-23 本机 Hub 的正式发行版列表显示它为 Unity 6.3 LTS 且未显示旧版警告标记，Unity CLI 预检无警告。这些事实不代替安装包数字签名或目标项目加载验证。

同日本机安装核对：Unity CLI `editors --installed` 返回 `6000.3.24f1` x86_64，`editors verify 6000.3.24f1` 返回 `ok=true`；编辑器位于 `C:\Program Files\Unity\Hub\Editor\6000.3.24f1\Editor\Unity.exe`，文件 `ProductVersion=6000.3.24f1_4e7b9b5b6244`。Windows Authenticode 对完整安装包和编辑器可执行文件均返回 `Valid`，签名者为 `Unity Technologies SF`。这一步只验证了本机安装和签名。

后续目标项目 `adapters/unity/sample_project/` 的包清单与锁文件实际解析为 URP `17.3.0`、glTFast `6.20.0`。Unity 批处理调用样件构建器导入 v2 GLB 并保存场景，`artifacts/unity-sample/target-validation-v2.json` 记录目标读取、东窗坐标及 26 个 MeshCollider 为 pass。该证据不等于运行时门洞/楼梯漫游通过；见 [008 样件说明](unity-sample-v0.1.md)。

Minecraft 官方 Launcher 安装了 1.21.11，本机客户端 JAR 内 `version.json.world_version=4671`。Fabric 官方安装器 1.1.2 安装 Loader 0.19.5，WorldEdit 7.3.19 的 1.21.11 模组已与发布方 SHA-512 核对并放入独立游戏目录。目标游戏已经启动，WorldEdit 加载日志与样件粘贴返回值见 [009 样件说明](minecraft-sample-v0.1.md)；连续玩家通行尚未证明。

## 软件与许可记录

| 项目 | 用途 | 许可/条款记录 |
|---|---|---|
| Python | 合同验证与工具 | PSF License；运行时不随本项目重新分发 |
| `jsonschema` 4.26.0 | JSON Schema Draft 2020-12 验证 | MIT |
| `pytest` 8.4.2 | 开发测试 | MIT |
| Unity | 008 的目标编辑器 | 适用 Unity 软件条款；本仓库不包含 Unity 二进制 |
| Minecraft Java Edition | 009/010 的目标应用 | 适用 Mojang/Microsoft EULA 与使用准则；本仓库不包含游戏文件 |
| WorldEdit 7.3.19 | `.schem` 目标加载验证 | GPL-3.0；若分发或链接其代码，008/009 必须复核义务 |
| Sponge Schematic v3 | 区域文件规范 | 仅按公开规范实现；开始分发前由 009 核实规范仓库的当前许可文件 |

## 资源预算

005 只验证数据契约，不设性能通过线。006 起以 `tx5` 为唯一基准机，初始总工作集预算 4 GiB、查看器 1080p 的 p95 帧耗时 33.3 ms、无云调用的小对象编辑 p95 200 ms。API 每世界 token、费用和重试上限在选定供应商后写入新的版本化 profile；未知价格不填假数。
