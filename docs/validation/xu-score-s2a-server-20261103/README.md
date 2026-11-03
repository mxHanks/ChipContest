# xu S2a 服务器 VCS 双调度验收（2026-11-03 归档）

原始服务器在同一 S2a 候选 RTL 上，分别执行旧 ABI 和 stream16 的八步开发验收，两份 `acceptance.json` 均为 `PASS`，state 为 `VCS_ACCEPTED_NOT_RETAINED`。本次只采纳根流程指定的唯一原始路径 `resume-export-01/s2-s2a-accept-01/`；未使用同传输包的截断 `.head` 文件或其他同名导出。

原执行在 2026-11-02，本目录于 2026-11-03 独立复核归档。现有记录采用开发装载窗口，没有候选正式任务前 clear/request 窗口；本结果不构成正式吞吐、能耗、PPA、资格、保留或得分结论。

## 冻结身份与参数

主仓 **`3c13930c1f36d6516577d33d8587d89a86b49563`**、E203 **`faaa3e3d8b7832012fe48a8e27f684e5b5706306`**，分支 `codex/xu-s2a-stream`。实际改动的 Chisel 文件：**无**；子仓相对 `f49a5fc` 只改 `rtl/e203/perips/accel_icb_slave.v`。主仓基点为 `74e0118`，实际标量流实现提交 `01a6a5d`，`3c13930` 补充本地证据。数值定义 signed16 X/W、signed40 bias、signed48 Y、8 PE、共享槽格式和固定向量保持不变。

两条 schedule 分别为 `bias-hw-window` 与 `bias-hw-stream16-window`，共同使用 **SiFive GCC-Metal 10.2.0-2020.12.8**、**VCS Q-2020.03-SP2-6_Full64**、`-O2 / both-unroll-no-masks`。实际 RTL/TB、runner、contract、固件源、工具、fixture、48 个 real 向量声明哈希和模拟器声明 SHA 逐项相同；不同的是固件编译 schedule 和生成镜像。共用模拟器声明 SHA 为 `3253ddbb6a96852acdc43dc4fbafe306b5ff4f987d90b5c264643e6977edbfc3`。

每条八步为 host、numeric、check-vectors12、doctor、5 个 legacy 用例、synthetic1、synthetic2、real12。此紧凑导出没有回传 host/numeric 原文和其余步骤顶层日志；因此八步 PASS 是原 acceptance 的状态记录，不能据此独立断定 host/numeric 的测试数、skip 数或每条缺失日志的具体内容。已取回六次 synthetic/real 的实际 simulation log 和结果，均被独立严格重验。

## 十二层实际比较

| 层 | 旧 ABI 窗口周期 | stream16 窗口周期 | stream 减旧 ABI |
| --- | ---: | ---: | ---: |
| 0 | 1,375,864 | 1,280,113 | -95,751 |
| 1 | 1,375,860 | 1,280,113 | -95,747 |
| 2 | 1,375,864 | 1,280,113 | -95,751 |
| 3 | 1,375,860 | 1,280,113 | -95,747 |
| 4 | 1,375,864 | 1,280,113 | -95,751 |
| 5 | 1,375,860 | 1,280,113 | -95,747 |
| 6 | 1,375,864 | 1,280,113 | -95,751 |
| 7 | 1,375,860 | 1,280,113 | -95,747 |
| 8 | 1,375,864 | 1,280,113 | -95,751 |
| 9 | 1,375,860 | 1,280,113 | -95,747 |
| 10 | 1,375,864 | 1,280,113 | -95,751 |
| 11 | 1,375,860 | 1,280,113 | -95,747 |
| 合计 | **16,510,344** | **15,361,356** | **-1,148,988（-6.959201%）** |

两组均实际逐项通过 **304,128 个输出 / 608,256 个 Y 写回字**。旧 ABI 每层全部周期/PERF 与 frozen combined 的 [`reference4ns-real12` 原记录](../xu-score-s0-soc-20261102/functional-server-02/README.md) 一致；这里的主要比较直接取自同一 S2a RTL 的两次服务器运行，不拼接本地 GCC/Verilator 数据。

| 十二层阶段/工作量 | 旧 ABI | stream16 | 差值 |
| --- | ---: | ---: | ---: |
| W 装载 | 3,587,388 | 2,752,452 | -834,936 |
| X 装载 | 1,378,968 | 1,066,788 | -312,180 |
| bias 装载 | 93,312 | 93,288 | -24 |
| 计算/等待 | 2,623,104 | 2,623,104 | 0 |
| 写回 | 7,830,708 | 7,831,296 | +588 |
| 其他 | 996,864 | 994,428 | -2,436 |
| MMIO 写 | 668,640 | 397,128 | -271,512 |
| MMIO 读（实测） | 912,384 | 912,384 | 0 |
| shared 读 / 写 | 278,784 / 608,256 | 相同 | 0 |
| START / done | 38,016 / 38,016 | 相同 | 0 |
| busy / MAC 有效拍 | 2,585,088 / 2,433,024 | 相同 | 0 |
| shared 背压 | 130,320 | 349,572 | +219,252 |

