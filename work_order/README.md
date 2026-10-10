# 工单索引与协作流程

**2026-10-10 后续工单规划**：[028](028_followup_work_order_planning.md) 创建 029—038，覆盖通用场景任务、按能力调度、自然资产、稳定修订、局部修改、反馈工作台、平台配置/适配及历史状态核对。实施工单均 planned，024 分批真实验收，011 为独立可选扩展。当前顺序见 [总规划](000_project_master_plan.md)“当前实施路线”；旧日期段落与 006/013—022 状态属于对应历史路线，不应直接当作新增产品任务。

**2026-10-10 本地分支职责调整**：[027](027_branch_role_alignment.md) 将 API Agent 分支设为 `main`，原 `main` 完整保留为 `codex/local-validation`。远端未修改，两条本地分支暂未配置 upstream。场景调度、用户修改闭环和平台适配仍处于讨论阶段，本轮没有实现这些能力。

**2026-09-30 桌面应用完成**：[026](026_windows_desktop_application.md) 交付独立 WebView2 窗口与约 15 MB Windows 便携包，内含 Python、网页、契约和 skills；历史及非密钥设置保存在用户目录。95 项回归通过，exe 包内样例/回放、原生下载、关闭释放与重开历史/预览恢复通过。真实模型质量仍由 024 验收。

**2026-09-29 网页测试台完成**：[025](025_modular_web_workbench.md) 交付模块化本地应用：双击启动、API 设置、样例/回放、A—F 进度、历史、取消、源几何旋转/剖切/拾取、Skill/Schema/JSON 检查和下载。20 项新增测试加 36 项流水线回归共 56 passed；浏览器样例/回放/下载和两种布局实际验收通过。接口、任务服务与前端模块分离；真实 API 质量仍由 024 验收，007 完整编辑器另行实施。

**2026-09-29 模型驱动分支离线闭环完成**：[023](023_api_agent_pipeline.md) 在 `codex/api-agent-pipeline` 实现 API 驱动 A—F、六份实际运行 skill、严格 JSON 契约、预算、限定返工与回放。完整回归 220 passed；最终人工响应样例和回放均输出 45 网格 GLB、2707 方块 schematic，世界包/GLB 哈希一致。真实 API 使用 `yourapi` 占位；模型质量与目标实走未验收，后续 [024](024_api_agent_live_evaluation.md) 为 planned。

**2026-09-29 014 第二处收口：城堡/筒仓/开放空间跟随地面**：核对 manifest 时发现整座城堡**根本没被抬升**——记录包络已在 16.67…34.67，适配器发出的 336 个盒子却停在 0…21.6，而同足迹的地形壳在 15.52…18.04（城墙 6.5、门楼 9.8、主楼 14.7 全在地下）。根因是 `_compound_boxes`/`_cylinder_boxes`/开放空间铺装都按**设计自身的基准面**发盒，地面跟随只抬「相对记录」的几何。新增 `_raised()` 按 `bounds.min.z` 偏移后重导：与上一版逐格比对**只有 2 块变化**（含城堡的 `c01_01` 48,739 → 47,266、含广场的 `c02_02` 56,615 → 55,203），两块先清窗（各清掉 589,824 方块）再贴，`blocks affected` 与 manifest 逐字相等；探针显示主楼楼板从世界 −55 抬到 −39、`RELOAD_*` 在重载后仍命中，俯视图可见**城堡立在地表之上**（此前埋在土里）。完整回归 184 passed、文档检查零错误。详见 [014](014_terrain_plan.md)、[017](017_building_designer.md)、[022](022_scene_reconstruction_new_world.md)。

**2026-09-29 014 挖方落地：干船坞跟随地面，基坑真正敞开**：`_dock_boxes` 改为按记录自身的 **grade**（`bounds.min.z + depth_m`）发盒，于是地面跟随把干船坞一起抬到采样地面上——重导港口后与上一版逐格比对**只有含船坞的那一块变了**（71,934 → **65,715** 方块，盒数 14,801 不变、9 个 dock 盒整体 +7.6 m），实贴 `blocks affected = 65715` 与 manifest 逐字相等；探针确认地表被挖穿（`(47,−54,4056)` 空气）、坑底板与吊梁在预期高度，落盘走 Esc → Save and Quit to Title 并重载复核。**同轮查出的重要事实**：本环境里 **`//paste -a` 不会清除既有方块**（同一格连贴两次仍是旧雕纹石英，只有 `//set air` 清得掉）——所以以前"逐块核对 `blocks affected` 与 manifest 吻合"只能证明非空气方块放对了，不能证明空气格被清空；这次一个 chunk 窗口用 `//set air` 清出 **589,824** 个方块，说明 band 3 里仍积压着旧版本的实心填充。下一轮把其余 35 块（以及 band 0/1/2 抽查）按「先清窗、再贴」重做。详见 [014](014_terrain_plan.md)、[017](017_building_designer.md)、[022](022_scene_reconstruction_new_world.md)。

