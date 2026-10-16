# 客户端山谷 profile 0.1.0-client047

客户端设置后续由[048](../14_client048_saved_credentials.md)扩展为用户可选DPAPI保存且移除TXT导入；本页一次性凭据段落保留047原行为，模型/几何/范围契约不变。

日期：2026-10-16；实现工单：[047](../../work_order/047_client_nature_generation_and_adjustments.md)。这是 HTTP v1 的显式入口扩展，不替换默认 Agent 0.1.0、045 或冻结的 [046](nature046-v0.1.0.md)。桌面版本另为 `0.1.1-client047`。

## 输入与权威

`POST /api/v1/jobs` 新增 `pipeline: "nature047"`，未指定时仍为 legacy。固定 `region_m=768`、`seed=46`、`unity=true`、`minecraft=false`。保留四聚落64栋、两桥、东北城堡；没有通用新建筑或任意区域生成。

| mode | 行为 |
|---|---|
| api | A 检查描述是否属于本周范围；B/D 产生046 Schema的参数；本地构建通过后 F 审查源报告。E使用045录制配方，C为固定案例简报，不伪称全部六阶段重新生成 |
| fixture | 重建 `examples/nature047_reference.json` 中已录制的046参数；描述不可更改，零模型调用 |
| adjust | 必须提供成功 nature047 的 `source_id` 及非空 `changes`；仅允许下列白名单整数，新建运行不覆盖来源，零模型调用 |
| replay | 由 `replay_id` 恢复原输入/配置/来源模式，禁止联网补齐；worldpkg、GLB、nature_geometry 三者逐字节比较 |

A 的 payload 为 `{supported:boolean, reason:string}`，reason 上限300字符；false 在B之前停止。请求/响应 envelope 绑定 `0.1.0-client047`、阶段、作用域及请求哈希。模型范围判断仍不是开放语言正确性的证明；超出能力应明确失败，不冒充生成成功。

API 上限取用户预算与6调用/150000计账tokens/4000输出tokens/每阶段2次尝试/1并发中的较小值。场地预算至少64，构件预算和本地源检查不放宽。每次网络响应独立留证；本地编译可能占主要耗时，不显示虚构百分比。

## 调整字段

`changes` 为路径到整数的对象，例如 `{"B.trees":410,"D.castle.yaw":-4}`。禁止布尔、浮点、字符串、未知字段、越界和无变化操作。范围以 bootstrap 的 `nature.fields` 为界面/服务端同源声明。

| 路径 | 范围 |
|---|---|
| B.west_height / north_height / east_height | 30—70 / 45—95 / 25—65 |
| B.river_bend / river_width / river_phase_deg / valley_width / trees | 24—46 / 18—28 / 0—90度 / 96—144 / 300—440 |
| D.districts.{id}.x / y | 四聚落各自046冻结选址范围，见服务端 fields/LIMITS；不能跨聚落任意拖放 |
| D.districts.{id}.radius / home_percent / yaw_jitter | 98—112 / 40—60 / 12—28度 |
| D.castle.x / y / yaw | 580—650 / 650—680 / -22—22度 |

共31个字段。`home_percent` 是额外配方抽样住宅权重，不保证最终住宅数量恰为该百分比。布局、道路和地面会按新参数全图重建；未修改参数保持，不承诺所有未选中几何不变。树数单变量测试中非树林几何未变只适用于该测试。范围内参数组合仍可能不可行，失败版本留证，原成功版本不改写。每次重建世界身份随内容变化，不是032/033稳定修订或局部编辑。

## 版本、资源与凭据

新输入记录 profile/builder/配方/参考参数/skills 的生成上下文。回放上下文不匹配或缺失时拒绝；旧文件仍可查看，不伪造缺失上下文。开发期旧基准可读取参数创建新调整，但不能冒充新版精确回放。

bootstrap 增加 `nature` 元数据、`config_fields`。Job 增加 pipeline/source_id/source_mode；成功 detail 返回 parameters/changes。旧路径的 Host/Origin/会话令牌、清单下载与路径隔离继续有效。未知 config 字段不能持久化。密钥可由本地TXT首行导入密码框，仅供一次API运行，不写任务/偏好/浏览器存储，不随回放传递；运行结束清空 provider key。

预览读取实际 GLB 的三角网/材质与 manifest 源ID，使用WebGL2；地形开关、剖切、缩放、旋转、拾取均只改视图。浏览器不支持WebGL2时明确提示下载，不退回AABB冒充。该查看器无目标物理、贴图或Unity光照验收含义。导出保留 worldpkg 与 GLB，目标加载/实走在结果中分别为 `not_run`；046旧目标证据不自动继承给新参数场景。
