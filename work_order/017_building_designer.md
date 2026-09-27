# 017 单栋建筑设计器（流水线 E）

- 状态：in_progress
- 创建日期：2026-09-26
- 执行者：root
- 依赖：015（目录与设计条目）、016（site 与包络）
- 修改范围：`src/world_builder/planning/designer.py`、`settings/<name>/designs.json`、`skills/building-design/`、`tests/test_building_skill.py`、`docs/contracts/building-design-v0.1.md`；本轮限于建筑 skill、其参考资料及工单记录

## 目标与范围

给一栋建筑一块包络与一个类型，产出**这栋自己的设计**：外形轮廓、层数与层高、每层房间划分、楼梯与竖向通道、入口与门洞、屋顶原型、材质、家具布置。这是用户规划里的 E，也是"每栋不再一样"的关键。

现状对照：今天每栋的形态是"按种子取宽度/进深/层数 + 按功能查表"，平面只有一种模板——"楼梯井以东切两间房 + 一道隔墙"，家具按用途查表；没有单栋设计产物，没有按背景/包络变化的平面。详见 [docs/04_scene_pipeline.md](../docs/04_scene_pipeline.md) §2。

## 输入输出契约

`BuildingDesign` 至少包含：

| 字段 | 含义 |
|---|---|
| `outline` | 各层轮廓（可退台，米；与 006 的 `storey_insets_local_m` 对齐） |
| `storeys[]` | 层号、层高、楼板厚度、楼板开口（楼梯井） |
| `rooms[]` | 房间：所属层、用途、边界、面积 |
| `stair` / `vertical` | 楼梯类型（直跑/转折）、梯段、净空、落地点 |
| `entry` | 入口侧、偏移、宽度、高度、门洞与门楣 |
| `roof` | 原型（双坡/尖塔/平顶/退台）、高度、出檐 |
| `materials` | 墙体/楼板/屋顶/腰线的材质词汇（由背景包映射到具体方块或材质） |
| `furniture[]` | 家具：用途、位置、尺寸、所属房间 |

## 工作项

- [x] ~~面向古今中外多风格、多类型建筑，检索可核对的建造指南，扩充建筑 skill 的选型、构图、施工步骤与来源边界（2026-09-27 用户追加；本轮范围仅指导资料，不宣称生成器已实现）。~~

- [x] ~~定义 `BuildingDesign` Schema；所有尺寸显式单位，且必须在 site 包络内。~~
- [x] ~~把 006 已验证的形状规则搬进来作为**参考实现**：多层壳、楼板开口、隔墙与门洞、直跑楼梯、逐层退台、屋顶原型、出檐、楼层腰线。~~
- [x] ~~设计条目（`designs/*.json`）先行：住宅、商铺、工坊、图书馆、旅店、教堂、市政厅、公寓、写字楼；再补港口/工业园所需。~~
- [x] ~~让平面随包络与背景变化：同一类型在不同占地/高度下产出不同层数与房间划分，而不是同一模板缩放。~~
- [x] ~~建筑规划 skill：把"如何为某类型排外形/层/房间/楼梯/家具"写成可复用的技能文件。~~

  2026-09-27 落地：[skills/building-design/SKILL.md](../skills/building-design/SKILL.md)，含十条规则、机器校验清单、能力边界与来源。同日用户评审指出"只有一层楼梯、到不了其他楼层"，该条已在 022 的第一轮改进里修掉（每层一段梯）。
- [x] ~~独立校验规则：外形在包络内、房间不重叠且在层内、楼梯落地并与楼板开口对齐、入口接路、家具不挡门不占通道、屋顶与风格一致。~~
- [x] ~~成本策略：默认"设计模板 × 站点参数"实例化；只有地标类型允许单独设计入口（模型可选），并记录调用次数。~~

实现说明（如实记录）：

1. **模板是数据不是 skill 文件**：`settings/<id>/designs.json` 一条模板即可新增类型，比另造 skill 格式更接近"背景是数据"的原则；工单原文的 skill 文件形式未采纳，理由记录在此。
2. **`stair: "none"` 的模板强制单层**，并把净高抬到目录要求（厂房/仓库是大跨单层空间）；否则"两层却没有楼梯"会成为缺陷。
3. **高度对齐目录**：目录的高度区间是合同，层数按它反推；包络放不下时优先压低层高（≥2.6 m），只有连一层都放不下才降层。
4. **毫米网格容差**：设计坐标按毫米存储，包含关系用 2 mm 容差——早先版本用 `1e-6`，把向下取整的轮廓与向上取整的楼层之间 6 µm 的差判成"楼层跑到屋外"。

