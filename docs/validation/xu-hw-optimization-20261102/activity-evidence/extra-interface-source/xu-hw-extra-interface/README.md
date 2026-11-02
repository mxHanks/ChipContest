# xu 冻结源码的补充接口观察

本包仅补充接口验证，不改冻结提交 `97b35421dfbbfa8f4d495b6927a7c66610ff8206` 的运行源码。`base-tb_xu_cached_wrapper.sv` 是该提交的原始 directed TB；`supplement.patch` 为可复核的最小差异，新增测试位于 `tb_xu_cached_wrapper_extra.sv`。

- 对结果只读窗口 16 个字逐一写入相反数据，验证写入被忽略，且 `RESULT_INDEX` 不变。
- 在计算 busy 期间写入并读回 `CACHE_CTRL=1`、`CACHE_ADDR=173`，明确观察这两个寄存器没有硬件 busy 写保护。该操作违反固件的参数稳定约束；不检查该次计算数值，随后立即复位并核对 idle/legacy 控制状态。

先在展开包目录验证文件哈希：

```bash
sha256sum -c SHA256SUMS
```

可在临时目录复核 patch 重建的 TB（不修改仓库源码）：

```bash
patch -o /tmp/xu-extra-reproduced.sv base-tb_xu_cached_wrapper.sv < supplement.patch
cmp /tmp/xu-extra-reproduced.sv tb_xu_cached_wrapper_extra.sv
```

对已准备相同生成 RTL 的仓库运行，`--out` 必须是新目录。runner 在启动工具前会验证 manifest 中全部 13 个 RTL 文件的 SHA256。

```bash
python3 run.py --repo /path/to/ChipContest --sim iverilog --out /path/to/new-iverilog-output
python3 run.py --repo /path/to/ChipContest --sim vcs --out /path/to/new-vcs-output
```

完整编译/运行命令、工作目录、返回码、耗时、日志 SHA 写入输出目录的 `commands.json`；原始日志为 `compile.log` 和 `simulation.log`。runner 兼容 Python 3.6。本地 Icarus 原始日志随包提供，VCS 必须由同服务器环境另行实跑，包内不声明 VCS 已通过。
