# Unity 城邦静态区域导出 0.1

本阶段以 `artifacts/benchmark-city-v1/city-first.worldpkg` 的已校验 WIR 城邦为源，导出 512 m 区域的静态 GLB，并在 Unity `6000.3.24f1`、URP `17.3.0`、glTFast `6.20.0` 中实际导入。源世界为 `world_e98d1d4d587fb96f`，源修订为 `revision_c1b82ea36c16a34c95f97c42`。城邦导出器读取 WIR 实体，不使用固定手工样件的 26 构件清单。

## 产物与重建

`artifacts/unity-city/v1/` 包含 `city.glb`、`manifest.json`、`target_profile.json`、`export_report.json`。同一 GLB 和清单复制到 Unity 项目的 `Assets/WorldBuilderCity/`；`CityStatic.unity` 是目标编辑器实际保存的场景。根目录运行：

```powershell
$env:PYTHONPATH='src'
python tools/export_unity_city.py --source artifacts/benchmark-city-v1/city-first.worldpkg --output artifacts/unity-city/new-run
```

将新运行的 `city.glb` 与 `manifest.json` 复制到 `adapters/unity/sample_project/Assets/WorldBuilderCity/`，使用指定编辑器打开项目，执行 `World Builder > Build City Static`。批处理可用 `-batchmode -nographics -quit -projectPath <项目绝对路径> -executeMethod WorldBuilderCityBuilder.Build -logFile <日志路径>`；`WORLD_BUILDER_UNITY_CITY_VALIDATION` 指定验证 JSON 的绝对路径。导出目录必须是新目录，避免悄悄覆盖旧的目标产物。

## 转换边界

176 个 GLB 网格包括 92 条道路、1 座桥、80 栋建筑体量、2 块地表代理和 1 条河道代理。WIR `(东,北,上)` 先转 glTF `(西,上,北)`；目标 glTFast 对 X 轴反射后，Unity 场景为 `(X 东,Y 上,Z 北)`。GLB 节点、清单与 Unity `WorldBuilderSourceId` 组件均保留源实体 ID。每个网格挂 1 个 MeshCollider；区域地面是普通网格，未创建原生 Unity Terrain 或 NavMesh。

损失报告覆盖源包 294 个实体：94 个 `preserved`、82 个 `approximated`、118 个 `omitted`。道路和桥保留源 box 范围；80 栋建筑仅为实体边界的实心代理，未体现门洞、屋顶形状、楼层或室内；地形高程资源被平坦河岸代理替代，河水为半透明长方体；分区、地块、楼层、房间、楼梯和家具均未进入本次 GLB。它们仍在源 WIR 包中。报告状态 `succeeded_with_warnings` 指导出过程，不表示整城漫游通过。

## 本机验证

2026-09-24 对追踪的 `city-first.worldpkg` 重新校验并导出，GLB SHA-256 为 `9fbbe5c489c74ab1566705afa2faa3fd8d305640652599ee33644e205c97be52`。Unity 批处理在 `target-validation.json` 中记录 `target_load=pass`、`collision=pass`、`orientation=pass`，176/176 构件映射、176/176 MeshCollider，桥的目标边界为 X `[252,260]`、Y `[1.6,2]`、Z `[268,274]`，与 WIR 一致；编辑器正常以代码 0 退出。`editor-build-evidence.txt` 保留目标导入与正常退出的日志摘录。`tests/test_unity_city.py` 检查世界包输入、GLB 节点、源 ID、对象级损失报告和桥边界。

2026-09-25 追加 `CityBridgeWalk.unity` 独立运行夹具，可执行菜单 `World Builder > Build City Bridge Walk Validation` 或批处理方法 `WorldBuilderCityBuilder.BuildBridgeWalkValidation` 重建。夹具沿用同一 GLB 和 176 个 MeshCollider，添加高 1.8 m、半径 0.25 m 的 CharacterController，从 `(244,2.1,271)` 出发，沿 WIR `road_cross_west`、`bridge_main`、`road_cross_east` 连续移动。目标检查点为西岸道路 `(248,2,271)`、桥中心 `(256,2,271)`、东岸道路 `(268,2,271)`；每点要求位置、高度及接地，且桥面必须有至少 5 帧接地。35 秒总超时或 5 秒无进展即失败。角色与第一人称相机只属于验收夹具，不包含在 GLB 中。

