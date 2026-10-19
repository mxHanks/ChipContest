# 迁移环境与使用边界

环境服务于“2026-10-15 前得到可继续开发且有证据的迁移基线”。工具存在不代表设计通过验证；原 FPT 的 AMD Floating-Point/XPM、FPGA 综合结果不能代替本比赛的 E203、标准单元和 SRAM 验证。

## 当前已检查的环境（2026-10-14）

| 项目 | 首次侦察结果 | 用途 |
|---|---|---|
| 操作系统 | Ubuntu 24.04 系列，Linux x86_64 | 本地开发 |
| Python | `/usr/bin/python3`，3.12.3，系统含 pip/venv | 归档校验、数值检查、harness |
| C / C++ | `/usr/bin/gcc`、`/usr/bin/g++`，13.3.0 | 原包 C fixture、Verilator 生成模型 |
| 构建 | Make 4.3、CMake 3.28.3、Ninja 1.11.1 | 编译 |
| 仿真/综合 | 项目内已安装 Verilator 5.020、Icarus/vvp 12.0；Yosys 尚无 | 本轮仿真可运行；Yosys 暂不阻塞源码迁移 |
| RISC-V 编译器 | 首次 PATH 无 `riscv*-gcc` | 待取得组委会平台后选 ABI/ISA 与 SDK |
| 可用资源 | 本地约 6.5 GiB 可用内存，工作盘 47 GiB，`/tmp` 153 GiB | 资源为采样值，以最新 doctor 报告为准 |
| 服务器 | `leo@100.64.250.1` 已通过交互密码认证；BatchMode密钥认证未配置 | 后续可在独立目录运行，当前首轮用本地 |

`/media/leo/Data/iverilog/bin` 中的是 Windows `.exe`/DLL；`/media/leo/Data/vivado2025/2025.2` 看到 `win64`、`Vitis`、`tps`。这些目录不作为 Linux 已安装工具证据。未读取许可证、私钥或其他凭据。

## 第一层：可复现的本地最小环境

本包 `tools/verify_bundle.py` 和 `tools/run_host_checks.py` 的必要依赖是 Python 标准库与 GCC。先让它们运行成功，再扩展到新比赛模型。主机检查不需要先安装 PyTorch、ONNX 或下载完整数据集。

项目迁移工具的 Python 环境位于 `.venv/`；Linux HDL 软件包解压位置为 `.tools/eda/`，可执行包装器位于 `.tools/bin/`。这些目录属于可重建工具依赖，不随源码迁移复制。已安装 Ubuntu 的 Icarus 12.0 与 Verilator 5.020 软件包；安装入口是 `bash scripts/setup/bootstrap.sh --download`，包版本和SHA在脚本中固定。运行 `make doctor` 查实当前工具状态。

在 Bash 中激活项目环境：

```bash
source env/activate.sh
```

激活脚本只修改当前 shell 的 PATH/VIRTUAL_ENV，不修改用户启动配置；可重复执行。包装器负责处理项目内 EDA 软件包的运行位置。

运行环境侦察：

```bash
python3 scripts/env/doctor.py --json artifacts/environment.json
python3 scripts/env/doctor.py --require hdl --json artifacts/environment.json
```

第二个命令在既无可用 Verilator、又无可用 Icarus/vvp 时返回非零。它只判断工具是否能够报告版本，不表示任何 RTL 用例已通过。主机检查需要 Python、GCC、G++、Make。

`doctor.py` 优先检查 `.venv/bin`、`.tools/bin`、`.tools/eda/usr/bin`、`.tools/usr/bin`、`.tools/iverilog/bin`、`.tools/verilator/bin`，随后检查 PATH。环境报告记录实际路径与版本；未来有工具升级时重跑并将报告与对应验证记录一起保存。

脚本不自动安装、联网、修改 shell 配置或启动 EDA。`--json` 只写指定报告路径。Python 模块检查使用找到的项目 `.venv`，不存在时使用 PATH 中的 Python；不通过导入大型 ML 库进行探测。

## 第二层：参考 RTL 的独立验证

可先补齐 Linux Verilator 或 Icarus，选择哪一个应由实际文件集的编译诊断决定。新安装工具使用项目目录或现有环境，尽量不变更全局配置。原包共有 11 个独立文件集，来源为：

