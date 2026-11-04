# xu S2e：同服务器完整VCS与同RTL调度对照

服务器实际真实12层从旧调度 **11,842,200** 降到 paired-HI **10,420,140** 周期，减少 **1,422,060 / 12.0084106%**。12层分别都是986850→868345周期；[逐层原表](per-layer-comparison.csv)保持服务器原字节。两次运行采用同一main `5bf123bfead8f2a37f97f3234d4e40ce8201aae9`、child `a0767db69628ef30e53de2d1e93dd0360c0ccf76`、实际RTL、VCS二进制、SiFive GCC10.2、向量及-O2/both-unroll-no-masks，271个runtime身份执行前后相同。保留旧S2c调度作为这份新物理RTL上的对照，未借用历史旧网结果。

| 每层实际工作 | 旧调度 | paired-HI |
|---|---:|---:|
| 周期 | 986850 | 868345 |
| 结果MMIO读 | 50688 | 38016 |
| Y写入word | 50688 | 50688 |
| MAC fire | 202752 | 202752 |
| writeback周期 | 666370 | 547669 |

完整两次运行各核对304128个输出、608256个Y写入word。W、X、bias、48bit结果及64bit符号扩展的Y内存语义保持；高16位仍先恢复为有符号值。这里的周期是开发窗口，不能与nominal150MHz/LF绝对相位、任务前清空的正式能量窗口混用。

**本项没有改Chisel。** 生产修改位于child的`rtl/e203/perips/accel_icb_slave.v`和main的`tests/e203/firmware/accel.c`及调度契约：增加capability 0x0e0=`0x58480001`和0x140/144/148/14c的相邻两lane高16位合并读取。每两个结果采用两次原LO读取加一次paired-HI读取，维持原FIFO响应/POP退休所有权和全部旧地址语义；既有Chisel自动分组和8PE计算核心保持不变。具体生产起点为main `b01a895`，final74后续提交冻结入口和证据处理。

服务器完整验收已实际终态 `EXECUTED_VCS_ACCEPTANCE_NOT_PPA_OR_ENERGY_QUALIFIED`：64项host测试（3项skip）、42项numeric、直接wrapper VCS、五个旧平台VCS配置、synthetic1/2、paired真实12层及同RTL旧调度真实12层均完成。旧8调度×3优化×8实验共192配置的384次实际服务器编译，load image逐字节相同。host.log中的故意失败/缺工具负例文字原样保留，不误判为顶层真实验收失败；也不隐去3项skip。

**尚未取得新RTL的独立面积、完整150MHz、映射一致性或全SoC能量资格，不宣布最终保留或评分最优。** S2c的0.2948018380mm²、原Formality或能量数据不能直接登记成S2e结果。本地GCC14.2/Verilator筛选的10827459周期亦不替代本次服务器结果。

[原始归档](payload.tar.xz)为5052380字节，SHA256 `998b7e7622eda3e4e0934be395ed26f0a497d44a1af2c6a578eecb0b6a3deee9`；3752项payload共29571463字节，路径/大小/哈希见[original-manifest.json](original-manifest.json)。393个未返回正文（TB/vendor、obj/csrc、二进制等）逐项保留bytes、SHA和原因，正文仍在服务器，不能声称本地已有其原件。[归档器](tools/export_s2e87.py)逐项对照终态raw_files，日志内容没有改写。

离线完整核验并可提取到不存在的新目录：

```bash
python3 docs/validation/xu-score-s2e-server-20261104/check-evidence.py
python3 docs/validation/xu-score-s2e-server-20261104/check-evidence.py \
  --extract /absolute/path/new-s2e87-directory
```

服务器复现完整验收（先确认隔离源码为上述两个commit，保持原工具路径；新输出目录必须不存在，不与已有验收并发）：

```bash
B="$HOME/Desktop/xu-score-optimization-20261102"
python3 "$B/ChipContest-s2e-74/tools/scripts/xu_s2e_server_accept.py" \
  --expected-main 5bf123bfead8f2a37f97f3234d4e40ce8201aae9 \
  --expected-e203 a0767db69628ef30e53de2d1e93dd0360c0ccf76 \
  --out "$B/s2e-full-vcs-reproduce-new"
```