**更正（2026-09-29，对下一段）**：下面一段把 `_berth_boxes`（码头/岸壁）与 `_vessel_boxes`（船体）也算作"不参与地面跟随"的缺陷——本轮核对 manifest 后更正：它们的绝对标高是**水面相对**的（水面 z≈0，码头面 1.6…2.6 m、船体浮在水面高度），这是正确行为；真正需要跟随地面的只有干船坞，本轮已改。

**2026-09-29 band 3 收口 + 干船坞深度修正**：把 `settings/harbour/designs.json` 的 `dry_dock.depth_m` 由 5 m 改为 **3 m**（世界下限 −64，本带基线把局部 0 放在世界 −60，5 m 的坑底落在世界底之下），重导港口得 36 分块 / **885,778** 非空气方块 / `validation: pass`，与旧版逐格比对**只有带干船坞的那一块**变了；该块重贴后 `blocks affected = 71934`，与 manifest **逐字相等**（上一轮同一块只有 65,320 = 被世界底截掉 7,840），坑底/盆体/闸槛/龙门吊探针全部命中，落盘走 Esc → Save and Quit to Title 并重载截图复核。**至此 band 3 = 36/36 块与 manifest 吻合**。**新发现（负面，未修）**：`_dock_boxes`/`_berth_boxes`/`_vessel_boxes` 按**绝对基准面**发盒、**不参与地面跟随**，所以起伏开启后干船坞处在**地表薄壳（一格一块地表 + 台阶立面）下约 6 m 的空腔**里——坑体在、但不敞开；下一轮把这三处改为跟随记录抬升后重导重贴。详见 [014](014_terrain_plan.md)、[017](017_building_designer.md)、[022](022_scene_reconstruction_new_world.md)。

**2026-09-28 022 阶段性完成**：新存档 `WB Scenes Rebuild` 里四条带（band 0 魔法城邦 / 1 现代都市 / 2 工业园 / 3 港口）全部重贴为"最终版生成器"的产物，136 个分块的 `blocks affected` 与各自 manifest 逐块吻合；生成器本阶段补齐每层可达楼梯、体量分异退台、勒脚、角柱、入口台阶与门廊、采光窗与四套背景风格词汇。可视记录：每带俯瞰 + 斜俯视、跨带总览三张、band 0 建筑立面近景。完整回归 161 passed、`tools/check_project_docs.py` 零错误。**未达标**：近景仍是方块化体量、屋顶为平板；副本 `LevelName` 未改（需世界关闭后改 NBT）。下一阶段回主线：城堡室内与门楼/坡道、门廊立柱与按风格窗型、class 3 剩余形态、016/018/009 的遗留项。详见 [022](022_scene_reconstruction_new_world.md)。

**2026-09-28 主线 a 落地（城堡门楼/引道 + 城堡室内）**：[017](017_building_designer.md) 新增 `gate`/`ramp` 角色，城堡有了门墩 + 跨洞口门楣的门楼、门口平台与两侧踏步、按层层楼板与逐层直跑梯的主楼室内，以及主楼/大厅的门洞；冲突判据改为三维。seed 4 魔法城邦 36 分块 / 4,046 盒 / 669,049 方块、`validation: pass`，完整回归 **162 passed**、文档检查零错误。**未达标**：1 m 体素下踏步落在同一层，实贴为与地面齐平的铺装引道而非抬高坡道；塔楼仍实心；尚未重贴进新存档。详见 [017](017_building_designer.md)、[018](018_assembler_pipeline.md)。

**2026-09-28 主线 a 实贴 + 主线 b（窗型/门廊立柱）**：带门楼/引道/室内的城堡已重贴进 `WB Scenes Rebuild` band 0（36 分块逐块与 manifest 吻合）；随后按 skill 规则 4/9 补**按背景的窗型**（窄高木框 / 连续带窗 / 中梃高窗 / 石框方窗，含窗樘、窗台、窗楣，矮层由层间腰线代替窗楣）与**门廊立柱**。四场景 seed 4 复导 `validation: pass`，完整回归 **163 passed**。**未达标**：真正的拱窗与券洞需要新几何，尚未实现（也未声称）；东西两面尚未开窗；新内容尚未重贴进新存档。详见 [017](017_building_designer.md)、[018](018_assembler_pipeline.md)、[022](022_scene_reconstruction_new_world.md)。