其余口径：退台、楼梯井、1 m 隔墙位与屋顶原型已搬入设计器，**出檐与楼层腰线仍属适配器层（009）**；"入口接路"由 016 的 `siting.needs_road` 保证，"家具不挡门/不占通道"本轮未做；设计路径零模型调用。

## 验收标准

- [ ] 单栋设计与现有目标适配器兼容（同一份设计在 Minecraft 与 Unity 适配器下都能导出）——**未做**：设计还没写进 WIR，属 018。
- [x] ~~同一类型在三种不同包络下产出可核对的差异（层数、房间数、面积分布）。~~
- [x] ~~≥ 6 种功能原型（含至少一个地标类型）各有独立规则通过；家具全部落在房间里且不挡通道。~~
- [x] ~~设计批次可离线运行，零模型调用；模型路径与离线路径产出同一 Schema。~~
- [ ] 复用地标样例做一次目标平台实贴或导入——**未做**，待 018 之后。

验证方式：包络差异见 `test_design_fits_a_tight_envelope`（层数对齐目录，包络紧张时压层高而非砍层）；四个背景共 30 个模板、家具全部落在房间里由 `test_furniture_sits_inside_its_room` 覆盖（"不挡通道"仍未做）；离线路径零模型调用，模型路径只有契约、未启用。

## 明确不做

- 不写方块/三角面几何；设计只产出可校验的参数化描述，几何仍由适配器派生。
- 不做选址（016）与装配（018）；不训练模型。

## 执行记录

