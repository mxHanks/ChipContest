## 第一步：安装仿真工具

打开 Ubuntu 终端，执行：

```
sudo apt update
sudo apt install -y git make build-essential iverilog gtkwave
```

这些软件的作用：

| 工具           | 用途                       |
|----------------|----------------------------|
| Icarus Verilog | 模拟 CPU 和 SoC 电路       |
| GTKWave        | 查看数字电路波形           |
| Make           | 根据工程配置执行编译和仿真 |
| Git            | 下载、管理源代码           |

安装后检查：

```sh
iverilog -V | head -n 3
git --version
gtkwave --version
```

E203 官方文档要求使用 Icarus Verilog 12.0 进行仿真。

## 第二步：下载 E203 工程

按照确定的工作区结构，把 E203 放在 `third_party` 目录：

``` sh
mkdir -p ~./ChipContest/third_party

cd ~./ChipContest/third_party

git clone https://github.com/riscv-mcu/e203_hbirdv2.git

cd e203_hbirdv2
```

下载后检查：

``` sh
ls
git rev-parse --short HEAD
```

正常应该能看到 `rtl`、`tb`、`vsim` 和 `riscv-tools` 等目录。

## 第三步：运行第一次 RTL 仿真

进入仿真目录：

```
cd ~./ChipContest/third_party/e203_hbirdv2/vsim
```

按照官方 `vsim/Makefile` 的流程执行：

``` sh
# 清理与准备仿真环境
make clean
make install

# 编译 E203 SoC
make compile SIM=iverilog

# 运行默认 ADD 指令测试
make run_test SIM=iverilog DUMPWAVE=0
```

这里的 `DUMPWAVE=0` 是关闭波形文件生成，让第一次实验更轻便。之后需要分析信号时再打开。

## 第四步：安装 RISC-V 交叉编译器

你之前用的 g++ 是给 Ubuntu 电脑编译程序的。现在我们需要一个能生成 RISC-V 32 位机器指令的编译器。
先检查是否已经安装：

```shell
command -v riscv-nuclei-elf-gcc
command -v riscv64-unknown-elf-gcc
```

如果都没有输出，可以先安装 Ubuntu 提供的裸机交叉编译工具链：

```shell
sudo apt install -y \
gcc-riscv64-unknown-elf \
binutils-riscv64-unknown-elf
```

尽管名字中有 riscv64，它也支持生成 32 位 RISC-V 指令。Ubuntu 24.04 提供该工具链。

```shell
# 验证：
riscv64-unknown-elf-gcc --version
riscv64-unknown-elf-gcc -print-multi-lib
```

## 第五步：下载 E203 配套软件 SDK

官方的 Hbird SDK 已经提供启动代码、链接脚本、裸机示例和构建规则，比我们一开始自己写这些更方便。

```shell

cd ~/Projects/ChipContest/third-party

git clone https://github.com/riscv-mcu/hbird-sdk.git

cd hbird-sdk
```

我们最终会得到这样的结构：

```
ChipContest/              # 项目根目录（Chisel AI 加速器）
├── project.scala
├── src/
├── generated/
├── third-party/
│   ├── e203_hbirdv2/    # CPU 硬件
│   └── hbird-sdk/       # CPU 软件开发工具包
└── tools/
```

SDK 的 `application/baremetal/helloworld/` 里就有现成的 C 程序工程。

## 第六步：尝试编译官方 Hello World

先进入示例目录：

```bash
cd ~/Projects/ChipContest/third-party/hbird-sdk/application/baremetal/helloworld
```

我们先尝试使用 Ubuntu 的 GCC，而不是直接修改 SDK 配置：

``` shell
make CORE=e203 DOWNLOAD=ilm \
COMPILE_PREFIX=riscv64-unknown-elf- \
NEWLIB=normal dasm
```

成功的话，目录中应该出现：
```
helloworld.elf
helloworld.dump
helloworld.dasm
helloworld.verilog
```

其中 `.verilog` 是我们下一步要加载到 E203 仿真存储器的文件。