# 008 Unity 场景导出与加载验证

- 状态：in_progress
- 修改范围：2026-09-27 root 在已保存的 `OpenSpacePlaza.unity` 上新增独立 Play Mode 步道通行夹具与结果，不改既有 GLB/清单；验证 CharacterController 沿源 `open_space_site_001_path` 连续运动、接地与碰撞来源。修改 Unity Editor/运行组件、独立目标证据、说明及 008/000/索引，仅本地提交。
- 修改范围：2026-09-27 root 接入场景驱动 WIR 的 Unity 静态导出，并在已安装的 Unity 6000.3.24f1 中加载一个含开放空间的代表场景；新增独立产物与目标证据，不覆盖 city.7/v1—v3 历史场景。
- 创建日期：2026-09-21
- 执行者：root
- 依赖：005；具备对应样件源修订和可用 Unity 目标环境
- 修改范围：2026-09-25 本阶段由 root 实施五栋已生成室内建筑的 Unity 派生构件与通行验收，涉及 `src/world_builder/adapters/unity/city.py`、`tests/test_unity_city.py`、`adapters/unity/sample_project/Assets/WorldBuilderCity/`、`artifacts/unity-city/`、`docs/contracts/unity-city-v0.1.md` 及 008/000/索引。源 WIR、固定手工样件及 WIR 0.1 Schema 不改；导出版本另起 v2，不覆盖 v1 证据。
- 修改范围：2026-09-25 后续由 root 对其余四栋生成室内建筑逐栋做 Unity Play Mode 通行验收；修改 `WorldBuilderCityV2Builder.cs`、`WorldBuilderCityInteriorWalkValidator.cs`、新场景/运行证据、008/000/索引及 Unity 城邦说明。v2 GLB 与首栋已有证据保持不变。
- 修改范围：2026-09-25 root 继续分块子阶段；新增 v3 网格切分与多 GLB 清单、对应 Unity 静态导入和验证，修改 `city.py`、CLI、测试、`WorldBuilderCity/Editor/`、独立 v3 产物、说明及 008/000/索引。v1/v2 导出与目标证据不覆盖；导航和 007 联调另行验收。
- 修改范围：2026-09-25 root 继续 v3 运行时接缝验收；修改 `WorldBuilderCityV3Builder.cs` 与既有 `WorldBuilderCityBridgeWalkValidator.cs` 的场景专属证据路径，新增 v3 跨桥 Play Mode 场景及运行证据、说明与 008/000/索引。保留 v1/v2 和 v3 静态导出证据；导航与 007 联调仍独立验收。
- 修改范围：2026-09-25 root 继续 v3 导航子阶段；新增独立 Unity 导航场景、Editor 重建及目标 NavMesh 路径验证、对应证据与说明，同步 008/000/索引。限定道路与桥梁导航，保留既有 v1/v2/v3 场景和运行证据；007 联调、其它接缝与性能另行验收。仅本地提交。
- 修改范围：2026-09-25 root 继续 v3 NavMeshAgent 运行验收；新增独立运行场景、运行时记录组件和批处理/Play Mode 启动入口，修改 `WorldBuilderCityV3NavBuilder.cs`、`Assets/WorldBuilderCity/`、独立证据、Unity 城邦说明及 008/000/索引。复用已保存的 v3 NavMesh，不覆盖先前静态/控制器/NavMesh 证据；室内导航和 007 联调不在本阶段。仅本地提交。
- 修改范围：2026-09-25 root 继续 v2 首栋室内导航子阶段；从已验收的 `CityInteriors.unity` 派生独立 NavMesh 场景及目标路径验证，新增 `WorldBuilderCity/Editor/` 构建器、独立证据、说明和 008/000/索引。先验证 `building_000` 道路—东门—楼梯—二层房间，不改源 WIR、v2 GLB 或既有运行证据；其余四栋及 Agent 室内实走另行验收。仅本地提交。
- 修改范围：2026-09-25 root 继续 v2 首栋室内 NavMeshAgent 运行验收；修改 `WorldBuilderCityV2InteriorNavBuilder.cs` 并新增独立运行组件、场景、JSON/日志摘录、说明和 008/000/索引。验证已保存导航面上道路—东门—楼梯—二层房间的实际 Agent 运动；不覆盖先前导航/控制器证据。开工时发现 `v3-agent-walk-validation.json` 有阶段外未提交变化，保留原状且不纳入本次提交。仅本地提交。

## 当前主线衔接（2026-10-10）

既有样件与规则版城邦证据保留。新主线通用场景适配由 036 实施、真实模型产物验收由 024 实施；结果按子项回填本工单，避免重复开发。源表示/自然资产由 029/031 交接，target profile 归 035。007 同修订联调作为完整手工编辑的后续子项，不阻塞独立场景导入与加载。下方带日期的实现和未完成描述按对应版本理解，状态核对归 038。

## 目标与范围

把同一 WIR 修订转成可以在固定 Unity 环境使用的区域场景。

目标编辑器、固定两层样件导入和控制器连续漫游已验证；通用区域导出及与 006/007 同修订的代表性城邦联调尚未实施。

## 本机编辑器子阶段

