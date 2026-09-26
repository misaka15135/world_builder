# 018 装配器与场景流水线（流水线 F）

- 状态：in_progress
- 创建日期：2026-09-26
- 执行者：待认领
- 依赖：013、014、015、016、017
- 修改范围：未来的 `world_builder/planning/assembler.py`、`world_builder/planning/pipeline.py`、`tools/generate_scene.py`、`tests/test_scene_pipeline.py`、`docs/contracts/scene-pipeline-v0.1.md`

## 目标与范围

把 A—E 的产物合成**一个 WIR 修订**：地形 + 水系 + 区块归属 + 骨架 + 选址 + 每栋设计，形成可存档、可导出、可编辑的世界；并实现**失败按作用域回馈**与端到端预登记批次。这是用户规划里的 F，也是整条流水线的收口。

现状对照：今天是五个固定阶段顺序提交（terrain/network/parcels/buildings/interiors），冲突只在阶段内用"候选 + 有限修复"处理；没有独立装配阶段，也没有"一栋失败只重做一栋"的机制。详见 [docs/04_scene_pipeline.md](../docs/04_scene_pipeline.md) §2。

## 输入输出契约

- 输入：`SceneBrief`(013) + `TerrainPlan`(014) + `catalogue`(015) + `domains/blocks/network/sites`(016) + `BuildingDesign[]`(017)。
- 输出：WIR 修订（005 合同）+ 源端检查报告 + `.worldpkg` + 目标导出清单。
- 装配器必须产生**跨阶段不变量**检查：实体不越界、建筑不重叠、入口接路、楼梯可达、家具支撑、包络未超限、domain 规则被遵守。

## 工作项

- [x] ~~定义装配契约与修订结构：每个阶段产物作为资源存档（内容哈希 + 提供者 + 版本），可离线回放。~~
- [ ] 实现作用域回馈：单栋设计失败 → 该栋重试或换包络；某个 site 在包络内无解 → 该街区重划；整城在地形上不可行 → 回到 014。**不得**因为一栋失败重跑整城，也不得静默放宽用户约束。
- [ ] 把现有 `pipeline.py` 的阶段提交、候选上限、`repair.py` 的有限修复改造成装配器的重试预算机制（**未做**：目前是一遍成型 + 校验，没有作用域回馈的重试）。
- [x] ~~提供一条命令跑完整条流水线（背景包 → 地形 → 目录 → 区块 → 设计 → 装配 → 导出）。~~
- [ ] 端到端预登记批次：4 个背景包各若干输入，登记在运行前冻结，记录成功率、失败原因、耗时与峰值内存；离线零模型调用。
- [ ] 与目标平台串联（**未做**：适配器读的是 `city_spec`，本阶段产出 `scene_spec`）。

上述两个已完成项的说明：资源存档=简报摘要哈希 + 高程资源内容寻址 + 修订记录 `change_set_hash`；一条命令= `tools/assemble_scene.py`（输出 WIR 包 + SVG 平面图，**到 Minecraft/Unity 的导出尚未接通**）。

### 目标适配器接线的差距清单（下一增量的入口）

已核对 `adapters/minecraft/city.py` 对包的要求，场景包与它之间还差四件事，逐条记明，避免下次重新摸索：

1. **世界规格**：适配器从 `world_spec.extensions.city_spec.style_profile` 取材质风格；场景包用的是 `scene_spec`。接线时要么在投影里补一个 `city_spec` 兼容块，要么让适配器也认 `scene_spec`（本项目倾向前者：投影层负责翻译，源数据保持不变）。
2. **折线要摊成盒**：`road`/`rail`/`wall` 在场景包里是 `geometry.representation="polyline"`，而适配器只接受 `box` 与 `parametric_building`。需要投影层把每条折线拆成逐段盒（这也是"非正交路"能进游戏的前提）。
3. **水面策略**：适配器现在要求"一条笔直南北向河"（`target.city_river`），而场景包是河网/运河/海岸线。适配器需要一条按源水道多段盒生成水面的分支，并由投影层设置一个标记来选中它——本轮已写过这条分支，因为没有生产者能验证它，**已撤回**，避免留下未经验证的代码。
4. **建筑外壳**：`_building_shell` 目前只支持 `entry.side == "east"`，而设计器按临街方向给出南北侧入口；需要把门洞与门楣逻辑推广到四个方向，并让装配产出的楼梯实体带上 `geometry`（`steps`/`run_m`/`rise_m`/`landing_length_m`/`floor_levels_m`），否则 `target.interior_void` 会拒收。

