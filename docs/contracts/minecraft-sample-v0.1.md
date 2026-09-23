# 009 两层建筑 Minecraft 样件导出

状态：受限样件已在目标游戏加载并粘贴，玩家连续通行尚未验收。日期：2026-09-23。适配器版本：`0.1.0-sample.1`；源 WIR Schema：0.1.0。

## 来源与适用边界

输入固定为 [两层建筑手工样件](../../examples/two_storey_building.world.json) 的 `revision_two_storey_001`。适配器校验整个样件的规范 JSON 摘要；几何、版本或任何源记录改变后会拒绝导出，必须审查并发布新映射。源坐标为右手系 X 东/Y 北/Z 上，单位米；目标坐标为 X 东/Y 上/Z 南，按 `(x, z, -y)` 映射，1 米对应 1 方块。

Sponge [Schematic v3 官方规范](https://github.com/SpongePowered/Schematic-Specification/blob/master/versions/schematic-3.md)规定 GZip NBT、`Schematic` 根内复合标签、维度、`DataVersion`、`Blocks.Palette` 和按 `x + z×Width + y×Width×Length` 排列的 varint 方块数据。WorldEdit [7.3.19 命令文档](https://worldedit.enginehub.org/en/7.3.19/commands/)列出 `/schem load`；[项目变更记录](https://github.com/EngineHub/WorldEdit/blob/version/7.4.x/CHANGELOG.txt)记载 7.3.18 添加 1.21.11 支持，7.3.19 是后续 7.3 系列版本。来源访问日期均为 2026-09-23。规范和维护方记录说明目标格式与候选版本，并不构成本机加载成功证据。

手工源仅有建筑/房间体积、楼梯关系与家具资产引用，没有墙、门、楼板开口或梯段实体参数。这里明确采用样件专用的设计判断：生成 20×9×16 方块石砖外壳、南门、上下层地板和屋顶、东侧非对称玻璃窗、两格宽的四级北向楼梯及开口。1.4 米源楼梯净宽量化为 2 方块；源 4 米上层标高采用目标 y=3 的楼板上表面 y=4。链接的椅子 GLB 不在样件内，替换为西向橡木楼梯块。全部替代均列在 `export_report.json`，没有把模板推断称作已保留的源几何。

## 运行与文件

在项目根目录运行：

```powershell
$env:PYTHONPATH = 'src'
python tools/export_minecraft.py --source examples/two_storey_building.world.json --output artifacts/my-minecraft-sample --data-version 4671
```

`--data-version` 必须显式提供正整数；上例的 `4671` 已于 2026-09-23 从本机安装的官方 1.21.11 客户端 JAR 内 `version.json.world_version` 核对，但现有 v2 文件仍保留生成时的离线验证状态。导出器不替用户推断目标运行时版本。输出目录必须不存在，避免覆盖已有证据。文件有 `library.schem`、`manifest.json` 和 `export_report.json`：manifest 记录源修订/摘要、目标原点 `[4,0,-18]`、尺寸、方块数、Schematic 哈希、离线检查与目标加载状态；报告符合 WIR 0.1 `export_report` 形状，源快照不被修改。文件是区域剪贴板，不是独立 Minecraft 世界目录。

离线检查逐格验证门洞到上层房间的连续路径、至少两格头部净空与每级不超过一格的高度变化；独立测试解析 GZip/NBT、palette、varint 索引、门洞、窗、楼梯和楼板开口。它没有模拟 Minecraft 碰撞形状、导航、流体或实体行为，不能代替实际玩家通行。

## 目标运行验证

本机现已通过官方 Launcher 安装 `1.21.11`，并从其客户端 JAR 核对 `world_version=4671`。通过 [Fabric 官方安装器](https://fabricmc.net/use/) 1.1.2 安装 Loader 0.19.5；安装器与 Maven SHA-256 一致。专用配置 `World Builder 1.21.11 Fabric` 指向 `.minecraft/world_builder_1.21.11`，避免影响现有 26.x 配置。[WorldEdit 7.3.19 的 1.21.11 Fabric/NeoForge 发布页](https://modrinth.com/plugin/worldedit/version/SDczInMa)提供的 `worldedit-mod-7.3.19.jar` 已与 Modrinth API SHA-512 核对，放在该独立游戏目录的 `mods` 下。`library.schem` 也已复制到 `config/worldedit/schematics`，与 v2 SHA-256 一致。来源访问及本机核对日期：2026-09-23。

既有 v2 `manifest.json` 是安装前的离线证据，其 `data_version_verified_on_target=false`、`game_load=not_run` 和 `in_game_walk=not_run` 保持原样，不追溯改写。后续实际在 Fabric 1.21.11 主菜单看到 `Modded`，日志显示 WorldEdit `7.3.19+7378-cb4171a` 加载并注册命令；该游戏能够读取 DataVersion 4671 的 v3 剪贴板。

在隔离游戏目录中新建创造模式 Superflat 世界 `World Builder Sample`。游戏内 `//schem load library` 返回 `library loaded`，`//paste -a` 在 `(7,-60,3)` 返回 `1365 blocks affected`。新证据目录 `artifacts/minecraft-sample/target-v1/` 包含南门外观和一层室内的游戏原生 F2 截图，均采自测试世界未受后续误操作影响时。粘贴点是当时玩家位置；并非旧 manifest 中示例原点 `[4,0,-18]`，不可把两者混同。

定位楼梯后，电脑操作工具的键盘输入未再被游戏接收，一次试图恢复焦点的点击误拆了测试世界中的一个楼梯块。重启游戏后键盘故障仍在，后续窗口点击也可能影响测试世界方块。原始 `.schem`、源 WIR 与导出器均未改变；当前测试世界需重贴样件修复。已经观察到楼梯形状，但没有完成真实控制器连续上楼；`in_game_walk` 仍是 `not_run`，009 不因此视为完成。

下一步在输入可控时重新粘贴 `.schem` 修复测试世界，再实际穿过门、走完楼梯、进入上层房间，记录路线结果。WorldEdit 的[剪贴板文档](https://worldedit.enginehub.org/en/7.3.19/usage/clipboard/)说明配置目录和加载/粘贴流程。只有这些动作成功，009 的玩家通行子项才可勾选。
