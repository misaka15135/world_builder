# 工单索引与协作流程

**2026-09-27 暂停交接**：016/018/009 保持 `in_progress`。修复版场景离线生成和定向回归已通过，完整回归已中断，目标游戏尚未重贴。五小时后的续做顺序、证据路径与目标世界当前状态见 [018 交接](018_assembler_pipeline.md)。

更新日期：2026-09-27。

每次工作先阅读本文件、[总规划](000_project_master_plan.md) 和当前工单，再执行任务。具体规则见 [AGENTS.md](../AGENTS.md)。

| 编号 | 工单 | 状态 | 执行者 | 依赖 |
|---|---|---|---|---|
| 000 | [项目总规划](000_project_master_plan.md) | in_progress | 协调者 | 无 |
| 001 | [问题重述与正式方案](001_problem_and_proposal.md) | done | root | 002、003 提供证据 |
| 002 | [分层生成可行性调研](002_generation_research.md) | done | generation_research | 无 |
| 003 | [世界元数据与跨目标导出调研](003_representation_research.md) | done | representation_research | 无 |
| 004 | [方案独立审查](004_proposal_review.md) | done | proposal_review | 001 初稿、002、003 |
| 005 | [WIR v0.1 数据契约与样例](005_wir_contract.md) | done | root | 001—004 |
| 006 | [最小分层生成闭环](006_generation_vertical_slice.md) | in_progress | root | 005 |
| 007 | [本地三维查看与增量编辑](007_local_viewer_editor.md) | planned | 待认领 | 005；最终联调需要 006 |
| 008 | [Unity 场景导出与加载验证](008_unity_export.md) | in_progress | root | 005；完整验收 006、007 |
| 009 | [Minecraft Java 区域导出](009_minecraft_schematic_export.md) | in_progress | root | 005；完整验收 006、007 |
| 010 | [Minecraft Java 独立世界导出](010_minecraft_world_export.md) | planned | 待认领 | 009 |
| 011 | [IFC 建筑概念模型验证](011_ifc_concept_export.md) | planned | 待认领 | 005、006；游戏首版之后 |
| 012 | [大区域与资源扩展验证](012_large_world_benchmarks.md) | planned | 待认领 | 006、007、008、009 |
| 013 | [场景简报（流水线 A）](013_scene_brief.md) | in_progress | root | 005 |
| 014 | [地形方案（流水线 B）](014_terrain_plan.md) | in_progress | root | 013 |
| 015 | [风物目录与背景包（流水线 C）](015_landmark_catalogue.md) | in_progress | root | 013 |
| 016 | [区块归属与选址（流水线 D）](016_district_siting.md) | in_progress | root | 014、015 |
| 017 | [单栋建筑设计器（流水线 E）](017_building_designer.md) | in_progress | root | 015、016 |
| 018 | [装配器与场景流水线（流水线 F）](018_assembler_pipeline.md) | in_progress | root | 013—017 |
| 019 | [Minecraft 本机启动恢复](019_minecraft_recovery.md) | done | root | 无；参考 009、018 |
| 020 | [场景道路走廊栅格化与地面填充顺序](020_scene_corridor_rasterization.md) | done | root | 018、016 |

下一个可分配编号：021。编号由协调者串行分配，避免并行碰撞。

**2026-09-27 更新（open_space 全线接通）**：`kind: open_space` 从设计端接到 WIR 与 Minecraft 适配器——装配器产出 `open_space_<site>` 实体（`ground_plan` 几何：铺装/步道 token + 局部坐标固定块表），`validate_scene` 增加 `scene.open_spaces` 并只对建筑设计检查楼层链；适配器按 token 落块（`stone→stone_bricks`、`path→smooth_stone`、`gravel→gray_concrete`、`lamp→glass`、`bench→oak_slab`、`tree→oak_fence`、`planter→grass_block`）；魔法城邦加 `plaza`、现代都市加 `park` 模板。**实测 seed 4**：魔法城邦 72 个设计（71 建筑 + 1 广场），`no template yet` 只剩 `castle`；现代都市 32 个设计、**缺失类型清单为空**；两者都导出 36/34 分块且 `validation: pass`，清单里出现 `open_space_*`、`*_path` 与 `*_lamp/bench/tree` 盒。**两个真实约束**：地表景观的目录高度只有 0—1 m，选址给的包络可能低到 0.62 m（古代广场）甚至 **0.2 m**（现代 `green` 街区 `height_factor 0.2`）——固定块高度随包络收缩、包络 < 0.4 m 时只铺装；"green 街区高度因子过狠"已记为 016 的工作项。

