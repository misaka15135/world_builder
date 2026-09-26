# 019 Minecraft 本机启动恢复

- 状态：done
- 创建日期：2026-09-27
- 执行者：root
- 依赖：无；参考 009、018 的目标环境和故障记录
- 修改范围：本机 Minecraft Java 启动链、隔离备份恢复与必要的系统诊断；项目内修改本工单、索引和总规划。因官方启动器在项目临时产物下生成约 327 MB 运行时，另将 `artifacts/minecraft-recovery/` 加入 `.gitignore`，避免误提交机器专用二进制。不改生成器与导出器。

## 目标与范围

恢复 Minecraft Java 启动，并保留此前移入隔离目录的个人与项目存档。优先使用 Minecraft 官方提供的独立启动器，核对登录、目标版本与游戏主菜单；系统级修复按实际错误推进。

## 工作项

- [x] ~~核对现有启动器故障、系统依赖和隔离备份。~~
- [x] ~~恢复可用的 Java 启动路径。~~
- [x] ~~恢复原有游戏资料和项目隔离配置，并验证存档文件存在。~~
- [x] ~~记录启动、版本、模组与存档验证证据。~~

## 验收标准

- Minecraft Java 1.21.11 能进入主菜单；项目 Fabric/WorldEdit 配置能加载。
- 原有个人和项目存档保留且可见；无法恢复的部分逐项记录。

## 执行记录

| 日期 | 执行者 | 动作 | 结果与证据 | 下一步 |
|---|---|---|---|---|
| 2026-09-27 | root | 接手启动故障并核对交接记录 | 018 记录 Store/GDK `0x800700c1`、Store `0x80072EFD`，多次重装和清理无效；当前 Appx 启动器、Store、Xbox、Gaming Services 均已安装，代理开关为 0；隔离备份存在，原 `.minecraft` 不存在。项目仓库仅 018 有未提交改动。 | 优先试官方 Windows legacy 启动器；随后恢复备份并实际启动验证。 |
| 2026-09-27 | root | 获取官方替代启动器并恢复数据 | 从 `launcher.mojang.com/download/Minecraft.exe` 取得免安装 EXE，Mojang AB Authenticode 签名 `Valid`，SHA-256 `60C59EDEC70F5CD7D1CF880E7A1475DE6F73932DC23AE913F9C7DFEAF52489E1`。官方 MSI 签名有效但安装报 1925（当前用户无全机安装权限），未继续尝试安装。将隔离目录 `.minecraft-wiped-20260927` **复制**回 `%APPDATA%\.minecraft`，源备份保留；核对个人存档 2 个、项目存档 2 个、`versions/1.21.11` 和 `fabric-loader-0.19.5-1.21.11`、WorldEdit 7.3.19 JAR、38 个项目 `.schem` 文件存在。 | 恢复启动器安装配置并实际进入游戏。 |
| 2026-09-27 | root | 启动官方免安装版本并恢复项目安装配置 | 启动器打开，用户确认已登录；日志明确 `MSA sign-in succeeded`，Minecraft profile 与 license 请求完成、`online=1`。在用户关闭启动器后，将隔离备份中的 `World Builder 1.21.11` 与 `World Builder 1.21.11 Fabric` 两条 profile 合并进当前 `launcher_profiles.json`，先保存新文件备份 `launcher_profiles.json.before-project-restore`；重开后核对 profile 仍存在且 Fabric `gameDir` 指向项目隔离目录。电脑操作工具拒绝控制 `Minecraft-legacy`，无法代点“开始游戏”，已请用户点一次；尚无新 `javaw` 进程或游戏日志。 | 等待一次游戏启动，核对 1.21.11 主菜单、WorldEdit 与存档可见性。 |
| 2026-09-27 | root | 完成 Java 目标启动与稳定入口 | 用户确认进入游戏主菜单；同次 `world_builder_1.21.11/logs/latest.log` 记录 `Loading Minecraft 1.21.11 with Fabric Loader 0.19.5` 和 `WorldEdit for Fabric (version 7.3.19+7378-cb4171a) is loaded`，`javaw` 进程存在。个人两个存档和项目两个存档的 `level.dat` 与隔离备份逐一 SHA-256 相同；WorldEdit JAR 哈希也相同。将已运行的启动器及其 runtime 复制到 `%LOCALAPPDATA%\Programs\Minecraft Java Legacy`，EXE 哈希一致；开始菜单快捷方式 `Minecraft Java (Legacy)` 指向该固定目录。项目临时运行时加入 `.gitignore`。 | 019 完成；018 可继续游戏内场景验证。Windows Store/GDK 版本故障未修，不影响此 Java 路径；固定目录的下一次冷启动尚未单独复测。 |

## 交接说明

隔离备份位于 `C:\Users\misak\AppData\Local\MinecraftLauncherQuarantine-20260927`；不得删除。018 的未提交修改属于上一执行者，保持原样。Minecraft Java 从开始菜单的 `Minecraft Java (Legacy)` 启动；项目游戏配置为 `World Builder 1.21.11 Fabric`。Windows Store/GDK 启动器仍有原故障，此次成功路径为官方免安装 Java 启动器。
