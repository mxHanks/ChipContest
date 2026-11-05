## 子仓库配置

如果你**不是**使用以下命令 clone 的本目录：

```shell
git clone --recurse-submodules https://github.com/mxhanks/ChipContest
```

你还**需要**执行以下命令来拉取环境需要的子 module ：

```shell
git submodule update --init --recursive
```

## 修改 E203 怎么提交？

假设你修改了 `accel_icb_slave.v`，需要进行**两次**提交：

先在 E203 仓库内：
```shell
cd ./third-party/e203_hbirdv2

git add .
git commit -m "feat: add accelerator ICB slave"
git push -u origin feature/e203-accelerator
```

再回到主仓库：
``` shell
cd 主仓库目录

git add third-party/e203_hbirdv2
git commit -m "chore: update E203 submodule"
git push
```

顺序**不能反过来**：先确保 E203 的 Commit 已经推送到 Fork，再提交和推送主仓库的子模块引用。
否则队友可能在克隆时遇到找不到 E203 提交的问题。

## E203 加速器寄存器访问测试

本节记录当前 E203 集成版本的仿真流程，以及加速器寄存器访问专项测试。

### 1. 安装 RTL 并运行基础测试

在项目根目录执行：

```bash
cd third-party/e203_hbirdv2/vsim

# 清理旧的仿真安装目录
make clean

# 将最新的 RTL 安装到仿真目录
make install

# 编译并运行默认的 RISC-V 基础测试
make run_test DUMPWAVE=0
```

预期结果：日志中出现 `TEST_PASS`。

注意：修改 E203 RTL 后，需要重新执行 `make clean` 和 `make install`，避免仿真使用旧的 RTL 副本。

### 2. 安装并检查 RISC-V 工具链

本测试使用 Ubuntu 提供的 RISC-V 裸机交叉编译工具链。

检查工具是否已经安装：

```bash
command -v riscv64-unknown-elf-gcc
command -v riscv64-unknown-elf-objcopy
command -v riscv64-unknown-elf-objdump
```

如果没有安装，可执行：

```bash
sudo apt update
sudo apt install -y gcc-riscv64-unknown-elf binutils-riscv64-unknown-elf
```

### 3. 创建加速器寄存器测试程序

在项目根目录创建 `tests/e203/accel_mmio.S`：

```bash
mkdir -p tests/e203 build/e203

cat > tests/e203/accel_mmio.S <<'EOF'
.section .text.init
.globl _start
.option rvc

_start:
    # Test 1: read accelerator ID at 0x10042000.
    li   t0, 0x10042000
    lw   t1, 0(t0)
    li   t2, 0xACCE2030
    bne  t1, t2, fail_id

    # Test 2: write and read back scratch register at 0x10042004.
    li   t3, 0x12345678
    sw   t3, 4(t0)
    lw   t4, 4(t0)
    bne  t4, t3, fail_scratch

    # Both checks passed.
    li   gp, 1
    j    write_tohost

fail_id:
    li   gp, 2
    j    write_tohost

fail_scratch:
    li   gp, 3
    j    write_tohost

    # tb_top.v monitors PC == 0x80000086.
    .org 0x86
write_tohost:
    j    write_tohost
EOF
```

该测试检查以下行为：

| 地址 | 操作 | 预期结果 |
|---|---|---|
| `0x10042000` | 读取加速器 ID | `0xACCE2030` |
| `0x10042004` | 写入 `0x12345678` 后再读取 | 读回值为 `0x12345678` |

测试结果通过 `gp`（即 `x3`）区分：

- `x3 = 1`：两项检查均通过。
- `x3 = 2`：加速器 ID 检查失败。
- `x3 = 3`：scratch 寄存器读写检查失败。

本程序针对当前仿真测试平台的结束地址 `0x80000086` 编写。如果修改了 `tb_top.v` 中的结束地址，需要同步调整测试程序。

### 4. 编译测试程序并生成仿真镜像

在项目根目录执行：

```bash
RISCV_TESTS="$PWD/third-party/e203_hbirdv2/riscv-tools/riscv-tests"

riscv64-unknown-elf-gcc \
  -march=rv32imac_zicsr_zifencei \
  -mabi=ilp32 \
  -nostdlib -nostartfiles -static -mcmodel=medany \
  -Wl,--no-relax \
  -T "$RISCV_TESTS/env/p/link.ld" \
  tests/e203/accel_mmio.S \
  -o build/e203/accel_mmio

# 生成反汇编文件，便于检查指令地址
riscv64-unknown-elf-objdump \
  --disassemble-all build/e203/accel_mmio \
  > build/e203/accel_mmio.dump

# 生成 Verilog 十六进制格式的程序镜像
riscv64-unknown-elf-objcopy \
  -O verilog build/e203/accel_mmio \
  build/e203/accel_mmio.verilog

# 沿用现有 E203 测试框架的镜像地址转换方式
sed -i 's/@800/@000/g' build/e203/accel_mmio.verilog
```

检查结束地址是否正确：

```bash
grep -A3 'write_tohost' build/e203/accel_mmio.dump
```

应确认测试结束循环位于 `0x80000086`。

### 5. 运行加速器专项测试

进入仿真目录：

```bash
cd third-party/e203_hbirdv2/vsim

make run_test \
  TESTCASE="$(realpath ../../../build/e203/accel_mmio)" \
  DUMPWAVE=0
```

注意：`TESTCASE` 不需要包含 `.verilog` 后缀，测试平台会自动追加该后缀。

预期结果：

```text
~~~~~~~~~~~~~~~~ TEST_PASS ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
```

如果出现 `TEST_FAIL`，查看日志中的 `final x3 Reg value`：