**2026-09-28 band 0 换版（窗型实贴）**：band 0 已换成带框窗 + 门廊柱的版本。第一遍贴完进游戏看立面后**自我否决**——1 m 窗洞被两侧深色橡木窗樘压没（正是 historic-and-vernacular 卡点名的禁忌），于是把古代窗洞加宽到 2 m 重导、**再清一次重贴**，36 分块两遍都逐块与 manifest 吻合。截图五张在 `artifacts/minecraft-scene-mainline-b/arcane_medieval/target-20260928/`。**待办**：band 1/2/3 仍是上一版 `rebuild-4` 内容。详见 [017](017_building_designer.md)、[022](022_scene_reconstruction_new_world.md)。

**2026-09-28 band 1 换版**：现代都市（band 1）也已换成主线 b 版本——34 个分块按列清空后重贴，逐块 `blocks affected` 与 manifest 吻合（合计 810,765 非空气方块，清单缺的两格跳过）。街面截图可见成排水平带窗（4 m 玻璃 + 浅灰混凝土窗樘/窗楣）。完整回归 **163 passed**、文档检查零错误。**待办**：band 2/3 仍是上一版；本带未走室内。详见 [022](022_scene_reconstruction_new_world.md)。

**2026-09-28 band 2 换版**：工业园（band 2）也已换成主线 b 版本——34 个分块逐块与 manifest 吻合（合计 590,783 非空气方块，缺的两格跳过）。过程失败如实记录：外来窗口抢焦点导致游戏暂停、三条清带命令静默失效；`//pos1` 两次丢失造成选区合并；均靠 `latest.log` 复核发现并重做。曾试图用 `/gamerule doDaylightCycle false` 固定白天，**但命令被拒（`Incorrect argument for command`），两次都没生效**——该说法已更正。完整回归 **163 passed**、文档检查零错误。**待办**：band 3 仍是上一版。详见 [022](022_scene_reconstruction_new_world.md)。

**2026-09-28 四带换版完成**：港口（band 3）也换成主线 b 版本——36 个分块逐块与 manifest 吻合（合计 612,922 非空气方块）。**至此 `WB Scenes Rebuild` 的 band 0/1/2/3 全部是带框窗 + 门廊立柱的版本**，四带共 140 分块、逐块核对通过，截图分别在 `artifacts/minecraft-scene-mainline-b/<setting>/target-20260928/`。过程记录：本轮探针命令 2 分钟后才入库（服务器滞后，非暂停）。完整回归 **163 passed**、文档检查零错误。主线 b 的目标侧工作收口，下一轮起回主线 c)（class 3 剩余几何）或 e)（018 失败按作用域回馈）。详见 [022](022_scene_reconstruction_new_world.md)。

**2026-09-28 主线 c 第一项：圆柱 `silo_tank`**：[017](017_building_designer.md) 新增第三种设计种类 `kind: "cylinders"`——模板给直径/高度/数量/盖型，规则在场地内按 2 m 服务间距布罐、场地偏窄时**减少数量而不是把罐压成管子**；目标侧第一次出现**非轴对齐盒**的几何：每只罐是**弦盒环 + 基座盘 + 分层穹顶**，壳体保持中空。工业园 seed 4 设计数 16 → **18**，导出 34 分块 / **1,907 盒** / **594,303 方块** / `validation: pass`，且工业园的 **`no template yet` 首次为空**（罐体 116 盒：基座 28 + 壳 48 + 穹顶 40）。完整回归 **165 passed**、文档检查零错误。**未做**：`cargo_ship` 与 `dry_dock`；城堡圆塔仍是盒环；工业园新版本尚未重贴进新存档。详见 [017](017_building_designer.md)、[018](018_assembler_pipeline.md)。

**2026-09-28 主线 c 第二项：船体 `cargo_ship`**：查清缺口不在选址而在目标侧——016 早已把两艘货轮排成折线（`work_002/003`，73.5 m 系泊线 + 12.2 m 船宽），但导出里 `cargo_ship` **方块数为 0**。本轮让投影层不再把船压成走廊盒，适配器新增 `_vessel_boxes()`：沿系泊线 **30 段断面、船中 1.0 → 首尾 0.38 线性收分**，下红上灰、加甲板、艉船楼与烟囱；调色板补红/白/黑三色。港口 seed 4 导出 36 分块 / **2,412 盒** / **621,768 方块** / `validation: pass`（船体 184 盒）。完整回归 **167 passed**、文档检查零错误。**同轮核实**：`pier`（2 座）与 `quay`（1 段）在导出里**同样是 0 盒**——码头几何列为下一项；`dry_dock` 仍待 014 开挖。详见 [017](017_building_designer.md)、[018](018_assembler_pipeline.md)。

