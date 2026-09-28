# 018 装配器与场景流水线（流水线 F）

- 状态：in_progress
- 创建日期：2026-09-26
- 执行者：待认领
- 依赖：013、014、015、016、017
- 修改范围：未来的 `world_builder/planning/assembler.py`、`world_builder/planning/pipeline.py`、`tools/generate_scene.py`、`tests/test_scene_pipeline.py`、`docs/contracts/scene-pipeline-v0.1.md`
- 修改范围：2026-09-27 root 接手 Minecraft 场景目标验收；仅核对现有 `minecraft-scene-arcane-interiors-2` 分块与恢复后的项目游戏配置，备份 `WB Verify Flat` 存档，在不覆盖旧城的位置分批粘贴并记录游戏内证据，随后同步本工单、000 与索引。保留开工前其他执行者的未提交修改；不重装启动器、不改源生成器。
- 范围变更：目标实贴发现两层住宅 `building_site_026` 室内水方块；先保留失败证据并恢复粘贴前存档，再在 016 的选址和 Minecraft 场景水面投影处修正相互叠压、补回归并重导。修改 `planning/siting.py`、`adapters/minecraft/city.py`、相应测试与新版本独立产物；不覆写已验收的旧导出。

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
- [x] ~~端到端预登记批次：4 个背景包各若干输入，登记在运行前冻结，记录成功率、失败原因、耗时与峰值内存；离线零模型调用。~~
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
| 2026-09-27 | root | 按用户要求排查"游戏未运行"的上游阻塞：Minecraft 启动器启动失败 | **现象**：启动器只出现一个全黑的 `Minecraft Launcher` GDK 启动画面（`gamingservicesui.exe`），约 2.5 分钟后消失；`Minecraft.exe` 进程从未出现，`%APPDATA%\.minecraft\launcher_log.txt` 无新行。用 UI Automation 读出弹窗原文：**"启动你的游戏时出现错误。错误代码: (0x800700c1)"**（0x800700c1 = ERROR_BAD_EXE_FORMAT）。**对比**：Store 运维日志里 09-23—09-26 00:18 每次成功启动都在 `GameLaunchHelper.exe | licensemanagerapi.dll` 之后 2—3 秒出现 `Minecraft.exe | InstallService.dll`；09-27 的 4 次尝试（04:26/04:28/04:34/04:36）都没有该后续事件。**Xbox 侧**：`Microsoft.GamingAppTray` ETL（`tracerpt` 转 XML）显示 `SignInUserSilentlyAsync` → `GetConsentStateAsync: silent sign-in requires user interaction, returning ConsentState::OptedOut` → `GetXuidAsync: called without a user`，随即 `TrayApp: Closing app`；Xbox 应用窗口显示"无法将你登录到 XBOX Live (0x89235107)"。**文件层**：`WindowsApps\Microsoft.4297127D64EC6_2.6.2.0_x64__8wekyb3d8bbwe\Minecraft.exe`（硬链接指向 `C:\XboxGames\Minecraft Launcher\Content\Minecraft.exe`，2,948,096 字节）**无法打开读取**（ACCESS_DENIED，三次重试、`Get-FileHash`/`certutil`/`copy` 均失败），而同一目录其它文件（`gamelaunchhelper.exe`、`XCurl.dll`、`libHttpClient.GDK.dll`）读取正常且签名为 Microsoft 有效；该文件 DACL 与同目录可读文件一致，进程完整性为 Medium。**系统层**：`WindowsApps\Deleted` 下 Intel Arc Software 卸载残留 35 个文件自 09-22 10:20 起删除失败（每 6 分钟重试，830+ 条 AppXDeploymentServer 493 警告）；`MdOdrMcpFilterPackage_1.0.0.0` 卡在"已暂停/必须暂存"；`gamingservicesproxy_13.dll` 有待重启清理的挂起项；`CredentialUIBroker.exe` 反复在 `Windows.UI.Xaml.dll` 崩溃（0xc000027b）；近一个月多次蓝屏 0x133。另：Microsoft Store 应用自身也连不上微软服务（`0x80072EFD`，含显式 `127.0.0.1:7897` 超时），临时关闭 Clash 系统代理后仍失败，而普通 Win32 进程直连与走代理访问同端点均正常（200/404/405 真实响应）；Clash 为系统代理 `127.0.0.1:7897`（TUN 关闭），Store/Xbox/启动器包均不在 `CheckNetIsolation LoopbackExempt` 列表中。**未做**：修复动作需要管理员权限，当前登录账户 `MISAKA\misak` 不在 Administrators 组，机器上另有本地管理员账户 `MISAKA\Administrator`。本轮未改动仓库文件，临时关掉的系统代理已还原 | 用管理员账户修复：① 先重启（完成 `gamingservicesproxy_13.dll` 的挂起清理）；② `Get-AppxPackage Microsoft.4297127D64EC6 \| Reset-AppxPackage`（或卸载后从 Store 重装）以恢复可读可执行的 `Minecraft.exe`；③ 同样处理 `Microsoft.GamingApp` 与 `Microsoft.GamingServices`；④ 停掉 Intel Graphics Software 后清掉 `WindowsApps\Deleted\AppUp.IntelArcSoftware_*`；⑤ `CheckNetIsolation LoopbackExempt -a -n=<PFN>` 为 Store/Xbox/启动器加回环免除；⑥ `sfc /scannow` + `DISM /Online /Cleanup-Image /RestoreHealth`；修好后按已记录的粘贴方案完成 36 块粘贴与截图 |

