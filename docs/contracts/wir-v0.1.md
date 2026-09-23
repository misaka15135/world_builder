# WIR 0.1 数据契约

状态：冻结供 006—009 使用。Schema：[wir-package-0.1.0.schema.json](../../schemas/wir-package-0.1.0.schema.json)。

## 权威范围

WIR 保存世界意图、稳定实体身份、包含关系、跨对象关系、约束、生成配方、资产引用、修订及目标 profile。网格、方块和 IFC 文件是派生结果。当前 JSON 文件是便于评审和测试的完整快照；运行期权威存储遵循 ADR-0001。

## 身份、层级与关系

- 所有记录 ID 在一个快照内唯一，格式为小写字母开头的稳定标识符。显示名称不承担身份作用。
- `parent_id` 形成无环包含树；根世界实体的父对象为 `null`。分块通过 `chunk_ids` 索引，不改变对象身份。跨块桥梁只有一个实体，可同时属于多个分块。
- `Relation` 表达连接、相邻、跨越、支承和冲突等非树关系。关系目标必须存在。
- `Recipe.dependency_recipe_ids` 形成任务 DAG，不得形成环。
- 人工锁以 JSON Pointer 指向字段或子树。后续生成器不能静默覆盖锁定值。

## 状态语义

`generation_state` 表示对象生成阶段；`semantic_completeness` 表示语义内容深度，与渲染 LOD 无关。`deferred` 表示内容尚未细化，不等于空内容或已完成内容。

生成任务把“如何终止”和“能否满足约束”分开记录。只有完成了无解证明的任务可以使用 `infeasible`，且必须提供 `proof_ref`。超时、候选耗尽、预算耗尽、取消和实现错误均使用 `unknown`。完成并通过约束的结果使用 `feasible`。

## 坐标与数值

- 长度单位为米，角度为弧度；源坐标使用 float64。
- 世界坐标是右手系，`+X` 向东、`+Y` 向北、`+Z` 向上。
- 变换使用列向量，世界变换为 `T_world = T_parent × T_local`。
- 四元数顺序为 `[x, y, z, w]`，必须在 `1e-9` 内归一化。
- 区域、建筑、室内和角度分别使用 manifest 中的容差，禁止用一个全局阈值覆盖所有尺度。

目标转换：glTF/Minecraft 使用 `(x, z, -y)`；Unity profile 使用 `(x, z, y)`，其三维线性部分行列式为负，导出器必须反转三角形绕序并修正法线/切线；IFC 概念 profile 与 WIR 轴向相同。适配器仍须用不对称样件验证，不能只依赖公式。

## 扩展和版本

实现必须理解 manifest 中的全部 `required_capabilities`。遇到未知必需能力立即失败。可选数据放在 `optional_extensions` 或记录的 `extensions` 中；不理解的读取器不得据此改变核心语义，重新写出时应保留原值。

0.1 到后续版本的迁移必须生成新快照和修订，不修改历史快照。Schema 只验证形状；`world_builder.wir.validator` 继续验证引用、环、边界、四元数、结果状态、损失统计与修订摘要。

## `.worldpkg` 交换协议

`.worldpkg` 是 ZIP64 容器，路径统一使用 `/`，UTF-8 编码。建议布局：

```text
manifest.json
snapshot/records.jsonl
assets/sha256/<hash>
reports/<target-profile-id>.json
```

本工单仓库中的 `*.world.json` 是将 manifest 和 records 合并的等价评审形式。006 实现正式打包器时，必须做到：

1. 规范 JSON 使用 UTF-8、排序键、无多余空白；内容哈希使用其字节序列的 SHA-256。
2. `manifest.json` 列出每个成员的路径、字节数、哈希和角色；压缩容器本身的哈希另行记录。
3. 禁止绝对路径、`..`、反斜杠逃逸、重复条目和符号链接；设定解压字节数、条目数和压缩比上限。
4. 导入先在隔离临时目录验证 Schema、语义引用和资源哈希，再创建新修订；失败不得移动分支头。
5. `linked` 包可以引用外部资产，但必须记录 URI、哈希、许可与缺失行为；离线完整性只对 `self_contained` 包承诺。

## 接口合同

规划器输入为不可变 `revision_id`、作用域实体、约束、目标 profile、稳定 seed 和资源预算；输出为候选记录差异、依赖、任务 outcome 与验证报告。验证器不修改输入。适配器只读取一个不可变修订，输出派生文件与 `export_report`，不得把目标工具状态写回为 WIR 真值。

编辑器发送带 `base_revision_id` 的领域命令。存储层在提交前验证引用、锁和基础修订；冲突时返回新旧值及相关实体，不使用最后写入覆盖。

## 手工样例

- `river_bridge_cross_chunk.world.json`：证明跨块实体仍只有一个身份，并保存跨越关系。
- `two_storey_building.world.json`：证明建筑、房间、楼梯、家具、资产和目标量化报告可共存。
- `locked_edit_conflict.world.json`：证明失败候选可保留锁、硬约束失败、无解证据和上一有效修订，而不冒充已提交结果。
