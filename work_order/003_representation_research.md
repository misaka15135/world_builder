# 003 世界元数据与跨目标导出调研

- 状态：done
- 创建日期：2026-09-21
- 执行者：representation_research
- 依赖：无
- 修改范围：本工单、`docs/research/003_representation_evidence.md`

## 目标与工作项

- [x] ~~调研 OpenUSD、glTF、IFC、Unity 和 Minecraft 的表示与导出边界。~~
- [x] ~~基于官方规范或维护方资料，提出语义世界元表示的必要能力。~~
- [x] ~~说明跨目标信息损失、建筑概念模型与可施工成果的差异。~~

## 验收标准

提供一手来源和访问日期；明确哪些格式适合作为派生输出，哪些问题必须由项目自己的语义和约束数据解决。

## 执行记录

| 日期 | 执行者 | 动作 | 结果与证据 | 下一步 |
|---|---|---|---|---|
| 2026-09-21 | representation_research | 阅读协作规则、总规划和本工单；认领调研 | 修改范围限于本工单和专属证据文档；确认首版目标为普通电脑可编辑魔法城邦及 Unity/Minecraft 导出 | 验证官方规范与维护方资料 |
| 2026-09-21 | representation_research | 核对 OpenUSD、Khronos、Unity、Sponge、EngineHub、buildingSMART 与 IfcOpenShell 一手资料 | 已确认场景组合、运行时几何发布、区域剪贴板、构件语义分别承担不同职责；完整世界存档另涉及 region/poi/entities 数据 | 编写世界中间表示和导出能力矩阵 |
| 2026-09-21 | representation_research | 编写元表示证据、能力矩阵、版本/单位/坐标合同和导出验收边界 | `docs/research/003_representation_evidence.md`；包含 10 组一手资料及统一访问日期，区分文献证据、设计判断和待验证事项 | 与总方案统一存储选择 |
| 2026-09-21 | representation_research | 读取总方案相关段落并统一单一权威存储 | 采用 SQLite 语义/修订记录 + 内容寻址不可变资源；JSONL/.worldpkg 仅为快照；单位及右手 Z-up 与总方案一致 | 检查文档并交接 |
| 2026-09-21 | representation_research | 检查文档来源链接格式、范围声明、访问日期、必要主题与工程语言 | Python 检查通过；未运行生成器或实际目标软件，互操作性明确保留为后续验收 | 交由 004 独立审查，后续 schema/样件工单完成实现验证 |

## 交接说明

只修改本工单和专属调研文件，由 root 更新共享总规划及索引。

已交付研究文档：[003_representation_evidence.md](../docs/research/003_representation_evidence.md)。

下一步：004 审查研究和正式方案的一致性；后续数据契约工单冻结 WIR 与目标版本 profile，双导出样件验证 Unity 场景和 Minecraft 区域的实际可用性。整世界 `.mca`、IFC 语义概念模型和外部修改回写分别验收。