`artifacts/unity-city/editor-bridge-build-evidence.txt` 记录重建 176 构件、保存场景和编辑器正常以代码 0 退出。随后在 Unity 图形 Play Mode 实走，`artifacts/unity-city/bridge-walk-validation.json` 为 `status=pass`、3/3 检查点、4850 帧接地、桥段 1539 帧接地、零侧向碰撞，终点约 `(267.84,2.08,271)`，同次 Game View 截图为 `bridge-walk-validation.png`。实际目标编辑器曾提示河道代理存在跨度超过 500 单位的大三角形，后续应对长条网格分块并单独验收物理查询稳定性；本次过桥实走通过并不消除该限制。

## 五栋生成室内建筑 v2

2026-09-25 新增独立 `0.1.0-city.2` / `profile_unity_city_6000324_v2` 导出；v1 文件及桥梁证据不变。根目录运行：

```powershell
python tools/export_unity_city.py --source artifacts/benchmark-city-v1/city-first.worldpkg --output artifacts/unity-city/new-interior-run --interiors
```

将新运行的 `city.glb` 与 `manifest.json` 放入 Unity 项目 `Assets/WorldBuilderCity/v2/`，执行菜单 `World Builder > Build City Interior Walk Validation`，或批处理方法 `WorldBuilderCityV2Builder.BuildInteriorWalkValidation`。可用 `WORLD_BUILDER_UNITY_CITY_V2_VALIDATION` 指定目标加载 JSON 路径。生成 `CityInteriors.unity` 和带控制器的 `CityInteriorWalk.unity`；图形 Play Mode 后使用 `WORLD_BUILDER_UNITY_CITY_INTERIOR_WALK_VALIDATION` 指定运行 JSON 路径，默认写入 `artifacts/unity-city/interior-walk-validation.json`。

v2 仍以 WIR 米为单位，目标 Unity 坐标为 `(X 东,Y 上,Z 北)`。五栋 `interior_state=generated` 的建筑使用源入口、墙厚、楼板厚、楼梯洞、直楼梯 20 级参数派生壳体、东侧门洞、两层楼板、梯级和平台；家具仅用源边界盒代理。其余 75 栋仍为实心体量。屋顶为平板代理，没有实现源屋顶形状、室内房间隔墙或原生 Unity Terrain/NavMesh。每个 GLB 构件都保留源实体 ID；源楼层、楼梯和家具可能对应多个网格。对象级报告在 294 个源实体中列出 94 `preserved`、107 `approximated`、93 `omitted`，报告的成功状态只表示导出完成。

本机产物为 `artifacts/unity-city/v2/city.glb`，SHA-256 `31884caef930c85372d42ee62215fda06076bf75d405908a11a0491dab2796fd`，346 个网格。Unity `6000.3.24f1` 批处理正常退出，`v2-target-validation.json` 记录 346/346 源映射与 MeshCollider、首栋东门朝向、五栋各 20 级楼梯映射均通过。图形 Play Mode 中，高 1.8 m、半径 0.25 m 的 CharacterController 从首栋入口道路连续穿过东门、抵达楼梯底、登上二层平台并进入二层房间；`interior-walk-validation.json` 为 `status=pass`、5/5 检查点、零侧向碰撞，末端脚部约 `(25.67,5.28,25.99)`，同次截图为 `interior-walk-validation.png`。

