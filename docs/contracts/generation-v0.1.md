# 006 本地生成试验版本

版本：128 m 试验 `0.1.0-pilot.3`；512 m 源端城邦 `0.1.0-city.1`。更新日期：2026-09-24。状态：006 已完成固定规格闭环、有限模板修复、模型规格接口与世界包交换子阶段，512 m 城邦源端基准通过；尚不是完整目标平台验收。WIR Schema 仍为 0.1.0。

## 当前能力

固定规格使用 128 m × 128 m 区域、1—6 栋建筑和 0—建筑数栋室内，默认 6 栋建筑、2 栋室内。长度为米、角度为弧度，右手 X 东/Y 北/Z 上，局部变换相对于父实体；实体 `bounds` 在本试验中明确采用世界坐标 AABB。全部模板仅支持平移，旋转/缩放会被试验验证器拒绝。

新增 `--city` 选择独立的 512 m × 512 m 离线固定规格：80 栋建筑、5 栋双层室内、单条直线主河与一座桥、三类分区。两岸各 5 列 × 8 行地块，列间纵向道路由一条横向道路与桥连成网；建筑通过短引道连接街道。密集街区使用较小列/行间距，山地只改变合成高程幅度。高程资源为 4 m 采样的 129 × 129 网格。该规格使用独立的 `city_spec` 和 `0.1.0-city.1` 生成配方，不更改历史 128 m 世界身份或已接受模型响应合同；目前不接受云服务产生城邦规格。城市建筑相交检查用 X 轴扫描验证所有可能相交对，将无相交结果汇总为一条约束，避免把 3160 条通过记录写入每个修订。检查仍只覆盖轴对齐模板，城邦未在 Unity/Minecraft 导出或实走。

五个提交阶段为地形水系、道路桥梁、分区地块、建筑体量、室内。每个阶段先构造候选，再运行独立模板规则、WIR Schema 与语义检查，最后发布资源和提交 SQLite 修订。各阶段都可恢复；一个阶段失败或取消时，上一已提交阶段仍可加载。

地形为 4 m 采样、33 × 33 的合成高程场，河道为固定直线。河畔使用缓起伏；山地试验只提高合成坡度，不代表复杂山地算法；密集街区试验将分区节距从 40 m 减至 32 m。道路和建筑使用 2 m 高平台，地块记录两角原地面高度与基础平台策略；目前没有挖填方网格、完整河流动力学或真实地基设计。

建筑保存盒状体量、墙/楼板厚度、入口和屋顶参数。室内保存楼层、房间、家具、直跑楼梯和楼板开口参数；未细化建筑明确为 `interior_state: deferred`。楼梯通过尺寸、楼层标高、包络和开口检查，但尚无编译后的墙门网格或角色体积导航测试，因此不能称为已经证明玩家可走通的建筑。

## 运行与恢复

在项目根目录的 PowerShell 中运行：

```powershell
$env:PYTHONPATH = 'src'
python tools/generate_world.py --output artifacts/my-pilot --seed 101 --scenario riverside
python tools/generate_world.py --city --output artifacts/my-city --seed 101 --scenario riverside --timeout-ms 120000
```

输出目录包含 `wir.sqlite3`、`assets/sha256/`、`world_<id>.world.json`、`world_<id>.run.json` 和 `runs/run_<uuid>.jsonl`。数据库和不可变资源为权威数据；JSON 是原子发布的派生快照和最新执行报告，不能修改 JSON 后认为数据库已更新。逐次运行日志使用新 ID 追加保存，重试不覆盖历史失败。快照引用相邻 `assets/`；需要单文件交换时使用下述 `.worldpkg` 导出。

重复同一命令从最后提交的阶段继续；全部阶段完成时直接返回既有修订。不同规格/seed 使用不同世界 ID，可以存于同一目录。按 Ctrl+C 请求取消；整个生成调用的超时通过 `--timeout-ms` 设置，每阶段候选上限用 `--max-candidates 1..3` 设置（包括初始候选）。取消和时限在每次候选、修复边界及数据库提交前检查，不保证立即中断单条 Python/SQLite 调用。