- `vendor/fpt-r1/metadata/dependencies.json`
- `vendor/fpt-r1/04_DEPENDENCIES_AND_STATUS.md`

文件集路径相对 `vendor/fpt-r1/`；从该目录编译或明确转换路径。FP32 测试模型和 vendor 同名 wrapper 不得同时编译。`fp32_reference_vectors` 需要先生成矢量并传入 `+VECTORS=...`；请求缓冲需区分 `CLEAR_IN_FLIGHT=0/1`。Verilator 侧通过不自动等于四态检查通过。

轻量 RTL 验证可在本机开始，建议最多 2 个编译任务，避免当前可用内存不足。报告须区分“编译失败”“仿真失败”“未运行”；不要把环境缺失写成设计失败，也不要把静态依赖检查写成仿真通过。

## 第三层：比赛验收尚需外部输入

| 依赖 | 何时必须有 |
|---|---|
| 组委会 E203 SoC 工程、编译环境、总线/NICE 接口 | 写最终驱动与完成 SoC 联调之前 |
| 标准单元库及指定 SRAM 宏、仿真/功耗模型 | 比赛面积、时序与功耗结果之前 |
| KWT 指定源码、权重与 Speech Commands V2 固定划分 | 完整模型精度、误差及吞吐基准之前 |
| 与比赛流程匹配的综合/时序/功耗工具 | 声称 PPA 或最终比赛达标之前 |

这些项目不会由安装一个通用开源仿真器自动解决。项目源码迁移和主机 smoke 可以先完成，但最终验收必须等输入到齐。取得平台后记录来源、版本/提交、SHA-256 和使用范围。

## 服务器只读检查与后续运行

用户允许使用服务器加速。首次 BatchMode 密钥认证失败；用户随后提供凭据，已通过SSH的交互密码提示成功登录并只读查询。服务器为 t7920，EL8/Linux4.18、112逻辑CPU、总内存约219.5GiB，可用约116GiB，采样负载2.39，/tmp剩余38GiB。PATH有Python3、GCC/G++、make，未检出Icarus/Verilator/Yosys/RISC-V GCC/dc_shell/genus（不代表其他安装路径不存在）。未执行远端计算、安装工具或修改旧FPT工作区。凭据不记录到文件；Ubuntu本机二进制不得直接当作EL8工具。

在正常 SSH 认证配置就绪后，可重新探测：

```bash
python3 scripts/env/doctor.py --ssh leo@100.64.250.1 --json artifacts/environment-with-server.json
```

该模式只读取 PATH 中的工具版本、CPU 数与 home 可用磁盘空间，超时后退出。SSH 失败记为 `UNAVAILABLE`；不会要求输入密码或自动设置密钥。若后续使用远端，应创建独立的新比赛目录、只同步新工程，记录命令/日志/退出码，不覆盖或停止旧 FPT 活动任务。

## 真实模型环境单独建设

指定提交的 [requirements.txt](https://raw.githubusercontent.com/ARM-software/keyword-transformer/237e4097/requirements.txt) 固定 TensorFlow 2.4.0rc1 和 NumPy 1.19.5，其他依赖未全部锁定；[README](https://raw.githubusercontent.com/ARM-software/keyword-transformer/237e4097/README.md) 说明更换TensorFlow版本可能影响评估采样。当前Python3.12环境供迁移/验证工具；旧模型使用独立 `.venv-kwt/`，Python3.8.20运行时放 `.tools/python/`。

2026-10-15已安装TensorFlow CPU2.4.0、NumPy1.19.5、Addons0.12.1、protobuf3.20.3，导入及checkpoint张量读取成功。精确2.4.0rc1在官方PyPI本次查询返回404/无可用版本，当前2.4.0为显式兼容替代，不能宣称完整复现rc1。全部43个包锁定在 `env/requirements-kwt.lock`。

```bash
bash scripts/setup/bootstrap_kwt.sh
```

脚本使用项目内uv0.13.1与Python，`--no-bin`避免在用户bin目录创建链接，缓存也在 `.tools/uv-cache/`。首次网络安装约150MB，数据集未包含。模型运行限制2个intra-op线程和1个inter-op线程；环境能导入不代表真实精度通过，实际导出和RTL结果另报。
