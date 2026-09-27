# 020 场景道路走廊栅格化与地面填充顺序

- 状态：planned
- 创建日期：2026-09-27
- 执行者：待认领
- 依赖：018（场景装配与目标导出）、016（区块与路网）
- 修改范围（计划）：`src/world_builder/adapters/minecraft/scene.py`、`src/world_builder/adapters/minecraft/city.py`、`tests/test_scene_projection.py`、`tests/test_assembler.py`、[场景装配合同](../docs/contracts/scene-assembly-v0.1.md)

## 来源：018 目标实贴暴露的真实缺陷（2026-09-27）

把修复版魔法城邦贴进目标世界后做方块探针与目视对照，发现地面被大面积石砖覆盖，建筑只剩木色体量浮在石板上。量化证据（离线，可复算）：

| 证据 | 数值 | 出处 |
|---|---|---|
| 折线投影后街面盒总面积 | 565,292 m²（场景本体仅 262,144 m²） | 解析 `artifacts/minecraft-scene-arcane-interiors-3/manifest.json` |
| 单个最大街面盒 | `connector_block_036_seg000` 187 m × 368 m | 同上（`minecraft:stone_bricks`，y 层 0.0—0.4） |
| 一层楼板被街面覆盖的建筑 | 30 / 33 个 `building_site_*` 足迹 | 同上的 1 m 网格采样（如 `building_site_032` 全覆盖） |
| 游戏内探针 | (300, −60, 884) 实为 `minecraft:stone_bricks`，而 WIR 中该格是 `building_site_032` 的一层 `oak_planks` | 目标世界 `WB Verify Flat`，日志 `artifacts/minecraft-scene-arcane-interiors-3/target-20260927/` |

原因是两处叠加：

1. **投影把斜向折线折成外接盒**：`project_for_minecraft()` 对每条 `polyline` 段只生成“两端点外接矩形 + 宽度外扩”的一个盒（`src/world_builder/adapters/minecraft/scene.py`），斜段因此变成覆盖整片区域的大矩形，而不是走廊。
2. **填充顺序让街面压过地面与楼板**：场景分支按“地面与水 → 街面/外壳/楼板”的既有顺序写块，街面盒晚于 `terrain_proxy` 与建筑一层楼板，于是在共用的 y=0 层上覆盖它们。

这是渲染语义缺陷，不是目标贴错：同一份分块在目标世界逐块 `blocks affected` 与清单完全一致（36/36，见 018 执行记录），缺陷在导出物本身。

## 目标

- 折线道路/轨道/城墙不再产生外接大盒：把每段细分成走廊单元（阶梯化），单盒的短边不超过道路宽度 + 1 m 网格容差，长边不超过一个上限（建议 ≤ 8 m）。
- 地面语义恢复：场景本体在走廊之外保持 `terrain_proxy` 的草地，建筑一层楼板保持 WIR 声明的材质。
- 生成器行为变化必须升版本（适配器/投影 `0.1.0-city.5`），并按项目规则重跑完整回归、重导分块、重贴目标世界、留截图。

## 工作项

- [ ] 在投影层实现走廊栅格化：按段长与走向把 `points_m` 折线拆成若干轴对齐盒，写入 `projected_from`/`segment`/`sub_index`，并保留源包不做修改。
- [ ] 调整场景分支填充顺序或加"街面不得覆盖建筑足迹"的规则，使一层楼板材质与 WIR 一致。
- [ ] 扩充 `tests/test_scene_projection.py`：断言单盒长边上限、走廊面积占比上限（例如街面总面积 ≤ 场景面积 × 1.25）、斜段不再产生外接大盒。
- [ ] 重导 512 m 魔法城邦（`tools/assemble_scene.py --export-minecraft`），跑完整回归与文档检查，版本升到 `0.1.0-city.5`。
- [ ] 重贴目标世界并复验：地面草地区块比例、`building_site_032`/`building_site_026` 一层材质、街面探针，截图存档到 `artifacts/minecraft-scene-arcane-interiors-5/target-<日期>/`。

## 验收标准

- 同一输入两次生成仍然是同一世界身份与语义哈希（006 口径）。
- 离线清单中不再存在长边超过上限的道路盒；街面总面积与场景面积的比值落在设定阈值内。
- 目标世界方块探针：走廊之外为草地、建筑一层楼板为 WIR 声明材质，且 36 分块的 `blocks affected` 与清单一致。

## 明确不做

- 不改 Unity 适配器（008）与 006 冻结的参考实现。
- 不改写 018 已记录的失败与证据；本工单只做修复与再验收。
- 不在无人值守时改用户的世界存档备份与隔离目录。
