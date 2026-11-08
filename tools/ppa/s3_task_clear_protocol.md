# S3 独立任务前清空候选

状态为 `GENERATED_NOT_FULL_SOC_SIMULATED / REVIEW_PENDING`。它不修改历史清空 helper、固件 main、RTL 或原 payload observer；不能用生成成功代替完整 SoC 清空／功耗／比赛资格通过。

只支持每个任务一个 fresh-reset process、`TASKS=1`。固件先读 HOST 任务数并拒绝其他数量，再检查 ID、旧 capability、fresh STATUS、bias capability。HOST 控制字不属于 X/W/bias 任务输入；清空代码不读取任务输入或参数。完成后才调用 SHA 冻结的原 main，参数完整上传仍在原任务路径中。

## 配方

公共 MMIO 全字写依次覆盖 W 16,384 个 signed16 字、legacy bias 8 个 signed40 值、X 64 字。bias capability `EC=0x42530001` 时执行 `E8=1`，等待真实 ICB 完成；该完成必须晚于 768 个物理 bias 写和两组 staging 清零。`EC=0` 时用全部 256 个 CACHE_ADDR/LO/HI 零写覆盖寄存器 bias。其他 capability 拒绝，不猜测其语义。

| 模式 | 接受的 clear 写 | W 数据写 | bias 路径 | legacy bias 写 | X 写 |
|---|---:|---:|---|---:|---:|
| SRAM | 32,930 | 16,384，另含 bank/address 选择 | 1 次 E8；768 个物理字及640bit staging | 24 | 128 |
| 寄存器 | 33,697 | 同上 | 768 次 CACHE_ADDR/LO/HI | 24 | 128 |

两种模式各另有一次 CACHE_CTRL=0（已计入表内写数），四个初始 MMIO ABI 读。结尾 `fence iorw, iorw` 后再做一次 STATUS=0 验证读，作为明确 clear 完成标记。计数是事务数，不能当 CPU 周期。被动 observer 还要求物理 W/X strobe、cache/stream pending、所有 MMIO 响应在首个 source request **之前**排空。

## 生成

```bash
python3 tools/ppa/s3_task_clear_protocol.py \
  --main /absolute/repo/tests/e203/firmware/main.c \
  --main-sha256 <explicit-verified-sha256> \
  --out /absolute/new-s3-clear-recipe
```

输出 `s3_clear_main.c`、`s3_clear_observer.svh`、`clear-recipe.json`。主函数 SHA 不同、非法 include 路径、已存在输出目录均拒绝。原清空 helper 仅复用严格 SHA/path 校验；历史配方与其资格限制保持原样。

新的 campaign 构建时只用 `s3_clear_main.c` 替代原 `main.c`；其他 gcc、架构、ABI、优化／实验宏、accel.c、header、start.S、link.ld 均须冻结并记录完整命令、SHA、ELF、反汇编。现有 `e203_soc.py` 不会自动选择新 main，直接运行它不构成接入证明。

## Observer 接入约定

把生成的声明放在专用 TB module 内；每个复位释放后的观察边沿，在任何 payload observer 之前调用一次：

```systemverilog
// TASKS=1 and fresh reset must be enforced by the campaign and TB.
// Example source range is the frozen benchmark's X/W/bias source range.
s3_observe_task_clear(
  cmd_valid && cmd_read && cmd_addr>=BASE && cmd_addr<BASE+'h18800,
  !`NICE.owner_valid && !`NICE.nice_req_valid &&
    !`NICE.nice_icb_cmd_valid && !`NICE.nice_icb_rsp_valid &&
    !`NICE.nice_rsp_valid && !`NICE.nice_mem_holdup,
  payload_phase);
if (payload_phase) xu_observe_upload();
```

这里的 `cmd_valid` 不能带 `cmd_ready`。首请求的等待时间由 campaign 的原任务计时器实际纳入；helper 不擅自移动计时器。`nice_idle` 必须接真实信号，不能在全 SoC campaign 中常量绑1。wrapper-only probe 因没有 CPU/NICE，单独注入该布尔输入测试 observer 的拒绝分支，不把该 probe 叫 NICE 资格通过。

所有原 payload 数据、mask、地址覆盖、次序、完整计数、FIFO／POP、NICE／OITF／rd、最终 Y response 检查都应保留。只分流 clear 与 payload 的 observer 调用，每个观察边沿仍恰好一次。首个 source request 上验证 clear 完整后，`payload_phase` 当拍为1。

observer 追踪所有 MMIO 接受／响应、响应背压稳定、W/X/legacy/cache 地址覆盖、物理 bias clearDone 与最短768拍、所有清空写的完整mask与零值。`S3_TASK_CLEAR_OBSERVED` 输出独立 clear 周期、最后响应拍、到首请求间隙和完整计数。clear 波形／能量应单独留存；官方未明文要求把 clear 放进 payload 计时，正式接受口径仍待审查。

冻结 main 的 `accel_linear()` 在首次 W source 前还会执行原有 ID／STATUS／capability 检查。最终 STATUS 验证读成功退休后，这些有限白名单的只读预检单独计数；任何参数写、其他寄存器读取、未知／错误响应仍失败。它们不能冒充第二次 clear。`clear_cycles` 结束于最终验证响应，预检至首 source 的间隙另报，不把间隙藏进清空周期。

## 尚未证明的项目

- fresh reset 将 NICE 私有 snapshot 和 MAC 状态复位；应在实际全 SoC 中观察，不能靠 probe 常量代替。
- FIFO 的 payload Reg 没有物理清零，仅 metadata 无效。helper 明示 `fifo_payload_physical_zero=UNPROVEN`，不把它说成已物理清空。
- bias clear 的 probe 使用仓库行为 SRAM，不能代替厂商宏、严格 mapped 或 SRAM 内部功耗覆盖。
- 生成和 wrapper probe 不包含真实 CPU 全任务，也没有正式缓存政策、PPA 或150MHz验收结论。

先保留现有未清空的完整12层开发对照；新资格 campaign 独立测量，不能把不同窗口／配置的最优 T/E/A 拼接。
