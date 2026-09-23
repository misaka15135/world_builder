# 开发与目标环境基线

冻结日期：2026-09-22。对应工单：005。状态：开发基准已实测，目标应用组合尚未安装验证。

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
| Unity | Unity `6000.3.0f1`（6.3 LTS）、URP；glTFast `6.19.0` 候选 | 已冻结，未在 `tx5` 安装验证；008 开始时记录 URP 精确包版本 |
| Minecraft | Java Edition `1.21.11`、WorldEdit `7.3.19`、Sponge Schematic v3、Java 21 | 已冻结，未执行加载测试；009 必须先验证该组合，失败时新修订 profile，不能覆盖历史配置 |
| IFC | IFC4 ADD2 TC1；IfcOpenShell 版本由 011 安装后固定 | schema 已冻结，工具版本待验证 |

冻结目标用于形成可复现 profile，并不表示兼容性已得到证明。Unity 6.3 LTS 和 Unity 6000.3.0f1 有官方发布记录；Minecraft 1.21.11、WorldEdit 7.3.19 和 Sponge v3 均有维护方资料，但组合仍须在 `tx5` 实测。

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
