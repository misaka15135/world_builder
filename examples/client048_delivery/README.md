# 049 精选客户端交付证据

日期：2026-10-16。覆盖045/046必要依赖、047山谷客户端、048密钥保存。此目录是原有本地运行的精选截图/汇总，不是新的API样本，也不包含原始调用、密钥/DPAPI文件、世界包、GLB、Unity大场景或EXE。

- [实际山谷预览](client047-overview.png)、[关闭重开后的历史](client047-history.png)：410树调整版9491源网格。
- [047交付核对](client047-validation.json)：22项核对通过，文件扫描只说明当时扫描范围，不作为发布后的全部内容保证。
- [真实API与回放汇总](client047-api-validation.json)：4次真实A/B/D/F、6489计账tokens；E为复用录制配方，精确回放0网络。新400树版本未做Unity目标实走，不能继承046旧目标结论。
- [048设置窗口](settings-reopened.png)：仅example.test与合成模型；密码框空白、已保存状态，无TXT输入。截图不是DeepSeek真实密钥验证。
- 合成凭据[保存](credential-save.json)、[新进程重开](credential-reopened.json)、[清除](credential-clear.json)：均通过、无付费调用。合成密钥已清除。

原证据中的run ID、构建哈希和部分文件目录指向原作者本地未发布记录，不表示克隆后有这些运行历史。源参考参数/录制E配方已发布到examples，可用客户端“离线样例”零API重新构建。模型/编译环境改变需要新登记，不改写原批次。

使用与干净克隆启动方式见[客户端说明](../../docs/14_client048_saved_credentials.md)。旧045/046 Unity派生场景及完整物理验证证据留本地，不用本目录的客户端预览冒充目标实走。

发布前仅暂存文件副本的168项回归全部通过，另以该副本实际[重建参考山谷](clean-reference-result.json)：0API、9425网格/388树/64栋、220源房间路线与69室外路线通过，worldpkg和GLB与原046基准哈希一致。251.125秒包含归档验证；使用本机现有Python依赖，不是干净Windows安装或Unity新实走验收。
