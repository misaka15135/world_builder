# 022 新存档四场景重构

- 状态：in_progress
- 创建日期：2026-09-27
- 执行者：root
- 依赖：013—018（现行流水线）、017（含建筑 skill）、009（Minecraft 导出）
- 修改范围：`settings/*/designs.json` 与 `planning/designer.py`（按 skill 补规则）、`artifacts/scene-rebuild-*`、`artifacts/minecraft-scene-rebuild-*`、新存档 `WB Scenes Rebuild`、本工单

## 用户指示（2026-09-27）

> 利用另一个智能体更新的建筑生成 skill，**新开一个世界**，整合此前所有已完成的规划，**重新生成各个场景的地图（这次要求把所有建筑都重新生成）**，并尽快在新存档里完成四个场景的重构。

## 已定方案（不再变动，除非用户改口）

**新存档**：`%APPDATA%\.minecraft\world_builder_1.21.11\saves\WB Scenes Rebuild`，由 `WB Verify Flat` 复制而来。

- 创建记录：复制时源世界**正在游戏里打开**，因此 `region/*.mca` 等文件被占用，`Get-FileHash` 大面积失败、`session.lock` 无法复制。实际结果：源 208 文件 / 192.6 MB，副本 **207 文件 / 192.6 MB**（唯一缺 `session.lock`，Minecraft 打开时会自建）。因此**本次没有可信的全量源哈希**，只记录了"逐文件路径+大小+前 16 位 SHA-256"的部分清单（其中被占用文件的哈希缺失）；要做到可核对的完整哈希，必须在游戏里退出该世界后再复制一次——这条记为待办。
- 世界内两座 city.7 城邦与旧魔法城邦/现代都市的粘贴**都还在**（复制自 `WB Verify Flat`）→ 新存档里会与四个新场景共存，需要时再清理；本轮不动它们，避免误删证据。

**四个场景的带位（band）**：每个场景 512 m，粘贴基线

```
(chunk_x * 128, -61, chunk_z * 128 + 1024 + band * 1024)
band 0 = 魔法城邦 arcane_medieval
band 1 = 现代都市 modern_metropolis
band 2 = 工业园   industrial_park
band 3 = 港口     harbour
```

每个场景实占 `x −128…640`、`z` 方向 640 m；相邻带之间留 384 m 安全距。旧内容（两座 city.7 在 `z −512…0`、旧魔法城邦在 `z 384…1024`、旧现代都市在 `z 1408…2048`）与新带位：band 2/3（`z 2048…2688` / `z 3072…3712`）与旧内容不重叠；**band 1（`z 1024…1664`）与旧现代都市（`z 1408…2048`）重叠**，粘贴前必须先清空该带并确认旧现代都市的证据已在 `artifacts/` 留档。

## 每轮增量顺序（自动化 `world-builder-35m` 按此推进）

1. 生成器改进一条，对应 [建筑 skill](../skills/building-design/SKILL.md) 与三份参考卡里的具体条目：
   a) **每层可达楼梯**（现在只出一部到二层的梯：设计师逐层出梯段、适配器逐段渲染、逐层复核井与落点）；
   b) 体量组合与立面线脚（腰线 / 出檐 ≥0.6 m / 勒脚 / 角柱）进模板；
   c) 按背景给风格词汇（魔法城邦=都铎半木构+石构、现代=Art Deco 退台与幕墙、工业=厂房/锯齿屋顶/筒仓、港口=仓库/灯塔/干船坞）；
   d) 采光与门廊台阶字段。
2. 用 `tools/assemble_scene.py --prompt "<登记提示词>" --seed 4`（提示词见 `benchmarks/scene_cases_v1.json` 的 `settings`）重导四个场景到 `artifacts/scene-rebuild-<setting>/` 与 `artifacts/minecraft-scene-rebuild-<setting>/`。
3. 分块拷进游戏目录 → 逐列 `//pos1/pos2` + `//set air` 清带 → 按上面基线 `/tp` + `//schem load` + `//paste -a` → 逐块核对 `latest.log` 的 `blocks affected` 与 manifest 一致。
4. 每轮：针对性测试 + 完整回归 + `tools/check_project_docs.py` + 更新本工单 + 本地提交（不推远端）。

## 验收标准

- 四个场景在 `WB Scenes Rebuild` 中各占一条带，**每个分块的 `blocks affected` 与 manifest 逐一吻合**；
- 每个场景的"必现风物清单"在导出物里可查（含城堡、广场、公园、堆场等此前补齐的类型）；
- 逐场景留俯瞰与地面截图；多层建筑可逐层到达（楼梯数 = 层数 − 1 且逐层复核）；
- 失败与未达标处如实记录，不换分母、不把设计目标写成已实现。

## 执行记录