v2 新增 `layout_profile`、`lock_stair_void` 规格字段；v3 又在生成配方中记录已接受模型响应的摘要与来源，因此版本变化产生新的世界身份。不原地升级旧数据。v1/v2 历史仓库仍可通过 `Repository.load(old_world_id)` 读取，旧生成器版本不接受原地续生成。版本迁移尚未实现，新的运行使用新的世界身份和日志。

## 自然语言规格与回放

模型接口限定在生成规划入口：服务接收项目自定义 JSON 请求，返回唯一候选规格；校验通过后才发布原始响应到内容寻址资源，记录 SHA-256、服务和模型标识、输入/输出 token 数及预算。后续五阶段生成仍使用相同的有限模板。离线样例与回放命令：

```powershell
$env:PYTHONPATH = 'src'
python tools/generate_world.py --output artifacts/model-demo --seed 17 --prompt '一座河畔魔法小镇，有一座可进入的图书馆' --model-fixture examples/pilot_model_response.json
python tools/generate_world.py --output artifacts/model-demo --replay-world-id world_ddaf0480b19874da
```

`--model-endpoint https://... --model-id <id>` 可替换 fixture；`--api-key-env` 指向持有 Bearer token 的环境变量名，密钥不进入规格或日志。接口只接受 HTTPS 且拒绝重定向。请求含 `contract_version`、`model_id`、`prompt`、`seed`、`response_fields` 与 `response_format`；响应 JSON 必须恰好含 `contract_version: "0.1.0"`、`provider_id`、`model_id`、`candidate`、`usage`。`candidate` 必须恰好含 `scenario`、`building_count`、`interior_count`、`layout_profile`、`lock_stair_void`；`usage` 必须给出非负整数 `input_tokens` 和 `output_tokens`。响应最大 64 KiB，默认 token 预算 4000，可用 `--model-token-budget` 调整；超过预算、无效规格或不符合同版本的响应被拒绝。fixture 是已准备的响应，并不调用云端；本阶段没有验证任何具体商业模型服务的实际协议、费用或稳定性。回放从已存响应重建规格，不再次调用服务。

## 世界包交换

```powershell
$env:PYTHONPATH = 'src'
python tools/worldpkg.py export --repo artifacts/model-demo --world-id world_ddaf0480b19874da --output artifacts/model-demo/world.worldpkg
python tools/worldpkg.py verify artifacts/model-demo/world.worldpkg
python tools/worldpkg.py import artifacts/model-demo/world.worldpkg --repo artifacts/imported-demo
```

包采用 ZIP64，包含规范 JSON 的 `manifest.json`、换行结束的 `snapshot/records.jsonl` 与全部内容寻址资源；`manifest.json` 逐成员列出路径、字节数、SHA-256 与角色。仅导出自包含的一个已提交修订。导出写入同目录暂存包、完整重读校验后原子发布，已有目标路径不覆盖。读取时检查路径穿越、重复成员、符号链接、加密成员、成员数/大小/压缩比、哈希、WIR Schema 和资源完整性；当前上限为 512 个成员、总解压 128 MiB、单成员 64 MiB、压缩比 1000。导入先完整验证，再发布资源并以新的修订事务提交；原包修订 ID 与包哈希记入导入来源。此为本地交换子集，没有实现任意 linked 包、增量多修订包或跨 Schema 迁移。

## 有限修复与上层反馈

```powershell
$env:PYTHONPATH = 'src'
python tools/generate_world.py --output artifacts/compact-demo --seed 101 --layout-profile compact
python tools/generate_world.py --output artifacts/locked-demo --seed 101 --layout-profile compact --lock-stair-void
```

`standard` 使用原有宽松模板。`compact` 是偏好较小预留空间的初始候选策略，不是要求保留具体尺寸的硬约束。建筑阶段先提交 6 m 长的楼梯预留；室内初始候选的梯段长 4 m、层间高差 3 m，违反源端坡度规则。

