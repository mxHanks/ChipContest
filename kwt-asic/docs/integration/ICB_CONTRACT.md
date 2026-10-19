# KWT ICB 融合接口 v1

状态：本项目新增 adapter 的实现契约；E203 Fork 的原始 o15 仍需由融合入口打补丁连接。默认基址 `0x10042000`、4 KiB、32-bit 数据、4-bit byte mask、单 outstanding、单时钟/复位域。固定点协议仍为 `fixed16_acc48_v1`，MAC 核心为 `kwt_linear_engine_rowpair(PIPE_MUL=1, RESULT_BUFFERS=2)`。

RTL：`soc/kwt_icb_slave.sv`。软件常量：`soc/include/kwt_accel_regs.h`。适配器测试：`sim/tb_kwt_icb_slave.sv`。新增文件不修改团队 Fork 的原始 RTL。

## 寄存器

全部地址须 4 字节对齐。写操作必须 `wmask=4'hf`；部分写、未定义偏移、方向错误及不合法状态均返回 `rsp_err=1,rdata=0`，并设置协议错误诊断，不触发计算、提交 payload 或 pop 输出。读请求的 wmask 无语义，忽略。

| 偏移 | 名称 | 权限 | 行为 |
|---|---|---|---|
| `0x000` | ID | R | `0x4b575431`（KWT1） |
| `0x004` | STATUS | R | 位定义见下 |
| `0x008` | CONTROL | W | 精确写 `1`=START、`2`=WRITEBACK_ACK、`4`=ABORT_RESET；不能 OR 多个动作 |
| `0x00c` | ERROR | R | `[7:0]` 最近一次协议错误码；`[16]` 核心 error |
| `0x010` | CORE_CYCLES | R | 核心 start 接受后到最终输出被 adapter/CPU 接受，含输出背压；32-bit 饱和 |
| `0x014` | OUTPUT_COUNT | R | 已完成 HI 响应握手的输出个数，范围 0–25344 |
| `0x018` | WINDOW_CYCLES | R | 首次有效 staging 写被接受至 WRITEBACK_ACK 响应被 CPU 接受的本地窗口，32-bit 饱和 |
| `0x020` | LOAD_KIND | R/W | `0`=X、`1`=W、`2`=Bias |
| `0x024` | LOAD_ADDR | R/W | 14-bit 元素地址；每次成功 COMMIT 自增 |
| `0x028` | LOAD_DATA_LO | R/W | X/W 原始 int16 放低 16 位，写入的高 16 位必须为零；Bias 原始低 32 位 |
| `0x02c` | LOAD_DATA_HI | R/W | Bias 原始 40-bit 的 `[39:32]` 放低 8 位，写入高 24 位必须为零 |
| `0x030` | LOAD_COMMIT | W | 精确写 `1`，原子提交一个完整元素 |
| `0x040` | Y_LO | R | 首次读锁存 48-bit 当前输出及 index/last，返回低 32 位；重复读同一快照 |
| `0x044` | Y_HI | R | 必须先读 LO，返回快照高 16 位，响应完成握手时才 pop 一次 |
| `0x048` | Y_INDEX | R | `[14:0]` 元素索引，`[31]` last；优先返回已锁存快照，否则当前有效输出；均无效时返回零 |

STATUS：

| bit | 意义 |
|---|---|
| 0 | 核心 busy |
| 1 | 可以写 staging/提交输入；包括软件交接状态约束 |
| 2 | 可以 START；要求全部 6336 X、16384 W、256 Bias 已按各自顺序重新装载 |
| 3 | 核心当前输出有效 |
| 4 | LO 快照已锁存，等待 HI 消费 |
| 5 | CORE_DONE sticky：核心全部输出已经通过 HI 响应交给 CPU |
| 6 | SOFTWARE_DONE：软件 WRITEBACK_ACK 的响应已完成 |
| 7 | 核心 error |
| 8 | 协议错误 sticky；仅复位/ABORT_RESET 清除，不阻止后续合法访问 |
| 9 | 已接受当前任务的 START |
| 10 | 本地窗口计数仍在进行 |

## 装载与任务新鲜度

X、W 均按模型定义的行优先次序编码；Bias 按列索引。每种 tensor 必须从地址 0 起顺序提交，没有复用上一任务权重的隐含路径。可在不同 KIND 之间切换，但每一 KIND 的计数必须继续符合自身下一地址。

软件对每个 tensor 先设置 KIND 和 ADDR=0，然后逐元素写 LO（Bias 还需 HI）与 COMMIT。COMMIT 成功使 ADDR 自增，并清除 LO/HI 的 payload-valid，所以不能重复提交同一组旧数据。KIND/ADDR 本身保留，可减少装载操作数量。

