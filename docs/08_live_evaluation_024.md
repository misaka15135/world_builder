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

## 结果复核

每例检查 `result.json`、`events.jsonl`、`calls/*/{request,response,completion}.json` 的请求身份、响应哈希、真实模型 usage、首次接受与拒绝原因；失败的调用也保留。成功案例用同一脚本离线回放：

```powershell
python tools/run_live_024.py --case single_storey --replay
```

脚本比较 `scene.worldpkg`、Unity GLB、所有 Minecraft schematic 哈希，读取世界包并对照 WIR 校验结果，写出 `replay_validation.json`。回放不联网，不能算作第二个真实样本。

人工逐例按预登记的 `manual_focus` 核对需求符合、布局、风格和必要手工修整。目标验收按文件结构、Unity/Minecraft 实际导入与重开、碰撞或支撑、适用的连续通行分开记录；缺少目标环境或未实际执行时写 `not_run`，不能用已有旧分支截图代替。四例均完成机器检查才可称本首批机器验收通过；四例样本不足以估计总体成功率。

本批完成后，024 仍须等待自然/混合场景、用户反馈修改及新版双目标真实场景的后续批次，不能仅凭本批将工单置为 `done`。