这四项都属适配器与投影层，改完必须同时跑：适配器专项测试、场景装配测试、**完整回归**，并重跑一次既有 512 m 城邦导出确认没有回归。

**第 2 项（折线摊盒）与第 1 项的一半已落地**：新增 `adapters/minecraft/scene.py` 的 `project_for_minecraft(package)`——把 `road`/`rail`/`wall`/`pier`/`quay` 的折线逐段拆成盒（每个盒记录 `projected_from` 与段号），并在 `world_spec.extensions` 里补一个 `city_spec` 兼容块（`style_profile`/`region_size_m`/`building_count`…）供既有材质查找使用。投影**不修改源包**（语义模型仍是折线）。`tests/test_scene_projection.py`（3 passed）验证：折线确实摊成更多盒、盒尺寸非退化、源包保持折线、风格与边长被正确带过；最后一条测试**故意断言导出仍会在已记录的缺口处停止**（`target.city_river` 或 `target.building_*`），这样缺口不会因为测试变绿而被忘掉。剩下两项——水面策略分支与四方向门洞——仍未做。

**2026-09-27 唤醒（第 3、4 项已落地）**：适配器现在接受场景包并**成功产出方块**（同一场景 736 个盒）。三处改动：

1. **水面策略分支**：包里有 `scene_spec` 时不再要求"一条笔直南北向河"，而是用平坦地面代理 + 按源水道折线逐段生成水面盒（河网、运河、海岸线都适用）。
2. **四方向门洞**：`_building_shell` 的门洞/门楣从"只认东侧"推广到东/南/西/北；`building_geometry` 检查同步放宽到四个方向。
3. **单层楼不再要求楼梯井**：单层建筑没有楼梯预留，原先会因空井被拒。

过程中被适配器逐条拦下的**真实缺陷**（都已修）：装配出的楼梯井贴到外墙外沿（不合法，现已内收 1 m 并按进深收窄梯段）；被压扁到 2.6 m 的层高放不下 2.4 m 门（现最低 2.8 m，压不下就减层）；窄地块上的入口被声明在过短的墙面上（现自动换到能开门的一侧）。

**新发现待修**：场景里建筑的入口由 `tools/assemble_scene.py` 的启发式给出（拿区块中心与场址自身的南北边比较，因而几乎总是选南面），**并没有真正朝向该街区的临街道路**；四方向门洞的南/北分支已被真实场景覆盖（`_south_wall_west/_east`），东/西分支只在单元测试与旧城邦路径里覆盖。下一轮应把选面改为"朝向该街区的临街一侧"。**勘误**：本轮曾据一次省略 `entry_side` 的诊断脚本记录"所有入口都落在东面"，该结论有误，已按实际断言更正。

### 本轮落地与未完成（2026-09-26）

**已落地**：`planning/assembler.py` + `tools/assemble_scene.py` + `tests/test_assembler.py`（6 通过 / 1 已知缺陷记为 xfail）+ 合同 [docs/contracts/scene-assembly-v0.1.md](../docs/contracts/scene-assembly-v0.1.md)。一条命令把五个阶段的产物写成**一个 WIR 包**并通过 005 的 0.1 合同与装配级不变量（层齐全、建筑数=设计数、高度一致、楼层挂建筑、**子实体落在父实体世界 AABB 内**、桥有 `crosses`）。实测魔法城邦 565 条记录、`failed=0`：`world 1 / terrain 1 / river 4 / domain 3 / district 40 / road 173 / bridge 16 / wall 1 / building 33 / storey 42 / room 84 / partition 42 / furniture 89 / stair 7`；同时输出一张 SVG 平面图（地形、水系、道路、桥、街区、建筑按实现/未实现着色）。

