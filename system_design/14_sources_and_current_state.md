# 14 现状核对、技术来源与适用边界

日期：2026-11-11。所有“目标设计”与现状分开；外部标准仅支持格式或概念，不证明本项目实现、性能或目标验收。

## 1. 本轮仓库核对

读取时分支为 `main`，HEAD 为 `244e3f2b190019c2daf1f8fc8342b6e115a34358`。分支/提交通过本地 Git 查询；未查询远端同步状态。工作区位于 SMB 挂载卷，不能据此推断生产数据目录必须位于该卷。

| 读取来源 | 确认事项 | 不可推导 |
|---|---|---|
| [基线](../docs/00_project_baseline.md)、[08](../docs/08_agent_target_architecture.md)、[09](../docs/09_agent_migration_plan.md) | 产品目标、D01/D02、当前边界 | 新路线已经实现 |
| [048](../work_order/048_agent_foundations.md)及049—052 | 契约、运行时、分阶段交付职责 | 工单文本等于验收 |
| [runtime.py](../src/world_builder/agents/runtime.py) | 固定 A/B/C/D/E/F 调度 | 动态工具 Agent 循环 |
| [providers.py](../src/world_builder/agents/providers.py) | 现有解码拒绝 tool_calls | 已支持原生工具协议 |
| [compiler.py](../src/world_builder/agents/compiler.py) | 当前身份受接受计划摘要影响 | 同一世界持续编辑已完成 |
| [repository.py](../src/world_builder/storage/repository.py) | SQLite、事务、expected_head、锁、资源摘要与快照基础 | 新候选/空间读依赖/全部恢复语义已覆盖 |
| [server.py](../src/world_builder/workbench/server.py) | 回环服务、Host 与 X-Workbench-Token 防护已有基础 | 所有未来命令或导入路径已安全 |
| [坐标函数](../src/world_builder/wir/transforms.py)、[Agent GLB 编译](../src/world_builder/agents/compiler.py)、[GLB 序列化](../src/world_builder/adapters/unity/sample.py) | 通用坐标变换与 Agent GLB 导入链需区分 | 单一矩阵适合所有既有导出 |
| [pyproject.toml](../pyproject.toml) | Python ≥3.10、jsonschema 依赖、已有 CLI 入口 | 已选择新的运行框架 |

本轮不调用付费模型、不启动目标引擎、不生成新场景，不把设计检查作为功能/真实质量验收。

## 2. 本轮查阅的规范

| 技术来源 | 固定适用点 | 边界 |
|---|---|---|
| [JSON Schema Draft 2020-12](https://json-schema.org/draft/2020-12) | Action草案的 oneOf、必填字段与封闭结构 | Schema 无法替代世界引用和权限校验 |
| [OpenAPI 3.1.1](https://spec.openapis.org/oas/v3.1.1.html) | 关键 HTTP 命令草案描述 | 选择固定版本，不宣称最新；仅关键子集 |
| [Mermaid 类图](https://mermaid.js.org/syntax/classDiagram.html)、[状态图](https://mermaid.js.org/syntax/stateDiagram.html) | UML 类/状态和时序表达 | 其他架构/ER/流程图不标称严格 UML |
| [SQLite WAL](https://sqlite.org/wal.html) | WAL 依赖同主机共享内存，不用于网络文件系统 | 源码可放 SMB；活动 DB 应另选本地盘 |
| [MCP 官方架构](https://modelcontextprotocol.io/docs/2026-07-28/learn/architecture) | Host/Client/Server 职责 | 具体协议/SDK由049冻结，版本不可混用 |
| [MCP 2025-11-25 Tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools) | 版本化工具调用示例 | 不作为2026协议完整实现说明 |

以上访问日期均为 2026-11-11。安全、Unity/glTF、Minecraft 的详细一手来源及边界记录在 07、08、11 章，与相关设计靠近放置。没有另行采信商业平台宣传或第三方性能数字。

## 3. 推导与假设

- 数据库写入串行、候选隔离、CAS 与取消代际是对当前持久化基础的设计扩展，需要故障注入验证。
- 本地模块化部署沿用现有产品方向；工作进程数量、最大场景预算、存储保留时间、模型兼容矩阵均需实施时测量。
- 几何、检索、导出和界面设计只声明可注册的能力，不默认自由旋转、曲面、挖方或游戏玩法可用。
- 模型返回的语言、检索资料和工具结果都不具有提升权限或覆盖用户锁的效力。

## 4. 维护规则

正式实施前由 048 冻结公共术语、字段、Schema、profile 与版本。运行契约变化同步原运行说明，不原地重写旧版本。本设计若发生范围变化，先更新关联 ADR、图源、机器示例与验收追踪，再重建离线阅读页。每张图的 `.mmd` 是可编辑源，SVG 为派生产物；图中名称与正文差异以冻结契约为准，并应作为缺陷修正。