每层共享读 **23,232**、Y 写 **50,688**、START/done **3,168**、MAC 有效拍 **202,752**，全部满足原严格 schedule 契约。每层 MMIO 写旧 ABI **55,720**、stream16 **33,094**；六阶段之和逐层严格等于窗口。原 TB HF 为 4ns；窗口从首个共享读接受至最后 Y 写响应退休，预装载和 CAP 探测在窗口外，流游标初始化、内部提交、轮询、写回在窗口内。流命令改变 modulo-7 共享背压的相位，故保留实测背压差。

固件 mcycle 合计为 **16,511,202 / 15,361,968**；它含不同前后开销，不替代硬件窗口。实际固件 ELF 声明 SHA 旧 ABI 为 `3ebce7dfe768ae98556500d408e3a564ebb590a31ddf48f49bd164741d0b0395`，stream16 为 `2c13e1701186754b8779749a2f5571852a11d842b761216ee013fe1d017fe9e5`。装载镜像声明 SHA 分别为 `6e22a1bffbd74c5cfc9b6d8603ce71a9f413ec5d2aea5df8bf792b922461e4e1` 和 `e1db681da1eba37bc95b0b2092ba3fa14e39fc3621bd1338992c61c06ede651b`。

## 复核与缺口

`check-evidence.py` 默认只读，执行以下复核：

- 从原完整 export manifest 逐 path 选择 **24 个唯一 payload**，要求各路径恰好出现一次，长度/SHA 与原字节一致；不采用 `.head` 或名称匹配。原完整 manifest 保留为 `original-export-manifest.json`，选中列表为 `selected-manifest.json`。
- 核对两份 acceptance 的状态、八步顺序、实际命令、参数和 state 中的 acceptance SHA；三种模式共六次实际 VCS TASK/PERF/SOC 重验，逐层全部计数与结果记录一致。对这些实际日志作 **48 种**缺行、重复行、工作量±差、缺 SOC、附 FATAL 破坏，均被原检查器拒绝。
- 报告的 **151 个 RTL/TB 源文件**与冻结 main/child Git blob 的 SHA 逐项一致；runner、contract 和固件源也匹配。`frozen-git-sources.tar.xz` 保存这些 Git 字节，`git-source-audit.json` 绑定其哈希。本地 S2a 源码无需修改即可离线重放原检查器。
- 两组 real fixture 和 48 个向量声明哈希与固定样本一致，vectors/result 的独立整数检查记录也一致。归档时从仓库固定 archive 重新计算 **304,128 个** XW+b 整数输出通过；不是 600 样本浮点 NRMSE 结论。
- 两组已取回的 cached-wrapper 服务器 VCS 日志均为 `accepted=retired=4,909`。这是旧 cached TB；**没有回传新 stream direct TB 的服务器日志**。冻结 `test_stream_wrapper.py` 硬编码 Icarus，在缺工具时可 skip。不能将 cached VCS PASS 或八步状态冒充新 direct TB 的 VCS 覆盖。独立本地 direct stream 证据仍见 [`xu-s2a-stream-20261102`](../xu-s2a-stream-20261102/README.md)。

`missing-evidence.json` 保存逐调度的已知缺失清单。未带回 host/numeric/各步骤顶层日志、firmware-build/sections/symbols、build/version 日志、固件 ELF/镜像、模拟器二进制和服务器实际向量文件。result 内对应 SHA/版本是服务器原报告的记录身份，没有声称重新哈希缺失字节；取回的实际 simulation log 已与声明 SHA 匹配。原始绝对路径、时间、日志文本与哈希均保留，不改写旧失败/负例记录。需要补强时应从服务器再次导出缺失原文件。

## 复现

在上述 frozen main/child 的独立 checkout 和同版工具链下，两个输出目录必须尚不存在。源码上的八步入口可直接重现两种配置；新 stream direct TB 服务器后端覆盖须另外保存，不能通过 skip 验收。

```bash
python3 docs/validation/xu-score-s2a-server-20261103/check-evidence.py

python3 tools/scripts/server_accept.py --sim vcs \
  --cross-prefix "$xu_cross_prefix" --firmware-schedule bias-hw-window \
  --firmware-opt=-O2 --firmware-experiment both-unroll-no-masks \
  --out "$xu_new_s2a_oldabi_out"
python3 tools/scripts/server_accept.py --sim vcs \
  --cross-prefix "$xu_cross_prefix" --firmware-schedule bias-hw-stream16-window \
  --firmware-opt=-O2 --firmware-experiment both-unroll-no-masks \
  --out "$xu_new_s2a_stream_out"
```

原始 cross-prefix 为 `/storage2/2026contest/server4/s4_23usr/Desktop/xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf-`，原始 frozen checkout 为 `/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/ChipContest-s2-s2a-01`。两份 acceptance 的所有八步 argv 已保存在 `raw/` 原文，可据此调整实际位置后执行。

`comparison.json` 为机器可读逐层全计数/身份/差值与缺失记录，`per-layer.csv` 为周期表；`sha256.json` 覆盖本目录其余所有文件。本次独立归档没有运行新服务器模拟、Chisel、综合、STA、formal、活动或功耗测量。