**装配级不变量当场抓到的三个真缺陷**（都已修）：子实体用了局部坐标而非世界 AABB（楼层/房间/家具跑到屋外）；街区高度写死 8 m，装不下 61.6 m 的塔；归属层高度同样写死，装不下它自己的街区。

**该缺陷已修（同轮后续）**：`_place_sites` 不再强放"装不下"的地块，而是跳过并把缺口交给 `siting.sites_present` 报告；同时给 016 加了数据一致性规则 `siting.catalogue_fits_blocks`（任何建筑的中值占地不得超过最大地块的 75%），并把工业园与港口的地块区间调到 `[6000, 52000]` / `[4000, 45000]`、目标块数下调到 18—40 / 18—36。修后四个背景的选址与装配全部 `pass`，场址数没有减少（工业园 13、港口 13），`test_assembler.py` 的 xfail 已移除。

## 验收标准

- 同一输入两次生成语义一致的世界（按 006 既有口径：世界身份、修订、语义哈希），并可离线回放。
- 一栋失败的作用域只影响该栋（有日志与修订证据），整城其余部分不变。
- 至少两个背景（如 `arcane_medieval` 与 `harbour` 或 `industrial_park`）各产出一座可导出的 512 m 世界，且"必现风物清单"逐项在 WIR 中可查。
- 预登记批次不筛选失败样例，失败原因分类记录；不把"设计目标"写成"已实现能力"。
- 端到端导出与 008/009 的既有适配器兼容，不回归已知缺陷。

## 明确不做

- 不接入真实云模型服务（供应商与额度由用户决定后再启用模型路径）。
- 不做大区域分块与流式缓存（012）、不做 IFC 语义扩展（011）。
- 不改写 001—012 的历史结论与已验收证据。

## 执行记录