**2026-09-28 主线 c 第三项：码头与岸壁**：新增 `_berth_boxes()`——码头＝木梁 + 石甲板架在水面上，岸壁＝0→3 m 的整块石面（桩不逐根建模，理由写在代码里）。港口 seed 4 导出 36 分块 / **2,678 盒** / **648,902 方块** / `validation: pass`（码头 56 盒、岸壁 210 盒、船 184 盒），平面图 `artifacts/scene-mainline-c/harbour/berths-20260928.png`。完整回归 **168 passed**、文档检查零错误。**新发现未修**：船的系泊线与码头走廊在码头头部**重叠约 6 × 14 m**，船实际是从码头里穿过去停的——这是 016 侧的避让缺失。详见 [017](017_building_designer.md)。

**2026-09-28 修掉「船穿码头」（016）**：`cargo_ship` 的定位从「最近水面 + 平行岸线」改为**搜索式**：外移 0—80 m、沿岸 ±64 m 步进，接受条件是**不压任何已排码头/岸壁走廊**且**整条水线都在水里**，找不到就不放船。实测港口 seed 4：两艘船水线取样 21/21 在水里、与码头重叠 **0**（此前 1 艘半搁浅、2 处重叠）；重导 36 分块 / 2,678 盒 / **649,832 方块** / `validation: pass`。新增 `test_a_ship_is_moored_clear_of_the_berths`。完整回归 **169 passed**、文档检查零错误。**不足**：船是停在码头外侧的安全水域，并非严格贴靠码头侧壁。详见 [016](016_district_siting.md)、[017](017_building_designer.md)。

**2026-09-28 主线 c 内容实贴（用户指示「继续朝实际落地推进」）**：**band 2（工业园）与 band 3（港口）已换成本轮产物**——工业园有**阶梯化筒仓**（两张圆筒 + 分层穹顶，游戏内可见），港口有**船体、两座码头与岸壁**。band 2 34 分块（594,303 方块）、band 3 36 分块（**649,832** 方块）逐块 `blocks affected` 与 manifest 吻合。过程事故：band 3 第一遍清带有一次 `//pos1` 丢失；随后**游戏再次卡死**，按用户指示强制重启，band 2 已落盘、band 3 重做。**存档教训**：`/save-all` 被输入通道弄坏、暂停保存也没落盘，最终用「Save and Quit to Title」才写盘（band 3 的 9 个区域文件 16:34:17 更新），**重新载入世界后再截图**确认内容来自磁盘。截图见 `artifacts/minecraft-scene-mainline-c/{industrial_park,harbour}/target-20260928/`。完整回归 169 passed、文档检查零错误。

**2026-09-28 主线 e：失败按作用域回馈**：[018](018_assembler_pipeline.md) 新增 `design_sites()`——逐块设计，失败**只在该块内重试**：先按原包络，再把同一包络内收 10% / 20% 重试，三次都失败才丢弃该块并记录 `{site_id, type, code, attempts, shrink}`，其余地块照常设计，**不重跑整城、不放宽 brief**；两个工具（`assemble_scene.py` / `design_buildings.py`）改用它，后者顺带修掉「只认建筑」的既存缺陷（对 compound/cylinders 会 AttributeError）。四背景 `failures=0`（74 / 32 / 18 / 14）。完整回归 **170 passed**、文档检查零错误。**未做**：街区重划与回到 014；另一处验证缺口——设计器对 1×1 m 或 `max_height_m=1.0` 这类极小包络**不抛错**（事后校验才判 fail），因此「悄悄越界」尚未被作用域回馈覆盖。详见 [018](018_assembler_pipeline.md)。

**2026-09-28 包络底线 + 输入口径统一**：① 设计器补三道**包络底线**并抛 `design.envelope`——平面放不下梯井 + 两间房（6×5 m）、没有任何一面墙放得下 2 m 门洞、层高 + 屋顶超出包络高度。上一轮记录的空洞（1×1 m 也「设计成功」、`max_height_m=1.0` 产出 3.2 m 建筑）**已闭合**；四背景 `design_sites` 仍零失败（74/32/18/14），说明没有地块被误伤。② 修掉 [016](016_district_siting.md) 要求的输入口径不一致：`tools/design_buildings.py` 原本给 `--setting` 自拼「<setting> scene」提示词，导致同背景在它这里 13 个设计、在 `assemble_scene.py` 里 14 个；现在 `--setting` = 该背景登记的 `default_prompt`，四背景两工具数字逐一同为 **74 / 32 / 18 / 14**，且 `--setting` 与 `--prompt <登记文本>` 的产物 JSON 逐字节相同。完整回归 **172 passed**、文档检查零错误。

