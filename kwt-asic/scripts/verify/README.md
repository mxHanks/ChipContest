# 迁移验证运行器

在项目根目录执行（Python 3.10+，不依赖第三方 Python 包）：

```bash
python3 scripts/verify/run_checks.py --tier static
python3 scripts/verify/run_checks.py --tier host
python3 scripts/verify/run_checks.py --tier rtl --jobs 1
python3 scripts/verify/run_checks.py --tier rtl --groups reset_edges async_fifo --simulator iverilog
python3 -B -m unittest discover -s tests -p 'test_verification_runner.py'
```

各层累积执行：`static` 调用原包完整性工具；`host` 增加有限 BF16 转换、FP32 辅助函数和 16 例 fake-MMIO C 检查；`rtl` 再仿真明确选择的元数据 source set。默认 RTL 只执行 reset、async FIFO、slot bank、service observer、counter adapter 五组，其中后两组各执行两个场景。不会递归编译 vendor 下的 RTL。

`auto` 对 reset/FIFO 优先 Icarus 四态仿真，其余组优先 Verilator。可用 `--simulator` 固定工具。Verilator 需要支持 `--binary --timing` 的 5.x，以及 make/g++；Icarus 建议 11+，需同时有 vvp。所有组串行，编译默认单线程、最多四线程，Verilator 仿真固定单线程；超时会终止整个进程组，默认编译 180 秒、仿真 60 秒。可用 `--compile-timeout`、`--sim-timeout`、`--host-timeout` 调整。

可选组名称来自 `vendor/fpt-r1/metadata/dependencies.json`。QK request buffer 自动分别编译运行 CLEAR_IN_FLIGHT=0/1；FP32 reference vectors 需显式提供 `--vectors /absolute/path/vectors.hex`，每行四个 8 位十六进制值（a、b、预期乘积、预期和）。它会核对向量条数与实际完成条数，不接受空文件。未准备的组记 `BLOCKED`，未选择的组记 `NOT_RUN`。不自动回退掩盖编译或仿真失败；应查看日志并记录工具兼容性。

每次运行独占新建 `artifacts/runs/<UTC时间-随机ID>/`，包含结果 JSON、命令日志、工具版本和可执行文件 hash、来源文件 hash、起止时间和耗时。只有退出码为 0、无失败诊断且所有指定最终完成标记出现，场景才是 `PASS`；仅 `$finish` 或中间 PASS 不算通过。退出码：0=选定范围 PASS，1=FAIL，2=BLOCKED。导入完整性失败时阻断 host/RTL。

这些 PASS 只说明原 FPT 参考件可导入/局部复用；新 KWT 功能、精度、E203 集成、综合、时序和功耗一律单独标记 `NOT_RUN`。原包不被修改，日志不能作为新比赛验收证明。
