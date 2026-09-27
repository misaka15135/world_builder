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