**2026-09-28 主线 c 收口：干船坞 `dry_dock`**：新增第四种设计种类 `kind: "dock"`——基坑取场地减作业边距、坑底在标高下、闸门开在朝水那面、另给龙门吊高度；适配器新增 `_dock_boxes()`，**用 `minecraft:air` 的基坑体真正挖穿地面与水面**（这是整条流水线唯一会移除方块的地方），并把它排在所有盒子之后，避免被街道/建筑填回。港口设计数 14 → **15**，导出 36 分块 / **2,687 盒** / **652,938 方块** / `validation: pass`，**港口的 `no template yet` 首次为空**（干船坞 9 盒：基坑 + 坑底 + 3 壁 + 闸槛 + 龙门吊 3）。完整回归 **174 passed**、文档检查零错误。**未达标**：基坑只挖穿地表那两层（真实下沉要等 014 的地形开挖）；龙门吊只是剪影；新港口尚未重贴进世界。详见 [017](017_building_designer.md)。

**2026-09-28 band 3 再次换版（干船坞实贴）**：新港口（含干船坞）已重贴进 `WB Scenes Rebuild` band 3——36 分块逐块 `blocks affected` 与 manifest 吻合（**652,938** 方块）。清带助手这轮加了**选区丢失重试**（affected < 100 万即判 `//pos1/pos2` 丢命令并整列重做）。落盘沿用教训：不依赖 `/save-all`，直接用 **Esc → Save and Quit to Title**（band 3 的 9 个区域文件 18:09:55 更新），**重新载入世界后截图**确认基坑与龙门吊来自磁盘。至此 **band 0/1 = 主线 b、band 2/3 = 主线 c**（筒仓、船、码头、岸壁、干船坞齐备）。完整回归 **174 passed**、文档检查零错误。详见 [022](022_scene_reconstruction_new_world.md)。

**2026-09-28 主线 e 第二项：`.worldpkg` 端到端回放**：把场景包提交仓库时直接失败（`resource.missing`），查出**两个既存缺陷**——① 高度场资产的**字节从未写下来**（只记了 hash），场景包因此不自洽、根本无法归档；② 记的 hash 与写的字节**不是同一个对象**（`digest` 漏了 `axes`/`origin`），补上字节也会被 `hash_mismatch` 拒收。修法：装配器新增 `asset_sink` 回调把 `(record, payload)` 交给调用方（不改变返回类型），并让 payload 与 checksum 由同一个资产体产出。**回放结果**：港口包 → `.worldpkg`（`sha256:a09f9a848a6fb69a…`）→ 读回的包与原包完全相等；**回放包再导出 Minecraft 得 36 个分块、`schem_sha256` 与直接导出逐一相同**、非空气方块同为 652,938。`tools/assemble_scene.py` 新增 `--worldpkg`。新增 `tests/test_scene_package_replay.py`；完整回归 **176 passed**、文档检查零错误。详见 [018](018_assembler_pipeline.md)。

**2026-09-28 016 遗留：地表景观包络复核**：把四类开放空间的**声明高度**与适配器**实际画出**的高度逐一对照，发现四处对不上—— plaza 包络只有 **0.62 m**、park **1.0 m**（都低于自己画的 1.25 m 固定块）；freight_yard / container_yard 却写着 **4—12 / 3—10 m**（那是房子的高度，而这两类只铺地堆物、从不盖楼）。按事实改目录：plaza `[0.5, 1.5]`、park `[0.5, 2.0]`、两类堆场 `[1.0, 2.0]`。实测包络变为 **1.25 / 1.25 / 1.72 / 1.80 m**，固定块仍各 32 件，四背景设计数与失败数不变。新增 `test_surface_landscapes_declare_a_height_that_covers_their_furniture`。完整回归 **176 passed**、文档检查零错误。详见 [016](016_district_siting.md)。

