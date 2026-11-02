# xu S2a 标量装载流候选

独立候选基于主仓 `74e011813dbf215327e59016d34136a36e87ba05`、E203 `f49a5fc914971426bd4530db39e270a84b41139f`，父子分支均为 `codex/xu-s2a-stream`。仅实现 W/X 标量自动索引，不包含 packed2、DMA、自动 group、双缓冲或 PE 改造。8 PE、signed16 X/W、signed40 bias、signed48 Y、共享存储槽与数值夹具保持原定义。S0 资格及正式同配置 (T,E,A) 仍待完成，本候选没有保留/得分或服务器 PPA 结论。

## 可选接口

旧寄存器和 `CAPABILITY@0x050=0x58550003` 保持原值及检查；旧 firmware schedule/experiment 的编译 define 不增加任何流开关。初始提案曾考虑扩大原 CAP 的 bit 集，本实现为兼容旧固件严格相等检查，改用独立 `STREAM_CAPABILITY`。只有新地址触发流行为，没有隐式全局模式。

| 偏移 | 名称 | 语义 |
| --- | --- | --- |
| `0x054` | W_CURSOR | RW，原始 W row-major 元素序号 0..16384，终点不回卷 |
| `0x058` | W_STREAM16 | WO，低 16 位写当前元素，提交后游标加 1；读 0 |
| `0x060` | X_CURSOR | RW，当前行元素序号 0..64，终点不回卷 |
| `0x064` | X_STREAM16 | WO，低 16 位写当前行元素，提交后游标加 1；读 0 |
| `0x06c` | STREAM_STATUS | bit0=pending、bit1=sticky error；其他读 0。bit1 W1C，只由 mask[0] 控制 |
| `0x070` | STREAM_CAPABILITY | RO `0x58530003`：高 16 位签名，bit0=W_STREAM16、bit1=X_STREAM16 |

W 游标 `s=k*256+c` 解码为 `bank=s[2:0]`、`addr={s[7:3],s[13:8]}`，对应原布局 `bank[c%8][(c/8)*64+k]`。CPU 顺序读原有 W 32 位槽；X/W 高 16 位被硬件截断，符号位仍为 bit15。旧 X_ADDR/W_BANK/W_ADDR、最近数据寄存器独立，流写不修改它们。

新 CURSOR/DATA 写必须 `cmd_wmask=1111` 且 busy=0；cursor 全 32 位值必须在表中区间内，DATA 必须还有至少一个元素。非法 mask、忙时写、越界或终点继续写：响应 `rsp_err=1`、置 sticky error，不修改游标或存储。旧地址保留各自原有 mask/启动/W1C 语义，旧响应错误仍为 0。未实现的 packed 地址不增加任何 capability。

接受 DATA 命令时捕获其数据、物理 bank/addr，置 pending 并撤销命令 ready；下一时钟边沿由真实 core 写口提交一次，然后推进游标并产生响应。响应有效之前内部写已经生效，`rsp_valid/rsp_rdata/rsp_err` 在背压时一起保持，不重复装载。最后一个写响应退休同拍可接受 START，pending 期间不能接受 START；忙时旧 START 仍忽略。没有修改 Chisel 或 SRAM 端口/容量。

## 固件及事务契约

新 schedule 为 `bias-hw-stream16-window`，沿用 H1 bias 上传及 H2 固定结果窗口，可结合现有优化/展开实验。新固件同时严格检查旧 CAP 和新 STREAM_CAP，缺流接口返回 -5。旧默认 schedule、数值格式、夹具和命令参数保持原定义。

W 首元素共享读先发生，再写 W_CURSOR=0，随后流上传全部 16,384 个 W；每行 X_CURSOR=0 并上传 64 元素。全部初始化、共享读取、内部提交、轮询及写回都留在原首共享读至末 Y 写响应退休窗口。每任务重新完整装载 W/X/bias，不跨任务复用。

| 窗口内每任务工作 | 旧 H1+H2 | S2a |
| --- | ---: | ---: |
| W MMIO 写 | 32,774 | 16,385 |
| X MMIO 写 | 12,672 | 6,435 |
| bias MMIO 写（含模式） | 770 | 770 |
| GROUP/W1C/START 写 | 9,504 | 9,504 |
| MMIO 总写 | 55,720 | 33,094 |
| 共享读 / Y 写 | 23,232 / 50,688 | 相同 |
| START / done / MAC 有效拍 | 3,168 / 3,168 / 202,752 | 相同 |

旧 W 完整循环有 32,776 写，其中首 BANK/ADDR 两写在窗口外；新 W_CURSOR 明确在窗口内。因此窗口 MMIO 写减少 22,626 次，不能用完整循环差值替代。TB 新地址分类仍按实际接受命令开始阶段，以最终 stream 响应退休结束 W/X 阶段；所有阶段之和必须等于完整窗口。MMIO 轮询读次数继续实测，不固定成历史编译器结果。

## 本地验证与复现

直接接口 TB 使用实际 Chisel core/SRAM RTL，在真正写口采样边沿检查每次写；独立 row/column 模型遍历全部 16,384 个 W 位置、64 个 X、全部 32 个 group 的 signed48 计算，覆盖终点、符号极值、旧/新指针独立、所有非法 mask、busy/越界错误、响应背压、接受与退休平衡和最后写后 START 顺序。原 cached-wrapper 用例继续检查旧模式、mask、结果窗口和背压。

```bash
python3 -m unittest discover -s tests/e203 -p 'test_*.py' -v
python3 -m unittest discover -s tests/numeric -v
python3 tools/scripts/e203_soc.py --mode baseline --sim iverilog --out build/xu-s2a-baseline
python3 tools/scripts/e203_soc.py --mode real --tasks 1 --sim verilator \
  --firmware-schedule bias-hw-stream16-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks --out build/xu-s2a-real1
```

输出目录必须尚不存在；本机 GCC 版本及本地行为存储背压下的周期单列，不能与服务器 GCC 10.2/VCS 周期混比。最终验证记录保存在本候选的 `docs/validation/xu-s2a-stream-20261102/`，包括实际运行源/ELF/向量/日志哈希、事务和明确测量边界。
