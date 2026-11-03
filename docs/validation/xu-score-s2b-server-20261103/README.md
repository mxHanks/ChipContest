# xu S2b packed32 服务器验收

服务器对冻结主提交 `a2a1f076060c43fcefb1148edaa83c89bb1d4320` / E203 `d5faa5e8c857fa35df62a68de667bdb8a6e954f7` 完成八步开发验收与两个强制 direct VCS。实际12层总周期 **14,532,449**，全部 **304,128** 个结果、**608,256** 个 Y 写字匹配。对前一 S2a stream 的 15,361,356 周期下降 **5.396054%**；对 combined 基准 16,510,344 下降 **11.979732%**。这是同服务器开发仿真周期，不是正式评分吞吐。

生产 Chisel 修改：**无**。硬件相对 f49a5fc 仅改 `third-party/e203_hbirdv2/rtl/e203/perips/accel_icb_slave.v`：保留旧接口，新增 packed32 能力寄存器与 W/X 流写端口，一次32bit命令提交两个16bit元素，内部两拍完成后才产生响应。固件减少地址控制和写事务；8PE、signed16/40/48、32KiB逻辑W、原12个生成SV、固定向量不变。独立实现和本地证据在候选分支，未合并为最终比赛配置。

| 层 | 实际窗口周期 |
| --- | ---: |
| 0 | 1,211,034 |
| 1 | 1,211,035 |
| 2–11（各层均实际运行） | 1,211,038 |
| 总计 | **14,532,449** |

逐层全部阶段/工作计数见 `per-layer.csv` 和 `comparison.json`。每层 shared 读23,232、写50,688，START/done各3168、MAC有效拍202,752、MMIO写21,734；六阶段严格覆盖实际窗口。服务器使用 SiFive GCC-Metal **10.2.0-2020.12.8**、VCS **Q-2020.03-SP2-6_Full64**、`-O2 / both-unroll-no-masks / bias-hw-pack32-window`。

八步 host、numeric、vectors、doctor、legacy5、synthetic1、synthetic2、real12 均有原始日志。host实跑54项、skip2（辅助stream/packed测试依赖本机Icarus），numeric42项通过；host原文中的FAIL/缺工具消息来自拒绝测试，最终 unittest 状态为OK。另行强制执行 direct packed/stream VCS，不使用这些skip代替新接口验收：packed accepted=retired=9653、16457次内部写、W16390/X67/33次start；stream accepted=retired=17828、16454次写、W16387/X67/33次start。实际cached VCS辅助日志也保留。

`check-evidence.py`只读核对95个唯一取回payload及其原始清单、174个冻结Git源、每次SoC仿真的151个RTL/TB身份、runner/contract/固件源、62份声明日志、全部TASK/PERF/工作量、实际direct计数和后端；从固定archive独立重算304,128个整数结果。对三份SoC日志注入27种缺行、重复、错误工作量、缺SOC、FATAL，要求全部拒绝。源码archive保存installed路径对应的原Git字节，未拷贝厂商模型。

原始传输包：95,472 bytes，SHA256 `5cb9b56becb29d139e5db62a5d3a7d203f14355130126b534e1135eaedb35bcc`；原完整manifest含239项，本目录只选择95个S2b原文件。字节、绝对路径、时间、错误测试及日志空白均保持原样。`sha256.json`覆盖本目录其余交付文件。

未取回ELF/image/simulator二进制和实际服务器向量字节，其SHA是原报告声明，不声称本地重新哈希；固定仓库向量已独立核验。TB采用4ns HF/66ns LF开发窗口（首shared读接受至最后Y响应退休），并未做候选正式物理clear及首请求计时，也未在此证明映射等价、150MHz STA、全SoC能耗、候选保留或比赛合格。同库PPA另有独立输出，不拼接到本次配置作评分。

复核：

```bash
python3 docs/validation/xu-score-s2b-server-20261103/check-evidence.py
```

在上述冻结主/子独立checkout和服务器同版本工具链上复现八步（输出目录必须全新）：

```bash
python3 tools/scripts/server_accept.py --sim vcs \
  --cross-prefix "$xu_cross_prefix" --firmware-schedule bias-hw-pack32-window \
  --firmware-opt=-O2 --firmware-experiment both-unroll-no-masks \
  --out "$xu_new_s2b_out"
```

原始cross-prefix为 `/storage2/2026contest/server4/s4_23usr/Desktop/xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf-`。强制direct VCS的完整编译/运行argv在 `raw/s2b-accept-01/direct-{packed,stream}-vcs/{compile,simulation}.log` 首行，必须另行执行并保留原始日志，不能只调用可能skip的辅助unittest。八步命令和原部署归档SHA保存在原state/deploy日志中。
