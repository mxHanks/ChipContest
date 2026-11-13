# 最终374宏Formal准备证据

已从三轮实际 R-2020.09-SP5 文档/属性探针完成可执行adapter及API contract，30项离线门禁和4项纯合成TSV/opaque-pin归一化测试通过。**没有实际读取本轮设计/map进行FM，没有RTL→mapped通过结果**。用户当前优先原1064.35开发候选；此374流程独立保留，不嫁接给原候选。

三份原生小包保存probe、执行收据、完整native.log、driver及run.py。所有probe RC0、affinity[0,1]、launcher实际SHA一致；只读help/man/属性定义，没有本轮RTL/两库/设计match/verify。FM启动自带gtech加载不属于本轮两库设计验证。原r1解析保留作历史原件，`native-api-combined-review.json`修复了man返回0却打印Error的识别，明确列出不存在的get_object_name、无man的hdlin_error_on_mismatch_message及两个attributes topic。adapter使用实际已证get_attribute属性定义，不调用这些未支持接口。

API contract绑定当前adapter SHA及三个完整日志的逐字节拼接，列出32个已审命令、四个实际已证cell/pin属性及全部设置/报告角色。它只证明API文档准备，不把资源设置/实际设计调用说成已经执行。native timeout使用有文档的2:0:0，外层7200秒；纯整数3600会被此版本解释为3600小时。

`source-preparation-final.json`绑定159源/六defines/profile与own final.svf要求。实际执行前还必须有同374 GPIO CPU12、同包原生DC/map/SVF、完整原始报告/TSV、全部opaque宏/引脚对应和逐项未比较/假设审查。归一化遇到未知格式或缺项即失败，保留真实native stdout/TSV，不伪造零计数。合成测试仅证明工具门禁逻辑，不证明任何EDA结果。

工具、准备/执行/审查命令见experiments/s3-y32-final/formal/README.md。当前374设计FM未启动，正式执行仍须主session按当前授权和资源安排操作。