随后执行菜单 `World Builder > Build Remaining City Interior Walk Validations`，或批处理 `-executeMethod WorldBuilderCityV2Builder.BuildRemainingInteriorWalkValidations`，为 `building_001`—`building_004` 生成 `CityInteriorWalk001.unity`—`CityInteriorWalk004.unity`。本固定基准的五栋建筑沿东向每栋相隔 44 m；这组验收场景仅将首栋路线平移，不表示导出器对任意布局自动规划路径。`editor-interior-remaining-build-evidence.txt` 记录四个场景保存与批处理退出码 0；`v2-remaining-target-validation.json` 再次记录 346/346 源映射与碰撞通过。

四个场景均在 Unity 图形 Play Mode 独立运行，分别生成 `artifacts/unity-city/interior-walk-building-001.json`—`interior-walk-building-004.json` 和同名 PNG。四份 JSON 均为 `status=pass`、5/5 检查点、零侧向碰撞；终点脚部 X 依次约为 69.67、113.67、157.67、201.67 m，Y 均约 5.28 m。连同首栋，五栋生成室内建筑各一条道路—东门—楼梯—二层房间路线已实走通过。河道长三角形的物理警告仍存在；法线逐面、分块、导航和性能也未验收。

## 128 m 分块 v3

2026-09-25 新增独立 `0.1.0-city.3` / `profile_unity_city_6000324_v3`，保留 v1/v2 文件和验收证据。v3 以 v2 的同一 346 个源派生盒体为输入，沿 WIR 东、北水平轴按 128 m 半开网格切分；每个切分盒体保留原源 ID、材质索引和米制边界。切分面可能有相邻盒体的内部面；此版本不进行网格合并或远近层级优化。产物为 16 个 `chunks/city_cXX_YY.glb`、`manifest.json`、`target_profile.json` 和 294 实体的 `export_report.json`，共 420 个目标构件。清单记录块路径、SHA-256、构件数量和每个构件的块 ID。材质索引 0/1/2/3 对应 GLB 内的 `stone` / `oak` / `glass` / `dark_oak`；Unity 导入器为每个构件配置普通 `MeshCollider`。源到 glTF、Unity 的坐标矩阵与 v2 相同。普通网格地表仍不等于原生 Terrain；不输出 NavMesh。

根目录运行：

```powershell
$env:PYTHONPATH='src'
python tools/export_unity_city.py --source artifacts/benchmark-city-v1/city-first.worldpkg --output artifacts/unity-city/new-chunked-run --interiors --chunked
```

将新运行的 `manifest.json` 和 `chunks/` 复制到 Unity 项目 `Assets/WorldBuilderCity/v3/`，执行菜单 `World Builder > Build Chunked City v3`，或使用批处理 `-executeMethod WorldBuilderCityV3Builder.Build`。导入器核对每个 GLB 的 SHA-256、源 ID、构件数量、法线与三角面绕序、桥合并边界、最大三角形边长，并生成 `CityChunks.unity`。`WORLD_BUILDER_UNITY_CITY_V3_VALIDATION` 可指定验证 JSON 绝对路径。GLB 使用逐面法线、固定颜色 PBR 材质；没有法线贴图和切线属性，不声称验证带切线材质的反射处理。

本机批处理在 Unity `6000.3.24f1` 正常以代码 0 退出；`artifacts/unity-city/v3-target-validation.json` 记录 16/16 块、420/420 源映射和 MeshCollider、法线/绕序、桥方向与边界均通过，目标网格最大三角形边长 181.0193 m。`editor-v3-build-evidence.txt` 摘录本次日志，未出现先前的超长三角形警告。源端测试还对照 v2 验证各盒体切分后体积完整、坐标不越界。静态检查本身不证明接缝通行；下述 Play Mode 路线单独验证这一点。

2026-09-25 追加独立 `CityChunkBridgeWalk.unity` 运行场景。可通过菜单 `World Builder > Build Chunked City Bridge Walk v3` 或批处理方法 `WorldBuilderCityV3Builder.BuildBridgeWalkValidation` 重建；`v3-seam-target-validation.json` 再次核对 16/16 块、420/420 构件/碰撞。CharacterController 从西岸道路 `(244,2.1,271)` 出发，沿桥面经过 x=256 m 的两个 GLB 分块接缝，抵达东岸道路。此路线使用源修订的桥梁 `bridge_main`，其边界为 x=252—260 m；桥中心检查点位于切分面附近。