| 2026-09-27 | root | 用户用 Store 重装启动器到 D 盘后，复查"旧残留阻塞解包"的假设 | **核实：旧启动器残留已不存在**——`C:\XboxGames\Minecraft Launcher` 只剩 `C:\XboxGames\GameSave`；C:/D: 的包数据、`XboxGames`、`WpSystem` 下搜不到任何 `libcef.dll`/`launcher.dll` 或 `game`/`update_files` 目录；包数据已迁到 `D:\WpSystem\<SID>\...\Microsoft.4297127D64EC6_8wekyb3d8bbwe`（各子目录 09-27 05:32 新建且基本为空），没有半解包产物。**当前真实失败**：UI Automation 读出 GDK 窗口为"正在准备您的游戏 / 10.1 MB/10.1 MB / 错误 / 重试"，即下载完成后的应用（解包）阶段失败；重装后 `D:\XboxGames\Minecraft Launcher\Content\Minecraft.exe` 仍 ACCESS_DENIED，而 `gamelaunchhelper.exe`/`XCurl.dll` 可读且签名有效，`cipher /c` 显示两者均非 EFS、ACL 相同，火绒 `log.db`/`applog.db` 的 `HrLogV3_60` 无任何 Minecraft 拦截记录；Store 日志仍只有 `GameLaunchHelper.exe`、无 `Minecraft.exe \| InstallService.dll`。本轮把可再生的启动器缓存改名移出：`%APPDATA%\.minecraft\webcache2`（约 60 MB）与 `staging`（空）→ 后缀 `.bak-20260927`（可恢复），并关掉卡住的 GDK 窗口；**未动** `%APPDATA%\.minecraft` 的游戏数据与 GDK 激活状态 | 仍需管理员：重启 → `Reset-AppxPackage` 启动器/Xbox/Gaming Services → 停掉 Intel Graphics Software 后清理 `WindowsApps\Deleted\AppUp.IntelArcSoftware_26.26.2459.0_*`（其旧 DLL 被新版服务占用，是唯一仍在每 6 分钟重试的真残留）→ 回环免除 + `sfc`/`DISM`。备选绕开 GDK/Xbox 链：装 minecraft.net 独立版启动器（复用同一 `.minecraft`） |

