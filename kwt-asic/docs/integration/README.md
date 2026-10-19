# 队友仓库审计与融合入口

本目录记录 2026-10-17 对队友仓库的实际读取、quickstart 运行和开发融合。原 `ChipContest/` 与其 E203 子模块保持只读；融合副本在 `integration/ChipContest/`，当前工程新增适配器和开发验证文件在 `soc/`、`sim/`、`soc/firmware/`。

- [主仓库源码、测试和面积流程审计](CHIPCONTEST_AUDIT.md)
- [E203 Fork、ICB 地址译码和默认测试审计](E203_AUDIT.md)
- [Nangate45 / SRAM / 面积脚本审计](LIBRARY_AUDIT.md)
- [完整 quickstart、差异、融合结果和后续步骤](FUSION_RUN.md)
- [ICB 寄存器与错误/背压契约](ICB_CONTRACT.md)
- [Chisel 真实向量测试契约](CHISEL_REAL_VECTOR_CONTRACT.md)

开发融合复现：

```bash
source env/activate.sh
# 原队友 E203 quickstart（每次先清理安装副本）
cd ChipContest/third-party/e203_hbirdv2/vsim
make clean && make install && make compile SIM=iverilog
make run_test SIM=iverilog DUMPWAVE=0

# 当前工程开发融合（已保存可复核产物，不把行为共享模型加入正式宏清单）
cd /media/leo/Data/Vitis/RISC-V-forward-acceleration
source env/activate.sh
# 生成/运行 E203 融合需要使用 artifacts/integration/20261017-teammate/soc-build 中冻结的命令
make test
```

当前状态是“开放 Fork 开发平台融合 PASS、正式组委会 E203/指定器件 PPA BLOCKED”。不要把 `frequency_mhz=150` 的开发 TB 参数当成 STA 结果；它只是与赛题目标一致的仿真时钟标记。