在 Unity 图形 Play Mode 的两次独立运行中，控制器均通过西岸道路、桥中心和东岸道路 3/3 检查点，侧向碰撞帧为 0。首次运行文件保存在 `artifacts/unity-city/v3-seam/`（4998 接地帧、1562 桥段接地帧）；首次启动沿用旧默认输出路径，故先保存该次证据并恢复 v1 历史文件。刷新脚本后复测写入独立 `v3-seam-walk-validation.json` 及同名 PNG，结果 `status=pass`，4465 接地帧、1453 桥段接地帧，东岸终点约 `(267.84,2.08,271)`。新夹具按场景名选择默认输出路径，不覆盖 v1 证据。该路线证明一处桥面分块接缝在此控制器设置下可连续通过；其它接缝、NavMesh、性能及 007 联调仍待验证。

## v3 道路与桥梁导航

独立 `CityChunkNavigation.unity` 以 v3 的 16 个 GLB 为输入，通过 Unity AI Navigation `2.0.14` 的 `NavMeshSurface` 烘焙。`WorldBuilderCityV3NavBuilder.Build` 首先重建并核对静态场景，再根据 `WorldBuilderSourceId` 只标记 `road_*`、`access_*` 和 `bridge_main` 的渲染网格；分别为 44、90、2 个分块构件，共 136 个。地表、河道、建筑、楼层及楼梯没有进入此导航面。使用 Unity 默认 agent type 0，半径 0.5 m、高 2.0 m；NavMesh 数据单独保存为 `CityChunkRoadsAndBridgeNavMesh.asset`。这是一份道路及桥梁导航夹具，不代表通用室内导航或全部接缝可达。

在项目目录用 Unity `6000.3.24f1` 执行菜单 `World Builder > Build Chunked City Navigation v3`，或批处理 `-executeMethod WorldBuilderCityV3NavBuilder.Build`；用 `WORLD_BUILDER_UNITY_CITY_V3_NAV_VALIDATION` 指定构建验证 JSON。独立执行 `-executeMethod WorldBuilderCityV3NavBuilder.ValidateSaved` 可重新打开保存的导航场景，使用 `WORLD_BUILDER_UNITY_CITY_V3_NAV_REOPEN_VALIDATION` 指定重载验证 JSON。该方法检查场景对 NavMesh 资产的引用，并在新编辑器进程中重新计算西岸 `(244,2,271)` 到东岸 `(268,2,271)` 的路径。

2026-09-25 目标编辑器批处理生成 `artifacts/unity-city/v3-navigation-validation.json`：136 个指定网格、`PathComplete`、路径 24 m，路径于 z=271 m 穿过桥面 x=256 m；`v3-navigation-reopen-validation.json` 在重新打开场景后仍为 `PathComplete`、24 m。两个批处理日志均以退出码 0 结束，摘录见 `editor-v3-navigation-evidence.txt`。已有 Play Mode 接缝实走证据与本次 NavMesh 路径查询分别验证控制器运动和导航数据；Agent 运行由下述独立场景另行验收。

随后新增独立 `CityChunkAgentWalk.unity`，由 `WorldBuilderCityV3NavBuilder.BuildAgentWalkValidation` 从已保存的导航场景派生，不重新烘焙或覆盖 NavMesh。场景中的 Agent 使用 type 0、半径 0.5 m、高 2.0 m、速度 3 m/s，从西岸 `(244,2,271)` 自动寻路到东岸 `(268,2,271)`。运行组件逐帧核对 Agent 始终处于 NavMesh、路径完整、连续位移穿过 x=256 m 的桥中心，并以物理射线确认移动时桥面支撑网格来自源 `bridge_main`。菜单 `World Builder > Build Chunked City Agent Walk v3` 创建场景；`World Builder > Run Chunked City Agent Walk v3` 启动 Play Mode。批处理先用 `-batchmode -nographics -quit -executeMethod WorldBuilderCityV3NavBuilder.BuildAgentWalkValidation` 建场景，再用 `-batchmode -nographics -executeMethod WorldBuilderCityV3NavBuilder.RunAgentWalkValidation` 运行；后者在写出结果后自行退出，可用 `WORLD_BUILDER_UNITY_CITY_V3_AGENT_VALIDATION` 指定 JSON 路径。

