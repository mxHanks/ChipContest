# xu：2026-11-01 服务器 VCS 验收

结果：**VCS 开发平台验收 PASS**。本轮在实际 EDA 服务器执行，不沿用 2026-10-27 的历史 PASS。原版 `--full`、服务器 Chisel、官方 SRAM/PPA 和新浮点 validation 各自独立，未包含在这个结果内。

主仓基线为 `ddcf6cc5ea9119b3dd162249be8c4521eef45da2`，E203 为 `e36d34a52e6eef93fd0bdfed1b13009e1056bea3`。本轮仅改运行器、标准库软件数值链、测试与文档；计算 RTL、MMIO、Scala/Chisel 版本和子模块 gitlink 保持不变。运行发生在适配文件提交前，报告中的 HEAD 保留基线；[执行文件清单](runtime-source-manifest.json) 记录本轮运行代码身份，不能用分支名推断执行版本。

| 检查 | 实际结果 |
| --- | --- |
| Python 主机检查 | 19/19 |
| 标准库数值模型 | 34/34，含外部同名模块不能覆盖整数参考的回归 |
| 真实夹具独立整数核算 | 12 层，304128 结果 |
| 固件/子模块 doctor | RV32 实际构建、结束地址及 gitlink 检查通过 |
| 原 SoC 基础回归 | ADD、MMIO、compute、multigroup、repeat_x：5/5 |
| 合成矩阵 | 一层全部 25344 结果通过，含极值和高位正负结果 |
| 真实静音矩阵 | 12 层，304128 结果、608256 写字全部匹配 |
| 篡改首个参考输出 | 实际 VCS 触发 result mismatch，运行器返回失败 |
| 限制为 1000 周期 | 实际 VCS 触发 timeout，运行器返回失败 |
| 外部上游/checkpoint 来源 | 固定提交 237e4097 的 104 文件 SHA/长度通过 |

真实12任务中间不复位；第一层开发计时 2368078 周期，其余层各 2368074，固件计时分别为 2368150 与 2368146。VCS 日志报告 CPU time 513.00 s。该计时排除 TB 预装载，且使用行为存储与开发时钟，不是比赛吞吐量或 150 MHz 收敛结论。

## 环境与复现

服务器环境：Python 3.6.8、Git 1.8.3.1、glibc 2.17、Make 3.82、主机 GCC 4.8.5、Java 1.8.0_25、VCS Q-2020.03-SP2-6。交叉工具使用 SiFive GCC-Metal 10.2.0-2020.12.8 CentOS6 发行版的未改二进制/头文件子集，仅支持本工程 freestanding C/汇编。原发行包来自 [SiFive December 2020 release](https://github.com/sifive/freedom-tools/releases/tag/v2020.12.0)，来源地址、原包和子集 SHA 保存在 [观察记录](observed-summary.json) 及服务器工具清单。

本轮服务器独立目录位于：

```text
/storage2/2026contest/server4/s4_23usr/Desktop/xu-platform-eval-20261101-codex/
```

原 `xu-work/ChipContest` 保留。本轮适配副本在上述目录的 `ChipContest/`，工具前缀是相邻 `sifive-rv32-c/bin/riscv64-unknown-elf-`。在副本内重新验收：

```bash
python3 tools/scripts/server_accept.py --sim vcs \
  --cross-prefix ../sifive-rv32-c/bin/riscv64-unknown-elf-
```

运行器每次生成新输出目录。原始报告保存在服务器 `vcs-acceptance-01/acceptance.json`、各步骤 `result.json` 和 `simulation.log`；失败负例在 `vcs-negatives-01/result.json`，汇总在 `server-summary.json`，代码身份在 `final-source-manifest.json`。本地仅保留明确标注的观察摘要和 VNC 截图：FTP 允许上传、拒绝 RETR，因此这些本地文件不冒充从服务器复制的原始 JSON。

## 范围与后续

原版 `--full` 在该服务器先因 Python 3.6 的较新 subprocess 参数报两个 host 错误；这些错误已修复并用同机19项回归确认。原版所需 Icarus、Verilator 和 Scala CLI 尚未补齐，本轮按已批准路线使用 VCS；其结果不能替代服务器 Chisel 回归。

上游来源字节已在服务器核实，系统 Python 的真实导出尝试返回 **2/BLOCKED**：尚需隔离 Python 3.8.20、tensorflow-cpu 2.4.0、NumPy 1.19.5 环境及开发数据。没有重跑4445条浮点 validation，也没有宣称官方600评测通过。静态尺度与编码/解码已在 [数值契约](../../numeric-contract.md) 固定；正式平台装载、宏、约束和计时待按 [接口契约](../../platform-interface.md) 对接。

[完整12层结束日志截图](vcs-real12-pass.png)、[一键验收与负例截图](vcs-acceptance-and-negatives.png) 和 [模型来源/环境边界截图](kwt-source-and-inference-boundary.png) 保留实际输出。[观察摘要](observed-summary.json) 中列出证据 SHA256。
