# 实际无负载单元清理50、驱动修复FM49及reset55失败

本目录保存服务器实际执行原件，**尚未达到完整150MHz/比赛资格**。44份原件共31,681,981字节逐份XZ无损存储；每个展开原件与实际export60逐字相同。完整原export60有60份payload，31,715,543字节，tar.xz为478,696字节，SHA256 `cdda0f31421fe3d0c957e3386cff74697e2553352e70e17c53307329199a2f1e`。具体日志SHA和展开路径见[manifest.json](manifest.json)。没有清洗工具日志尾空白，也没有把失败状态改为成功。

| 实验 | 实际结果 |
|---|---|
| 49定点驱动修复后的完整Formality | 41462点PASS：17136 BBPin、144 Port、24143 DFF、39 LAT；511 unread、17 reference unmatched另行披露 |
| 50无负载单元清理 | 删除1404个单元；DC/PT各return0、唯一完成marker、无脚本Error |
| 50电气检查 | max-cap保持0；min-cap由1404变为187，并未闭合 |
| 50时序覆盖 | 294473 total / 267344 met / 5 violated / 27124 untested |
| 55-from50-n4 reset插入实验 | DC失败于缺省`dont_use`属性返回空值，**尚未执行缓冲插入** |

FM49证明目标是 `5df0b568d1751d19388edb33d244f8b19051a9fa7c77b24a2e023bf1e2ee4b4c`。169个冻结输入before/after相等，包含原RTL、两份实际SS DB和完整default→08→09→49 SVF链；本次实际Tcl和fm.log均有独立SHA绑定。SRAM仍按原黑盒边界、原auto-setup/undriven假设验证，不能据此证明SRAM内部、时序或能量。原件没有独立aborted统计行，不凭空补0。

50目标网表是 `9b7265e703ea62487c5b5c39c66adf245e720ac02f1066063cfd0eb4753f460c`。删除前对1404个单元重查全部输出、跨层`all_connected -leaf`和唯一owner；包括3个有原RTL未使用证明的PLIC优先级寄存器，其余不做盲递归删除。层级端口与net segment保留，**leaf只有自身不能推导不存在层级端口**。原1404中1287个输出的net跨2–8个segment。

删除后重新审查1059个唯一上游driver，187个变为source-only；它们与最终PT的187个min-cap pin集合相同。setup/hold各67245 met、0 violated、3790 untested；仍有5个原reset removal违例，最差−0.12148283ns。全coverage比49少39个check、36 met和3 untested，与删除3个PLIC寄存器相符。保留70个first-D cut与6个forwarded-clock实验场景、原SDC及0.1ns uncertainty；没有添加reset/UART豁免。50自己的完整SVF链FM仍须以终态归档为准，不能借用49的PASS。

55失败原件准确保留了DC `UID-101` 和 `expected boolean value but got ""`。修正版必须在新目录执行。即使后续插入成功，两个PMU SDN的conditional recovery及其余untested范围仍需检查；对特定输入相位添加mapped delay不能证明任意异步复位释放相位安全。

离线校验：

```bash
python3 docs/validation/xu-score-electrical-cleanup-server-20261104/check-evidence.py
# 若保留原解包目录，可再逐字对照全部44份：
python3 docs/validation/xu-score-electrical-cleanup-server-20261104/check-evidence.py \
  --source-export build/xu-score-resume-20261103/next-results-export-60
```

服务器原命令（输出已存在时禁止重用，独立复现实验应改新输出名及相应helper）：

```bash
python3 "$HOME/Desktop/launch_min_cell_cleanup50.py"
python3 "$HOME/Desktop/launch_electrical_formality54.py" 49
python3 "$HOME/Desktop/launch_reset_buffer55.py" 50 4
```

上述helper的确切代码与SHA已在前次[修复工具归档](../xu-score-electrical-repair-20261104/README.md)保留。此处原件及复现命令不构成最终选型。