Unity `6000.3.24f1` 无图形 Play Mode 的最终 `v3-agent-walk-validation.json` 为 `status=pass`：8.21 秒到达东岸 `(267.80,2.02,271.00)`，461 帧有实际位移，其中桥段 163 帧均射线命中 `bridge_main`，跨过 `(256.00,2.02,271.00)`；全程 0 帧离开 NavMesh，最大单帧位移 0.0726 m，最终路径为 `PathComplete`。场景构建和运行进程退出码均为 0，日志摘录见 `editor-v3-agent-evidence.txt`。另一次运行也通过，但无图形模式的帧数随编辑器速度变化，因此这里以实际位移、桥面来源和位置为连续运动证据，不以帧数衡量性能；该 v3 道路场景没有覆盖建筑室内、其它分块接缝、多人避障或性能。

## v2 首栋室内导航

独立 `CityInteriorNavigation.unity` 从已验收的 v2 `CityInteriors.unity` 派生，沿用同一 WIR 修订与 346 构件的目标场景。导航夹具只选 `building_000` 的 `access_000` 接入道路、5 块楼板、20 级楼梯和 1 块平台为可行走源，共 27 个网格；6 块墙体/门楣标为 `Not Walkable`，其余建筑、地表和河道不参与烘焙。Unity AI Navigation `2.0.14` 使用默认 agent type 0（半径 0.5 m、高 2.0 m）和 0.05 m 体素；烘焙数据保存为 `CityInterior000NavMesh.asset`。此文件不修改源 GLB，也不代表五栋都具备导航。

首次目标烘焙中，入口道路与首层楼板在 x=32 m 处仅接边，NavMesh 的首段路线为 `PathPartial`；结合构件边界，推断 Agent 半径收缩使两块导航面无法自动连接。因此在 WIR 东门洞 x=32 m、z=16.5 m 增加宽 1.2 m 的双向 `NavMeshLink`，连接道路顶面与室内首层。该 Link 单独序列化在场景中；仅复制 NavMesh 数据资产不足以重建门洞连接。修订后从道路 `(34,2,16.5)` 到二层房间 `(25.5,5.2,26)` 的直接路径为 `PathComplete`、18.61 m；道路—门内—梯底—二层平台—房间的四段路径也均完整。直接路径在源门洞范围穿越 x=32 m，并于梯级范围从低层升至上层。

在 Unity `6000.3.24f1` 使用菜单 `World Builder > Build First City Interior Navigation v2` 或批处理 `-batchmode -nographics -quit -executeMethod WorldBuilderCityV2InteriorNavBuilder.Build` 重建；`WORLD_BUILDER_UNITY_CITY_V2_INTERIOR_NAV_VALIDATION` 指定 JSON 路径。菜单 `World Builder > Validate Saved First City Interior Navigation v2` 或方法 `WorldBuilderCityV2InteriorNavBuilder.ValidateSaved` 会在另一编辑器进程重开场景、核对 NavMesh 资产和东门 Link，并重新查询路径；`WORLD_BUILDER_UNITY_CITY_V2_INTERIOR_NAV_REOPEN_VALIDATION` 指定结果路径。`v2-interior-nav-validation.json` 与 `v2-interior-nav-reopen-validation.json` 均为 `status=pass`、18.61 m，两次批处理退出码均为 0；初始失败与修复的日志摘录见 `editor-v2-interior-nav-evidence.txt`。该阶段验证静态 NavMesh 路径；室内 NavMeshAgent 实际运动、其余四栋和运行性能仍待验。