| 日期 | 执行者 | 动作 | 结果与证据 | 下一步 |
|---|---|---|---|---|
| 2026-09-26 | root | 根据用户对流水线的重构要求创建本工单 | 本文件与 [docs/04_scene_pipeline.md](../docs/04_scene_pipeline.md)；尚无实现或测试结果 | 先搬 006 的形状规则作为参考实现，再做"平面随包络变化" |
| 2026-09-26 | root | 实现阶段 E：设计 Schema、模板、逐栋设计与校验 | 新增 `src/world_builder/planning/designer.py`、`settings/*/designs.json`、`tools/design_buildings.py`、`tests/test_designer.py`（9 passed）与合同 [docs/contracts/building-design-v0.1.md](../docs/contracts/building-design-v0.1.md)。四个背景 seed 4 全部 `failures=0`：魔法城邦 33 栋（跳过城堡/广场）、现代都市 25（跳过公园）、工业园 10（跳过货场/储罐）、港口 11（跳过堆场/干船坞）；最高 61.6 m 的摩天楼 17 层成功排出，厂房/仓库为单层大空间且净高对齐目录 | 018 把设计写进 WIR 并对接 Minecraft/Unity 适配器 |
| 2026-09-27 | root | 修入口面选择，配合 016 提高密度 | **实际缺陷**：魔法城邦加密后导出在 `target.building_entry: building_site_063` 中断——门是 2.0 m 宽，目标适配器要求门洞离墙角至少 0.3 m、门垛至少 1.0 m（即墙面 ≥ 3.31 m），而设计器直接把入口挂在声明的面上。现在短于此值的墙面会把入口改到**最长的一面**，并让门垛取 `max(1.0, min(0.3×墙长, 墙长 − 门宽 − 0.31))`。原先考虑的"把层高下限从 2.8 提到 3.0"**已撤回**：它会破坏 `test_design_fits_a_tight_envelope` 钉住的"压层高而不是砍层"口径，而短墙面才是真正的失败原因（两者不叠加）。定向测试 `tests/test_designer.py tests/test_scene_brief.py` 25 passed | 继续按 017 分类做 class 1 其余项与 class 2 的 `open_space` |
| 2026-09-27 | root | class 2 第一步：`kind: open_space` 的设计端落地 | 模板新增 `kind`（默认 `building`）与开放空间三键 `paving`/`path`/`fixtures`；词汇 `OPEN_SPACE_PAVING = {stone, path, gravel}`、`OPEN_SPACE_FIXTURES = {lamp, bench, tree, planter}`。新增 `design_open_space()`（铺装 = 场地范围、**一条从临街边穿到对边的 2 m 步道**、固定块按规则排布：灯具沿周界每 8 m、长椅在临街内侧一排、树按 6 m 网格，上限 24 件）与 `validate_open_space()`（不出场地、不超包络高度、固定块在铺装内、步道贴临街边、材质 token 合法），并加 `design()` 作为阶段 E 的统一入口。**测试**：`test_open_space_design_paves_and_furnishes_without_storeys`（24 件固定块、校验 pass、同一输入同一平面）。可视记录 `artifacts/scene-open-space/plaza-design-20260927.png`（铺装灰、步道浅灰、灯/椅/树三色）。**未做（下一轮）**：把开放空间写进 WIR（装配器要分支处理无楼层设计）、两个目标适配器的块渲染，以及给 `settings/*/designs.json` 加 `plaza`/`park` 模板——因此**当前四个背景的导出内容没有变化** | 装配器与适配器接线 + plaza/park 模板 |
| 2026-09-27 | root | class 2 收口：开放空间接进 WIR 与 Minecraft 适配器，plaza/park 模板上线 | ① **装配器**：`OpenSpaceDesign` 走独立分支，产出实体 `open_space_<site>`（`geometry.representation = "ground_plan"`，携带 paving/path token 与局部坐标的固定块表），`validate_scene` 新增 `scene.open_spaces` 并只在建筑设计上检查楼层链。② **适配器**（`0.1.0-city.6` 起）：场景分支按 token 落块——铺装 = 场地范围 0—0.25 m、步道 0.25—0.4 m、固定块 0.25 至（0.25+高度）；`stone→stone_bricks`、`path→smooth_stone`、`gravel→gray_concrete`，`lamp→glass`、`bench→oak_slab`、`tree→oak_fence`、`planter→grass_block`（调色板没有树叶，树因此是"栅栏树干"代理，如实记录）。③ **模板**：魔法城邦加 `plaza`、现代都市加 `park`。**实测 seed 4**：魔法城邦 72 个设计（71 建筑 + 1 广场）、`no template yet` 只剩 `castle`，导出 36 分块 `validation: pass`；现代都市 32 个设计、**`no template yet` 为空**、34 分块 `validation: pass`；两城的方块清单里都出现 `open_space_*`、`*_path` 与 `*_lamp/bench/tree` 盒。④ **两个真实约束**：广场/公园的目录高度只有 0—1 m，而选址给的包络可能低到 0.62 m（古代）甚至 **0.2 m**（现代的 green 街区 height_factor 0.2）——固定块高度改为随包络收缩，包络 < 0.4 m 时只铺装不摆固定块（`wants_fixtures`），并把"green 街区的 height_factor 对地表景观过狠"记进 016 | 目标世界重贴这两套新导出；016 调 green 街区高度因子 |
| 2026-09-27 | root | class 2 补齐堆场：工业园货场、港口集装箱堆场 | 固定块词汇扩到 `crate`（→ `barrel`）与 `stack`（→ `gray_concrete`）——堆场按 5/6 m 网格成排堆放，和树的网格同一套规则；`settings/industrial_park/designs.json` 加 `freight_yard`、`settings/harbour/designs.json` 加 `container_yard`（均为 `kind: open_space`，铺装 gravel、步道 stone）。**实测 seed 4**：工业园 16 个设计（+1 货场），缺失清单从 `freight_yard, silo_tank` 缩到 **`silo_tank`**，33 分块 `validation: pass`；港口 36 分块 `validation: pass`，缺失清单从 `container_yard, dry_dock` 缩到 **`dry_dock`**——但港口**设计数仍是 13**：堆场类型在港口选址里 demand 1 / placed 0（016 早先记录过），模板有了、场址还没有，如实记录不当作已完成 | 016 让港口堆场拿到场址；class 3（圆柱 silo、船体、干船坞、城堡多体量）等新几何词汇 |
| 2026-09-27 | root | class 3 首项：**多体量组合 `kind: compound`**，城堡落地 | 模板第三种类：`{"kind": "compound", "parts": [{role, height_m, roof}, …]}`，角色词汇 `{wall, tower, keep, hall}`。新增 `design_compound()`：幕墙（临街边留 4 m 门洞，因此是两段）、四座角塔（贴幕墙内face，不与墙体重叠）、中央主楼、靠里侧的大厅；每件都按包络**等比缩放**（模板给绝对高度，包络放不下时整体缩，塔楼 18 m→主楼 14.7 m→大厅 8.2 m→幕墙 6.5 m 保持剪影，不会拍成一样高）；包络太窄时宁可少一件（大厅放不下就不放），校验 `validate_compound()` 管"在场地内、不超包络、有墙塔主楼、两两不重叠"。装配器产出 `compound_<site>` 实体（`representation: compound`，parts 走局部坐标），`validate_scene` 新增 `scene.compounds`；Minecraft 适配器把每件落成**中空壳体 + 屋顶**（墙/塔/主楼用 `smooth_stone`、大厅用 `oak_planks`，屋顶按 flat/gable/spire），因此城堡是空心的、内部天井留白而不是实心大方块。`settings/arcane_medieval/designs.json` 加 `castle` 模板。**实测 seed 4**：魔法城邦 **74 个设计（72 建筑 + 1 广场 + 1 城堡）**，`no template yet` **首次为空**；导出 36 分块 / 2,719 盒 / 665,060 方块 / `validation: pass`，其中城堡 **61 个盒**（5 段幕墙 × 5 + 4 角塔 × 6 + 主楼 6 + 大厅 6）。布局图 `artifacts/scene-open-space/castle-layout-20260927.png`。**未做**：城堡没有室内、没有门楼与坡道，护城河依赖 014 的地形开挖 | class 3 其余（圆柱 silo、船体、干船坞）与城堡室内 |
| 2026-09-27 | root | 城堡幕墙改为**圆形环绕**（对应用户点名的"圆形环绕的城墙"） | 模板加可选键 `"ring": "rectangle" | "circle"`：圆形时幕墙沿一条**多边形圆环**铺（弦长按半径取 16—32 段，段盒用弦的外接盒，半径 = 短边一半 − 1.5 m），临街方向的弧段按门宽跳过留出城门；四座塔**跨在墙环上**（塔身与墙体重叠是允许的——它们本来就是同一条墙线），大厅因为"圆环没有直的远墙"改为放在环内、正对城门的内侧，并按半径收缩到四角不撞墙。`validate_compound()` 相应放宽："墙段之间可以相接/重叠（同一道墙线），其它结构两两必须留空"。**实测 seed 4**：城堡 38 件（32 段墙 + 4 塔 + 主楼 + 大厅）、场地内/不超包络/无结构重叠全部 pass；导出 36 分块 / 2,853 盒 / 665,884 方块 / `validation: pass`。布局图 `artifacts/scene-open-space/castle-ring-20260927.png`。矩形环仍是默认值（其它背景/紧凑场地可用） | 城堡室内与门楼；class 3 其余（圆柱 silo、船体、干船坞） |
| 2026-09-27 | root | 用户评审 E 阶段：建筑既没美感也没设计感、功能也不全 → 落 skill + 记缺陷 | 用户原话：E 阶段"完全是自己想怎么构造就这么构造，造出来既没有美感，又没有设计感（所有建筑都是四方建筑，没有特性），功能性又缺失（**只有一层楼梯，不能到达其他楼层**）"。本轮① 新增 [skills/building-design/SKILL.md](../skills/building-design/SKILL.md)：十条规则（体量 2—4 个且高差 ≥2 m、开间:进深 1.0—1.6、层高 ≥3.0 m、立面深度靠腰线/出檐≥0.6 m/勒脚/角柱、屋顶原型与出檐、材质 3—4 种靠明度区分、入口 2.0×2.4 m 与门垛 ≥1 m、**每层都要有可达楼梯**、每层 ≥2 间用途房间+通道、每 6—8 m 一扇窗、与环境的关系）+ 机器校验清单 + 能力边界（只有轴对齐盒/退台/三种屋顶，圆柱与自由曲面还没有）+ 来源与访问状态（Wiki《Tutorial:Construction》可读、直连被 Cloudflare 403、`Building tips` 等页面不存在、DuckDuckGo 返回人机验证按规则不破解）+ 明确标注哪几条是**设计判断**而非文献结论。② 新增 `tests/test_building_skill.py` 钉住 skill 存在、九类主题齐全、关键数字（3.0/0.6/2.0/2.4/1.0/0.3 m）与能力边界/来源都在。**未做（按用户评审拆成下一批）**：a) 竖向交通只到二层——设计师每层都要出楼梯、适配器要渲染多部梯并逐层复核井与落点；b) 体量与立面深度还没进模板（现在同类型建筑仍是同一个盒子，只靠尺寸与退台分异）；c) 采光/窗户、门廊台阶、与环境的高度协调都还没有对应字段 | a) 多部楼梯与逐层可达；b) 给模板加体量组合与立面线脚字段；c) 用 skill 的十条规则逐条补设计与校验 |
| 2026-09-27 | root | 按用户追加要求联网扩充建筑 skill | 查阅 Minecraft 官方建造教程/访谈，以及 UNESCO、Historic England、English Heritage、NPS 关于东亚、欧洲、西亚/北非、南亚、西非、美洲及近现代建筑的案例资料（链接与访问日期逐卡记录）。将 skill 改为索引 + 三份参考卡：13 个历史/地方卡、6 个近现代/工业卡、10 类功能空间与七步建造流程；把旧版“一律 2—4 体量/≥2 房/≤4 材质”等经验规则降为有条件的设计选项，入口尺寸与门垛仍单独标为当前适配器约束。`skill-creator` 首次快检因 Windows 默认 GBK 解码 UTF-8 失败，设置 `PYTHONUTF8=1` 后为 `Skill is valid!`；`pytest tests/test_building_skill.py -q` 为 1 passed；最终项目文档检查 87 Markdown/118 本地链接/6 JSON/21 工单、零错误。新卡是研究与设计转译，**尚未进入生成器，也没有目标平台样件** | 从一栋具体建筑开始按风格卡做设计、导出、同视角观感与逐层通行验证；优先解决多层楼梯和窗/立面词汇 |