X/W 的负数以原始 `uint16_t` 位图写入，不能用 sign-extended 32-bit 值。例如 int16 -1 应写 `0x0000ffff`。Bias -1 应写 LO=`0xffffffff`、HI=`0x000000ff`。引擎内部接收原始 signed40，不进行浮点缩放。

START 仅在核心 start_ready 且上一任务交接完成时接受；接受后清除 staging validity。忙时 staging 写/COMMIT、重复 start、缺失/乱序/越界 payload 返回错误。最终 HI 消费会清除引擎与 adapter 的输入新鲜度计数。下一任务必须等待上一任务 SOFTWARE_DONE，然后首次合法 staging 写会清除旧 done/count 标志并开始新本地窗口。

## 输出原子性与响应背压

1. 软件等待 Y_VALID，读 Y_LO。该命令锁存完整 48-bit 值和 index/last；该响应被背压时值/错误位保持。
2. 可以读 Y_INDEX 或重复读 LO；核心 out_ready 仍保持 0。
3. 读 Y_HI 后，其 ICB 响应保持至 `rsp_valid && rsp_ready`；只有这个握手才产生一个核心 out_ready、OUTPUT_COUNT+1 和快照 invalid。
4. 尚未完成 HI 响应时，不会接受另一个命令。这保证 final 输出不会在 CPU 真正获得高字前消失。

响应至少使用一个寄存器周期；`cmd_ready = !rsp_valid`（且不在复位中），不同时退休旧响应并接受新命令。当前设计优先保证可审计握手；后续减少总线开销时必须保持相同的软件可见原子性。

无效 HI 读会产生 OUTPUT_ORDER 错误，且不消费数据。输出 48-bit 从 HI 的低 16 位和 LO 拼接后，由软件明确符号扩展到 64-bit；HI 返回寄存器高 16 位为零。

## 完成、外存写回和计时范围

CORE_DONE 沿用核心现有定义：全部 Y 已交付给 CPU，而非仅 MAC 已算完；它不能证明 CPU 已把结果写入共享存储器。

软件必须在获得全部 25344 个输出、完成所有外部存储写响应后，再写 CONTROL=WRITEBACK_ACK。adapter 检查输出计数、核心完成/非 busy、无半个输出快照；该控制响应被 CPU 接收时设置 SOFTWARE_DONE。本 adapter 只有 ICB 从设备端口，无法独立观察外部存储写响应，实际 SoC TB 必须监视共享存储器总线并交叉检查这一软件承诺。

WINDOW_CYCLES 从第一条有效 staging 写命令的接受边沿计到 WRITEBACK_ACK 响应接受边沿的时钟间隔。该计数包括 staging、CPU 调度、核心等待和输出/写回期间经过的时钟，但不覆盖第一条 staging 命令之前的 CPU 启动/准备。比赛完整窗口需要在 SoC TB/正式计时点另外测量，不能用此局部计数或 CORE_CYCLES 代替。多层任务需分别记录并按正式规则计入层间调度与全部写回。

## 复位和错误

外部 rst_n 清除请求/响应有效位、所有输入新鲜度、输出快照、计数和 done/error。SRAM 内容无需清零，只有重新完整装载后才允许 START。

CONTROL=4 可在 busy 时中止任务。adapter 产生一次核心复位脉冲，同时清除 staging/快照有效位、计数、done 和协议错误；该控制自身仍返回一个正常响应。软件必须把中止前任务视为未完成。

ERROR[7:0] 码：0=NONE、1=ADDRESS、2=ACCESS、3=MASK、4=VALUE、5=STATE、6=LOAD_RANGE、7=LOAD_SEQUENCE、8=LOAD_INCOMPLETE、9=OUTPUT_EMPTY、10=OUTPUT_ORDER、11=WRITEBACK。多个错误时记录最近一次；具体拒绝优先级以 RTL 中地址→写掩码→寄存器/状态校验顺序为准。

## 验证边界

`sim/tb_kwt_icb_slave.sv` 使用真实 row-pair RTL，装载完整 X/W 零输入与有符号 Bias，检查四个真实输出、非法访问无核心装载副作用、Bias 半字提交、自动地址、LO 重读、HI 响应背压下不 pop、忙时拒绝、abort 和外部复位。该短回归只证明这些协议/算术场景，不替代完整随机/真实模型矩阵、CPU 程序、12 层或正式工艺 PPA。

命令：

```bash
source env/activate.sh
iverilog -g2012 -s tb_kwt_icb_slave -o /tmp/kwt-icb.vvp \
  soc/kwt_icb_slave.sv src/rtl/kwt_linear_engine_rowpair.sv sim/tb_kwt_icb_slave.sv
vvp /tmp/kwt-icb.vvp
```

必须同时检查编译/仿真退出码为 0，日志含 `ICB_ADAPTER_PASS` 且没有 FATAL/ERROR/超时；运行器另外绑定源码 SHA256。