**2026-09-28 城堡塔楼改为真正的圆塔**：复合体量的 `parts` 新增可选 `shape`（`box`/`round`），城堡的四座角塔声明 `round` 后改用与筒仓同一套**阶梯弦盒环**，塔尖变成逐层收缩的锥；环半径取「预留方框一半减半个墙厚」，保证**整圈墙内接在预留包络内**。实测魔法城邦：城堡 336 盒（塔环 48 = 4×12 段弦、塔尖 64），整场景 36 分块 / **5,132 盒** / **669,887 方块** / `validation: pass`，设计数 74、缺失为空。完整回归 **178 passed**、文档检查零错误。**未做**：band 0 尚未重贴这一版（世界里城堡的塔仍是方的）。详见 [017](017_building_designer.md)。

**2026-09-28 band 0 换圆塔版并实测**：36 分块逐块 `blocks affected` 与 manifest 吻合（**669,887** 方块）；Esc → Save and Quit to Title 落盘（band 0 的 9 个区域文件 19:32—19:37 更新），**重新载入世界后截图**确认圆塔来自磁盘（俯瞰可见圆形幕墙 + 四角塔 + 中央主楼）。当前版本对照：**band 0 = 主线 f**（圆塔 + 门楼 + 引道 + 主楼室内 + 带框窗），band 1 = 主线 b，band 2/3 = 主线 c（筒仓/船/码头/岸壁/干船坞）。完整回归 **178 passed**、文档检查零错误。详见 [022](022_scene_reconstruction_new_world.md)。

**2026-09-28 城堡室内的目标侧验收**：先在**本机**用 `voxelize()` 按同一顺序体素化 manifest 反查目标坐标的方块，再用游戏里的 `/execute if block … run say <探针>` 逐点核对并读日志判定。六条探针**全部命中**：一层楼板（y −56）、二层楼板（y −51）、踏步（y −60）都是深色橡木，门洞（x152/z910）是空的、紧邻墙垛是实心石、对照组墙上确有石。两次探针落空也查明原因：一次把踏步的 y 猜低一层（世界 y = 局部 −60），一次把门猜在**东面**（门其实开在 siting 给的 **north** 面）。截图 `keep-upper-floor-20260928.png`（站在二层楼板上）与 `keep-interior-20260928.png`（一层看向门洞）。完整回归 **178 passed**、文档检查零错误。**未做**：用控制器连续走一遍上下楼。详见 [017](017_building_designer.md)。

**2026-09-27 风格建筑双目标样件**：[021](021_style_building_cross_target_sample.md) 已完成；同一木构街屋设计导出 Unity GLB 和 Minecraft Sponge v3。v5 在 Unity 目标导入/重开 143/143 构件通过，1.8 m 控制器连续走通门、商铺、楼梯、二层房间；Minecraft 在 `WB Verify Flat` 实贴 1,571 方块，生存模式同路线从街道连续走到二层居室，两端目标截图与检查点已留证。手工样件尚未接入通用 E 设计器。

**2026-09-27 最新状态**：008/009/016/017/018 保持 `in_progress`。开放空间代表样件已在两目标推进：Minecraft 广场 1 分块、公园 2 分块实贴且路径/灯具探针通过；广场冒险模式落地和脚下方块验证通过，自动输入未能完成连续实走。Unity 同修订广场 34 构件导入与重开通过，新增 Play Mode 控制器沿源步道 3/3 检查点连续通行。完整场景导出/漫游仍未验收；证据见 [008](008_unity_export.md)、[009](009_minecraft_schematic_export.md)、[018](018_assembler_pipeline.md)。此前冻结 20 例复跑 20/20 通过。

**2026-09-27 建筑 skill 调研扩充**：按用户要求，017 将原十条通用建议修订为 [skill 入口](../skills/building-design/SKILL.md)和历史/地方、近现代/工业、功能/流程三份参考卡；覆盖 13 个历史及地方风格案例、6 个近现代与工业案例、10 类功能空间。逐卡附 Minecraft 官方、UNESCO、Historic England、English Heritage 或 NPS 来源，区分案例事实与项目转译；取消跨风格的体量数、房间数和材质数硬规则。资料卡尚未驱动生成器，建筑观感和多层通行仍需目标样件验证。详见 [017](017_building_designer.md)。