| 2026-09-27 | root | 按用户要求清空启动器侧安装与状态，准备重新下载 | `Remove-AppxPackage Microsoft.4297127D64EC6_2.6.2.0_x64__8wekyb3d8bbwe` 执行成功：`Get-AppxPackage` 已无该包，`C:\Program Files\WindowsApps\Microsoft.4297127D64EC6_2.6.2.0_x64__8wekyb3d8bbwe`、`D:\WindowsApps\Microsoft.4297127D64EC6_...`、`D:\XboxGames\Minecraft Launcher`（含此前 ACCESS_DENIED 的 `Minecraft.exe`）、`%LOCALAPPDATA%\Packages\...` 的 junction 与 `D:\WpSystem\...` 包数据全部消失，开始菜单入口消失，无相关进程残留。`.minecraft` 内的启动器状态（`launcher_*.json`/`.bin`、`launcher_log*.txt`、`launcher_cef_log.txt`、`webcache2`、`staging`、`clientId_v2.txt`、`treatment_tags.json`、`usercache.json`、`realms_persistence.json`、`launcher_gamer_pics_*.json`）共 24 项移入隔离目录 `C:\Users\misak\AppData\Local\MinecraftLauncherQuarantine-20260927`——执行侧命令策略禁止对工作区外路径直接 `Remove-Item`，故用等价的可恢复移动；用户在资源管理器删除该目录即等于永久删除。**保留**游戏数据：`assets`/`libraries`/`versions`/`saves`/`mods`/`bin`/`logs`/`options.txt`/`servers.dat` 与项目专用 `world_builder_1.21.11`（含 `.fabric`、`config/worldedit/schematics`、`saves`、`screenshots`） | 用户关掉 Clash 系统代理/VPN 后重装启动器（关闭回环代理后 Store/Xbox 才能联网，这是重装能成功的前提）；重装后仍失败则走管理员修复（重启 → Reset-AppxPackage 启动器/Xbox/Gaming Services → 回环免除 → sfc/DISM）；`WindowsApps\Deleted\AppUp.IntelArcSoftware_26.26.2459.0_*` 仍需管理员清理 |

| 2026-09-27 | root | 用户确认"后续重建"，按指示清空游戏数据 | `%APPDATA%\.minecraft` 整目录（`assets` 574 MB、`libraries` 132 MB、`versions` 102 MB、`saves` 797 MB、`world_builder_1.21.11` 120 MB、`bin`、`logs`、`mods`、`options.txt`、`servers.dat` 等）整体移入隔离目录 `C:\Users\misak\AppData\Local\MinecraftLauncherQuarantine-20260927\.minecraft-wiped-20260927`（执行侧策略禁止对工作区外路径 `Remove-Item`，故先移动；用户删除该隔离目录即等于永久删除）。随之移走的存档：主档 `新的世界`、`新的世界 (1)`，项目档 `WB Verify Flat`、`World Builder Sample`，以及项目档 `config/worldedit/schematics` 下 38 个 `.schem`（36 个场景分块 + `library.schem`/`library-v3.schem`）。**重建素材确认仍在仓库**：`artifacts/minecraft-scene-arcane`、`minecraft-scene-arcane-interiors(-2)`（各 39 文件）、`minecraft-city-v7`、`minecraft-city-v7-modern`、`minecraft-sample`。另：检查时 **Clash 系统代理仍为开启**（`ProxyEnable=1`、`ProxyServer=127.0.0.1:7897`），这是 Store/Xbox 无法联网、因而重装后仍失败的直接嫌疑 | 用户关掉 Clash Verge 的【系统代理】开关（不只是 VPN 节点）后再启动；若仍失败走管理员兜底（重启 → `Reset-AppxPackage` 启动器/Xbox/Gaming Services → 回环免除 → `sfc`/`DISM`），并清 `WindowsApps\Deleted\AppUp.IntelArcSoftware_26.26.2459.0_*`；重建流程：装好 1.21.11 + Fabric + WorldEdit → 从 `artifacts/` 复制 `.schem` → 按既定偏移基线粘贴 |