| 2026-09-27 | root | 按风格卡完成首个木构街屋双目标样件 | [021](021_style_building_cross_target_sample.md) 手工 20×18×12 m 店住楼已在 Unity 和 Minecraft 分别加载、截图、连续走通一层入口与楼梯至二层。证明该参考卡能指导一个具体样件；尚未证明 E 设计器可以自动选样式、生成相同细节。目标侧仍见 Minecraft 室内缺固定照明、屋顶退台和木框缺细部 | 将楼梯井/入口净空、照明采光与立面屋顶词汇提入设计契约和模板，选第二种跨文化/现代风格再做对照 |

## 交接说明

开始前重读 006 的 shapes/interiors 规则、008/009 适配器的失败教训与 docs/04 §3.2；完成有结果的动作后更新执行记录。

## 剩余模板的分类判断（2026-09-27，下一轮的入口）

把"缺模板"的类型按**能否用现有形状词汇诚实表达**分三类，避免下次盲目开工：

1. **可以直接补**（盒 + 退台 + 平顶/双坡/尖塔即可）：`transit_hub`（单层大跨候车厅）、`school`/`hospital`/`government`（低层板楼，先给两间房平面即已优于现状）、`rail_line` 类已有走廊、`customs_house`（已给双坡门廊近似）。这些属于"模板工作量"，不需要新词汇。
2. **需要新的设计种类：开放空间**（当前设计器只会产"有楼层的建筑"）：`plaza`（魔法城邦）、`park`（现代都市）、`courtyard`、`container_yard` 的堆场部分。它们的高度上限只有 0—2 m，本质是**地表设计**：铺装、步道、树/灯/长椅成排、边界矮墙。建议在模板里加 `"kind": "building" | "open_space"`，`open_space` 走一条独立分支：不产生楼层/房间/楼梯，只产生地面铺装 + 固定块（树、灯、长椅、花坛）与一条穿过它的步道；校验规则改为"不出包络、不超高、与道路连通"。**这是设计决策，不是笔误修补**，故本轮只记录不动手。
3. **需要新几何词汇**：`silo_tank`（圆柱）、`cargo_ship`（船体自由曲面）、`dry_dock`（下沉开挖，依赖 014 的真实地形开挖）、`castle`（主楼 + 塔楼 + 内院 + 幕墙的组合体，等于"多体量建筑"而不是单体量）。这些应当在"多体量建筑"或"圆柱/自由曲面"成为源侧词汇之后再做，否则只能做出失真的盒子。

下一轮的推荐顺序：先做第 1 类里最影响观感的（`transit_hub`、`school`、`hospital`、`government`），再做第 2 类的 `open_space` 分支（一次性解决 plaza/park/yard），第 3 类等词汇扩展。