| 日期 | 执行者 | 动作 | 结果与证据 | 下一步 |
|---|---|---|---|---|
| 2026-09-26 | root | 根据用户对流水线的重构要求创建本工单 | 本文件与 [docs/04_scene_pipeline.md](../docs/04_scene_pipeline.md)；尚无实现或测试结果 | 先定义装配契约与作用域回馈，再串起 013—017 |
| 2026-09-26 | root | 实现阶段 F 首轮：装配成 WIR 包 + SVG 平面图 + 装配级校验 | `planning/assembler.py`、`tools/assemble_scene.py`、`tests/test_assembler.py`、[合同](../docs/contracts/scene-assembly-v0.1.md)。四个背景里 3 个 `pass`、现代都市因"地块装不下仍强放"这一已知缺陷落成 xfail；三类坐标/高度缺陷已修 | 修地块尺寸与目录占地的匹配、接通 `city_spec`/适配器、端到端预登记批次 |
| 2026-09-27 | root | 新链路第一次产出 Minecraft 分块 | 适配器接线完成后（水面分支、四方向门洞、单层楼免楼梯井），`tools/assemble_scene.py --export-minecraft` 实测魔法城邦 seed 4：**36 分块 / 736 盒 / 626,309 方块**，`x -1…4`、`z -5…0`（环形城墙与连接路本就在 512 m 建成区外）、`region_y [-1,32]`、适配器 `0.1.0-city.4`、每块非空气 432—42,778。产物 `artifacts/minecraft-scene-arcane/`。完整回归 **145 passed**、文档检查零错误 | 把这 36 块自行贴进 Minecraft 世界并截图存档；`--interiors` 需先补楼梯实体几何；入口朝向改为临街一侧 |
| 2026-09-27 | root | 粘贴前准备完成，实际粘贴被"游戏未运行"挡住 | 36 个场景分块已拷进隔离游戏目录（36 文件，`city_c00_00.schem` SHA-256 与仓库产物一致）；游戏目录里现在是**场景包这一套**（与 city.7 两套同名，旧两套仍在 `artifacts/minecraft-city-v6*/schematics`）。**粘贴方案**：世界内古代城邦占 `x 0—512, z -512—0`、现代城邦占 `x 800—1312`，而场景分块是 `x -1…4, z -5…0`，直接按 `(cx*128,-61,cz*128)` 会压掉古代城邦，故改用偏移基线 **`(cx*128, -61, cz*128+1024)`** → 落在 `x -128…640, z 384…1024`，与两座旧城不相交；逐块文件↔坐标以 `manifest.json` 的 `chunks[].path/chunk_x/chunk_z` 为准。**阻塞**：`Get-Process javaw` 为空，Minecraft 未运行，启动游戏+36 块粘贴+探针+截图超出本次预算，**未开始**（避免清到一半停下） | 下一轮先启动游戏再执行上面的粘贴方案，截图存 `artifacts/minecraft-scene-arcane/` |
| 2026-09-27 | root | 给装配产出的楼梯补几何，室内导出前进一步 | 楼梯实体现在带 `geometry`（`straight_stair` + `size_m`/`rise_m`/`run_m`/`clear_width_m`/`headroom_m`/`steps`/`landing_length_m`/`floor_levels_m`），`--interiors` 于是越过了 `target.interior_void`，停在下一条：**`target.partition_geometry: site_002_partition_0`**——隔墙记录的几何形状还不符合适配器的要求。定向测试 `tests/test_assembler.py` + `tests/test_scene_projection.py` **9 passed**、文档检查零错误 | 下一轮补隔墙几何（适配器要求的具体形状见 `_partition_boxes`），随后重跑室内导出；完整回归与粘贴同轮做 |
| 2026-09-27 | root | **场景包的室内导出打通** | 两处修正：① 隔墙此前被写成"x 向 0.4 m 薄片、n 向 1 m"，而两间房是沿北轴排列的，墙应**沿 x 通长、n 向 1 m**——改对后 2 m 门洞才放得进；② 适配器的家具方块表新增场景词汇（table/crate/pallet/machine/board/lamp/reception），其中 `lamp` 映射到 `minecraft:glass` 而非 `glowstone`（后者不在调色板里）。实测同一场景：**36 分块 / 1,015 盒 / 628,355 方块**（仅外壳时是 736 盒 / 626,309 方块），产物 `artifacts/minecraft-scene-arcane-interiors-2/`。定向测试 20 passed（适配器 14 + 装配 6）、文档检查零错误 | 下一轮：完整回归 + 启动游戏执行已记录的粘贴方案（偏移基线 `cz*128+1024`）并截图存档 |
| 2026-09-27 | root | 补跑完整回归（室内导出两处修正之后） | `python -m pytest -q --basetemp artifacts/pytest-wake-full`：**145 passed**；`tools/check_project_docs.py` 零错误。至此工单里"完整回归待补"的缺口关闭 | 粘贴仍待做：本轮 `Get-Process javaw` 依旧为空（Minecraft 未运行），启动游戏+36 块粘贴+探针+截图超出本次唤醒预算，故未开始 |
| 2026-09-27 | root | 四个背景全部产出 WIR + SVG + PNG 可视记录 | 逐个运行 `tools/assemble_scene.py --setting <id> --seed 4 --output/--svg/--png`，四者全部 `validation: pass`，产物在 `artifacts/scene-<setting>/`（各 3 个文件）。记录数：魔法城邦 559（33 栋）、现代都市 **1,416**（25 栋、324 房间、419 家具）、工业园 243（10 栋）、港口 308（11 栋，含 `coast`/`pier`/`quay`/`work` 实体）。缺模板被跳过的类型：现代都市 `park`，工业园 `freight_yard`/`silo_tank`，港口 `container_yard`/`dry_dock`，魔法城邦 `castle`/`plaza` | 017 按这份清单逐条补模板；粘贴仍待下一轮启动游戏执行 |

## 交接说明

开始前重读 013—017 的契约、006 的 pipeline/repair 与 docs/04 §3.3；完成有结果的动作后更新执行记录，并在阶段结束时同步 000 与索引。