- [x] ~~停止用户报告有警告的 6000.3.0f1 安装，将目标修订为同一 6.3 LTS 系列的 6000.3.24f1。~~
- [x] ~~安装 6000.3.24f1 并核对 CLI 结构检查、可执行文件版本和 Windows 数字签名。~~
- [x] ~~建立与新版本匹配的 URP/glTFast 精确包配置，并完成手工两层样件实际导入。~~

## 工作项

- [x] ~~固定并记录 Unity、渲染管线、glTF 导入包版本及安装/运行步骤。~~
- [x] ~~005 完成后先转换手工两层建筑样件，验证坐标、门洞、楼梯和基础碰撞，作为 006 扩规模的前置子项。~~
- [x] ~~输出分块 GLB、场景清单、对象 ID、材质映射和碰撞描述。~~
- [ ] 实现 Editor 导入器，恢复场景层次、位置、碰撞与约定的导航设置。
- [ ] 验证坐标、法线、比例、实例化与目标材质降级，生成损失报告。
- [ ] 输出符合 WIR 0.1 `export_report` 的对象映射与损失统计；Unity 反射变换必须处理绕序、法线和切线。
- [ ] 导入与查看器同一修订的代表性城邦并进行漫游与室内可达性验收。

## 城邦静态区域子阶段（2026-09-24）

- [x] ~~从已校验的 512 m WIR 城邦包导出道路、桥、建筑体量和地表/河道代理 GLB，保留源 ID 与修订。~~
- [x] ~~输出符合 WIR 0.1 的逐实体损失报告，明确 80 栋实心代理、平坦地形及未进入场景的室内对象。~~
- [x] ~~在 Unity 6000.3.24f1 实际加载同一城邦修订，核对构件映射、碰撞体和桥的目标边界。~~
- [x] ~~在 Play Mode 连续实走道路和桥，建立可核对的运行证据。~~
- [x] ~~五栋生成室内建筑转为可进入壳体与楼梯，完成首栋道路—门—二层房间目标连续通行。~~
- [x] ~~逐栋验证其余四栋从入口道路经东门和楼梯到二层房间的连续路线。~~
- [ ] 完成分块、法线、导航及 007 同修订联调。

其中分块与普通材质逐面法线的静态目标导入已由 v3 验证；桥面 x=256 m 的一处接缝已 Play Mode 实走通过。其它接缝、切线材质、完整导航、性能及 007 联调尚未完成。

道路与桥梁的独立 v3 NavMesh 已完成烘焙、保存场景重载路径验证和独立 NavMeshAgent Play Mode 跨桥运动；v2 首栋室内已验证道路—东门—楼梯—二层房间的静态路径及 Agent Play Mode 运动。其余四栋室内导航、其它接缝及性能仍待验。

- [x] ~~为 v3 主路、接入道路和桥梁生成独立 NavMesh，并在保存场景重载后验证跨桥完整路径。~~
- [x] ~~在独立 Play Mode 场景中验证 NavMeshAgent 沿已保存的导航面连续跨桥。~~
- [x] ~~验证 v2 首栋从入口道路经东门、楼梯到二层房间的 NavMesh 完整路径及保存场景重载。~~
- [x] ~~在独立 Play Mode 场景中验证 v2 首栋 NavMeshAgent 经东门、梯级到二层房间。~~

## 2026-09-27 场景开放空间样件

- [x] ~~从场景流水线的 WIR 修订导出一个广场的铺装、步道和 32 个设施，保留源 ID、版本、单位及限制。~~
- [x] ~~在 Unity 6000.3.24f1 导入并保存场景，独立进程重开复核 34/34 源 ID 和 MeshCollider。~~
- [x] ~~从已保存场景派生独立 Play Mode 步道夹具，验证控制器沿源步道连续通过三个检查点、接地及碰撞来源。~~
- [ ] 将同修订的其余地形、道路、建筑及室内接入 Unity，生成完整对象级损失报告，并完成图形/Play Mode 与 007 联调。

证据：`artifacts/unity-scene-open-space-plaza/manifest.json`、`target-validation.json`、`target-reopen-validation.json` 和 `docs/contracts/unity-scene-open-space-v0.1.md`。本子阶段仅是一个开放空间的静态样件，不把它计为完整城邦验收。

## 验收标准

- 在指定 Unity 版本实际导入，无缺失引用；能够行走道路、过桥、进入室内并上下楼。
- 不对称坐标样例朝向正确；稳定实体 ID 可以追溯至 WIR。
- 明确是否使用普通地形网格，不能把 GLB 导入宣称为自动创建原生 Unity Terrain。
- 场景包包含重建指引、版本配置、报告和验证证据。

## 执行记录