修复按失败规则推进：第 1 次校验后把梯段延长至 6 m；第 2 次发现梯段加平台超出 6 m 包络，向建筑层反馈，将楼梯包络及楼板开口扩大到 8 m，并更新世界包围盒和跨块索引；第 3 次重新检查全部源端规则后才提交。建筑阶段的旧修订不修改，父层变化与室内结果在同一个新修订中提交。

若用户锁定楼板开口，父层修改提案会被拒绝，保留建筑阶段的有效修订，返回 `search_exhausted / unknown` 与 `conflict.locked_field`。日志中的提案记录包含前后值，但 `applied_to_candidate: false` 表明未应用。上层现有空间不足时返回 `constraint.parent_capacity`，需要更广范围的重新规划，不能据此声称所有布局都无解。

修复策略目前只支持直跑楼梯过陡、楼梯包络不足及楼板开口不足。未知失败规则、策略无法改善、锁冲突会停止搜索；不会无限重试、删除锁或静默降低阈值。软约束仍只报告，不参与优化。

每次候选记录哈希、检查失败项、修复前后值和 local/parent 作用域；通过后的 `recipe.extensions.attempt_history` 保存整段确定性历史。逐次运行日志记录 started、attempt_started、candidate_checked、repair_proposed、stage_committed、finished，并在每条事件后 flush/fsync。进程被强制终止时可能只留下日志前缀或最后一条不完整记录；没有 finished 不能推断完成，恢复以 SQLite 已提交分支头为准。新调用从阶段起点获得新的候选预算，而不是复用半写候选，历史运行仍可核对。

快照可用原有工具复核：

```powershell
$env:PYTHONPATH = 'src'
$snapshots = @(Get-ChildItem artifacts/my-pilot/*.world.json | ForEach-Object FullName)
python tools/validate_worldpkg.py @snapshots
```

## 存储和错误边界

存储实现沿用 `0001_initial.sql`，未修改历史迁移或冻结 Schema。SQLite `BEGIN IMMEDIATE` 事务统一写修订、记录、资源引用、R*Tree 和分支头，比较预期基础修订，提交前检查旧修订的字段锁。旧记录不可原地更新。解锁/编辑命令及任意 WIR 包导入接口留待后续实现；上面的 `.worldpkg` 只支持受限自包含交换子集。

资源按 SHA-256 发布到内容寻址路径，先同步临时文件、原子替换，再提交数据库引用。中断可能留下无引用资源；本版不自动垃圾回收。加载时校验 SQLite 完整性、记录哈希和本地资源哈希。该仓库 API 目前只接收本地内容寻址资源及带 `extensions.snapshot_manifest` 的完整修订，不是通用 linked 包导入器。

生成器保存独立的 `termination_reason` 与 `feasibility`。取消、超时、实现错误和未解决候选失败均为 `unknown`；候选上限耗尽返回 `budget_exhausted / unknown`，修复策略无法继续返回 `search_exhausted / unknown`。没有无解证明时不会输出 `infeasible`。本版尚未实现完备无解证明或云调用费用预算分支。

检查范围包括源端模板包含关系、平移/包围盒一致性、建筑间相交、河道退界、平台高度、道路表面连接、桥跨河及净空、入口连接、楼梯参数和家具支承/避让。软约束仅报告平台填筑高度偏好，不参与优化。这些检查不代表任意几何、Unity/Minecraft 通行或工程规范验证。

## 复现与回归

稳定身份来自固定规格；生成配方记录版本、种子、依赖和预算；高度资源记录哈希。建筑风格随机数由 seed、地块 ID 和生成器版本派生，不依赖其他建筑生成顺序。`semantic_hash` 比较非 revision 记录，排除修订时间戳；它不承诺跨版本或不同浮点环境的位级一致性。

```powershell
$env:PYTHONPATH = 'src'
$testRunDir = Join-Path (Get-Location) ('artifacts/pytest-006-' + [guid]::NewGuid().ToString('N'))
python -m pytest -q --basetemp $testRunDir
python tools/benchmark_generation.py --output artifacts/my-new-benchmark
python tools/check_project_docs.py
```

测试临时目录必须使用新的专属路径，避免 pytest 清理已有业务目录。当前机器默认 pytest 临时目录存在权限问题，以上命令不修改系统权限。