**2026-09-27 更新（018 端到端预登记批次）**：新增冻结登记 `benchmarks/scene_cases_v1.json`（四个背景 × seed 1—5 = 20 例）与运行器 `tools/benchmark_scene.py`（每例独立进程、导出写临时目录、离线零模型调用）。首轮 17/20，三例失败：一例是运行器自身的 `FileExistsError`（单例冒烟残留），两例是真实缺陷 `target.interior_void: building_site_006`——港口 6.85 m 进深的建筑**梯段比预留井长出 1.15 m**。修法：梯段前缘余量与平台随进深收缩，并新增源端规则 `design.stair_fits_void`（在源头拦，不再靠导出报错）。复跑 **20/20 通过、成功率 1.0、无失败原因**；耗时合计 300.2 s、单例均值 15.0 s、最大 19.9 s；进程峰值内存最大 146.1 MB、均值 136.9 MB；模型调用 0。报告 [artifacts/scene-benchmark-v1/report.json](../artifacts/scene-benchmark-v1/report.json)。

**2026-09-27 更新（现代都市贴入目标世界）**：把现代都市的新导出放到目标世界**不相交的 `z +2048` 区带**（`x −128—640, z 1408—2048`），与魔法城邦（`z 384—1024`）并存；34/34 分块的文件名 → 粘贴点 → `blocks affected` 与清单一致（795,205 非空气方块）。过程中把 z 偏移算错一次（分块顺序镜像），已整列清空重贴；列 4 漏贴一格、多贴一格也已纠正——两次错误都写在 016 的执行记录里。探针：街道 `gray_concrete` ✓、走廊外草地 ✓；建筑内部材质与离线预测不符（既非 `smooth_stone` 也非水），未查明，如实记录。截图存 `artifacts/minecraft-scene-modern_metropolis-dense/target-20260927/`。

**2026-09-27 更新（016 配比修复 + dense3 目标复验）**：街区接入从"每个街区连到最近的干道采样点"改为"按到干道距离排序、连到已连通路网的最近点"（12 m 内不补连接路），去掉与 `road_<block>` 重复的 `front_<block>` 车道、把服务弄堂收窄到 3.5 m 并用十分之一米避免同街区内撞名；`settings/arcane_medieval/catalogue.json` 把 shop/workshop/inn/library 升为必现、residence 需求 30 → 52（住宅区不再只有居住）；`planning/designer.py` 在墙面短于 3.31 m 时把入口改挂最长的一面（此前会以 `target.building_entry` 中断导出）；`planning/brief.py` 的必现需求按地区尺寸缩放（修 `brief.landmark_budget`）。**实测 seed 4 / 512 m**：建筑 33 → **71** 栋、足迹覆盖率 2.3% → **5.2%**、街面盒 115,991 → **53,888 m²**（两项目标均达成），导出 `artifacts/minecraft-scene-arcane-dense3/`（36 分块、`validation: pass`），地面层 PNG `artifacts/scene-arcane-021/ground-layer-dense-20260927.png`；`tests/test_siting.py` 新增比值回归测试。**目标世界已重贴并复验**：36/36 分块计数与清单一致；探针建筑室内 (94,−60,910)=`smooth_stone` 非水、草地 (6,−60,518)、街道 (6,−60,563)=`stone_bricks`；截图存 `artifacts/minecraft-scene-arcane-dense3/target-20260927/`。完整回归 **150 passed**、文档检查零错误。

**2026-09-27 更新（配比口径推广到四个背景 + 适配器 0.1.0-city.6）**：现代都市/工业园/港口此前**根本无法导出**——被压缩到 2.8—2.92 m 的首层放不下整格门洞，适配器以 `target.building_entry` 拒收（现代都市 `building_site_015`）。修复在适配器：遇到这种首层时把地坪板沿门洞切开（**门槛开洞**，开口从地面起算，门槛是迈上 0.2—0.3 m 地坪板的一步），正常层高路径与箱名不变；同时三个背景把已实现的商铺/旅店/图书馆/写字楼/工坊升为必现（现代都市商铺需求按中心街区容量定为 3，先按 6 跑时 `siting.sites_present` 如实报失败）。修复后四背景 seed 4 导出全部通过，**一层板覆盖率**：魔法城邦 71 栋 / **5.2%**、现代都市 31 栋 / **11.3%**、工业园 15 栋 / **7.7%**、港口 13 栋 / 3.6%（占陆地约 **6.3%**）；街面盒 53,888 / 61,285 / 44,438 / 51,613 m²——**现代都市超 60,000 目标 2%**，如实记录。新增适配器测试 `test_short_ground_storey_carves_the_doorway_through_the_floor`；合同 [minecraft-city-v0.1](../docs/contracts/minecraft-city-v0.1.md) 补记该策略与统计口径。

