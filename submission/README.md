# 当前提交：1064 修复候选

本目录是仓库当前工程候选的唯一身份入口。[candidate.json](candidate.json) 固定生产 RTL、执行入口、公开证据包、最终映射及十二任务向量的 SHA256；不复制或移动历史冻结原件。

| 对象 | 当前选择 |
|---|---|
| 候选来源提交 | `be67e5d745cd7123e0def870f26be9a84263d759` |
| 生产 RTL 子模块 | `5470c5650f2d11d16e7c52cc96626d21030a3973` |
| 最终 ECO mapped.v | `d83acb49caec51aabc66d8ad61b8784294bebe26c5458aa0b095f9d12a2ae0d1` |
| 当前验收 | 数值时序 0、电气违例 0；仍有 4 项 unknown，未完整签核 |

完整结果、边界和原始报告见[最终修复报告](../docs/s3-y32-ingress-perf-postfreeze-repair-20261114.md)。1064.350640 task/s 来自十二任务 RTL 实测周期在假定 150MHz 下换算；最终修复是映射 ECO，没有修改已测 RTL。面积为原库单位，非官方 mm²。

## 从仓库根目录使用

需要 Python 3.10+。以下校验和提取使用标准库，无 EDA、网络或音频模型依赖；所有输出目录必须不存在。

```sh
python3 -B tools/current.py info
python3 -B tools/current.py verify --submodule
python3 -B tools/current.py unpack-mapped --out build/1064/final-mapped
python3 -B tools/current.py vectors --out build/1064/vectors
python3 -B tools/current.py check-vectors --vectors build/1064/vectors
```

`info` 仅显示选择，不能作为验收。`verify` 按绑定 manifest 核对全部已发布原件，再核对压缩包内 80 份 payload、原生完整 STA 总数、4 项 unknown、电气报告及结构证明；它还校验性能 result/log 的 SHA，重新用独立检查器读取原日志、比较十二任务周期和输出、检查假定 150MHz 的吞吐公式，并以精确十进制核对三项面积与原生面积表。`--submodule` 另要求生产 RTL 初始化、提交一致且工作区干净。省略该选项会明确显示 RTL 尚未检查。

`unpack-mapped` 仅输出 `apply/mapped.v`、DC 导出的 `apply/mapped.sdc` 及保留原层级的 8 份 SVF。先验证完整包及全部 payload，再创建目录；拒绝覆盖、重复成员、链接和路径逃逸。最终 DDC、工艺库和许可证未包含。**从 RTL 重新综合本身不能复现最终 ECO 网表**；当前交付入口提供可直接审阅的同一原生映射与完整证据链。

运行入口回归需要 Icarus Verilog；完整任务另需 Verilator、GNU C++/Make 和 RISC-V bare-metal GCC/binutils：

```sh
python3 -B tools/current.py ingress
python3 -B tools/current.py cpu --vectors build/1064/vectors --out build/1064/full12
```

`cpu` 默认十二任务、warmup、两编译任务，并固定 `--load-pipeline 1`。可用 `--tasks 1` 做单任务检查，`--jobs 1` 降低编译资源，`--cross-prefix` 选择同目标工具链；不可将单任务结果当成完整十二任务验收。这些是原 SystemBus loader 的 RTL 工程测量，不是 GPIO 生产加载或带门延迟任务仿真。

## 目录关系

- `third-party/e203_hbirdv2/`：实际生产集成 RTL；当前核心、DMA 和 ingress 均在此子模块。
- `experiments/s3-y32-ingress-perf/`：当前验证、吞吐测量与 ECO 工具实现；统一入口只调用这套候选。
- `model/`、`tools/ppa/`、`tests/` 及被复用的其他实验模块：当前工具的真实依赖。
- `docs/validation/`：按日期保留的只读证据；旧候选及阶段数字由各自文档界定。
- `build/`：不入库的本地生成目录。

保留历史路径以维持已发布 SHA 和复现依赖。当前入口不会选择旧 S2e、374 宏整合版或其他候选。CDC/RDC、复位脉宽、物理时序与正式比赛验收仍按最终报告明确保留。