| 日期 | 执行者 | 动作 | 结果与证据 | 下一步 |
|---|---|---|---|---|
| 2026-09-27 | root | 建 35 分钟推进任务、整合 skill、建新存档 | ① 自动化 `world-builder-35m`（`FREQ=MINUTELY;INTERVAL=35`、ACTIVE、静默策略 `failed_runs_only`）已创建；② 另一位智能体的 skill 扩充（三份参考卡：13 历史/地方 + 6 近现代工业 + 10 功能空间）经完整回归 **159 passed** 后整合提交（`bde89d6`）；③ 新存档由 `WB Verify Flat` 复制为 `WB Scenes Rebuild`（207/208 文件，唯缺 `session.lock`；复制时源世界在游戏里打开，故**没有可信全量哈希**，已记为待办） | 按"每轮增量顺序"从 a) 每层可达楼梯开始；先清 band 1（与旧现代都市重叠）再贴 |
| 2026-09-28 | root | 用户要求"操控电脑退出当前存档进新存档"——**本轮 GUI 通道不可用，未能执行** | 尝试调用 Computer Use 的两条通道（`mcp__node_repl::js` 与 `mcp__cua_repl::js`）均返回 `unsupported call`，本会话未注册这两个工具，因此**无法用鼠标/键盘切换存档**；按项目与 Computer Use 规则，不用其它技术（直接 SendInput/自建 helper）绕过该通道，也不在无人确认下强杀正在运行的游戏进程（强杀可能丢掉未保存的世界状态）。**已核对**新存档本身可加载：`WB Scenes Rebuild` 有 `level.dat`（2,549 B）、`level.dat_old`、69 个 region 文件、192.6 MB，与源存档同尺寸。游戏进程仍在运行（javaw PID 38620，22:50 启动）。**另发现一个可用性坑**：副本沿用源存档的 `LevelName`，所以世界列表里会出现两个同名世界——重命名需要改 `level.dat` 的 `LevelName`（NBT），必须在世界关闭后离线改写，记为待办 | 用户在机器前时可按 Esc →「Save and Quit to Title」→「Singleplayer」→ 选新存档 →「Play Selected World」完成切换（约 10 秒）；下一轮唤醒先重试 Computer Use 通道，若可用则自行切换并同时修 `LevelName` |
| 2026-09-28 | root | 用户切换存档完成；GUI 通道恢复并实测可用 | ① **存档已切到新存档**：`WB Scenes Rebuild` 的 `session.lock` 为 00:07:20、目录在 00:07:28 仍被写入，而 `WB Verify Flat` 的锁停在 00:05:50（已不活动）。② **GUI 通道恢复**：`node_repl` 里 `await import("@oai/sky")` 成功（`sky` 含 `get_window_state/click/press_key/type_text` 等），绑定 `Minecraft* 1.21.11 - Singleplayer` 窗口截图正常。③ **命令通道实测**：Escape 退出暂停菜单 → `/time set noon`（日志 `Set the time to 6000`）、`/gamemode spectator`（日志 `Set own game mode to Spectator Mode`）、`/say WB_SCENES_REBUILD_GUI_OK`（日志命中）→ 说明 F9+输入+回车的链路在新会话里可用。④ 基线截图 `artifacts/scene-rebuild/new-save-baseline-20260928.jpg`（(256,−40,256) 处为空坪，与旧内容不重叠） | 按"每轮增量顺序"从 a) 每层可达楼梯开始改生成器；改完再重导四场景并按 band 贴进本存档 |
| 2026-09-28 | root | 第一条生成器改进：**每层可达楼梯** | 原状：设计师只声明一处梯井、装配器只出**一部**到二层的梯、适配器只认 `stairs[0]` 并把它钉死在首层与二层之间——三层及以上永远上不去。改法：① **装配器**按楼层出梯，`n` 层出 `n−1` 段（首段保留原名 `…_stair` 以免旧探针失效，其余为 `…_stair_s2/s3…`，每段带 `serves_level` 与逐层递增的 `floor_levels_m`）；② **适配器**改为接受任意段数、逐段校验"起点落在某一层楼板、梯段高差 = 层高、梯身在本井范围内"，并按每段自己的 `floor_levels_m` 铺踏步与平台（旧代码用固定的首层/二层高度）。**测试**：新增 `test_multi_storey_buildings_carry_one_flight_per_storey`（魔法城邦里每栋多层建筑的梯段数 = 层数 − 1，且起点逐层递增一个层高）；定向 `tests/test_minecraft_city.py tests/test_assembler.py` 22 passed，完整回归 **160 passed** | 仍待：设计师的梯井仍是一处声明（多层共用，符合现实但"每层独立梯井/转折梯"未做）；`city.py` 导出报告里 "storeys above the second have no stair" 的旧能力说明要改；随后按 skill 资料卡做体量与立面线脚 |
| 2026-09-28 | root | 第二条生成器改进：**勒脚与角柱**（skill 第 3 条"立面要有深度"） | 适配器新增 `_facade_blocks(style)`：古代 `stone_bricks` 勒脚 + `dark_oak_planks` 角柱，现代 `gray_concrete` 勒脚 + `light_gray_concrete` 角柱（"靠明度对比而不是色相"）。`_building_shell` 在腰线之后追加：**首层一圈勒脚**（高 1 m，**临街一侧留门洞不铺**，避免把门口封住）与**每层四个转角的角柱**（各层自己的轮廓，退台层跟着退）。全部是**新增盒**，旧墙体盒与探针坐标不变。**实测 seed 4 魔法城邦**：勒脚 **216 盒**、角柱 **376 盒**、楼梯踏步 **440 盒**（对照上一轮的"每层一段梯"），导出 36 分块 / 3,550 盒 / 666,167 方块 / `validation: pass` / 74 个设计（缺失清单为空）。**测试**：`test_block_types_land_at_the_source_coordinates` 的西墙断言改为"最低一层是勒脚"，`test_scene_streets_are_laid_before_the_building_shells` 的街面集合改为按"属于路网的名字"筛选（石砖现在同时是街面与勒脚，两者不能再用方块类型区分）——两处都是**测试口径跟随新行为**，已注明原因。完整回归 **160 passed** | 下一轮：体量组合（附属体量/塔楼）进模板；随后重导四场景并按 band 贴进新存档 |
| 2026-09-28 | root | 第三条生成器改进：**体量组合随建筑分异**（skill 第 1 条） | 原状：退台只有"三层及以上、顶层、固定西/南/北三面同时退 1 m"一种形态——同一街区里所有多层建筑长得一样。改法（源端 `_insets`，仍在包络内、只收不放）：指纹（`site.id`）决定**先退哪一面**（西/南/北，东侧永远保留给楼梯带），并决定**顶层两级是否一起退**；两层建筑只在开阔地块上退（`min(width, depth) ≥ 14 m`），且退距仍按 `setback_m` 与"房间留得下"双重封顶。**实测 seed 4 魔法城邦**：17 栋多层建筑里 **5 栋有退台、3 种不同退法**（西+南 / 南 / 北），另 12 栋因为模板声明 `setback_m = 0`（沿街商铺/工坊）或地块太紧而保持齐平——这是数据驱动的结果，不是全部一刀切。导出 36 分块 / 3,550 盒、楼梯实体 **22 段**（多层每层一段 + 顶层两级退台的额外段）、74 个设计、缺失清单为空、`validation: pass`。**测试**：新增 `test_massing_steps_vary_between_buildings`（魔法城邦至少两种退台形态；且任何上层轮廓不得比下层更大）；完整回归 **161 passed** | 下一轮：按背景给风格词汇（都铎半木构 / Art Deco 退台 / 厂房锯齿屋顶 / 仓库灯塔）；随后重导四场景并贴进新存档 |
| 2026-09-28 | root | 第四条生成器改进：**四种背景四套风格词汇**（skill 资料卡 modern-and-industrial / historic-and-vernacular） | 原状：投影把 `industrial_park` 与 `harbour` 都映射成 `modern_grid`——工业园和港口跟 CBD 用同一套墙、路、腰线与线脚，四个背景只有两套视觉词汇。改法：新增 `industrial_works`（墙 `bricks`、板 `gray_concrete`、街 `gray_concrete`、勒脚 `stone_bricks`、角柱 `light_gray_concrete`）与 `harbour_works`（墙 `chiseled_quartz_block`、板/护岸 `smooth_stone`、街 `stone_bricks`、勒脚 `gray_concrete`、角柱 `stone_bricks`）；腰线规则改为"只有古代用木腰线、其余用玻璃带"。**实测 seed 4（四场景重导，产物 `artifacts/minecraft-scene-rebuild-2/<setting>/`）**：魔法城邦 36 分块 / 3,550 盒 / 666,637 方块 / 74 设计；现代都市 34 / 7,049 / 810,050 / 32；工业园 34 / 1,283 / 590,490 / 16（缺 `silo_tank`）；港口 36 / 1,543 / 612,597 / 14（缺 `dry_dock`）；**四者全部 `validation: pass`**。材质直方图核对（可复核）：墙/线脚首位分别是 `smooth_stone`+`dark_oak_planks`、`light_gray_concrete`、**`bricks`**、**`chiseled_quartz_block`**；街面分别 `stone_bricks` / `gray_concrete` / `gray_concrete` / `stone_bricks`——**四套词汇互不相同**。完整回归 **161 passed** | 下一轮：把 `artifacts/minecraft-scene-rebuild-2/` 的四个场景按 band 0/1/2/3 贴进 `WB Scenes Rebuild`（band 1 先清，避开旧现代都市），逐块核对 `blocks affected` 并逐场景截图 |
| 2026-09-28 | root | **band 0（魔法城邦）在新存档实贴完成** | 分块拷入游戏目录（36 个文件与 `artifacts/minecraft-scene-rebuild-2/arcane_medieval/manifest.json` 逐项 SHA-256 一致，旧一套备份在游戏目录 `pre-rebuild-20260928/`）。逐列清空 `y −61…−25`（连带清掉副本里带的旧魔法城邦）后按基线 `(chunk_x*128, −61, chunk_z*128+1024)` 贴入 36 块；**日志逐块核对 36/36 通过**（文件名 → 粘贴点 → `blocks affected` 与清单一致，合计 **666,637** 非空气方块）。截图存 `artifacts/minecraft-scene-rebuild-2/arcane_medieval/target-20260928/`：俯瞰可见街道网格 + 河网 + 成排木构建筑（含新加勒脚/角柱/多层楼梯），地面视角可见街区与道路。聊天探针 `/say BAND0_VERIFIED_36_OF_36` 已写入日志 | 下一轮：band 1（现代都市，`z 1024…1664`）——**注意先清带**（与副本里旧现代都市 `z 1408…2048` 重叠）；再后续 band 2 工业园、band 3 港口 |
| 2026-09-28 | root | **band 1（现代都市）在新存档实贴完成** | 34 个分块与 `artifacts/minecraft-scene-rebuild-2/modern_metropolis/manifest.json` 逐项 SHA-256 一致（合计 810,050 非空气方块）；清单里缺 `(-1,−5)` 与 `(4,−5)` 两格，粘贴时按清单跳过、但整带照常清空。基线 `(chunk_x*128, −61, chunk_z*128+2048)`（band 1）逐列清空后贴入；**日志逐块核对 34/34 通过**。清带同时抹掉了副本携带的旧现代都市（`z 1408…2048`）——该旧证据已在本仓库 `artifacts/minecraft-scene-modern_metropolis-dense/` 留档。俯瞰截图 `artifacts/minecraft-scene-rebuild-2/modern_metropolis/target-20260928/aerial-band1-20260928.jpg`：可见 CBD 体量（灰色高低错落）、河网与街道网格；聊天探针 `/say BAND1_PASTED` 已入日志 | 下一轮：band 2 工业园（基线 `z = cz*128 + 3072`）；随后 band 3 港口（`z = cz*128 + 4096`），并做四场景总览截图 |
| 2026-09-28 | root | **band 2（工业园）在新存档实贴完成** | 34 个分块与 `artifacts/minecraft-scene-rebuild-2/industrial_park/manifest.json` 逐项 SHA-256 一致（合计 **590,490** 非空气方块）；清单缺 `(-1,−5)`、`(4,−5)`，粘贴时跳过、整带照常清空。基线 `(chunk_x*128, −61, chunk_z*128+3072)`（band 2）逐列清空后贴入，**日志逐块核对 34/34 通过**。俯瞰截图 `artifacts/minecraft-scene-rebuild-2/industrial_park/target-20260928/aerial-band2-20260928.jpg`：可见**砖红色厂房**（新 `industrial_works` 词汇）、铁路线、运河与工业街区，与 band 1 的灰色 CBD 明显不同；聊天探针 `/say BAND2_PASTED` 已入日志 | 下一轮：band 3 港口（基线 `z = cz*128 + 4096`，`harbour_works` 词汇：浅色石墙 + 石质码头街面）；随后做四场景总览截图与最终回归 |
| 2026-09-28 | root | **band 3（港口）在新存档实贴完成——四个场景全部就位** | 36 个分块与 `artifacts/minecraft-scene-rebuild-2/harbour/manifest.json` 逐项 SHA-256 一致（合计 **612,597** 非空气方块，清单无缺格）。基线 `(chunk_x*128, −61, chunk_z*128+4096)` 逐列清空后贴入，**日志逐块核对 36/36 通过**。俯瞰截图 `artifacts/minecraft-scene-rebuild-2/harbour/target-20260928/aerial-band3-20260928.jpg`：大面积水域 + 浅色石质码头与仓库（`harbour_works` 词汇）+ 突堤，和工业园/现代都市一眼可分；聊天探针 `/say BAND3_PASTED` 已入日志。**至此 `WB Scenes Rebuild` 内 band 0/1/2/3 四场景齐备**：魔法城邦 666,637、现代都市 810,050、工业园 590,490、港口 612,597 非空气方块，四者共 136 个分块、逐块 `blocks affected` 全部与各自 manifest 一致 | 下一轮：四场景总览截图（高空跨带俯瞰 + 每带一张地面视角）+ 一次完整回归收口，并把 `LevelName` 重命名的待办再做一次评估（需世界关闭才能改 NBT） |