**2026-09-27 更新（新城邦 / city.7 对照）**：把新魔法城邦（interiors-4）与世界里既有的两座 city.7 城邦做同高度俯瞰对照并存图（`artifacts/minecraft-scene-arcane-interiors-4/target-20260927/compare-*.jpg`）。逐箱统计：新城邦 33 栋 / 足迹 6,043 m²（占 2.3%）/ 街面盒 115,991 m²；city.7 古代 80 栋 / 18,704 m²（7.1%）/ 24,336 m²；city.7 现代 80 栋 / 23,312 m²（8.9%）/ 30,976 m²。**结构达标、配比不足**：非正交干道、放射斜街与自然河网都已出现，但建筑密度只有参考的 1/3、街面面积是参考的 4—5 倍，观感偏空偏灰。已在 [016](016_district_siting.md) 记为工作项（目标：足迹覆盖率 ≥ 5%、街面盒 ≤ 60,000 m²），下一步优先调密度与路网配比。

**2026-09-27 更新（020 完成）**：折线走廊不再折成外接大盒——轴对齐段仍是一个盒，跨网格段改为沿线方链（边长 = 走廊宽度，中心间距 0.7 倍宽，相邻必重叠），水面复用同一助手；场景分支填充顺序改为"地面 → 水面 → 街网/城墙/桥 → 建筑壳体与楼板"，让一层楼板在自己足迹内胜出（006 冻结的 city.7 逐箱顺序未动）。适配器升 `0.1.0-city.5`、投影升 `minecraft-city-0.2`，源世界身份不变。同一 seed 4 实测：街面盒总面积 565,292 → **112,575 m²**（走廊真值 90,561，比值 1.24），最大街面盒 187 m × 368 m → 219.9 m × 5 m（轴对齐直路本身即走廊），地面层石砖占比 72.0% → **25.1%**、草地 27.4% → **72.6%**、建筑木地板 0.6% → **2.3%**；重导 36 分块 / 3,535 盒 / 626,181 方块、`validation: pass`，对照图 `artifacts/scene-arcane-020/ground-layer-{before,after}-20260927.png`。**目标世界已重贴并复验**：36/36 分块日志计数与清单一致，探针 `building_site_032` (258,−60,888) 与 `building_site_026` (321,−60,618) 一层均为 `oak_planks`、斜向大道为 `stone_bricks`、走廊外为草地且非水；截图存 `artifacts/minecraft-scene-arcane-interiors-4/target-20260927/`。完整回归 **149 passed**、文档检查零错误。

**2026-09-27 更新（场景目标实贴验收 + 新缺陷）**：修复版魔法城邦（`artifacts/minecraft-scene-arcane-interiors-3/`，36 分块 / 1,024 盒 / 629,926 方块）已完整贴入目标世界 `WB Verify Flat`。做法：逐列清空到 y=−61 以上（保留地面层，避免玩家坠落导致粘贴点漂移），切观察者模式消除碰撞漂移，再按基线 `(chunk_x×128, −61, chunk_z×128+1024)` 逐块 `/tp` + `//schem load` + `//paste -a`；日志里 36/36 块的文件名、粘贴点与 `blocks affected` 与 `manifest.json` 逐项一致，早期误操作的 4 处越界残块经整列清空后不再存在。方块探针确认旧的"室内积水"缺陷已消失（`site_026`/`site_032` 一层均非水），但**发现新的渲染语义缺陷**：折线道路被投影成外接大盒（最大 187 m × 368 m，街面盒总面积 565,292 m²，超过场景面积 2 倍），并按当前填充顺序压过地面与建筑一层楼板，目标世界里 30/33 栋建筑的一层楼板变成石砖、场景呈大片石板。证据与修复计划见 [020](020_scene_corridor_rasterization.md)，截图存 `artifacts/minecraft-scene-arcane-interiors-3/target-20260927/`。

**2026-09-26 方向调整**：用户指出产物不满意源于构建思路不同，并给出 A—F 流水线设想（场景总控 → 地形分析 / 风物分析 → 区块划分与选址 → 每栋单独设计 → 汇总成 WIR → 导出）。核对结论是"差异全在控制面，不在数据面"，方案与理由见 [docs/04_scene_pipeline.md](../docs/04_scene_pipeline.md)。据此：**006 冻结为规则版参考实现**，控制面拆成 013（简报 A）、014（地形 B）、015（风物目录 C）、016（区块归属与选址 D）、017（单栋设计 E）、018（装配与流水线 F）六个可独立验收的工单；数据面（005/007/008/009/010/011）不变。另把此前并入 006 的"若干区块归属同一城堡"与"非正交路网"正式落到 016。

