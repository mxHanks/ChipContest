# S3-Y32 NICE read-pop 接口

本候选在配套 NICE 与加速器 wrapper 内减少一次总线事务，保持固件指令 ABI 和 Y32 数值不变。**两处 RTL 必须配套升级**：`rtl/e203/subsys/xu_nice_drain8.v` 与 `rtl/e203/perips/accel_icb_slave.v` 均位于 E203 子模块。

## 访问语义

| 相对 `0x10042000` 的偏移 | 语义 |
|---|---|
| `0x180…0x19c`，4 字节对齐 | 原有 8 lane Y32 只读快照，不 POP；保持原语义 |
| `0x1a0` | 新增 lane7 Y32 快照，并将一次 POP 附到这笔读响应的退休 |
| `0x0c8` | 原有显式 POP；保持原语义，仍可用于旧 CPU/MMIO 路径 |

新别名须为对齐读，且 `row_active && row_valid`、没有旧 POP 正在退休。写、未对齐访问、空 FIFO 或非活动行返回错误，不附 POP。它不带硬件来源鉴别位：任何主设备访问都会获得相同语义，调用者必须先收齐当前组其他 lane。

数据在命令接受时进入响应槽；响应被阻塞时，数据、valid、错误和 POP 描述符保持不变，FIFO 头仍被占有。成功响应在 **wrapper 端点**退休时只执行一次 POP。经过互连后，NICE 可以稍晚才收到 lane7 响应；此时数据已在响应通路中锁存，不再读取已释放的 FIFO 头。

NICE 按以下顺序执行：状态读（允许有界重复）→ lane0…6 普通读 → lane7 别名读 → 8 笔 Y 写 → completion。最少事务从 18 减为 17；始终最多一笔在途。每次响应错误均返回原 `ERR_BUS` 并停止后续命令；POP 已执行时也必须中止整任务，不能重试部分 drain。最后 Y 写响应被 NICE 接收后才能给出 completion，completion 保持到 CPU 接收。

原 custom3/funct3=7/funct7=0x20 编码、rs1 目的地址、rs2 组号/轮询上限、成功值和错误码保持不变。轮询上限仍按已退休状态响应计数。原 Y32 capability 常量保持不变；它不能单独识别 read-pop transport，部署须使用父仓 gitlink 锁定配套 RTL。

## 配置与验证

新硬件使用 `bias-hw-autogroup-y32-packed16-nice-read-pop-window`。旧 `…-nice-window` 保留给旧 18 事务基线；在新 RTL 上混用会被 SoC 顺序观察器拒绝。

两种 schedule 的固件编译宏相同。`+NICE_READ_POP=1` 仅选择测试台/计数契约，不是硬件运行时开关。每层必须有 3,168 次 alias 响应退休、0 次显式 POP 写、3,168 次真实 FIFO POP、25,344 次结果读和 Y 写、3,168 次 NICE 请求/完成/OITF 退休。计时窗口内 MMIO 总写从 15,497 减到 12,329，其余固定工作量不变。

快速回归：

```bash
python3.12 -B -m unittest discover -s tests/numeric -p 'test_s3*.py'
python3.12 -B -m unittest discover -s tests/e203 -p 'test_y32_firmware_contract.py'
python3.12 -B -m unittest discover -s tests/e203 -p 'test_read_pop_wrapper.py'
python3.12 -B -m unittest discover -s tests/e203 -p 'test_y32_wrapper.py'
```

本机完整开发回归（输出目录须不存在，前缀换成实际工具链）：

```bash
python3.12 -E -B tools/ppa/s3_task_campaign.py \
  --repo "$PWD" --out "$PWD/build/read-pop-new" \
  --bias-kind sram \
  --schedule bias-hw-autogroup-y32-packed16-nice-read-pop-window \
  --simulator verilator --cross-prefix /usr/bin/riscv64-unknown-elf- \
  --platform-clocks 150mhz --startup-profile external-reset \
  --layers 0,1,2,3,4,5,6,7,8,9,10,11
```

Verilator 为二态开发证据，启用 `--assert`，不替代 VCS 原厂 SVA 或门级验收。有 VCS 的环境使用默认 historical startup 与 `--platform-assertions`，不使用 `external-reset`（后者只为本机 Verilator 启动差异提供显式外部引脚复位）。详见 [campaign 入口](../tools/ppa/s3_task_campaign.md)、[实验记录](s3-y32-writeback-results.md)。

硬件只有新增地址选择和响应 POP 描述符，Y32 RNE 仍共用原有一条数据通路。面积、关键路径及功耗影响尚未综合实测，须交给整机验收负责人核实。