| 2026-09-27 | root | 按用户要求"把本机关于 minecraft 的所有东西再删一遍" | 全盘清点后处理：① 再次 `Remove-AppxPackage Microsoft.4297127D64EC6_2.6.2.0_x64__8wekyb3d8bbwe` 成功（清掉 05:48 那次重装），`%LOCALAPPDATA%\Packages\Microsoft.4297127D64EC6_8wekyb3d8bbwe`、`D:\WpSystem\...`、C:/D: 两处 `WindowsApps\Microsoft.4297127D64EC6_*`、`D:\XboxGames\Minecraft Launcher` 全部消失；② `C:\XboxGames`、`D:\XboxGames`、`D:\.GamingRoot` 移入隔离目录；③ `.minecraft` 此前已清空且未被重建；④ 核查确认无该 Appx 包、无开始菜单/桌面快捷方式、无相关计划任务、无 HMCL/PCL2/Prism/MultiMC/BakaXL 等其它启动器。隔离目录 `C:\Users\misak\AppData\Local\MinecraftLauncherQuarantine-20260927` 现为 **1.70 GB**（`.minecraft-wiped-20260927`、`XboxGames-C`、`XboxGames-D`、`GamingRoot-D`、`webcache2`/`staging`、24 个 launcher 状态文件），已确认其中 `新的世界`、`新的世界 (1)`、`WB Verify Flat`、`World Builder Sample` 四个存档仍完整可恢复。**两处未能清除**：`C:\.GamingRoot`（所有者非当前用户 SID，访问被拒，需管理员）、`HKCU\SOFTWARE\Mojang`（执行侧命令策略禁止删除注册表键）。**未动**：项目仓库 `D:\TongJi_Bache\RIKA\world_builder`（含 `artifacts/minecraft-*` 重建素材）与 `D:\BaiduNetdiskDownload\Minecraft怪物大乱斗v1.0.2`（第三方二次创作游戏包，非 Minecraft 本体） | 用户在资源管理器删除隔离目录即完成永久删除（我这边策略只允许移动、不允许删除工作区外文件）；`C:\.GamingRoot` 交给管理员；**重装前必须先关掉 Clash Verge 的【系统代理】开关**（当前仍为 `ProxyEnable=1`、`127.0.0.1:7897`，这是 Store/Xbox 无法联网、GDK 卡在"准备您的游戏"的直接原因）；重建路径：装 1.21.11 + Fabric + WorldEdit → 从 `artifacts/` 拷 `.schem` 回 `config/worldedit/schematics` → 按既定偏移基线粘贴 |