更新日期：2026-10-10。

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
| 007 | [本地三维查看与增量编辑](007_local_viewer_editor.md) | planned | 待认领 | 005、023、032、033；复用 025/034 |
| 008 | [Unity 场景导出与加载验证](008_unity_export.md) | in_progress | root | 005；新主线适配归 036，007 联调单列 |
| 009 | [Minecraft Java 区域导出](009_minecraft_schematic_export.md) | in_progress | root | 005；新主线适配归 036，007 联调单列 |
| 010 | [Minecraft Java 独立世界导出](010_minecraft_world_export.md) | planned | 待认领 | 009、035、036；输出形态需求明确后 |
| 011 | [IFC 建筑概念模型验证](011_ifc_concept_export.md) | planned | 待认领 | 005；专业工程用途明确后的独立扩展 |
| 012 | [大区域与资源扩展验证](012_large_world_benchmarks.md) | planned | 待认领 | 024、030、031、033、036；必要查看/加载性能子项 |
| 013 | [场景简报（流水线 A）](013_scene_brief.md) | in_progress | root | 005 |
| 014 | [地形方案（流水线 B）](014_terrain_plan.md) | in_progress | root | 013 |
| 015 | [风物目录与背景包（流水线 C）](015_landmark_catalogue.md) | in_progress | root | 013 |
| 016 | [区块归属与选址（流水线 D）](016_district_siting.md) | in_progress | root | 014、015 |
| 017 | [单栋建筑设计器（流水线 E）](017_building_designer.md) | in_progress | root | 015、016 |
| 018 | [装配器与场景流水线（流水线 F）](018_assembler_pipeline.md) | in_progress | root | 013—017 |
| 019 | [Minecraft 本机启动恢复](019_minecraft_recovery.md) | done | root | 无；参考 009、018 |
| 020 | [场景道路走廊栅格化与地面填充顺序](020_scene_corridor_rasterization.md) | done | root | 018、016 |
| 021 | [风格建筑双目标样件](021_style_building_cross_target_sample.md) | done | root | 017、008、009 |
| 022 | [新存档四场景重构](022_scene_reconstruction_new_world.md) | in_progress | root | 013—018、017、009 |
| 023 | [API 模型驱动 A—F 流水线](023_api_agent_pipeline.md) | done | root | 005、013—018、008/009 |
| 024 | [真实 API 与目标平台验收](024_api_agent_live_evaluation.md) | planned | 待认领 | 首批 023、008/009；新增批次 031、034、036 |
| 025 | [模块化本地应用与网页测试台](025_modular_web_workbench.md) | done | root | 023、005 |
| 026 | [Windows 桌面应用初版](026_windows_desktop_application.md) | done | root | 023、025 |
| 027 | [本地主线与验证分支职责调整](027_branch_role_alignment.md) | done | root | 023、025、026 |
| 028 | [场景搭建后续工单规划](028_followup_work_order_planning.md) | done | root | 027 |
| 029 | [通用场景需求与任务契约](029_scene_task_contracts.md) | planned | 待认领 | 023、028 |
| 030 | [能力驱动的任务调度与作用域返工](030_capability_task_runtime.md) | planned | 待认领 | 029、035 |
| 031 | [自然景观资产与分布构建](031_natural_scene_assets.md) | planned | 待认领 | 029、030、032、035 |
| 032 | [稳定世界身份与任务依赖存储](032_world_revision_identity.md) | planned | 待认领 | 005、023、029 |
| 033 | [用户修改指令与局部再生成](033_scoped_scene_revision.md) | planned | 待认领 | 030、031、032 |
| 034 | [场景反馈与修订工作台](034_feedback_workbench.md) | planned | 待认领 | 025、033 |
| 035 | [目标平台能力配置与后续平台选型](035_target_profiles_and_selection.md) | planned | 待认领 | 005、028、029 |
| 036 | [Unity 与 Minecraft 通用场景适配](036_unity_minecraft_scene_adapters.md) | planned | 待认领 | 031、035；复用 008/009 |
| 037 | [下一游戏平台场景适配原型](037_next_game_scene_adapter.md) | planned | 待认领 | 035、036、024；平台/形态/环境明确后 |
| 038 | [历史工单证据与当前职责核对](038_historical_work_order_reconciliation.md) | planned | 待认领 | 027、028 |

下一个可分配编号：039。编号由协调者串行分配，避免并行碰撞。

**2026-09-27 更新（新存档四场景重构启动）**：按用户指示，用更新后的建筑 skill 重新生成**所有**建筑并把四个背景整合进**新存档** `WB Scenes Rebuild`（由 `WB Verify Flat` 复制：207/208 文件、唯缺 `session.lock`；复制时源世界在游戏里打开，故**没有可信全量哈希**，已记为待办）。四个场景带位固定 `(chunk_x*128, −61, chunk_z*128 + 1024 + band*1024)`，band 0/1/2/3 = 魔法城邦/现代都市/工业园/港口；**band 1 与旧现代都市（`z 1408…2048`）重叠**，粘贴前必须先清带并把旧证据留档。每 35 分钟推进任务 `world-builder-35m` 已创建（`FREQ=MINUTELY;INTERVAL=35`，静默策略 `failed_runs_only`）。另一位智能体的 skill 扩充（13 历史/地方 + 6 近现代工业 + 10 功能空间资料卡）经完整回归 **159 passed** 后整合提交（`bde89d6`）。详见 [022](022_scene_reconstruction_new_world.md)。

