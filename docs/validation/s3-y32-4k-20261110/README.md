# 64 PE 仿真定稿证据

完整12任务：304,128个精确Y32、428,915主周期（含真实清零）；按假定150MHz约4,196.64task/s。
当前没有实际150MHz STA、候选面积或官方平台资格通过结论。详见 [结果报告](../../s3-y32-4k-results.md) 与 [handoff](../../s3-y32-4k-handoff.md)。

- [可下载冻结源／ELF／image／向量／日志包](frozen-delivery.tar.gz)，SHA256 `464bea138c254d842b1db656da0e8feb42e04e509f9ab85d92e0cd30736b543f`。
- [CPU原始日志](cpu-full12-raw.log)、[结果原件](cpu-full12-result.json)、[独立审计](independent-final-review.json)。
- [独立重建证明](delivery-rebuild-proof.json)、[原始状态位清单](storage-inventory-final.json)。
- [正式验收待办](../../s3-y32-4k-acceptance.md)。

原始记录保留当时实际路径和版本身份，不用当前HEAD改写历史日志。封存包默认只读验证，显式运行仿真需要新的时间授权；本轮只发布、不继续测量。