| x3 | 含义 |
|---:|---|
| 1 | ID 和 scratch 寄存器检查均通过 |
| 2 | ID 检查失败 |
| 3 | scratch 寄存器读写检查失败 |



## E203 加速器计算回归测试

### 测试覆盖范围

| 测试程序 | 验证内容 | 预期结果 |
|---|---|---|
| `accel_compute.S` | 单组 8 路点积计算，X 和权重均为 1，偏置为通道编号 | 第 j 路结果为 `64 + j` |
| `accel_multigroup.S` | 依次运行 group 0 和 group 1，验证权重组选择 | group 0 为 `64 + j`，group 1 为 `128 + j` |
| `accel_repeat_x.S` | 同一组权重连续执行两次，第二次将输入从 1 改为 2 | 第一次为 `64 + j`，第二次为 `128 + j` |

其中，`accel_repeat_x.S` 还检查输入缓冲区重载和重复启动后的累加状态重置。

### 1. 编译测试程序

在项目根目录执行：

```bash
set -e
mkdir -p build/e203
RISCV_TESTS="$PWD/third-party/e203_hbirdv2/riscv-tools/riscv-tests"

for name in accel_compute accel_multigroup accel_repeat_x; do
    riscv64-unknown-elf-gcc \
      -march=rv32imac_zicsr_zifencei \
      -mabi=ilp32 \
      -nostdlib -nostartfiles -static -mcmodel=medany \
      -Wl,--no-relax \
      -T "$RISCV_TESTS/env/p/link.ld" \
      "tests/e203/${name}.S" \
      -o "build/e203/${name}"

    riscv64-unknown-elf-objdump \
      --disassemble-all "build/e203/${name}" \
      > "build/e203/${name}.dump"

    riscv64-unknown-elf-objcopy \
      -O verilog "build/e203/${name}" \
      "build/e203/${name}.verilog"

    sed -i 's/@800/@000/g' "build/e203/${name}.verilog"
done
```

### 2. 运行测试

```bash
cd third-party/e203_hbirdv2/vsim

for name in accel_compute accel_multigroup accel_repeat_x; do
    echo "========== Running ${name} =========="
    make run_test \
      TESTCASE="$(realpath "../../../build/e203/${name}")" \
      DUMPWAVE=0
done
```

每项测试都应出现 `TEST_PASS`。如果修改了 E203 RTL，应先执行
`make clean` 和 `make install`，再运行测试，避免使用旧的 RTL 副本。

## xu 完整矩阵与写回回归

在本分支 `feature/e203-xu-integration`，先按前文初始化子模块和工具。完整矩阵默认使用 Verilator 的 `--binary --timing`（以及 g++）；原 ADD 和四项汇编回归仍使用 Icarus Verilog 12。Python 入口只依赖标准库。

```bash
git submodule update --init --recursive
python3 tools/scripts/e203_soc.py --mode doctor
python3 -m unittest discover -s tests/e203 -p test_runner.py
python3 tools/scripts/e203_soc.py --mode baseline
python3 tools/scripts/e203_soc.py --mode synthetic --tasks 1
python3 tools/scripts/e203_soc.py --mode real --tasks 12
```

运行器自动执行 `make clean`、`make install`。每次输出到新的 `build/e203/<时间>/`，保留原始日志和 `result.json`；也可用 `--out` 指定不存在的目录。进程退出码和完成标志都被检查，坏向量、超时和不匹配均失败。`--mode real --tasks 12` 的预期终止标志为：

```text
SOC_PASS tasks=12 outputs=304128 writes=608256
```

每层由 CPU 从共享存储读取输入/权重/偏置、经现有 MMIO 启动 3168 次八路计算，并完整写回 25344 个 signed48 结果。结果显式符号扩展为 signed64，检查器核对全部 50688 次字写及最后写响应后才接受层 ACK。层间不复位，下一层必须重新装载参数。

真实夹具来自仓库已归档 KWT 静音导出，来源和 SHA 保留在 `tests/e203/vectors/`。它证明所选输入上的整数功能联调，不证明官方600样本精度或十二层编码器推理。A 提供其他相同格式数据时使用：

```bash
python3 tools/scripts/e203_soc.py --mode vectors --vectors /实际数据目录 --tasks 12
```

每个 `layer_XX/` 包含定长十六进制补码 `x.mem`、`w.mem`、`bias.mem`、`y.mem`。详细布局、共享存储映射、时钟/计时范围、`--waves`、四态选项及官方服务器接入顺序见 [xu 集成说明](docs/e203-integration.md)。开发平台的输入预装载不计入当前测量，不能将其周期直接当比赛正式吞吐量。

Chisel 完整回归仍按 README 执行 `scala-cli test .`；已有系统 JDK 时可增加 `--server=false --jvm system`。项目 Scala/Chisel/ScalaTest 版本保持不变。

## 服务器接手验收

在接续分支 `feature/e203-xu-server-prep` 中，可用一个入口顺序执行上述开发验收并保留统一报告：

```bash
python3 tools/scripts/server_accept.py
python3 tools/scripts/server_accept.py --full
```

向量交付后可先独立检查整数参考：`python3 tools/scripts/e203_soc.py --mode check-vectors --tasks 12 --vectors /数据目录`。省略 `--vectors` 使用内置真实夹具。此检查不依赖仿真器或交叉编译器，不代表浮点精度验收。

doctor 还会实际构建 RV32 固件并检查子模块提交；缺失子模块须按本页开头初始化。离线 Git bundle、工具链、Scala缓存及官方平台检查表见 [服务器交接说明](docs/server-handoff.md)。
