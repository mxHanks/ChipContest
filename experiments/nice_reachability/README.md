# P0 NICE 真实 LSU 可达性探针

状态：**r1 已在 Linux 成功编译，pressure0 在第三个命令被接受前触发 NICE command hold 断言；没有可达性 PASS 结论。** 当前只增加现场日志，尚未重新运行；此目录不会修改完整 12 任务所用的固件、RTL、runner 或 TB。

依据：[只读调查与错误接口说明](../../../reports/s3-y32-development/NICE_REACHABILITY.md)。现有 demo 每条 lbuf/sbuf 只传输 **3 个连续 32 位字**，本探针不扩展指令、不实现 drain8，不测试错误 trap。

## 固件与严格通过条件

`main.c` 使用实际 demo 编码：lbuf `.insn r 0x7b,2,1,x0,rs1,x0`，sbuf `.insn r 0x7b,2,2,x0,rs1,x0`。若 rs1 固定为 a0，两者机器字分别是 `0x0205207b`、`0x0405207b`。内联汇编由编译器分配 rs1；funct3=010 的 rs/rd flags 与现有 RTL 一致。每条指令后有 fence，等待 OITF 排空再继续。

源输入是 `[3,0x0000a55a,5]`。固件自己初始化源、将两个输出区域逐字写为 `0xdeadbeef`；TB 初始 RAM 也全为 poison，不预置任何输出。源、输出以及真实 MMIO 地址互不重叠。

| NICE 指令序号 | 实际操作 | 3 字起始地址 |
| --- | --- | --- |
| 0 | lbuf 共享输入 | `0xa0040000` |
| 1 | sbuf 共享输出 0 | `0xa0040040` |
| 2 | sbuf 真实 MMIO | `0x10042014` |
| 3 | lbuf 真实 MMIO | `0x10042014` |
| 4 | sbuf 共享输出 1 | `0xa0040080` |

三个 MMIO 寄存器是 idle 时合法的 X_ADDR、X_DATA、W_BANK，写值恰在 6/16/3 位范围内。X_DATA 会初始化一项真实 X 行缓存；没有 CTRL、STATUS、ROW_CTRL 或 POP 写。固件先检查 ID 与空闲状态，再逐字验证输出 0、MMIO CPU 回读、输出 1；任一不符返回失败码，全部通过才返回 1。

`tb_nice_reachability.sv` 实例化真实 `e203_soc_top(EXTERNAL_SYSMEM=1)`，沿用现有 SoC TB 的 ITCM 镜像装载和 pad 配置。外部 RAM 只是 SoC sysmem 从设备；没有替换 NICE、LSU、core 或 MMIO wrapper，也没有 force 内部信号。监视器必须同时核对：

- 5 次实际 NICE instruction request、5 次 completion，正确 opcode/funct3/funct7/rd/rs2 和 rs1 地址。
- 15 个实际 NICE ICB 命令及响应；每条指令恰好 3 笔，地址、读写、32 位 size、写值准确。每笔接受命令必须在同拍真实 LSU 仲裁输出出现，写 mask 为 `4'hf`。
- 同一事务到达真实 MMIO/外部 RAM 端点并收回成功响应，NICE 接收的读值逐字准确。NICE 来源计数严格为 RAM 读 3/写 6、MMIO 读 3/写 3；CPU 初始化与校验不混入。
- 两个输出每字只由一次 NICE 写入，从 poison 更新为预期值；观察 CPU 逐字校验读取，以及三个 MMIO CPU 回读。CPU 不能在 NICE 开始后补写输出冒充搬运。
- 各命令/响应及 NICE 指令接口遇到 valid&&!ready 时，valid 和 payload 保持稳定。所有接受/退休请求守恒，当前真实 LSU 最多一个未完成请求；没有遗留响应。
- EXU `alu_cmt_i_valid && alu_cmt_i_ready` 在 `PC=0x80000086` 真正握手，gp=1，全部覆盖及计数通过后才打印唯一 `NICE_REACHABILITY_PASS`。watchdog、CPU trap 或任一偏离立即 fatal。