`benchmarks/pilot_cases_v3.json` 在批量运行前冻结三类各 10 个种子，每类 5 个 standard、5 个 compact，固定模板资产、离线零模型调用、每次调用 30 s 预算及每阶段最多 3 次候选；v1/v2 登记与报告保留。首次通过率与最终成功率分别统计；锁冲突、预算耗尽、取消/超时和故障作为独立测试组，不进入正常输入分母。基准工具为每个输入启动独立进程，保存所有输入和失败，记录分阶段耗时、实体规模、资源字节数、进程峰值工作集、依赖版本、代码与登记文件哈希。峰值来自操作系统进程计数器，覆盖 Python 生成进程；没有查看器/GPU/模型服务，不能与完整系统 4 GiB 指标等同。

## 建筑形态与室内 programme（0.1.0-city.2，2026-09-25）

城邦生成器升级为 `0.1.0-city.2`，历史 `0.1.0-city.1` 修订、其基准报告和 008/009 已验收证据保持不变；128 m 试验 `0.1.0-pilot.3` 的生成路径逐字未动。

每栋建筑现在由种子、地块 ID 与生成器版本确定一份形态与功能 programme：

- 体量在 12—18 m 见方的地块内取 12/14/16/18 m 宽、14/16/18 m 深，层高固定 3 m，层数取 1—3 层，屋顶仍为 gable 或 spire。楼梯井随宽度计算，并保持至少 10 m 进深，使 8 m 梯段加 2 m 平台仍然成立。
- 功能从 `residence`、`shop`、`workshop`、`library`、`inn` 中选取。每层沿南北方向在楼梯井以西切出两间房，房间用途按 programme 命名（如 `living_room`/`bedroom`、`shopfront`/`stockroom`、`reading_room`/`book_stack`），并放入与该用途匹配的家具（hearth、counter、workbench、shelf、bed、crate_stack 等，各带尺寸）。
- 单层建筑不再需要楼梯；两层及以上保留直跑楼梯，梯段仍为 8 m（compact 4 m）、20 级、rise 3 m。

新增独立规则：`city.room_storey_bounds`（房间必须在所属楼层内）、`city.room_stair_void`（房间让开楼梯预留空间）、`city.room_overlap`（同层房间不重叠），并把 `pilot.stair_required` 改为按层数判定。同时把 `pilot.furniture_stair` 从"每件家具 × 每座楼梯"改为只比较同一栋，避免 80 栋室内后出现二次方增长（该缺陷曾使单次生成超过 5 分钟）。

本机 `--city --seed 101` 实测：65 秒、1379 个实体、8175 项检查、首候选通过、`feasible`，世界身份 `world_e89db4bf2190762b`。新的预登记文件为 `benchmarks/city_cases_v2.json`（30 个输入、80 栋全部带室内）；v1 的 30 输入登记与报告作为历史保留。**该 30 输入批次尚未运行**。

尚未做到：家具仍是轴对齐盒代理，没有门窗构件与房间连通性证明；三层建筑只在 1—2 层之间有楼梯；地形仍是合成高程场，生态与街道家具未实现。这些属于 006 的其余工作项与 012 的范围。

## 分区驱动规划（0.1.0-city.3，2026-09-25）

上一版让每栋建筑各自分异，但没有"区域之间先有大划分"：同一个分区内外的建筑取同样的分布。本版把分区变成规划输入，并把它记录为规格字段 `plan_profile: district_v1`——因为它改变输出，必须让世界身份随之改变，否则同一 world_id 会对应不同内容。

三个分区的画像不同：

| 分区 | 建筑宽度 | 进深 | 层数 | 功能倾向 |
|---|---|---|---|---|
| `residential`（城市外缘，行 0—2） | 10/12/14 m | 14/16 m | 1—2 层 | residence 为主，少量 workshop |
| `market`（中部，行 3—5） | 14/16 m | 14/16/18 m | 2 层 | shop 为主，配对 workshop 与 inn |
| `civic`（中心带，行 6—7） | 16/18 m | 16/18 m | 2—3 层 | library、inn、workshop |

