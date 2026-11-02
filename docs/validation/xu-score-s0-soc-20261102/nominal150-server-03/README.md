# xu 150MHz真实十二层SoC宏模型对照

实际服务器VCS、同一SiFive GCC10.2工具链，源码299a5b5、E203 f49a5fc。原始参考模型与完整336宏SoC分别执行12个真实FFN1层，均逐字通过304128个Y/608256个写回字；各层所有PERF计数与旧4ns基线的测量周期一致，总inclusive cycles=16510344。逐层对照在per-layer.json；raw为服务器原文，不改写时间或周期。

独立的nominal150时钟采用1fs精度绝对边沿：HF 150MHz、LF 32.768kHz；每个任务的首个源读接受与末Y响应退休记录物理tick。源码断言覆盖整个reset后区间，逐层窗口误差在1fs内。原始固件mcycle值保留，不能将固定开销误称为硬件窗口。

这是一条独立功能/时钟运行证据：不证明门级等价、完整STA、宏时序、全SoC能量或比赛资格；本记录仍使用旧accept窗口，且未执行新增公共MMIO全量清空。正式request/clear窗口和全范围活动须另存，不把本记录冒充正式性能/能量任务。

复现命令见raw/state.json及helpers/nm3.py；在源码299a5b5上调用tools/ppa/xu_soc_ppa_verify.py --sim vcs --clock-mode nominal150 --tasks 12 --variants reference macro --firmware-schedule bias-hw-window --firmware-opt=-O2 --firmware-experiment both-unroll-no-masks，显式提供同一私有vendor-model/cross-prefix和新输出目录。

传输包full-soc-audit-15-private.tar.xz：47628字节，SHA256 5fe51089fac116accec16a7a77a7ecf1170b69d05a670f47951c5d1347926a2f；包同时含未公开工具手册片段，因此本目录仅提取本功能记录。SHA256清单绑定本目录原始日志及衍生对照。
