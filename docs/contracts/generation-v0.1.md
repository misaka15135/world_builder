# 006 本地生成试验版本

版本：`0.1.0-pilot.2`。日期：2026-09-23。状态：006 已完成固定规格闭环与有限模板修复子阶段；不是完整城邦验收。WIR Schema 仍为 0.1.0。

## 当前能力

固定规格使用 128 m × 128 m 区域、1—6 栋建筑和 0—建筑数栋室内，默认 6 栋建筑、2 栋室内。长度为米、角度为弧度，右手 X 东/Y 北/Z 上，局部变换相对于父实体；实体 `bounds` 在本试验中明确采用世界坐标 AABB。全部模板仅支持平移，旋转/缩放会被试验验证器拒绝。

五个提交阶段为地形水系、道路桥梁、分区地块、建筑体量、室内。每个阶段先构造候选，再运行独立模板规则、WIR Schema 与语义检查，最后发布资源和提交 SQLite 修订。各阶段都可恢复；一个阶段失败或取消时，上一已提交阶段仍可加载。

地形为 4 m 采样、33 × 33 的合成高程场，河道为固定直线。河畔使用缓起伏；山地试验只提高合成坡度，不代表复杂山地算法；密集街区试验将分区节距从 40 m 减至 32 m。道路和建筑使用 2 m 高平台，地块记录两角原地面高度与基础平台策略；目前没有挖填方网格、完整河流动力学或真实地基设计。

建筑保存盒状体量、墙/楼板厚度、入口和屋顶参数。室内保存楼层、房间、家具、直跑楼梯和楼板开口参数；未细化建筑明确为 `interior_state: deferred`。楼梯通过尺寸、楼层标高、包络和开口检查，但尚无编译后的墙门网格或角色体积导航测试，因此不能称为已经证明玩家可走通的建筑。

## 运行与恢复

在项目根目录的 PowerShell 中运行：

```powershell
$env:PYTHONPATH = 'src'
python tools/generate_world.py --output artifacts/my-pilot --seed 101 --scenario riverside
```

输出目录包含 `wir.sqlite3`、`assets/sha256/`、`world_<id>.world.json`、`world_<id>.run.json` 和 `runs/run_<uuid>.jsonl`。数据库和不可变资源为权威数据；JSON 是原子发布的派生快照和最新执行报告，不能修改 JSON 后认为数据库已更新。逐次运行日志使用新 ID 追加保存，重试不覆盖历史失败。快照引用相邻 `assets/`，分享时必须一起复制；当前没有正式 ZIP64 `.worldpkg` 导入导出器。

重复同一命令从最后提交的阶段继续；全部阶段完成时直接返回既有修订。不同规格/seed 使用不同世界 ID，可以存于同一目录。按 Ctrl+C 请求取消；整个生成调用的超时通过 `--timeout-ms` 设置，每阶段候选上限用 `--max-candidates 1..3` 设置（包括初始候选）。取消和时限在每次候选、修复边界及数据库提交前检查，不保证立即中断单条 Python/SQLite 调用。

v2 新增 `layout_profile`、`lock_stair_void` 规格字段，因此世界 ID 与 v1 不同；不原地升级旧数据。v1 历史仓库仍可通过 `Repository.load(old_world_id)` 读取，旧生成器版本不接受原地续生成。版本迁移尚未实现，新的运行使用新的世界身份和日志。

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

存储实现沿用 `0001_initial.sql`，未修改历史迁移或冻结 Schema。SQLite `BEGIN IMMEDIATE` 事务统一写修订、记录、资源引用、R*Tree 和分支头，比较预期基础修订，提交前检查旧修订的字段锁。旧记录不可原地更新。解锁/编辑命令及完整导入接口留待后续实现。

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

`benchmarks/pilot_cases_v2.json` 在批量运行前冻结三类各 10 个种子，每类 5 个 standard、5 个 compact，固定模板资产、离线零模型调用、每次调用 30 s 预算及每阶段最多 3 次候选；v1 登记与报告保留。首次通过率与最终成功率分别统计；锁冲突、预算耗尽、取消/超时和故障作为独立测试组，不进入正常输入分母。基准工具为每个输入启动独立进程，保存所有输入和失败，记录分阶段耗时、实体规模、资源字节数、进程峰值工作集、依赖版本、代码与登记文件哈希。峰值来自操作系统进程计数器，覆盖 Python 生成进程；没有查看器/GPU/模型服务，不能与完整系统 4 GiB 指标等同。

## 下一阶段

继续 006：可替换模型服务与已接受响应保存、正式世界包导入导出、更完整的参数化几何与更广范围修复策略。008/009 手工两层建筑的目标转换仍未执行；通过后才能扩展到 512 m、约 80 栋建筑及正式 30 输入验收。用户没有取消或降低该门槛。
