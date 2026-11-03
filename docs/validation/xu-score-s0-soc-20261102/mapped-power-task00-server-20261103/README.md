# xu 映射后全 SoC task00 功耗执行记录

同服务器 PT **T-2022.03-SP5-1** 对 baseline `f49a5fc` 的正式 clear/request 活动、实际全SoC综合网表及指定库执行成功，退出0，状态 **PARTIAL_EXECUTED_REVIEW_PENDING / NOT_QUALIFIED**。本目录保存 task00 的真实工具与报告身份，不构成比赛能耗验收。

实际网表 SHA256 `0f4898ba5ab6571c2125978cdce0a9984a87d4df9901757cb1c00662e4ef3616`，原分析SDC `404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98`。标准单元/1024 SRAM DB分别为 `f69c08a0b89c6d747ecb648e8c212a98d2bba6c8b9aeec766e90babc01a64723` / `c2cce1cf2bd8f25de5df3fe01e67b0ef40a933c2ec51da156dd47a288866bf0f`。完整输入身份和执行argv在原 `prepared.json`、`execution.json` 与state中。任务前33697次实际MMIO零清、从首个源REQUEST至最后Y响应RETIRE的9.13904ms窗口见同级 `clear-alias-server-20261103`，没有把accept窗口冒充request窗口。

实际PT库存含336个宏、22512个信号引脚。独立的映射桥按原库实例名建立SAIF，并仅对新建INSTANCE中的字面句点作转义；原VCS/归一化SAIF保持原样。目标PT读取成功：48551/139779个net来自活动文件（34.73%），2046/121078个leaf cell全部引脚已标注（1.69%）。这不是活动值逐位比较，更不是合格门槛通过。`report_switching_activity -coverage` 的激励比例另有含义，不与文件标注比例混用。

原工具收齐26类报告，检查两阶段336宏/22512引脚marker全量清单；报告marker存在只证明清单完整，尚未核对每位PT值和来源。原两份全属性报告分别806231776、804484837 bytes，仍存服务器，完整SHA保存在执行receipt；本目录仅保存首个完整引脚block的明确派生摘录。其他缺少字节的报告逐项列于 `result.json`，不声称本地重新解析了它们。独立服务器只读review重跑相同清单/哈希检查，与最终原工具receipt报告集合一致。

原始 `power.rpt` 总功率显示约 **0.0329W**；其详细分组原文保留。由于仅task00、剩余默认/传播/优化合并活动、非空inconsistent、SRAM unknown及Liberty联合控制模式尚未闭合，**不计算或选用评分能量**，也不与其他候选周期/面积拼接。完整150MHz时序资格仍单独待审。

原PT本身102s结束；旧Python诊断正则在大型属性报告上导致后处理延迟，最终仍正常写出退出0的终态receipt，未杀进程/重跑/覆写该输出。后续工具提交 `25d28d9` 改为线性诊断扫描，`042b871` 在报告扫描前先持久化工具退出凭证，`3a5d001` 流式检查引脚marker，均不更改这次测量或原日志。旧正则40000空格用例2s超时、新正则0.065s的本机筛查仅是后处理算法检查，不是EDA结果。

本目录21个唯一原payload来自95472-byte传输包，SHA256 `5cb9b56becb29d139e5db62a5d3a7d203f14355130126b534e1135eaedb35bcc`。原始绝对路径、日志空白、时间及数值未改；派生block也在原导出清单明确注明。复核：

```bash
python3 docs/validation/xu-score-s0-soc-20261102/mapped-power-task00-server-20261103/check-evidence.py
```

同服务器重新执行须新输出目录，并保留原源身份：

```bash
python3 tools/scripts/xu_soc_saif_power.py prepare --root "$xu_frozen_root" \
  --activity "$xu_task00_activity_result" --implementation "$xu_implementation_json" \
  --netlist "$xu_mapped_v" --constraints "$xu_analysis_sdc" \
  --mapped-sram-inventory "$xu_actual_pt_macro_inventory" --task-ids 0 \
  --out "$xu_new_power_out"
python3 tools/scripts/xu_soc_saif_power.py run --out "$xu_new_power_out" \
  --pt pt_shell --timeout 21600 \
  --lc-root /eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5
```

原producer为 `fc25468`；collector/helpers必须仍与原捕获SHA一致。新版本生产者若改变collector，不可静默重标注旧活动为新来源。下一步是用安装版已确认的有限query逐位比对实测/目标PT来源，审查标准单元传播边界及真实SRAM条件，再扩展完整12任务和候选各自活动。
