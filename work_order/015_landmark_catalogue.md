# 015 风物目录与背景包（流水线 C）

- 状态：in_progress
- 创建日期：2026-09-26
- 执行者：待认领
- 依赖：013（简报与背景包结构）
- 修改范围：未来的 `world_builder/planning/catalogue.py`、`settings/<name>/catalogue.json`、`tests/test_catalogue.py`、`docs/contracts/landmark-catalogue-v0.1.md`

## 目标与范围

按背景列出**应当出现的建筑与风物**：类型、语义角色、必需性、数量区间、目标尺寸、邻近与场址要求。这是用户规划里的 C，也是"让建筑能看出功能"的源头。

现状对照：今天的功能集合是固定元组 `PROGRAMMES`，分区功能来自两张硬编码表 `DISTRICT_PLAN`/`MODERN_DISTRICT_PLAN`，没有"必现风物""邻近关系""尺寸区间"这些可验收字段；"背景"只有两个样式常量。详见 [docs/04_scene_pipeline.md](../docs/04_scene_pipeline.md) §2。

## 输入输出契约

`catalogue[type]` 至少包含：

| 字段 | 含义 |
|---|---|
| `role` | 语义角色（如 `landmark`、`civic`、`commerce`、`workshop`、`housing`、`infrastructure`） |
| `required` / `count_range` | 是否必现与数量区间 |
| `footprint_m2_range` | 占地区间（供 016 分配包络） |
| `height_m_range` | 高度区间（层数与屋顶由此推出） |
| `adjacency` | 邻近要求（如"市政厅靠近广场""码头贴水""厂房靠铁路"） |
| `needs` | 场址要求：`water_front`、`road_front`、`rail`、`centre`、`hill` 等 |
| `materials` / `silhouette` | 材质词汇与外形基调（供 017 与目标适配器选材） |

## 工作项

- [x] ~~定义目录 Schema，包含上表字段与校验（区间合法、邻近关系无自相矛盾）。~~
- [x] ~~把现有 `PROGRAMMES`/`PROGRAMME_ROOMS`/`PROGRAMME_FURNITURE`/`PROGRAMME_ROOF` 抽成 `arcane_medieval` 背景包的目录与设计条目，**不改变现有输出**（先做等价搬迁，用现有批次结果对照）。~~
- [x] ~~新增 `modern_metropolis`（交通枢纽、摩天楼、整齐街区、居民楼、绿地公园、医院、学校、机关）、`industrial_park`（各类厂房、货场、整齐道路、烟囱/储罐）、`harbour`（码头、泊位、货轮、仓库、灯塔、船坞）三份目录初稿。~~
- [ ] 规则：同一背景内 `required=true` 的风物必须能被 016 全部安排（**取决于 016 实现**）；数量区间与占地/高度区间要和简报的 `scale_m` 相容。
- [x] ~~独立校验规则：必现风物齐全、尺寸与背景一致、邻近关系可满足。~~

等价搬迁的说明：本轮**没有改动生成器**（`generation/` 一行未动），因此既有 city 批次结果继续有效；等价性由两条独立证据支持——四个背景的 `maps_to_programme` 合集恰好等于 `PROGRAMMES`，且同一背景内一个 programme 不会被两个条目重复占用（`tests/test_scene_brief.py::test_catalogues_migrate_the_existing_programmes`）。等 017 真正改为"从背景包读设计"时，必须再用预登记批次复核等价性。

## 验收标准

- `arcane_medieval` 的目录搬运后，现有 city 批次的实体与检查数在容差内不变（证明这是等价重构，不是行为变更）。
- 四份目录都能通过 Schema 校验，且同一简报在四个背景下列出的必备风物集合互不相同，有可核对清单。
- 目录中的每个 `type` 都指向 017 的某个设计模板；缺失时给出明确错误，而不是回退到通用盒子。

## 明确不做

- 不做选址与包络分配（016）、不做具体外形与房间（017）。
- 不承诺目录覆盖率等于真实城市学结论；这是可校验的生成器输入，不是建筑规范。

## 执行记录

| 日期 | 执行者 | 动作 | 结果与证据 | 下一步 |
|---|---|---|---|---|
| 2026-09-26 | root | 根据用户对流水线的重构要求创建本工单 | 本文件与 [docs/04_scene_pipeline.md](../docs/04_scene_pipeline.md)；尚无实现或测试结果 | 先做 `arcane_medieval` 的等价搬迁，再写另外三个背景包 |
| 2026-09-26 | root | 实现阶段 C：目录 Schema 与四个背景包 | `settings/{arcane_medieval,modern_metropolis,industrial_park,harbour}/catalogue.json`：条目 11/12/10/11，必现 7/9/6/9，已实现 7/5/4/3，未实现 4/7/6/8。`design_state` 强制"已实现必指向真实 programme、未实现必写清缺口"，由 `tests/test_scene_brief.py` 强制（16 passed）。真实缺口集中在城堡、城墙、行会、广场、摩天楼、枢纽、地铁、厂房、仓库、储罐、突堤、岸壁、堆场、船坞、灯塔、海关、货轮 | 这些缺口是 017 的工作清单；016 需要先能消费 `needs`/`adjacency` |

## 交接说明

开始前重读 013、006 的 `PROGRAMMES`/`DISTRICT_PLAN` 与 docs/04；完成有结果的动作后更新执行记录。