| 2026-09-27 | root | 用户"你看屏幕吧,还是不行"，接管屏幕复查并做关键对照实验 | **画面**：Minecraft Launcher GDK 窗口为「正在准备您的游戏 / 错误 / **2.7 MB/10.1 MB** / 重试 / 准备就绪后启动游戏」，即 GDK 引导下载 10.1 MB 授权内容在固定 2.7 MB 处失败；同屏的 Microsoft Store 仍是满屏灰色骨架。**实验**：把 Clash 系统代理关掉（`ProxyEnable=0`，保留 `ProxyServer=127.0.0.1:7897`）后重启启动器，**仍停在 2.7/10.1 MB**；重开 Store 依旧持续 `0x80072EFD`（无法与服务器建立连接），而同一时刻普通进程直连微软各域名（`launchermeta.mojang.com`、`displaycatalog.mp.microsoft.com`、`licensing.md.mp.microsoft.com` 等）DNS/TCP443 全部正常、走代理也能取到 200。结论：**本机"商店类应用（AppContainer）的网络被整体挡住"**——Store 与 Xbox 同时中招，Xbox 静默登录持续 `ConsentState::OptedOut` / `GetXuidAsync: called without a user`（应用侧报 `0x89235107`），GDK 拿不到 Xbox 身份 → 那 10.1 MB 授权内容下载失败。Store 日志另有许可侧硬错误：`Product is not fulfillable (0x803FB104)`、`GetProductsAsync → HTTP 400`。**最大嫌疑转为火绒安全软件 6.0.12.1**（`HipsDaemon` 运行中）：其"联网控制/程序执行控制"可同时产生"单个应用网络被静默阻断（表现为超时→0x80072EFD）"与"单个 EXE 读取被拒（此前 `Minecraft.exe` 的 ACCESS_DENIED）"，其规则库 `appprot.db` 为加密格式无法读取、`log.db` 中也无 Minecraft 记录，无法从外部证实。本轮改动仅系统代理开关（已关，Clash 里点一下即可恢复） | 让用户托盘右键火绒→退出防护，再点启动器"重试"；若通过则把 Minecraft Launcher / Microsoft Store / Xbox 加入火绒联网与文件防护白名单。若退出后仍失败，转管理员：重启 → `wsreset` → `Reset-AppxPackage` Store/Xbox/Gaming Services → `netsh winsock reset` + `netsh int ip reset` → `sfc`/`DISM` → 清 Intel 残留 |
| 2026-09-27 | root | 接手已恢复的 Java 目标环境并试贴首块 | 游戏在主菜单，日志确认 1.21.11/Fabric/WorldEdit。含室内的 36 个分块与游戏目录逐项比 SHA-256，发现 5 个仍为旧文件；先将 `WB Verify Flat` 存档的 72 个文件及旧 5 文件备份到 `artifacts/minecraft-recovery/pre-scene-paste-20260927/`，再更新 5 文件，36/36 与最新清单哈希一致。进入 `WB Verify Flat` 后在隔离偏移区域 `(−128,−61,384)` 试贴 `city_c-1_05`，游戏回报 432 blocks affected，与清单 432 一致 | 继续分批粘贴其余 35 块，每批核对回报与目标坐标，再检查整体形态与代表性室内 |
| 2026-09-27 | root | 完成 36 分块首次目标实贴并发现室内积水 | 第一次连发命令有 1 块重复剪贴、1 块偏移；退出并用备份完整恢复后切观察模式、延长传送等待，重新粘贴 36/36 块，逐块 WorldEdit 的 `blocks affected` 与清单相同，粘贴原点均为 `(chunk_x×128,-61,chunk_z×128+1024)`；合计 628355 方块。高空可见河网、桥与建筑。抽查 `building_site_026` 一层 `(366,-60,733)` 时，游戏命令确认 `minecraft:water`，画面显示室内积水。源 WIR 中该住宅足迹与 `water_main_0` 的实际中心线半径相交（最近约 6.37 m，河宽 20 m）；`building_site_032` 也相交。选址当前只查中心点；Minecraft 适配器又将水面盒排在建筑之后覆盖楼板。截图见 `artifacts/minecraft-scene-arcane-interiors-2/target-20260927/`。本轮不将目标场景记为完整通过 | 保存失败实贴世界供核对，恢复目标世界基线；修足迹避水与投影层顺序后重导重贴 |
| 2026-09-27 | root | 复核并落库交接修复（完整回归 + 重新导出） | 上一执行者留下的两处修复经**完整回归 147 passed**、文档检查零错误后提交（`88a2f51`，未改动其内容，只复核与运行）：① 选址改为 `_footprint_is_dry` 按 2 m 网格采样整个包络并新增规则 `siting.site_footprints_dry`；② 适配器场景分支先落地面与水面、再落外壳与楼板。用修复后的代码重新导出同一场景：**36 分块 / 1,024 盒 / 629,926 方块**（修复前 1,015 盒 / 628,355 方块），`validation: pass`，产物 `artifacts/minecraft-scene-arcane-interiors-3/` | 下一轮：把这套新分块拷入游戏目录并重贴，重点核对 `building_site_026`(366,-60,733) 与 `building_site_032` 已是干楼板，然后截图存档 |
| 2026-09-27 | root | **修复版场景在目标世界首次实贴并确认原积水坐标已干** | 游戏（`Minecraft Java (Legacy)` 启动的 1.21.11 + Fabric + WorldEdit，存档 `WB Verify Flat`）已运行。清出 `x 256—383, y -59—-25, z 640—767` 后按基线 `(256,-61,640)` 贴入分块 `city_c02_03`（清单 38,242 非空气方块），回报 `The clipboard has been pasted at (256,-61,640)`。**探针**（原室内积水点 `building_site_026` 一层 `(366,-60,733)`）：`minecraft:water` → **Test failed**（不再是水）、`minecraft:oak_planks` → Test failed、`minecraft:stone_bricks` → **`[misaka15135] P_BRICKS` 命中**，即该格现为石砖铺装——场址已按"整包络避水"移到河外，原处变成街道。游戏内 F2 截图 `2026-09-27_07.39.44.png` 已复制进 `artifacts/minecraft-scene-arcane-interiors-3/target-20260927/`。**注意**：本轮只贴了 1 块（36 块中的 `c02_03`）用于定点验证，其余 35 块与整体对照仍待做 | 下一轮贴完其余 35 块，核对每块 `blocks affected` 与清单一致，再做新城邦与两座 city.7 城邦的目视对照与截图 |

## 交接说明

### 2026-09-27 额度暂停交接（root，状态 in_progress）