| 日期 | 执行者 | 动作 | 结果与证据 | 下一步 |
|---|---|---|---|---|
| 2026-09-27 | root | 广场步道 Play Mode 连续通行 | 首次无图形批处理因每帧步进低于移动阈值停滞，`walk-first-failure.json` 留证；修正仿真步长后 `walk-validation.json` 为 3/3 检查点、1,444 接地帧、1,459 源步道碰撞命中帧、0 侧面碰撞、12.26 秒仿真时间，场景构建/运行进程均退出码 0 | 完整场景、图形观察、其它道路/接缝及 007 同修订联调；008 保持 in_progress |
| 2026-09-27 | root | 场景流水线 WIR 的广场导出 Unity 静态样件，并在目标编辑器导入、独立进程重开 | 修订 `revision_6e0278367b0b90212b809b`；34/34 节点源 ID 与 MeshCollider，两个目标验证 JSON 均 pass；定向测试 2 passed、完整回归 156 passed、文档检查零错误；能力边界见 `docs/contracts/unity-scene-open-space-v0.1.md` | 接入其余场景实体、对象级损失报告、图形/运行时与 007 联调；008 保持 in_progress |
| 2026-09-21 | root | 根据正式方案创建后续工单 | 本文件；尚无实现或测试结果 | 依赖满足后认领，执行前重新阅读索引、总规划和本工单 |
| 2026-09-21 | root | 根据独立审查校准规划 | 与正式方案的状态合同、小样先行或需求确认边界保持一致；工单仍为 planned | 对应实施阶段再执行与验证 |
| 2026-09-22 | root | 接收 Unity 6000.3.0f1 候选 profile、坐标合同和能力矩阵 | 版本已冻结但未在 `tx5` 安装验证；`river_bridge` 不对称标记用于坐标检查 | 开工时先验证安装组合和手工样例 |
| 2026-09-23 | root | 按用户授权认领 Unity 目标环境安装阶段 | 本轮范围限于通过已安装 Unity Hub 获取 6000.3.0f1、核对模块与本机版本，并同步工单；场景导出与加载仍待实施 | 检查 Hub 状态和可用安装入口 |
| 2026-09-23 | root | 用 Hub 随附 Unity CLI 预检并启动 6000.3.0f1 安装 | 预检确认 x86_64 编辑器下载量 4,131,048,448 字节、默认安装路径 `C:\Program Files\Unity\Hub\Editor`；CLI 安装进程仍在运行，尚无已安装编辑器证据 | 等待下载与安装完成，运行版本核对 |
| 2026-09-23 | root | 按用户报告的官方签名警告取消旧版本安装并修订目标 profile | 用户停止 6000.3.0f1 后，另行运行的 Unity CLI 下载进程仍在；已中断该进程，CLI `editors --installed` 返回空。Unity 官方发布页与 Hub 正式发行版列表均列出 6000.3.24f1，Hub 列表中该版本无旧版的警告标记；保留旧样例 profile 作为历史输入，新目标版本待实际安装核对 | 预检并安装 6000.3.24f1，核对下载签名和运行结果 |
| 2026-09-23 | root | 预检并启动修订版安装，检查旧缓存清理 | 6000.3.24f1 CLI 预检下载量 4,127,507,400 字节、零警告；新下载已开始。尝试清理旧 6000.3.0f1 的部分下载文件被自动审批以 `blocked by policy` 拒绝，未删除文件；该缓存不作为安装结果 | 等待新版安装并核对数字签名和实际版本 |
| 2026-09-23 | root | 完成 6000.3.24f1 本机编辑器安装与签名核对 | Unity CLI 安装返回 `status=installed`、零错误/警告；`editors --installed` 列出 x86_64 目标，`editors verify` 返回 `ok=true`。完整安装包与 `Editor/Unity.exe` 的 Windows Authenticode 均为 `Valid`，签名者 `Unity Technologies SF`；可执行文件 `ProductVersion=6000.3.24f1_4e7b9b5b6244`。`docs/contracts/environment-baseline.md` 记录实际路径和边界 | 为手工样件建立新版本的 URP/glTFast profile，导入后才可验收 008 |
| 2026-09-23 | root | 按用户“继续推进”认领 Unity 手工样件子阶段 | 本轮修改范围见文件头；本机 6000.3.24f1 附带的 3D Cross Platform 模板 17.0.14 将 URP 固定为 17.0.1；Unity 包注册表显示 glTFast 6.20.0 为稳定版、最低 Unity 6000.0，待实际项目解析确认 | 建立可重现项目，导出样件并在编辑器中加载核对 |
| 2026-09-23 | root | 建立样件项目并首次目标导入 | Unity 批处理首次打开成功，实际包锁为 URP 17.3.0、glTFast 6.20.0。v1 GLB 的 26 个网格均被导入，但不对称东窗校验失败：目标中心为 `(-23.88,6,-13)`，而预期是 `(23.88,6,13)`；这表明 glTFast 在此版本反射 glTF X 轴，导出前的坐标矩阵需调整。失败记录见 `artifacts/unity-sample/editor-build-scene.log` 和 `target-validation.json` | 修正 WIR→glTF 矩阵，生成 v2 后重跑目标导入 |
| 2026-09-23 | root | 修正坐标矩阵并完成 v2 目标导入 | `artifacts/unity-sample/v2/library.glb` SHA-256 `f9dd083acf180287549b23d1aa70e1b0fab4eaa69a484ee4c58e425bb252f75a`；Unity `-executeMethod WorldBuilderSampleBuilder.Build` 退出码 0，`target-validation-v2.json` 记录 26/26 构件映射、26/26 MeshCollider、东窗不对称坐标与实际 prefab 导入均 pass。场景 `adapters/unity/sample_project/Assets/WorldBuilderSample/LibrarySample.unity` 已生成。`pytest tests/test_unity_sample.py` 2 passed；详见 `docs/contracts/unity-sample-v0.1.md`。尚未目视或控制器漫游 | 运行场景，验门洞/楼梯通行；之后才可扩大 006/008 联调范围 |
| 2026-09-23 | root | 收紧样件项目交付范围 | 编辑器生成的本地缓存、解决方案及模板教程/示例资产已加入 `.gitignore`，样件自己的 GLB、场景、脚本和 URP 配置保留；尝试清理本机模板教程/示例资产时自动审批以 `blocked by policy` 拒绝，未删除文件 | 复核包清单和场景引用，保持本机现状 |
| 2026-09-23 | root | 在 Unity 图形界面打开并重建样件 | Hub 识别 `sample_project` 为 Unity 6000.3.24f1 项目；用户授权接受编辑器条款后打开。图形菜单构建再次输出 `artifacts/unity-sample/target-validation.json`：26/26 构件、26/26 MeshCollider、方向 pass；Scene 视图显示屋顶/东窗，Game 视图显示南立面/门洞。包管理器在线检索 `packages.unity.com` 连接重置，但本地包已注册且场景构建成功。构建场景的 Build Settings 改为 `LibrarySample.unity`，不再指向忽略的模板场景 | 下一步加入角色通行验证，门洞与楼梯尚未以控制器连续走通 |
| 2026-09-23 | root | 复核最终项目保存与批处理重建 | `EditorBuildSettings.asset` 指向 `LibrarySample.unity` 的实际 GUID；构建器补充 `AssetDatabase.SaveAssets()` 后重新批处理，`artifacts/unity-sample/target-validation-final.json` 全项 pass，日志以 `return code 0` 结束；完整 Python 回归 63 passed、文档检查 33 Markdown/40 链接/5 JSON/13 工单零错误 | 保持 008 in_progress，下一步验证实际控制器穿门、上楼 |
| 2026-09-24 | root | 按用户要求开始 Unity 连续漫游验收并登记修改范围 | 既有 v2 GLB、26 个 MeshCollider、东窗方向和目标编辑器导入已通过；仍缺从南门到二层的控制器连续运动证据。本轮只新增样件验收场景与控制器，保留原 GLB 和源样例 | 构建可记录控制器碰撞与路线的目标运行场景，在 Unity Play Mode 实走并保存证据 |
| 2026-09-24 | root | 完成固定两层样件的 Unity 控制器漫游 | `LibraryWalkValidation.unity` 使用 1.8 m 高、0.25 m 半径、0.55 m 跨阶的 CharacterController；`walk-scene-build-evidence.txt` 摘录重新编译、重建和退出码 0 的日志。Unity 6000.3.24f1 图形 Play Mode 连续经过南门、一层、楼梯底、二层平台和二层房间；`artifacts/unity-sample/walk-validation.json` 为 `status=pass`、5/5 检查点、终点脚部 Y≈4.28 m；`walk-validation.png` 留下同次运行画面。`pytest tests/test_unity_sample.py` 2 passed，文档检查 33 Markdown/40 链接/5 JSON/13 工单零错误。夹具不属于通用 GLB/导出器 | 固定样件子项完成；008 仍 in_progress，下一步实现通用区域、道路/桥及与 006/007 同修订联调 |
| 2026-09-24 | root | 按用户继续推进认领城邦静态区域子阶段 | 本轮文件范围见文件头；512 m 源端城邦包与固定样件验收证据已具备，目标城邦尚未导出或加载 | 建立真实 WIR 派生 GLB、对象映射与明确损失，再运行 Unity 目标导入 |
| 2026-09-24 | root | 完成 512 m 城邦静态 GLB 与 Unity 目标加载 | `artifacts/unity-city/v1/city.glb` 对应源修订 `revision_c1b82ea36c16a34c95f97c42`，SHA-256 `9fbbe5c489c74ab1566705afa2faa3fd8d305640652599ee33644e205c97be52`；176 个网格、294 实体逐项报告（94 保留/82 近似/118 省略）。Unity 6000.3.24f1 批处理保存 `CityStatic.unity`，`target-validation.json` 为 176/176 ID 与碰撞、桥方向/尺寸、加载全 pass，日志记录退出码 0。Python 全套 `70 passed`，文档检查 34 Markdown/40 链接/5 JSON/13 工单零错误。详情见 `docs/contracts/unity-city-v0.1.md` | 008 保持 in_progress；下一步实际角色跨桥，再实现并验证 5 室内/楼梯、法线与导航；007 尚未提供同修订查看器联调 |
| 2026-09-24 | root | 提交本阶段产物并尝试推送 GitHub | 本地提交完成、工作树干净；三次推送均因 `github.com:443` 连接重置或无法连接失败，远端仍停留在上次提交；没有把未推送内容称为远端成果 | 网络恢复后推送本地 `main`，再继续目标跨桥验收 |
| 2026-09-25 | root | 补推上轮提交并认领城邦跨桥运行验收 | `git push origin main` 成功，远端推进至 `1f5c296`；核对 WIR `road_cross_west`、`bridge_main`、`road_cross_east` 在北向 268—274 m 连续衔接。本阶段修改范围见文件头 | 建立角色路线与独立场景，在 Unity Play Mode 连续过桥并留证 |
| 2026-09-25 | root | 完成 Unity 城邦道路—跨桥 Play Mode 连续验收 | `WorldBuilderCityBuilder.BuildBridgeWalkValidation` 批处理重建 176 构件与独立 `CityBridgeWalk.unity`，正常以代码 0 退出；图形 Play Mode 的 `bridge-walk-validation.json` 为 3/3 检查点、4850 帧接地、桥段 1539 帧接地、零侧向碰撞、`status=pass`，同次 `bridge-walk-validation.png` 留证。源修订仍为 `revision_c1b82ea36c16a34c95f97c42`。Unity 提示河道代理大三角形可能影响物理查询稳定性；本次路线未受阻，不视为普遍排除风险 | 008 保持 in_progress；下一步城邦可进入室内及楼梯、分块/法线/导航与 007 同修订联调 |
| 2026-09-25 | root | 提交跨桥验收产物并尝试推送 | 本地提交完成、工作树干净；前两次 `git push origin main` 分别因连接重置与 `github.com:443` 无法连接失败，远端当前仍为 `1f5c296` | 网络恢复后推送本地跨桥提交；继续室内阶段前重新确认远端状态 |
| 2026-09-25 | root | 认领五栋城邦室内目标验收 | 本次补推 `b529c49` 仍因连接重置失败，本地工作树干净；WIR 首例五栋生成室内建筑均具东侧入口、2 层、预留楼梯洞、20 级直楼梯，参数已核对。本轮文件范围见文件头 | 生成独立 v2 GLB、更新真实对象级损失，再在目标编辑器里实走门洞与楼梯 |
| 2026-09-25 | root | 导出五栋室内并完成 Unity 目标导入 | 独立 v2 GLB 有 346 构件，SHA-256 `31884caef930c85372d42ee62215fda06076bf75d405908a11a0491dab2796fd`；294 实体损失为 94 保留/107 近似/93 省略。Unity 6000.3.24f1 批处理退出码 0，`v2-target-validation.json` 为 346/346 ID/碰撞、东门朝向和五栋 100 级梯级映射 pass | 在图形 Play Mode 实走首栋入口与二层，检查截图与 JSON |
| 2026-09-25 | root | 完成首栋城邦室内的目标连续通行 | `CityInteriorWalk.unity` 图形 Play Mode 从道路穿东门、抵达梯底、登上平台并进入二层房间；`interior-walk-validation.json` 为 5/5 检查点、零侧向碰撞、`status=pass`，末端脚部约 `(25.67,5.28,25.99)`；同次 PNG 留证。其余四栋只通过静态映射，未逐栋实走；长河道网格仍提示大三角形 | 跑完整回归与文档检查；后续验证其余四栋、分块/法线/导航及 007 同修订联调 |
| 2026-09-25 | root | 完成 v2 回归与交接文档 | `python -m pytest -q --basetemp artifacts/pytest-unity-city-full` 为 71 passed；`python tools/check_project_docs.py` 检查 34 Markdown/40 链接/5 JSON/13 工单、零错误。`docs/contracts/unity-city-v0.1.md` 记录重建、目标证据和未验边界，`editor-interior-build-evidence.txt` 留存正常退出日志 | 提交并尝试推送；008 继续 in_progress，后续按未完成项推进 |
| 2026-09-25 | root | 提交并推送室内阶段与先前滞留的跨桥阶段 | 本地提交 `d687581`，`git push origin main` 成功，远端由 `1f5c296` 前进至 `d687581`，包含先前跨桥提交 `b529c49` | 008 继续 in_progress；后续逐栋通行、分块/法线/导航及 007 同修订联调 |
| 2026-09-25 | root | 认领其余四栋室内实走子阶段 | 工作树干净且 `main` 与 `origin/main` 一致；五栋源建筑几何按东向 44 m 等距排列，首栋相同路线已通过。本轮范围见文件头 | 生成四个独立验证场景，在目标编辑器逐栋运行并记录 JSON/截图 |
| 2026-09-25 | root | 完成其余四栋 Unity 室内路线验收 | `WorldBuilderCityV2Builder.BuildRemainingInteriorWalkValidations` 在 Unity 6000.3.24f1 保存四个独立场景并以代码 0 退出；`v2-remaining-target-validation.json` 再次为 346/346 ID/碰撞 pass。四栋各在图形 Play Mode 连续穿东门、上楼进入二层房间，`interior-walk-building-001`—`004.json` 各为 5/5 检查点、零侧向碰撞、`status=pass`，同名 PNG 留证；末端 X 依次约 69.67/113.67/157.67/201.67 m，Y 均约 5.28 m | 008 继续 in_progress；分块/法线/导航及 007 同修订联调待做 |
| 2026-09-25 | root | 复核四栋实走证据与项目文档 | 脚本逐项核对四份 JSON 的源建筑 ID、5/5 检查点、零侧向碰撞、二层终点、高于阈值的楼梯接地帧与 PNG 存在；全部通过。`python tools/check_project_docs.py` 为 34 Markdown/40 链接/5 JSON/13 工单、零错误；本阶段 Python 导出器未改，沿用上轮 71 passed 结果 | 整理提交与推送；008 未完成的目标能力继续留在工单 |
| 2026-09-25 | root | 提交四栋实走成果并尝试推送 | 本地提交 `38d4308` 完成；连续四次 `git push origin main` 分别因连接重置和 `github.com:443` 无法连接失败。本地 `origin/main` 最后已知为 `573d0eb`，未把本次提交称为远端成果 | 网络恢复后补推；008 后续实施分块/法线/导航和 007 同修订联调 |
| 2026-09-25 | root | 认领 v3 分块导出与静态目标验证 | 当前本地修改范围见文件头；先前积压提交本轮已推至 `origin/main` 的 `4ee4ce8`。用户随后明确改为自行处理远端，之后仅本地提交。Unity 曾报告 512 m 河道代理的大三角形警告 | 生成独立 v3 分块 GLB 并在 Unity 中核对源映射、碰撞和三角形跨度 |
| 2026-09-25 | root | 完成 v3 源端切分与回归 | 同一修订按 128 m 水平网格裁切盒体，独立输出 16 个 GLB、420 构件，每块有 SHA-256 与源 ID；对象级报告仍为 94 保留/107 近似/93 省略。`pytest tests/test_unity_city.py` 4 passed；测试对照 v2 验证切分体积覆盖、无越界及构件对角线小于 182 m | 在 Unity 6000.3.24f1 实际导入 v3 并核对碰撞、方向和长三角形警告 |
| 2026-09-25 | root | 完成 v3 分块 Unity 静态导入与几何核对 | `v3-target-validation.json` 为 16/16 块、420/420 源映射和 MeshCollider、法线/绕序、桥边界均 pass，最大三角形边长 181.0193 m；批处理退出码 0，同次构建日志无长三角形警告。`CityChunks.unity`、16 个项目内 GLB 和重建说明已保存；此证据不覆盖运行时接缝通行或 NavMesh | 跑完整回归与文档检查，再做分块接缝 Play Mode、导航和 007 同修订联调 |
| 2026-09-25 | root | 完成 v3 全量回归与文档检查 | `python -m pytest -q --basetemp artifacts/pytest-unity-city-v3-full` 为 72 passed；`python tools/check_project_docs.py` 为 34 Markdown/40 链接/5 JSON/13 工单、零错误。导出器、CLI、目标场景、报告与说明均已形成独立 v3 产物 | 只做本地提交；008 继续 in_progress，后续运行时接缝/导航/007 联调待做 |
| 2026-09-25 | root | 认领 v3 桥面分块接缝实走 | 本地提交 `f0ec14b` 后工作树干净、相对 `origin/main` 领先 1；桥的东向 252—260 m 范围在 x=256 m 分块边界被裁切，既有 v1 桥梁控制器路线可直接验证该边界 | 构建独立 v3 Play Mode 场景，从西岸道路连续通过桥面接缝到东岸道路并留证；本轮只本地提交 |
| 2026-09-25 | root | 完成 v3 一处桥面分块接缝 Play Mode 实走 | `CityChunkBridgeWalk.unity` 批处理重建退出码 0，`v3-seam-target-validation.json` 再次 16/16 块、420/420 构件/碰撞通过。图形 Play Mode 两次从西岸道路连续经过 x=256 m 接缝到东岸道路，均为 3/3 检查点、零侧向碰撞；复测 `v3-seam-walk-validation.json` 为 `status=pass`、4465 接地帧/1453 桥段接地帧、同次 PNG。首次运行证据独立保存于 `artifacts/unity-city/v3-seam/`，v1 历史文件已恢复 | 仅该接缝已验；其它接缝、导航、性能、切线材质及 007 同修订联调继续待做 |
| 2026-09-25 | root | 核对接缝证据与文档 | 清单确认 `bridge_main` 在 `c01_02` 与 `c02_02` 两块的 x=256 m 交界，脚本核对 v3 `status=pass`、3/3 检查点、零侧向碰撞、截图存在且 v1 JSON 仍是 `CityBridgeWalk`；`python tools/check_project_docs.py` 为 34 Markdown/40 链接/5 JSON/13 工单零错误。Python 导出器本轮未改，沿用前阶段 72 passed | 只做本地提交；008 保持 in_progress |
| 2026-09-25 | root | 认领 v3 道路与桥梁导航子阶段 | 本轮修改范围见文件头；Unity 项目已锁定 `com.unity.ai.navigation` 2.0.14，既有 v3 为 16 块/420 构件，桥面 x=256 m 接缝实走通过。导航尚无目标验证证据 | 构建独立导航场景并在 Unity 目标编辑器查询跨桥完整路径 |
| 2026-09-25 | root | 完成 v3 道路与桥梁 NavMesh 目标验证 | `CityChunkNavigation.unity` 的 `NavMeshSurface` 仅烘焙 44 个 `road_*`、90 个 `access_*` 和 2 个 `bridge_main` 分块网格；Unity 6000.3.24f1 批处理保存 NavMesh 数据并以代码 0 退出，`v3-navigation-validation.json` 为 `status=pass`、`PathComplete`、西岸至东岸 24 m。独立批处理重开场景后 `v3-navigation-reopen-validation.json` 再次为 `PathComplete`、24 m，资产引用有效；`editor-v3-navigation-evidence.txt` 摘录两次日志。最初只选 `road_*` 和桥的试跑漏掉接入道路，已修正并复验，未作为最终成果。文档检查为 34 Markdown/40 链接/5 JSON/13 工单零错误 | 只本地提交；008 仍需室内导航/Agent、其它接缝、性能及 007 联调 |
| 2026-09-25 | root | 认领 v3 NavMeshAgent 运行验收 | 工作树干净，上一阶段本地提交 `444b296`；独立导航场景重载后路径为 `PathComplete`、24 m，但未验证 Agent 在 Play Mode 实际运动。本轮修改范围见文件头 | 建立独立运行夹具，使 Agent 从西岸经桥面到东岸并记录位置、耗时与碰撞/停滞证据 |
| 2026-09-25 | root | 完成 v3 NavMeshAgent Play Mode 跨桥运行 | `CityChunkAgentWalk.unity` 从保存的导航场景派生，目标 Unity 6000.3.24f1 场景构建和无图形 Play Mode 进程均以代码 0 退出。最终复测 `v3-agent-walk-validation.json` 为 `status=pass`、`PathComplete`、8.21 秒走到东岸；461 个位移帧，其中桥段 163 个位移帧均由 `bridge_main` MeshCollider 支撑，经过 x=256 m 桥中心，0 帧离开 NavMesh，最大单帧位移 0.0726 m。`editor-v3-agent-evidence.txt` 摘录日志；两次运行均通过，无图形模式帧数变化不用于衡量性能 | 同步说明、总规划及索引，验证文档与提交；后续室内导航、其它接缝、性能、切线材质和 007 联调仍待做 |
| 2026-09-25 | root | 认领 v2 首栋室内导航路径验证 | 上一阶段本地提交 `678d9e3`、工作树干净；五栋室内的 CharacterController 路线已实走，但尚无楼梯 NavMesh。先以 `building_000` 验证从 access road 到二层房间的目标路径，本轮范围见文件头 | 核对源构件边界和导航包参数，建立独立场景并在 Unity 目标编辑器查询门洞与楼梯路径 |
| 2026-09-25 | root | 首次 v2 室内 NavMesh 烘焙发现东门断点 | 目标编辑器构建了首栋 1 接入道路、5 楼板、21 梯/平台及 6 墙/门楣构件的独立 NavMesh，入口道路到门内的第一段路径为 `PathPartial`，进程退出码 1；首次失败信息摘录于 `editor-v2-interior-nav-evidence.txt`。道路与首层楼板在 x=32 m 只接边，推断 Agent 半径收缩后没有拓扑连接；原 CharacterController 物理跨阶证据不等同 NavMesh 连通 | 在源门洞位置增加显式双向 NavMeshLink，重新查询全路线；若楼梯仍断开，逐段定位 |
| 2026-09-25 | root | 增加东门连接并通过首栋室内 NavMesh 路径 | 在 x=32 m、z=16.5 m 源门洞添加 1.2 m 宽双向 NavMeshLink；Unity 6000.3.24f1 批处理退出码 0。`v2-interior-nav-validation.json` 为 `status=pass`、入口到二层房间 `PathComplete`、18.61 m，四段检查点全部完整；直接路径穿过东门且在楼梯区域由低至高。源端 v2 GLB 与已验收场景未覆盖 | 独立进程重开导航场景并复核资产/连接，再同步说明与索引 |
| 2026-09-25 | root | 完成首栋室内导航场景重载验证 | 另一个 Unity 6000.3.24f1 批处理进程重开 `CityInteriorNavigation.unity`，核对 `CityInterior000NavMesh.asset` 引用与东门双向 Link，`v2-interior-nav-reopen-validation.json` 再次为 `status=pass`、`PathComplete`、18.61 m，退出码 0；工单仅勾选首栋静态路径，不将其余四栋或室内 Agent 视为已验 | 文档/索引检查后只本地提交；继续其余四栋、室内 Agent、性能及 007 联调 |
| 2026-09-25 | root | 核对室内导航交付文件与工单 | 场景 YAML 包含 33 个 `NavMeshModifier` 和 1 个东门 `NavMeshLink`；整理后另一编辑器进程重载仍 `PathComplete`、18.61 m，四段路径 4/4 完整。`python tools/check_project_docs.py` 检查 34 Markdown/40 链接/5 JSON/13 工单零错误；本阶段未修改 Python 导出器 | 只本地提交，008 保持 in_progress |
| 2026-09-25 | root | 认领首栋室内 NavMeshAgent 实际运行 | 上阶段本地提交 `b733be4`；首栋静态路径及保存场景重载已通过，Agent 尚未运行。本轮范围见文件头；工作树中原有 `v3-agent-walk-validation.json` 未提交变化属于阶段外证据，保持原状 | 构建独立 Play Mode 夹具并观察东门 Link、楼梯支撑与二层终点 |
| 2026-09-25 | root | 首次室内 Agent Play Mode 完整通过 | `CityInteriorAgentWalk.unity` 在 Unity 6000.3.24f1 批处理建场景及无图形 Play Mode 均以代码 0 退出；首次 `v2-interior-agent-validation.json` 为 `status=pass`、`PathComplete`、9.29 秒抵达二层房间，越过东门、梯级支撑移动 22 帧，0 帧离开 NavMesh。无图形模式单帧最大位移接近当前守卫阈值；将补充门 Link 实际位移与终点楼板来源后复测，再固定最终证据 | 加强运行证据，确认终点支撑并复测 |
| 2026-09-25 | root | 复测发现帧数阈值不适于无图形 Agent 验收 | 增加门 Link 位移及终点楼板来源后，Agent 仍约 9.29 秒到二层、`PathComplete`，门 Link 有实际位移、终点由 `storey_000_1` 支撑；但无图形模式的楼梯射线命中位移帧降至 7、楼层移动帧为 0，触发自设阈值，进程退出码 1。该失败属于采样频率敏感的验收指标，不据此断言楼梯不可达 | 改为沿位移段按固定距离采样楼梯支撑，并以经过楼梯高点、终点楼板来源和位移距离验收 |
| 2026-09-25 | root | 固定间隔初版仍低估路径长度 | Agent 再次约 9.29 秒到达二层、`PathComplete`，但记录器只累计单帧大于 1 mm 的位移，得到不合理的 1.65 m、梯级支撑 0.03 m，触发阈值并退出码 1。无图形模式大量微小位移被过滤；此为证据采样缺陷，不是目标路径失败 | 累计全部位移，按空间累积到固定间隔后再做楼梯支撑射线抽样 |
| 2026-09-25 | root | 修正室内 Agent 证据采样并通过运行 | `v2-interior-agent-validation.json` 为 `status=pass`、`PathComplete`、9.29 秒抵达二层房间；全程 18.62 m、东门 Link 段 3.03 m、源梯级支撑 9.88 m，终点由 `storey_000_1` 楼板支撑，0 帧离开 NavMesh，进程退出码 0。改为累计全部微小位移并按 0.05 m 空间间隔采样，避免无图形帧率左右距离证据 | 再做独立运行确认稳定性，随后整理说明和提交 |
| 2026-09-25 | root | 独立复测室内 Agent 运动 | `v2-interior-agent-validation-repeat.json` 为 `status=pass`、`PathComplete`、9.29 秒、总位移 18.61 m、东门 Link 3.02 m、梯级支撑 9.88 m，终点仍为 `storey_000_1`、0 帧离开 NavMesh，进程退出码 0。两次空间距离指标一致；无图形模式单帧最大位移不同，不据此推断运行性能 | 固定两份结构化证据、场景与说明，文档检查后本地提交 |
| 2026-09-25 | root | 核对整理后的独立 Agent 场景 | 清理新 Unity 场景序列化的尾部空格后，另一无图形 Play Mode 进程再次 `status=pass`、`PathComplete`、梯级支撑约 9.83 m、退出码 0；此次临时复核 JSON/日志在系统临时目录，不覆盖两份交付证据。`python tools/check_project_docs.py` 检查 34 Markdown/40 链接/5 JSON/13 工单零错误。阶段外的 `v3-agent-walk-validation.json` 未提交变化仍保留 | 暂存区检查后只提交本阶段文件，008 继续 in_progress |

