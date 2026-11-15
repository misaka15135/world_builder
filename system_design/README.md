# World Builder 系统架构设计

更新日期：2026-11-12 · 业务契约草案：`design-2026-11-11` · 技术基线：`stack-2026-11-12` · 归属：[053 系统详细架构设计](../work_order/053_system_architecture_design.md)

> 本设计包面向“用户接入受支持 LLM，由 Agent 使用知识与工具构建自然、建筑和混合游戏场景”。当前实现仍为固定 A—F 0.1.0；本包是完整目标设计及实施输入，不代表 048—052 已实施或已通过真实模型/目标平台验收。

## 具体技术选型

先读 [16 技术栈与版本基线](16_technology_stack.md)和 [17 代码与实施蓝图](17_implementation_blueprint.md)。推荐 Python/FastAPI/asyncio/SQLite 后端，React/TypeScript/Vite/Three.js 工作台及 pywebview Windows 宿主；包含精确版本、配置默认值、17 表 SQL、线程进程边界和构建验证。

## 阅读入口

直接打开 [离线阅读页](index.html)，无需启动服务器或联网；正文和 SVG 已嵌入。需要修改时编辑本目录 Markdown、`diagrams/*.mmd` 与契约草案，再运行构建脚本。

| 章节 | 内容 |
|---|---|
| [00 目标与需求](00_scope_and_requirements.md) | 产品范围、事实边界、R01—R14、用户场景与术语 |
| [01 系统结构](01_system_architecture.md) | 上下文、模块职责、依赖、控制权和现有代码映射 |
| [02 运行时与 Agent](02_runtime_and_agents.md) | A—F 角色、任务 DAG、行动循环、预算、调度与恢复 |
| [03 协议与工具](03_protocols_and_tools.md) | 双协议归一、ToolSpec、MCP、幂等回执与错误 |
| [04 世界与事务](04_world_and_transactions.md) | WIR、身份、表/索引、候选、CAS、锁、修订与回收 |
| [05 几何与校验](05_geometry_and_validation.md) | 单位坐标、地形水体、建筑自然对象、通行与空间检查 |
| [06 知识与资产](06_knowledge_and_assets.md) | 检索、Skill、版本、来源许可、资产生命周期 |
| [07 目标与导出](07_targets_and_export.md) | Unity/Minecraft profile、坐标、量化、损失与验收 |
| [08 安全与隐私](08_security_and_privacy.md) | 信任边界、凭据、提示注入、文件与网络安全 |
| [09 工作台](09_workbench_and_interaction.md) | 页面/命令、候选预览、修改、锁、错误与无障碍 |
| [10 API 契约](10_api_contract.md) | HTTP 目录、行动、事件、错误、幂等与缓存 |
| [11 部署与运维](11_deployment_and_operations.md) | 本地进程、数据根、恢复、备份、观测与发布 |
| [12 质量与验收](12_quality_and_acceptance.md) | 需求追踪、测试矩阵、真实模型与目标证据 |
| [13 决策与交付](13_decisions_and_delivery.md) | 已确认决策、技术权衡、冻结项、048—052 承接 |
| [14 来源与现状](14_sources_and_current_state.md) | 代码证据、规范查阅日期、适用范围与假设 |
| [15 图册](15_diagram_catalog.md) | 17 张 UML/架构/ER/流程图与可编辑源 |
| [16 技术栈](16_technology_stack.md) | 明确选型、精确版本、依赖清单、配置与迁移阶段 |
| [17 实施蓝图](17_implementation_blueprint.md) | 包目录、Protocol、DB/GUI线程、worker RPC、SQL与构建命令 |
| [验证报告](VERIFICATION.md) | 本轮实际检查、结果与未验证边界 |

实现者先读 16/17；架构师再读 00/01/04/13；运行时开发读 02/03/10；几何和目标适配开发读 05/06/07；前端读 09/10；测试与运维读 08/11/12。公共契约由 048 冻结，不能以章节作者划分成多套不一致运行契约。

## 契约与样例

- [Action JSON Schema](contracts/action.schema.json)：五种行动的封闭结构草案。
- [OpenAPI 关键命令子集](contracts/openapi.design.json)：启动操作、取消、接受候选三个接口；其余接口详见 10 章目录，正式契约待冻结。
- [有效行动](examples/actions.valid.json)与[无效行动](examples/actions.invalid.json)：用于验证协议边界。
- [三类场景任务图](examples/scenario_graphs.json)：单栋、无建筑森林、森林营地，附覆盖缺失、依赖环、能力假覆盖、审查缺失/不可达反例。

这些文件仅用于设计评审，不复制到现有运行 `schemas/`，不会改变当前产品行为。

## 技术实现附件

- [后端依赖](implementation/backend.requirements.txt)、[前端依赖](implementation/frontend.package.json)与[前端完整锁](implementation/frontend.package-lock.json)。
- [运行配置](implementation/runtime.design.toml)与[配置 Schema](implementation/runtime-config.schema.json)。
- [17 表 SQL 设计](contracts/repository-extension.design.sql)：只用于空库演示，不是生产迁移。
- [后端/配置/SQL 验证](verification/technology-check.json)与[前端构建验证](verification/frontend-stack-check.json)。

## 图形格式

UML 类图、时序图和状态图使用 Mermaid 表达；系统上下文、组件、部署、威胁边界及交付路线采用架构流程图，存储采用 ER 图。它们分别标注类型，不把全部图都称为 UML。SVG 可放大查看并用于报告，`.mmd` 可编辑与版本对比。

## 维护与复现

在隔离 Python 3.12 环境安装 [文档工具依赖](tools/requirements.txt)，然后运行：

```sh
python tools/verify_design.py --repo /absolute/path/to/world_builder
python tools/build_reader.py
```

以上命令从 `system_design` 目录执行；它们只检查/构建设计文件，不启动模型、工具或游戏环境。验证器覆盖 Schema、正反例、任务 DAG/必需覆盖、OpenAPI 本地引用/路径和文档链接；不宣称完整 OpenAPI 规范认证。

重新渲染时单独安装 `@mermaid-js/mermaid-cli@11.12.0`，使用本地 Chrome/Chromium：

```sh
python tools/render_diagrams.py --mmdc /absolute/path/to/mmdc --chrome /absolute/path/to/chrome
python tools/build_reader.py
```

渲染会更新 [图形摘要清单](diagrams/render-manifest.json)。字体优先 PingFang SC / Noto Sans CJK SC；跨机器渲染需准备中文字体，SVG 已有布局不依赖在线服务。工程正文使用标准中文，记录建议/事实/未验状态；新增正式实现应同步运行契约及对应工单证据。