- 已修复选址只查中心点导致建筑足迹跨水的问题，以及 Minecraft 场景投影中水盒晚于楼板写入的问题；改动位于 `planning/siting.py`、`adapters/minecraft/city.py` 和对应测试。定向回归 `tests/test_siting.py tests/test_scene_projection.py tests/test_minecraft_city.py`：**29 passed**。
- 新产物 `artifacts/scene-arcane-dry/` 与 `artifacts/minecraft-scene-arcane-interiors-dry/`：WIR `world_39d0699d1d4a3907`、修订 `revision_61ba8d7f71e30bfc6417eb`，36 分块、881 盒、626682 方块。独立解析 36 个 schem，在 33 栋建筑的 4484 个一层足迹单元中未发现水。**这是离线证据，目标游戏尚未重贴验收。**
- 首次错误剪贴与积水的目标存档分别归档在忽略目录 `artifacts/minecraft-recovery/failed-first-scene-paste-20260927/`、`failed-flooded-scene-20260927/`；目标世界 `WB Verify Flat` 已从事前备份恢复，仍为原两座 city.7 城，没有新场景。游戏的 36 个同名 schem 已换成修复版，哈希与新清单一致。旧场景的目标截图见 `artifacts/minecraft-scene-arcane-interiors-2/target-20260927/`。
- 完整回归 `python -m pytest -q --basetemp artifacts/pytest-scene-dry-full` 运行到约 48% 且未见失败，因用户要求暂停主动中断，**不能记为通过**。本阶段未做本地提交；保留其他 agent 原有未提交改动，不推送远端。
- 五小时后续做：先重读 README、000、018、016、009 并检查 `git status`；重跑完整回归和文档检查；核对修复版 manifest 与游戏目录 36/36 哈希，再在恢复后的 `WB Verify Flat` 按 `(chunk_x×128,-61,chunk_z×128+1024)` 分批粘贴，逐块核对 WorldEdit 回报；重点用方块探针和画面复验 `building_site_026` 及另一处旧跨水场址的干燥室内，再记录截图、更新 009/016/018/000/README。验收通过后仅做本地提交，远端由用户处理。

开始前重读 013—017 的契约、006 的 pipeline/repair 与 docs/04 §3.3；完成有结果的动作后更新执行记录，并在阶段结束时同步 000 与索引。

- 2026-09-27 唤醒（40 分钟任务）：接手继续粘贴时发现**目标窗口画面不可用**。窗口标题仍是 `Minecraft* 1.21.11 - Singleplayer`（世界仍在），但 `get_window_state` 截图**整帧全黑**，首次调用还报 `GetCursorPos failed: 拒绝访问 (0x80070005)`；重试一次后标题可取、画面仍黑。**读不到聊天回报就不做批量粘贴**（历史教训：第一次连发命令曾出现 1 块重复剪贴与 1 块偏移），本轮因此停下并如实记录，未做任何世界改动。下一次先确认窗口能出画面（最小化后还原/切前台，或重启 Java 版启动器），再继续贴其余 35 块。

- 2026-09-27 黑屏原因澄清并继续粘贴：用户说明黑屏是**屏幕保护程序到点关闭了显示器**，现已关闭该设置。画面恢复后继续实贴：第 2 列（`chunk_x=2`）剩下的 5 块全部贴入，基线分别为 `z = 384/512/768/896/1024`（即 `cz = -5/-4/-2/-1/0`）。聊天回报中**直接读到的计数与清单一致**：`cz=-1` → `32768 blocks affected`（清单 32,768 ✓）、`cz=0` → `4873 blocks affected`（清单 4,873 ✓）；`cz=-3` 上一轮已核对 38,242 ✓。另三块（`cz=-5` 4,628、`cz=-4` 34,208、`cz=-2` 41,871）本轮只在同一批日志里连发，**未逐条读到计数，不记为已核对**。至此修复版场景已贴 **6/36 块**（第 2 列全部），其余 4 列 30 块与 `building_site_032` 的室内复验待下一轮。