`+BACKPRESSURE=1` 对每个外部 RAM 命令固定等待两拍，并将响应按事务序号延迟 1…7 拍；0 模式仍使用注册响应，禁止零周期返回。压力模式必须观测到 **NICE 来源**的 RAM 命令等待、RAM 响应延迟以及 NICE LSU 命令等待，否则不能通过。所有响应 valid 后被阻塞时的稳定性均有断言，但真实接收端可能一直 ready；最终标记分别报告实际 hold 拍数，不将 0 拍说成已覆盖。

## 在 Linux 新目录编译与运行

以下命令在 **S3-Y32 仓库根目录**运行。先将 `RV_PREFIX` 设为本轮完整 12 任务实际使用的交叉工具前缀；不要另换编译器。`build/nice-reachability-p0` 必须是新目录。需要完整 12 任务所用的冻结 `vsim/install/rtl` 已存在；这里**不执行 make clean/install，也不覆盖现有 simulator cache**。

```bash
: "${RV_PREFIX:?Set the exact frozen RISC-V tool prefix}"
export NICE_PROBE_ROOT="$PWD"
export NICE_PROBE_OUT="$PWD/build/nice-reachability-p0"
mkdir "$NICE_PROBE_OUT"
"${RV_PREFIX}gcc" -march=rv32imac_zicsr2p0_zifencei2p0 -mabi=ilp32 -O2 \
  -ffreestanding -fno-builtin -msmall-data-limit=0 -nostdlib -nostartfiles \
  -static -mcmodel=medany -Wl,--no-relax -Wl,--build-id=none \
  -T tests/e203/firmware/link.ld tests/e203/firmware/start.S \
  experiments/nice_reachability/main.c -o "$NICE_PROBE_OUT/probe"
"${RV_PREFIX}objcopy" -O verilog "$NICE_PROBE_OUT/probe" "$NICE_PROBE_OUT/probe.verilog"
"${RV_PREFIX}objdump" --disassemble-all "$NICE_PROBE_OUT/probe" > "$NICE_PROBE_OUT/firmware.dump"
python3 - <<'PY'
import os
from pathlib import Path
root = Path(os.environ['NICE_PROBE_ROOT'])
out = Path(os.environ['NICE_PROBE_OUT'])
image = out/'probe.verilog'
image.write_text(image.read_text().replace('@800', '@000'))
installed = root/'third-party/e203_hbirdv2/vsim/install/rtl'
sources = sorted(p for p in installed.rglob('*') if p.suffix in ('.v', '.sv'))
if not sources:
    raise SystemExit('frozen installed RTL is missing; do not rebuild over an active run')
sources.append(root/'experiments/nice_reachability/tb_nice_reachability.sv')
(out/'rtl.f').write_text(''.join(str(p)+'\n' for p in sources))
PY
verilator --binary --timing -CFLAGS -std=gnu++20 -j 2 -Wno-fatal --top-module tb_nice_reachability \
  -Mdir "$NICE_PROBE_OUT/obj" -o nice_reachability -DDISABLE_SV_ASSERTION=1 \
  -Ithird-party/e203_hbirdv2/vsim/install/rtl/core \
  -Ithird-party/e203_hbirdv2/vsim/install/rtl/perips \
  -Ithird-party/e203_hbirdv2/vsim/install/rtl/perips/apb_i2c \
  -f "$NICE_PROBE_OUT/rtl.f" > "$NICE_PROBE_OUT/simulator-build.log" 2>&1
"$NICE_PROBE_OUT/obj/nice_reachability" \
  "+TESTCASE=$NICE_PROBE_OUT/probe" +BACKPRESSURE=0 +MAX_CYCLES=100000 \
  > "$NICE_PROBE_OUT/no-pressure.log" 2>&1
"$NICE_PROBE_OUT/obj/nice_reachability" \
  "+TESTCASE=$NICE_PROBE_OUT/probe" +BACKPRESSURE=1 +MAX_CYCLES=100000 \
  > "$NICE_PROBE_OUT/backpressure.log" 2>&1
```

