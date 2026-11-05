# xu own-S2e155：接续134的TSV读取失败

actual134五个原生步骤均rc0、各自唯一完成标记且无native error，随后Python CSV默认字段上限
131072拒绝`posthold-inventory/native-cells.tsv`中的大型真实扇出字段。原失败及原件保持不变。
155在新输出目录中只把CSV字段上限设为64MiB，不截断字段、不改变筛选、SDC、修复限额或RTL。

`resume155.py`使用逐字节冻结的原134实现与reset Tcl，严格绑定实际134失败终态SHA
`1ce842c387872e473352bc84cef7eac11680dad5dfd32b794b2236a69251b435`。
它重新哈希原204冻结输入、全部诊断报告、hold mapped/SVF和五项native log/script；
要求before==after、无冻结错误且恰为该CSV失败。
仅接续这五项已经完成的原生执行，在新目录复制有回执的输出，
逐字节验证生成Tcl只发生输出路径重定位。每条接续run保留完整original_native_run及
`ADOPTED_ORIGINAL134_NATIVE_PHASE_NOT_RERUN`，不将复制文件称为新执行。

随后必须真正执行final DC、同一final映射PT以及完整own-S2e FM，有序链为own89 default SVF、
原134 hold SVF的相同字节副本、155自己的final repair SVF。不借baseline116映射或证明。
退出前再次核验所有原134输入和155自身文件。所有结果保持`NOT_QUALIFIED`；
完整150MHz、SRAM内部/活动与能量资格不由该工具自动解除。

在原服务器以foreground单入口交给总控：

```sh
python3 -B -u /absolute/xu-campaign-batch154/timing155/resume155.py \
  --out "$HOME/Desktop/xu-score-optimization-20261102/s2e-own-timing-repair-20261105-155"
```

输出不得已存在，原134不会覆盖或重启。终态沿用原134严格实现的
`EXECUTED_OWN_S2E_SAME_MAPPED_DC_PT_FULL_FM_NOT_QUALIFIED`或`FAILED_NOT_QUALIFIED`；
`state.json.resume155`区分五项接续和后续新原生步骤。
外部原件先验失败可能不创建结果目录，总控应保留worker log和孤儿审查状态。

本地五项检查（不运行EDA）：

```sh
python3 -B /home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-s2e-timing155/test155.py
```

检查真实同类大字段触发原限制、无截断读取、五阶段有序接续、Tcl超出路径重定位的变更拒绝，
以及原报告变更拒绝。本机不持有原约99MB native-cells正文，其完整重哈希在服务器执行。
