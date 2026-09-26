# 场景装配 0.1

版本：0.1.0。日期：2026-09-26。实现：`src/world_builder/planning/assembler.py`、`tools/assemble_scene.py`。状态：**已产出通过 WIR 0.1 合同的包；目标适配器尚未接入。**

本文是流水线阶段 F（[018](../../work_order/018_assembler_pipeline.md)）的合同。

## 1. 做什么

把五个阶段的产物写成**一个 WIR 包**：世界规格（含 `scene_spec` 扩展与简报摘要哈希）、世界根、地形实体 + 高程资源（内容寻址）、水系、归属 domain、街区 district、道路/铁路/码头/城墙（折线）、桥（含 `crosses` 关系）、每栋建筑的 `building` 实体，以及展开后的 `storey`/`room`/`partition`/`furniture`/`stair` 实体与楼梯 `connects` 关系。

```powershell
$env:PYTHONPATH = 'src'
python tools/assemble_scene.py --prompt "河谷里的魔法城邦，要有城堡和冒险者工会" --seed 4 --output artifacts/scene-arcane/wir.json --svg artifacts/scene-arcane/plan.svg
```

## 2. 校验

1. `world_builder.wir.validator.validate_package` —— 005 的 0.1 合同（manifest 必填项、记录形状、父子引用、修订头）。
2. 装配级不变量：各层齐全、建筑记录数等于设计数、建筑高度与设计一致、楼层是建筑的子实体、**子实体世界 AABB 落在父实体之内**、桥有 `crosses` 关系。

实测（seed 4、512 m、8 m 网格）：魔法城邦 565 条记录、`failed=0`——`world 1 / terrain 1 / river 4 / domain 3 / district 40 / road 173 / bridge 16 / wall 1 / building 33 / storey 42 / room 84 / partition 42 / furniture 89 / stair 7`。

## 3. 已知边界（重要）

- **目标适配器尚未接入**：Minecraft/Unity 适配器今天读的是 512 m 城邦的 `city_spec` 扩展与它自己的记录词汇；本阶段产出的是 `scene_spec`。因此这个包**能通过合同校验、能被本地查看，但还不能直接导出到游戏**。接线是下一个增量。
- 还没有写入 SQLite 修订库或 `.worldpkg`（包是 JSON 快照）。
- 地形仍是固定 8 m 采样的高程资源；没有把水位/海岸线写成水方块。
- 家具的 AABB 目前按 1×1 m 记录，尺寸细节留在设计阶段的数据里。