**2026-09-27 更新（E 阶段建筑 skill + 缺陷清单）**：用户评审指出 E 阶段"没美感、没设计感（全是四方盒子）、功能也不全（只有一层楼梯，到不了其他楼层）"。本轮新增 [skills/building-design/SKILL.md](../skills/building-design/SKILL.md)——十条可核对的规则（体量 2—4 个且高差 ≥2 m、开间:进深 1.0—1.6、层高 ≥3.0 m、立面深度靠腰线/出檐 ≥0.6 m/勒脚/角柱、屋顶原型与出檐、材质 3—4 种靠明度区分、入口 2.0×2.4 m 且门垛 ≥1 m、每层都要有可达楼梯、每层 ≥2 间用途房间+通道、每 6—8 m 一扇窗、与环境协调）+ 机器校验清单 + 能力边界 + 来源与访问状态（官方 Wiki 直连 403、可读页面向生存建造、搜索引擎要验证码故不引用社区教程；哪些是设计判断单独标注）。`tests/test_building_skill.py` 钉住主题、关键数字与边界。**按用户评审拆出的下一批**：a) 多部楼梯与逐层可达；b) 模板加入体量组合与立面线脚；c) 采光/门廊/环境协调字段。

**2026-09-27 更新（class 3 首项：城堡 / `kind: compound`）**：设计器新增第三种模板种类——多体量组合，角色词汇 `{wall, tower, keep, hall}`；`design_compound()` 按规则在场地里摆出"带门洞的幕墙 + 四角塔 + 中央主楼 + 大厅"，各件高度按包络**等比缩放**（保持剪影），放不下的件宁可少摆；`validate_compound()` 管场地内、不超包络、角色齐备、两两不重叠。装配器产出 `compound_<site>`（parts 走局部坐标），`validate_scene` 加 `scene.compounds`；Minecraft 适配器把每件落成**中空壳体 + 屋顶**（因此城堡是天井留白的空心体，不是实心方块）。**实测 seed 4**：魔法城邦 74 个设计（72 建筑 + 1 广场 + 1 城堡），**`no template yet` 首次为空**；导出 36 分块 / 2,719 盒 / 665,060 方块 / `validation: pass`，城堡占 61 盒。布局图 `artifacts/scene-open-space/castle-layout-20260927.png`。**未做**：城堡室内、门楼与坡道、护城河（依赖 014 地形开挖）。

**2026-09-27 更新（城堡幕墙改圆形）**：模板加 `"ring": "circle"`（默认仍 `rectangle`）——幕墙沿**多边形圆环**铺（16—32 段弦盒），临街弧段跳过留城门；四座塔跨在墙环上，大厅改放环内正对城门并按半径收缩；校验放宽为"墙段同属一条墙线可相接，其它结构两两必须留空"。实测：城堡 38 件（32 段墙 + 4 塔 + 主楼 + 大厅）、全部校验 pass，导出 36 分块 / 2,853 盒 / 665,884 方块 / `validation: pass`。布局图 `artifacts/scene-open-space/castle-ring-20260927.png`。

**2026-09-27 更新（城堡场景重贴目标世界）**：带圆形城堡与广场的最新魔法城邦已替换掉旧 dense3：36/36 分块的文件名 → 粘贴点 → `blocks affected` 与清单一致（665,884 方块）。探针 (153,−50,920)=`air` 确认**主楼内部空心**；三条"墙/屋顶在哪"的估算探针未命中，说明还**没有逐格核对壳体**，如实记录在 009。截图 `castle-aerial-20260927.jpg` 等存 `artifacts/minecraft-scene-arcane-castle/target-20260927/`。两次被"窗口内有用户输入"中断，均按规则重新观察后继续，未做世界改动以外的操作。

**2026-09-27 更新（class 2 补齐堆场）**：固定块词汇加 `crate`（→ barrel）与 `stack`（→ gray_concrete），堆场按 5/6 m 网格成排堆放；工业园加 `freight_yard`、港口加 `container_yard` 两个 open_space 模板。seed 4 实测：工业园 16 个设计、缺失清单 `freight_yard, silo_tank` → **`silo_tank`**；港口 36 分块通过、缺失清单 `container_yard, dry_dock` → **`dry_dock`**，但港口设计数仍 13——堆场在港口选址里 demand 1 / placed 0（016 已记录），模板就位而场址缺席。

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