| 2026-09-27 | root | **修复版场景完成 36/36 目标实贴并做方块级验收，同时发现新的渲染语义缺陷** | 目标世界 `WB Verify Flat`（1.21.11 + Fabric + WorldEdit 7.3.19，观察者模式）。流程：逐列 `//pos1 x,-61,384` → `//pos2 x',-25,1023` → `//set air` 清空到地面上层，再按基线 `(chunk_x×128, −61, chunk_z×128+1024)` 每块 `/tp` + `//schem load` + `//paste -a`。**核对**：解析 `logs/latest.log`（WorldEdit 回报进入日志，比读屏更可靠），36/36 个分块的文件名 → 粘贴点 → `blocks affected` 与 `manifest.json` 逐项一致；早期误操作产生的 4 处非规范粘贴点（`(-1,-61,767)`、`(366,-59,733)`、`(514,-60,826)`、`(128,-62,768)` 及 x 640—641 越界段）均落在整列清空范围内，已不复存在。**过程中修掉的两个操作陷阱**：① `/tp` 后若玩家落在被清空的柱里会下坠一格，粘贴点随之变成 y=−62（本列重做）；② 玩家被刚贴入的方块挤出会随机 ±1 偏移粘贴点（`(512,-61,385)`、`(512,-61,1023)`），改观察者模式后 36/36 全部落在规范坐标。**验收**：方块探针 `(300,-57,884)`→`oak_planks`（二层楼板）、`(300,-59,879)`→`smooth_stone`（隔墙）、`(291,-53,875)`→`bookshelf`（家具）、`(100,-62,800)`→`dirt`（世界地面）均命中；`site_026`/`site_032` 一层多点探针**均非 water**，旧的室内积水缺陷确认消失。**新缺陷**：投影把斜向折线折成外接大盒（最大 187 m × 368 m，街面盒总面积 565,292 m² > 场景面积 262,144 m²），按当前顺序压过 `terrain_proxy` 与建筑一层楼板，导致 30/33 栋建筑一层楼板由 `oak_planks` 变成 `stone_bricks`、场景呈大片石板（探针 `(300,-60,884)` = `stone_bricks`）。这是导出物本身的语义缺陷，与本轮贴入无关（分块计数逐块吻合）。证据截图 `artifacts/minecraft-scene-arcane-interiors-3/target-20260927/{aerial-stone-plain,ground-view}-20260927.jpg` | 新工单 [020](020_scene_corridor_rasterization.md)：走廊栅格化 + 填充顺序修复 + 版本升级 + 重导重贴 |
| 2026-09-27 | root | 新城邦与既有 city.7 两城的目标侧对照（同高度俯瞰 + 离线指标） | 三张同参数截图（`/teleport @s <center> 80 <center> facing <center> -60 <center>`，正午、观察者模式）与逐箱统计存 `artifacts/minecraft-scene-arcane-interiors-4/target-20260927/compare-{old-ancient-city7,old-modern-city7,new-arcane}-20260927.jpg`。**离线指标（每箱面积求和）**：新城邦 33 栋、足迹 6,043 m²（占 512² 的 2.3%）、街面盒 115,991 m²；city.7 古代 80 栋、18,704 m²（7.1%）、街面 24,336 m²；city.7 现代 80 栋、23,312 m²（8.9%）、街面 30,976 m²。**结论**：新流水线的空间结构确实是"非正交路网 + 放射斜街 + 自然河网"（对应用户要求），但**建筑密度只有参考实现的 1/3、街面面积是参考的 4—5 倍**——观感上因此显得又空又灰。这是源端（014 地形/016 路网与选址）的配比问题，不是适配器问题；适配器侧的街面占比已由 020 从 72% 降到 25% | 在 016 记录"提高建筑覆盖率、降低街面占比到参考量级"为工作项；017 继续补设计模板 |
| 2026-09-27 | root | 端到端预登记批次落地（018 最后一项待办） | 新增 `benchmarks/scene_cases_v1.json`（**运行前冻结**：四个背景 × seed 1—5 共 20 例、逐例记录口径与"不过滤失败"的声明）与 `tools/benchmark_scene.py`（每例一个独立进程，便于逐例测峰值内存；导出写临时目录；离线零模型调用）。**首轮结果**：20 例 17 通过，3 例失败——1 例是**运行器自身**的 `FileExistsError`（单例冒烟测试留下了同名目录），2 例是真实缺陷 `target.interior_void: building_site_006`。**修复**：① 运行器改为把每例导出写进 `tempfile` 临时目录；② 港口 6.85 m 进深建筑的**梯段超出预留井 1.15 m**（设计师按"井够宽"算，没按"井装得下整段梯 + 平台"算），现在前缘余量/平台随进深收缩（8 m 以上 3 m + 2 m，以下 1 m + 1 m），并新增源端校验规则 `design.stair_fits_void`（不用等导出才发现）。**复跑结果**：**20/20 通过、成功率 1.0、失败原因空**；耗时合计 300.2 s、单例均值 15.0 s、最大 19.9 s；进程峰值内存最大 146.1 MB、均值 136.9 MB；**模型调用 0**。报告 `artifacts/scene-benchmark-v1/report.json` | 018 的验收项齐了；剩余为 017 的 class 1 余项与 `open_space`、以及把三个新导出贴进目标世界（可选） |
| 2026-09-27 | root | 开放空间接入后复跑冻结端到端批次 | `benchmark_scene.py` 改用与正式装配相同的 `design()` 入口，保留原 20 例分母及提示词。`artifacts/scene-benchmark-v1-current/report.json`：**20/20 通过**、失败原因空、总耗时 309.6 s、单例峰值最大 147.0 MB、模型调用 0；旧报告未覆盖。完整 Python 回归 154 passed，文档检查零错误 | 017 后续模板；开放空间尚未在目标游戏重贴验证 |
| 2026-09-28 | root | 城堡门楼/引道/室内接进装配器与 Minecraft 适配器（主线 a 的 018 侧） | 装配器把 compound 的每件体量连同新字段（`base_m`、`levels_m`、`stair`、`door`）写进 `geometry.volumes`，楼梯矩形随场地原点重定位；Minecraft 适配器新增 `_compound_boxes()` 取代原先的“每件四壁 + 屋顶”内联循环：`ramp` 渲染成**实心**踏步/平台（0.25 m 的踏板挖空就没有落脚面）、`gate` 的门楣从 `base_m = 4 m` 起跳，形成可通行的门洞、`keep` 按 `levels_m` 铺楼板（按楼梯井切四块）并按层出直跑梯、主楼与大厅按 `door` 在朝门那面开洞（两面墙分段 + 门楣）。**实测 seed 4 魔法城邦**：36 分块 / 4,046 盒 / 669,049 方块 / `validation: pass`；城堡由 38 件增到 46 件。**未达标**：1 m 体素下 0.25/0.5/0.75 m 的踏步落在同一层，渲染成与地面齐平的铺装引道，不是抬高坡道。完整回归 162 passed | 下一轮把新内容重贴进 `WB Scenes Rebuild` band 0 |
| 2026-09-28 | root | 窗型与门廊立柱接进 Minecraft 适配器（主线 b 的 018 侧） | 适配器新增 `WINDOW_STYLES` 与 `_window_boxes()`（窗樘/玻璃/窗台/窗楣/中梃），`_building_shell` 的采光分支改为调用它，门廊下补两根落地柱（`{name}_porch_column_*`）；全部仍是轴对齐盒，未引入新几何种类。四场景 seed 4 复导全部 `validation: pass`，盒数 5,177/13,638/1,791/2,228、非空气方块 669,335/810,765/590,783/612,922；门廊立柱 144/62/30/26 = 2 × 门廊数。**未做**：东西两面开窗、真正的拱券。完整回归 163 passed | 下一轮：class 3 剩余几何或重贴四场景 |
| 2026-09-28 | root | 圆柱进装配器与 Minecraft 适配器（主线 c 第一项的 018 侧） | 装配器新增 `CylinderDesign` 分支，出 `cylinders` 实体（`representation: cylinders`，每只罐的局部中心/半径/高度/盖型）并在 `validate_scene` 加 `scene.cylinders` 计数；适配器新增 `_disc_rows()`（按行铺满圆盘）与 `_cylinder_boxes()`（弦盒环 + 基座盘 + 分层穹顶），`city_boxes` 的场景分支按 `kind == "cylinders"` 调用。**这是本项目第一次有非轴对齐盒的几何**（仍由盒近似）。实测工业园 seed 4：34 分块 / 1,907 盒 / 594,303 方块 / `validation: pass`，罐体 116 盒（基座 28 + 壳 48 + 穹顶 40）。完整回归 165 passed | 船体与干船坞仍是下一项 |