**2026-09-26 推进（013 + 015 首轮）**：阶段 A 与 C 的离线路径已落地——`src/world_builder/planning/{brief,catalogue}.py`、四个背景包 `settings/*/`、`tools/compile_brief.py`、`examples/brief_model_response.json`、`tests/test_scene_brief.py`（16 passed）与合同 [docs/contracts/scene-brief-v0.1.md](../docs/contracts/scene-brief-v0.1.md)。四个背景的目录共 44 条风物：已实现 19 条（对应现行 9 个 programme 的改名归类）、未实现 25 条，缺口由 `design_state` 与 `note` 逐条写明，并由测试强制。阶段 A 的模型路径只有契约与本地 fixture，真实服务待用户定供应商与额度。

**2026-09-26 推进（014 地形）**：阶段 B 落地——`planning/terrain.py`、四个 `settings/*/terrain.json`、`tools/plan_terrain.py`、`tests/test_terrain_plan.py`（8 passed）与合同 [docs/contracts/terrain-plan-v0.1.md](../docs/contracts/terrain-plan-v0.1.md)。512 m、8 m 网格下四个背景全部通过独立校验（`terrain.relief/slope/water_fraction/channel_count/width/coast/flow_downhill/water_in_valley/water_connected`）：arcane 水域 7.8%、4 条水道；modern 8.1%；industrial 5.2%；harbour 42.5% 且带海岸线。地形模型是"区域斜坡 + 平行排水的皱褶 + 河谷底衰减"，其下降是构造保证的；真正的排水求解器列为后续升级。下一步是 016 选址（消费 `needs`/`adjacency`/`buildable_at`）。

当前状态：001—005 done。006 in_progress：128 m 固定试验已有存档恢复、有限修复、模型规格合同、响应回放和 ZIP64 世界包；独立 512 m、80 栋/5 室内离线源端城邦的预登记输入 30/30 成功、首次 15/30、三类各 10/10。008 in_progress：Unity 6000.3.24f1 两层样件的 26/26 对象/碰撞、方向和连续控制器上楼通过；512 m 城邦 v1 的 176/176 源 ID/碰撞、连续跨桥 3/3 检查点通过；独立 v2 的五栋生成室内导入 346/346 构件/碰撞，五栋各一条 Play Mode 穿门上楼路线均为 5/5 检查点通过；v3 的 16 块/420 构件静态导入、碰撞、法线绕序与最大三角形边长 181.0193 m 通过，桥面 x=256 m 分块接缝 Play Mode 实走 3/3 检查点通过；独立道路/桥梁 NavMesh 的 136 个源网格在保存场景重载后跨桥路径为 `PathComplete`、24 m，Agent Play Mode 8.21 秒连续到达东岸，最终复测桥段 163 个位移帧均有源桥碰撞体支撑；v2 首栋室内导航在显式东门 Link 后道路到二层房间为 `PathComplete`、18.61 m，保存场景重载通过，Agent 两次 Play Mode 均从道路经梯级到二层房间。其它接缝、其余四栋室内导航及 Agent、性能、切线材质和 007 同修订联调待做。009 in_progress：Minecraft 1.21.11/Fabric/WorldEdit 版 1363 方块样件由玩家连续走通南门—二层；同一城邦修订已生成 16 个 128 m 分块共 687,427 方块，其中 `city_c01_03` 已粘贴进目标世界并与离线清单 42232 非空气方块逐块吻合，其余 15 块与游戏内通行待做。真实模型服务和复杂地形未验证；007、010—012 未开始。010 为必要性待明确的可选后续路线。

2026-09-25 更新：009 的 512 m 城邦 Minecraft 方块化已完成 16 个 128 m 分块并全部粘贴进目标世界（逐块 `blocks affected` 与离线清单一致），高空俯视可见完整 512×512 城邦；跨桥自 `(245.5,-58.2,-270.5)` 按键驱动前进 22.2 m 跨越 x 252—260 桥面，桥面/桥下/引桥方块抽查通过。首栋生成室内也已实走：从一层 `(28.5,-57,-17.5)` 上楼落稳于 `(28.5,-53.8,-28.7)`，壳体空心、门洞与楼板开口连通，量化后的整格台阶需跳跃上升。其余 4 栋生成室内与 `deferred` 建筑（源里无楼梯）待做。