| 2026-09-27 | root | 风格建筑样件 v5 Unity 目标落地 | 独立木构街屋导入与另进程重开均为 143/143 构件来源 ID、MeshCollider 通过；`artifacts/building-style-study/v5/unity-walk-validation.json` 的 1.8 m CharacterController 连续走通门、商铺、楼梯、二层房间，6/6 检查点、326 帧楼梯支撑、0 帧侧向阻挡；斜向目标截图已取得。v3/v4 的入口受阻失败证据保留在各自目录，修复和任务边界见 021；此结果仅限手工街屋样件 | 继续通用 E 设计器与场景适配器的多层/风格能力 |

## 交接说明

2026-10-10 路线变更（028）：仅更新文档依赖和职责，未新增 Unity 导出、加载或实走证据，状态保持 in_progress。下一增量按 036 范围认领，新真实模型批次交接 024。

开始前登记负责人及实际文件范围。完成每个有实际结果的动作后更新记录；通过验收后用 `- [x] ~~工作描述~~` 划掉完成事项，并由协调者同步索引和总规划。
| 2026-09-29 | root | **跨目标核对：同一修订的开放空间在 Minecraft 与 Unity 两端一致** | 用**今天的修订**（港口 seed 4，`world_d387dde2dfa293df` / `revision_ae9b214ce8c50a2e16eaf6`）跑两端：① 先把场景包落成 WIR JSON（`artifacts/scene-mainline-e/harbour.wir.json`，`validation: pass`）；② `tools/export_unity_open_space.py --source-id open_space_site_000` 导出 Unity GLB（`artifacts/unity-scene-open-space-20260929/container_yard/`，44 KB GLB + manifest）。**可核对的一致性**：**两端都是 34 个构件**——Minecraft 侧按 source id 反查是「铺装 1 + 步道 1 + WIR 里 32 个 fixture 全部命中」= 34 盒；Unity manifest 的 `piece_count` 也是 **34**，并带着 `source_id` / `source_revision_id` / `source_snapshot_sha256` / `glb_sha256` / 版本与 `limits`。**如实记录的两点**：① Unity 的场景侧目前只有 `export_open_space()` 一个入口（**只覆盖开放空间**，地形/道路/建筑/城堡/干船坞都还没接），这正是 008 未完成的那条；② Minecraft manifest 里 `open_space_*` 前缀盒子只有 2 个，是**fixture 用自己的 id 落盒**（例如 `site_000` 的 32 件），不是丢件——按 WIR 的 fixture id 反查是 32/32 命中。**测试/回归**：本轮无代码改动，未新增测试；完整回归与文档检查按轮次要求执行 | 下一轮：把 Unity 场景侧再补一个种类（建筑或城堡体量），或干船坞深挖所需的地形开挖 |
