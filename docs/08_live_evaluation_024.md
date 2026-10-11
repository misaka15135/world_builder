# 024 DeepSeek 官方 API 首批真实评估

登记日期：2026-10-11。执行范围是当前 `main` 的固定 A—F、建筑场地导向 0.1.0 原型；自然场景、用户修改和新版目标适配待相应工单交付后另建批次。本批四例输入及通过口径在首次真实调用前冻结于 [`agent_live_024_deepseek_v1.json`](../benchmarks/agent_live_024_deepseek_v1.json)。任何已启动案例，即使 API、格式、几何或预算失败，也计入分母。

## 服务与预算

使用 DeepSeek 官方 `https://api.deepseek.com/chat/completions`、`deepseek-flash`、非流式 Chat Completions、`json_object` 和 `max_tokens`。实际模型由响应的 `model` 字段留证；官方文档截至 2026-10-11 见[首次调用](https://api-docs.deepseek.com/guides/codex)、[JSON 输出](https://api-docs.deepseek.com/guides/json_mode/)、[模型与价格](https://api-docs.deepseek.com/quick_start/pricing/)。当前模型默认启用 thinking；本项目的通用 Provider 不额外传 thinking 开关，故该行为计入本批配置。

[无密钥配置](../config/agents.deepseek-024.json)规定每例最多 12 次请求、50 万本地计账 token、单次最多 1.6 万输出 token、最多两次尝试及一次 F 返工，墙钟上限 30 分钟。四例每例各运行一次。以上是程序侧停止条件，**不是供应商账单硬限**；包括超时且无法取得 usage 的请求在内，实际费用以 DeepSeek 控制台为准。先运行单层案例，查看实际 token 和失败分类，再依序运行另三例；不因首例表现修改冻结输入后继续把结果算作同批。

## 本机执行

在仓库根目录以装有 `jsonschema` 的 Python 3.10+ 运行：

```powershell
python tools/run_live_024.py --check
python tools/run_live_024.py --case single_storey
```

第二条命令会在本机终端无回显地提示输入 DeepSeek API 密钥；密钥只设置在这次 Python 进程的 `WORLD_BUILDER_API_KEY` 环境变量里，不写入配置或结果。不要把密钥发到聊天、命令行参数或截图。若已由可信的本地运行环境设置该变量，脚本不会再提示。其余 ID 为 `two_storey_shop`、`multiple_sites`、`uneven_ground`，逐个运行并检查上一个结果。输出写入被 Git 忽略的 `artifacts/agent-runs/live-024-deepseek-v1/<case-id>/`，已有同名目录时拒绝覆盖。`evaluation_context.json` 只记录案例、配置及预登记哈希、代码提交与退出码，不含密钥。

如果密钥较长，可将其放在本机 UTF-8 或带 BOM 的 UTF-16 文本文件第一行，使用 `--key-file C:\Users\rjc\Desktop\api.txt`。程序只读取首行并将其用于当前进程，不输出密钥或将文件复制进仓库。桌面明文文件仍有被其他程序或同步服务读取的风险，评估后应由用户自行安全删除或移入受保护的密钥管理器；不要提交该文件。

## 结果复核

每例检查 `result.json`、`events.jsonl`、`calls/*/{request,response,completion}.json` 的请求身份、响应哈希、真实模型 usage、首次接受与拒绝原因；失败的调用也保留。成功案例用同一脚本离线回放：

```powershell
python tools/run_live_024.py --case single_storey --replay
```

脚本比较 `scene.worldpkg`、Unity GLB、所有 Minecraft schematic 哈希，读取世界包并对照 WIR 校验结果，写出 `replay_validation.json`。回放不联网，不能算作第二个真实样本。

人工逐例按预登记的 `manual_focus` 核对需求符合、布局、风格和必要手工修整。目标验收按文件结构、Unity/Minecraft 实际导入与重开、碰撞或支撑、适用的连续通行分开记录；缺少目标环境或未实际执行时写 `not_run`，不能用已有旧分支截图代替。四例均完成机器检查才可称本首批机器验收通过；四例样本不足以估计总体成功率。

本批完成后，024 仍须等待自然/混合场景、用户反馈修改及新版双目标真实场景的后续批次，不能仅凭本批将工单置为 `done`。

## 首例 HTTP 400 诊断记录

2026-10-11 首次 `single_storey` 真实调用在 A 阶段两次收到 HTTP 400，未获得模型内容或服务端 usage。此案例仍属于 v1 的四例分母，不覆盖输出或把诊断请求算作新的预登记样本。DeepSeek [错误码说明](https://api-docs.deepseek.com/quick_start/error_codes/)将 400 归为请求格式错误，具体字段需要服务端错误正文确认。Provider 现在只保留长度受限且密钥脱敏的错误摘要；独立诊断脚本 `tools/diagnose_live_024.py` 使用原始 A 请求做至多一次请求，结果放在被 Git 忽略的 `diagnostic-A/`，与评估样本分开。若需修复配置或协议，应另冻版本再运行，不能改写 v1 记录。

使用新密钥、原请求及原配置的一次独立诊断返回 `deepseek-flash`，986 输入 / 5475 输出 token，响应通过 A 阶段 JSON Schema。它证明该请求在诊断时可用，但不能证明原 HTTP 400 的具体原因。v1 只启动了单层案例，失败仍保留；其余三例未启动。另以完全相同的四例输入、预算、模型、skill 与验收口径冻结 [v2 批次](../benchmarks/agent_live_024_deepseek_v2.json)，以隔离重试和原记录：

```powershell
python tools/run_live_024.py --batch-version v2 --check
python tools/run_live_024.py --batch-version v2 --case single_storey --key-file C:\Users\rjc\Desktop\api.txt
python tools/run_live_024.py --batch-version v2 --case single_storey --replay
```

v2 输出在 `artifacts/agent-runs/live-024-deepseek-v2/`；上述回放仅在真实案例完成后运行，且不读取密钥文件。每个已启动的 v2 案例都计入 v2 分母，不能用 v1 或诊断结果替代。

## v2 语义失败与 v3 预登记

v2 单层首例的 A 响应格式有效，但把一栋房屋、道路、入口和房间拆为五个各需一个场地的需求，超过冻结的 `max_sites=4`，因此在一次调用后以 `budget.sites` 失败，没有继续到 B—F。这个结果保留；v2 其余三例未启动。A/C skill 现明确附属特征不单独占场地；A 超限仍被硬规则拒绝，但以 `brief.site_budget` 在阶段尝试预算内允许反馈重提。原输入、上限、模型和验收口径冻结为独立的 [v3 批次](../benchmarks/agent_live_024_deepseek_v3.json)：

```powershell
python tools/run_live_024.py --batch-version v3 --check
python tools/run_live_024.py --batch-version v3 --case single_storey --key-file C:\Users\rjc\Desktop\api.txt
python tools/run_live_024.py --batch-version v3 --case single_storey --replay
```

三版的运行日志与分母独立；后两版是调试后的新评估，不能抹去先前两次失败或作为无偏模型成功率估计。
