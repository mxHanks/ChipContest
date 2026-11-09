# S3-Y32 软硬件联调候选 v1 发布证据

生产方案和软件 ABI 见[handoff](../../s3-y32-hw-sw-handoff.md)。父/子仓库分支均为 `codex/s3-y32-hw-sw-v1`；子仓提交固定为 `45e61b6101ad6f0aaa7583098294ffb1550f1f2d`。

该候选为 16 PE、共享 W/bias、独立外围 DMA、共同 fabric clock/reset，使用独立命名的 `DmaBiasSramPrefetch` 保留旧接口。当前发布状态是**功能验证通过的联调候选**。新面积未测、时序尚未闭合，正式平台资格未验证。

## 已实际执行的验证

- 发布源码 CPU 单层和完整 12 层均通过。完整 12 层 304,128 个 Y32 输出，主口径 1,514,236 拍，含 gap 1,514,728 拍；额外预热任务的 25,344 个输出也逐位检查。
- 每任务独立参数、真实物理清零和全部请求/响应退休均检查。源码漂移为零；逐层向量、计数和周期与原 full12 相同。
- 158 项生产 RTL 和 PPA 包装逐字节匹配当前 Git 源码与完整 CPU 冻结源；42 项 CPU core 文件不变。
- 旧接口真实 CPU 回退通过：25,344 输出，payload 422,768 拍、clear 66,802 拍、gap 102 拍。
- 重新执行 Chisel 生成，11 个 SV 文件与发布 RTL 全部逐字节相同。
- 命名隔离前曾出现旧接口缺五个端口的编译失败。原失败、修复和成功回退均保留，不将首轮失败说成通过。

1,188.72 task/s 是按假定 150 MHz 换算的功能仿真值，不能当作时序通过后的正式吞吐。

## 文件

| 文件 | 内容 |
| --- | --- |
| [publication.json](publication.json) | 子提交、包身份、数值与缺项 |
| [source-audit.json](source-audit.json) | 158 项已提交生产源及 PPA 包装与完整测试源对应 |
| [full12-result.json](full12-result.json) | 原始 CPU full12 运行凭据、工具与所有身份 |
| [full12-simulation.log](full12-simulation.log) | 原始完整日志 |
| [per-layer.csv](per-layer.csv) | 逐层周期 |
| [generator-identity.json](generator-identity.json) | 11 个生成 SV 的字节一致性 |
| [dma-bias-namespace-proof.json](dma-bias-namespace-proof.json) | 精确逆命名归一证明 |
| [fallback-namespaced-r2/result.json](fallback-namespaced-r2/result.json) | 修复后真实旧接口 CPU 回退 |
| [fallback-committed-child-r1/result.json](fallback-committed-child-r1/result.json) | 修复前真实编译失败 |
| [frozen-run.tar.gz](frozen-run.tar.gz) | 当前 170 文件测试源、固件、仿真器、12 层向量、完整日志和清单 |
| [baseline-frozen-run.tar.gz](baseline-frozen-run.tar.gz) | 命名隔离前 168 文件历史候选，用于追溯，非当前生产版本 |

当前包 SHA256：`c93a484178553e1f65a4af9bc0c4728bb6e3ab486b01b8b96757cefc9384bc07`，4,403,136 B；257 个原件和 manifest 已逐字节核验。历史包 SHA256：`e88a2fad53f32d6bf04f566746700f2d89d970c30ef6ab53f25485cec25780c5`。历史包内“未推送”等字段描述的是原打包时状态，不能覆盖本次 Git 发布身份。

## 获取和复核

```sh
git clone --branch codex/s3-y32-hw-sw-v1 --recurse-submodules https://github.com/mxHanks/ChipContest.git ChipContest-hw-sw-v1
cd ChipContest-hw-sw-v1
git submodule status
sha256sum docs/validation/s3-y32-hw-sw-v1-20261109/frozen-run.tar.gz
mkdir -p build/hw-sw-v1
tar -xzf docs/validation/s3-y32-hw-sw-v1-20261109/frozen-run.tar.gz -C build/hw-sw-v1
python3 experiments/s3-y32-dma-day/replay_frozen.py --sealed-run build/hw-sw-v1/frozen-run --out build/hw-sw-v1/replay --tasks 12 --jobs 2
```

默认重建全部冻结 RTL，开启 Verilator assertions；不使用旧路径、Git 历史源码或已编译二进制冒充新编译。需要 Python、Verilator 和支持 C++20 的 g++；使用包中固定固件，无需重新安装 RISC-V 编译器。重放前核实源、ELF/image、向量和清单身份，运行后检查所有输出、物理清零、时序窗口与逐层周期。

当前截止保护为 `2026-11-09T23:59:00+08:00`。若以后重新授权复核，须明确传入新的 `--deadline`，不会自动延长实验。

若需要把**当前 checkout** 的生产 RTL 重新绑定到相同测试台并编译固件，可运行：

```sh
python3 experiments/s3-y32-dma-day/run_published.py --sealed-run build/hw-sw-v1/frozen-run --out build/hw-sw-v1/checkout-task0 --tasks 1 --dual 1 --warmup --jobs 2
```

该入口额外需要 `riscv64-unknown-elf-gcc/objcopy/objdump`。它从当前子仓和父仓 PPA 包装取生产源，保留包中已验证的 fabric-clock 测试台和物理观察器，继续使用原 CPU 检查器；不修改生产内存、不预置 Y、不添加新测试后门。

生产构建打开 `XU_MATRIX_DMA`，共同 clock/reset 从 SoC 现有 fabric 导出。包内 `boundary_tb_shared_endpoint.sv` 仅是测试模型，不可替代正式 SRAM 或宏模型。不要把历史 `CPU-VALIDATION.md` 中的旧测试台当作本修复的时钟/复位证明。