由此外缘低矮密集、中心高大，而不再是整张图一个模样。家具位置也按房间实际尺寸收缩，避免窄房间触发包含关系硬失败。

本机 `--city --seed 101` 实测：50 秒、1269 实体、7516 检查、首候选 feasible，世界身份 `world_157e6995219b02bc`（与 city.2 的 `world_e89db4bf2190762b` 不同）。新的预登记文件为 `benchmarks/city_cases_v3.json`；city.1 与 city.2 的登记与产物作为历史保留，city.2 的批次因在修改前启动而被中止、未产生结论。

### city.3 预登记批次结果（2026-09-25）

`artifacts/benchmark-city-v3-batch/report.json`：**30/30 完成、30/30 feasible、首候选通过 15/30**（每个场景各 5），达到预登记的"总计至少 27/30 且每类至少 8/10"门槛，`source_city_threshold_met=true`、`full_city_acceptance=false`。单世界耗时 44,428—73,735 ms，独立工作进程峰值工作集 80,117,760—89,821,184 bytes，模型调用为 0。报告记录 `implementation_hash` 与 `registration_hash`。

首候选通过率与前两版一致（15/30）：compact 布局的 15 个输入仍需要候选修复，standard 的 15 个一次通过。这属于既有设计，不是回归。

Minecraft 适配器从该修订导出 16 分块、2,451 盒、622,535 方块（含 150 个房间隔墙）。**目标世界的重贴尚未执行**，世界里仍是 city.2 的结果。

**尚未实现**：道路宽度随分区变化（脊柱仍为固定 4 m）、路网与河道仍是正交直线、分区形状仍是南北条带而非真正的"若干街区归属同一城堡"、建筑外形仍是盒体加平屋顶（没有教堂/市政厅/城墙等原型）、样式不随时代背景变化。这些需要在 006 的分区规划上继续扩展，或按 012 重开范围。

## 512 m 预登记基准与下一阶段

008/009 固定两层样件的目标环境通行均已通过。`benchmarks/city_cases_v1.json` 在批量运行前冻结了河畔、山地、密集街区各 10 个种子（101—110、201—210、301—310），每类前 5 个标准、后 5 个紧凑布局；80 栋/5 室内、离线零模型调用、每阶段最多 3 次候选、每世界 120 s 预算、每进程 180 s 超时。目标为至少 27/30，且每类至少 8/10。运行：

```powershell
$env:PYTHONPATH = 'src'
python tools/benchmark_generation.py --cases benchmarks/city_cases_v1.json --output artifacts/my-city-benchmark
```

工具保留所有成功与失败结果，报告输入登记与实现源码哈希、阶段耗时、峰值工作集、记录数和语义哈希。`source_city_threshold_met` 只表示这批源端模板结果达到预登记数量门槛；`full_city_acceptance` 保持 false，直至通用 Unity/Minecraft 区域导出、道路/桥/室内可达性及同修订联调完成。继续 006 还需验证真实模型服务适配、复杂地形和更广范围修复；固定直线河、盒状地块和建筑不代表任意世界生成。

本机 `artifacts/benchmark-city-v1/report.json` 记录 30/30 成功，河畔、山地、密集街区各 10/10；15 个首次通过，15 个在紧凑布局下于第三次候选通过。单世界生成耗时 22,516.487—30,015.911 ms、均值 26,011.602 ms，独立 Python 工作进程峰值工作集 55,349,248—56,303,616 bytes。首个结果包含 80 栋建筑、80 个地块、3 个分区、92 段道路、1 座桥、5 部楼梯和 10 个房间，最终 2,156 条记录；所有 30 个输入离线运行，模型调用数为零。`city-first.worldpkg` 的 SHA-256 与导入核对见同目录 `package-validation.json`：2,156 条记录、非验证记录一致、导入后硬约束失败数为零；导入时验证记录指向新修订，因此包含验证记录的整体语义哈希不与原修订直接相等。完整目标平台城邦导出、玩家/控制器通行和真实模型服务仍待验。
