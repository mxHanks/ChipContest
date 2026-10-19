# 复用地图

下列路径均相对 `reference/fpt/`。源码保持原字节；路径归一化以及采用快照覆盖的来源都写入 `metadata/source_manifest.json`。

| 类别 | 入口文件 | 可以借鉴的内容 | 比赛所需改造 |
|---|---|---|---|
| 多上下文调度 | `rtl/core/bc/qk/cats_r4_qk_32lane_scheduler.sv` | 多个点积上下文的请求与返回重叠、逐维依赖、标签守恒 | 当前来自 `qk_context_pipeline_20260927_r2` 快照；存在因果与128维/32-lane硬编码。改成非因果99行、64维、256输出通道，不能只改参数 |
| 乘加流水 | `rtl/core/bc/qk/cats_r4_qk_32lane_fp32_service.sv` | 累加上下文隔离、first/last、输入输出回压 | 选择比赛数值格式、加入偏置、替换算术核；既有浮点顺序是历史参考而非新题的固定要求 |
| 请求缓冲 | `rtl/core/bc/qk/cats_r4_qk_32lane_engine.sv` | 两槽请求FIFO、占用守恒、计算输出缓冲 | 取2026-10-13 r2快照；重定任务字段与矩阵循环，裁掉head/group/causal字段 |
| 双缓冲生命周期 | `rtl/core/cluster/cats_r4_qkv_banked_mem.sv` | 填充、发布、激活、读取和退役；避免覆盖未读完数据 | Q/K/V语义改为输入/权重；重做尺寸、bank数、端口和尾块。该文件不是通用可任意改参RAM |
| bank与端口仲裁 | `rtl/core/cluster/cats_r4_slot_bank.sv` | bank所有权、冲突观察、输出回压 | 三行槽是原设计结构，比赛按面积/访问计划重新选择，不必照搬 |
| 存储读边界 | `rtl/core/cluster/cats_r4_qkv_axi_bank_bridge.sv` | 读地址与使能寄存、tag/数据延迟匹配 | 取2026-10-13 retime快照；依赖XPM，须改成指定SRAM宏接口；原AXI64不是E203集成接口 |
| FIFO和复位 | `rtl/core/cluster/cats_r4_async_fifo.sv`、`cats_r4_reset_sync.sv` | Gray指针、复位释放、流控协议 | 单时钟方案可不使用异步FIFO；异步使用仍需新约束和CDC检查 |
| 数值编码 | `rtl/core/bc/qk/bf16_to_fp32.v`、`fp32_to_bf16.v`；`python/flash_attention_tile_model.py` | 位级转换、RNE、有限值计算的参考函数 | BF16不是定点16位；不能把这些函数当作KWT完整数值模型或完整IEEE异常值规范 |
| 精确参考方法 | `tests/check_cats_r4_fp32_reference.py` | Python Fraction有限FP32编码/解码与边界向量生成方法 | 旧CLI绑定Windows Icarus，不作为包内运行入口；移植功能只调用其纯函数 |
| 性能计数 | `rtl/board/cats_r4_core_service_observer.sv`、`cats_r4_core_service_from_counters.sv` | 被动计数、完成快照、异常/溢出标识 | 原计数窗口只覆盖core service；比赛必须另测从输入/参数装载开始到全部写回的总窗口 |
| C端读取 | `vitis/src/cats_r4_core_service.h`、`tests/cats_r4_core_service_coherence_fixture.c` | 快照一致性、epoch匹配、拒绝旧结果 | 是主机fake-MMIO参考，不是E203驱动；新寄存器映射与总线适配需实现 |
| 局部验证 | `tb/`、`tests/tb_*` 与 `filesets/` | 回压、复位、上下文隔离、buffer交替、计数断言 | 原测试验证FPT场景；需增加99×64×256、多层权重、偏置、尾块及NRMSE评测 |

## 选择来源时发现的差异

- 主目录存在同名旧scheduler，本包采用快照SHA `214397a87f0bcf840a42c27ae6121f99280a808830cc95c605ab6f973d05afc4`。
- 请求缓冲engine取r2实际文件，SHA `342dd73a7ccdf8dd6707b4246071da2a07df6d291430f13f54b460602f127c72`。其候选描述文件仍引用r1路径；本包以实际读入字节和当前源映射为准，不改历史文件来掩盖差异。
- bank bridge采用retime快照SHA `97c23748ba7753d491abebc39b3da41bb220b55a70e7b1e33f85f9127ffd2cf0`。其历史README中的“未验证”是创建时状态，本包不据此重写原FPT验证状态，也不迁移其PASS到比赛。
- 旧 `cats_r4_core_service_reader_fixture.c` 使用旧版三参数接口，本包不纳入；纳入与当前头文件相匹配的coherence fixture。
- `tb/tb_cats_r4_b3_fp32_mocks.sv` 选自已冻结的完整行为参考快照，提供独立FP32 MUL/ADD仿真实现。它不能作为可综合算术核。

## 不作为本科初版资产的部分

未收集完整四簇顶层、GQA多头映射、因果跳过、RoPE、Softmax/PV整链、DDR DMA/板级工程、BIT/XSA/ELF、远端运行器、账号配置和大型历史日志。本题初版应集中实现前馈第一线性层。AMD包装器保留为接口参考；AMD IP网表/库不在包内。

这些自有源码的原注释与来源均保留；没有找到项目根的统一LICENSE，不能据此声称整个FPT已按某开源许可证发布。比赛提交时需列出既有FPT贡献、新增比赛贡献及第三方来源。本包也不授予AMD库、比赛工艺库或SRAM宏的再分发权。官方KWT权重和数据未下载，后续从指定提交获取并保存其许可证及校验值。