009 后续更新：`building_001—004` 的壳体几何已用方块探测核对通过（一层楼板、空心室内、上层楼板均成立），但逐栋实走未完成——连按驱动的位移依赖「按下与抬起落在不同帧」，本机帧率掉到约 30 时完全失效（同一栋在 118 fps 可行走、30 fps 下 208—301 次连按位移为零）。因此 009 保持 in_progress，下一步是帧率稳定后补齐这 4 栋实走，并记录 `deferred` 建筑无楼梯这一源数据边界。

2026-09-25 更新（006）：城邦生成器升级为 `0.1.0-city.2`，建筑形态与功能按种子分异（12—18 m 体量、1—3 层、五种 programme），每层两间带用途房间与匹配家具；新增三条房间规则并修正家具—楼梯的二次方检查。单例实测 65 秒、1379 实体、8175 检查、feasible；`benchmarks/city_cases_v2.json` 预登记已冻结但**30 输入批次尚未运行**。让这些分异在目标平台可见需要先扩展 Minecraft/Unity 适配器（多层 + 房间隔墙），这是下一步。

2026-09-25 更新（city.2 目标侧）：Minecraft 适配器已支持任意层数与房间隔墙，并从 `city.2` 修订重导（16 分块、2,579 盒、627,953 方块、164 隔墙）、在目标世界清除旧建筑层后重贴。俯瞰可见大小不一的建筑，街面可见高矮不同的建筑、东门洞与室内木板地面。仍待：`benchmarks/city_cases_v2.json` 的 30 输入批次、三层以上楼梯、家具落块。

2026-09-26 当前状态（上方按日期的更新行保留为历史，最新状态以此行为准）：006 城邦生成器迭代到 `0.1.0-city.7`，内容剖面字段 `district_v4`。已实现且各有独立规则：建筑体量按分区与样式分异、功能 programme（住宅/商铺/工坊/图书馆/旅店/教堂/市政厅/公寓/写字楼）、每层两间带用途房间与匹配家具、隔墙作为源实体、**逐层退台外轮廓**（首层与东侧不动，退距取整米、逐层不递减）、屋顶原型（双坡/尖塔/平顶）、城墙（古代样式专属）、道路宽度与网格规则度按分区，以及样式 profile（`arcane_medieval` 坡屋顶加城墙；`modern_grid` 退台楼群、沥青路面与玻璃幕墙）；Minecraft 适配器策略 `0.1.0-city.4` 按层落墙环与腰线，加 0.6 m 出檐（古代木腰线、现代玻璃带）。源端预登记批次 city.3、city.4（重跑）、city.5 古代、city.5 现代、city.6 古代均达标（30/30、首候选 15/30；city.6 古代单世界 46.5—82.3 秒）；city.6 现代批次因实现已推进到 city.7 而作废，city.7 古代与现代两份登记（各 30 输入）待运行。**已更正一处错误记载**：屋顶原型自 city.4 起只写进属性、适配器读的是几何字段，因此 city.4—city.6 的导出全是平屋顶（v5/v6 清单各 80 个平屋顶代理、0 个阶梯屋顶盒），city.5 工单里"目标平台可见阶梯双坡屋顶"一句与产物不符，已在 006 中更正并在 city.7 修复。目标侧 Minecraft 1.21.11/Fabric/WorldEdit 世界中已贴入两座 **city.7** 城：古代 `x 0—512`（退台、双坡/尖塔屋顶、城墙与桥）、现代 `x 800—1312`（退台楼群、深灰车行道、玻璃带），16 分块逐块盒数与清单一致、分块地表抽验通过、两城俯瞰完整；同名 `.schem` 切换时曾误贴 4 个现代分块进古代城邦，已清层重贴。008 in_progress：Unity 城邦导出仍是单盒包络（退台与坡屋顶不可见），室内路径只支持"两层 + 一梯"，其余接缝、切线材质、性能与 007 同修订联调待做。009 in_progress：城邦方块化与目标验证已通，`building_001—004` 逐栋室内实走与通用跨目标联调未完成。007、010—012 planned。真实云模型服务、复杂地形与护城河开挖未验证。

## 执行约定

1. 读取索引、总规划和相关工单。
2. 确认依赖与文件所有权，登记执行者和状态。
3. 按验收标准实施，完成动作立即记录；完成条目同时勾选和划掉。
4. 记录验证命令、结果或文档证据，不将设计目标描述为已实现能力。
5. 阶段结束更新工单、索引和总规划；明确下一步。

新工单使用 [模板](TEMPLATE.md)。研究与方案交付物放在 `docs/`，工单记录计划、状态、动作和证据。