先检查固件反汇编中两种 `.insn` 的实际 opcode/funct3/funct7 和 fence，以及 `write_tohost=0x80000086`。保留 shell 退出码、完整编译命令、工具版本、固件 ELF/镜像/反汇编、filelist、实际 installed RTL 与三个新文件哈希、两个完整日志。每个日志应包含 15 组 `NICE_BUS_CMD/RSP`、15 组 `NICE_ENDPOINT_CMD/RSP`、5 组 request/completion，且仅一个严格 PASS；任何 fatal、超时、缺项或非零退出均保留为失败。

可选 VCD：单独新建带 `--trace` 的 simulator build，再在其工作目录传 `+DUMPWAVE=1`。VCD 是辅助定位；通过依据仍是精确事务检查和真实 CPU 退休。

## 尚未证明的项目

此探针只关闭正常三字 demo 的真实访问性问题，不能声明 NICE drain8 已实现、错误协议已通过、减少了周期或符合 PPA。demo 在最后 ICB 响应后退出状态，不等待 NICE completion 被 core 接收；如果真实 core 恰好不 ready，稳定性断言会揭示丢失响应，不能修改冻结 core 或删除断言绕过。

后续 drain8 必须稳定返回 `err=1` 和非零 `rdat` 错误码，固件显式检查码并让整任务失败，不能依赖 trap。真正的总线错误注入、错误码写到 rd/OITF 退休、失败后没有额外结果写或后续 POP，要在新的 drain8 实现上另测；当前探针没有声称覆盖这些行为。

## r1 失败诊断

真实证据：[nice-probe-r1.session.log](../../../reports/s3-y32-development/nice-probe-r1.session.log)。首条 lbuf 的前两次 RAM 读取及响应均成功，第三个命令尚未被接受即触发 `NICE memory command changed under backpressure`。原失败保留；当前未修改 RTL、断言判定、测试程序或事务要求。

待证伪假设按优先级排列：

1. demo 用 `lbuf_cnt_r < clonum` 这个响应计数条件生成 command valid；若第三个命令仍在等待，第二个响应使计数 1→2，便提前撤销 valid。预测失败时上次 valid=1/ready=0、地址为 SRC+8，当前 valid=0、lbuf_cnt=2，命令/响应总数均为 2。
2. posedge 监视器采到了前后 NBA 混合值。预测现场字段与真实同拍握手或独立相位采样不一致；如上一/当前现场完整吻合 demo 的计数/valid 方程，则该假设被削弱。
3. valid/address/read/size 均稳定，只有读命令无关的 wdata 改变。预测失败 dump 只在 data 字段有差异；此时先确认监视器的有效字段定义，再决定是否修监视器，不能先删断言。
4. r1 实际编译的 TB/demo/LSU/config 与本地副本不同。预测实际源码哈希或展开配置不匹配；应保留 r1 服务器源码身份后再同步新 TB。

当前 r3 instrumentation 使用固定前缀 `[DEBUG-NICE]`：仅在 NICE 总线响应握手和 hold 断言失败现场打印。失败 dump 列上一/当前完整命令字段及当前 TB 总/单指令命令与响应计数；响应日志的 `responses_before` 是本拍退休前计数。previous payload 沿用 r1 已有的 hold 快照。r3 不增加 saved 寄存器，也不读取 demo 内部 state/lbuf_cnt/maddr，只读 r1 已引用的 NICE 接口。

r2 加内部层次日志后在 Linux 编译成功，但程序启动即 SIGSEGV，GDB 指向 `Verilated::catName` 下的 AXI buffer/`__Syms` 构造器，尚未执行 TB 日志；它不是第二份 RTL 协议失败证据。r1 同环境仍复现原断言。r1/r2 原件保留；r3 仅缩小 instrumentation 的引用范围，根因仍待同一真实测试确认。

用同一原始测试、相同固件和 pressure0 运行获取现场，先区分真实撤 valid 与监视器误报。若证实 demo 错误，保留失败，后续新增独立 drain8 状态机并保留原 demo，不靠弱化协议断言宣布本探针通过。后续 cleanup 在结论和证据冻结后移除 `[DEBUG-NICE]` 临时日志。
