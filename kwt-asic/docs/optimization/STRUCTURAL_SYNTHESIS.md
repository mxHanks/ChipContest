# 保留存储的结构综合

本项目内安装 Yosys/ABC 0.33-5build2，入口 `bash scripts/setup/bootstrap_synth.sh --download`；包 SHA256 固定，不修改系统环境。`source env/activate.sh` 后可使用工具。

`python3 scripts/synth/run_structural.py --variant banked --lanes 8 --pipe-mul 1` 运行显式源文件的 elaboration、proc、opt、memory_dff、memory_collect、结构检查与 JSON 导出。全部 payload 存储应保持 373,760 bit；不运行 memory_map，不用寄存器展开冒充 SRAM 面积。完整命令、退出码、结束标记、源码/工具/派生输入/输出 SHA256 记录在独立 artifacts 目录。

Yosys 0.33 不解析源码的 `int'(index)`，工具仅对四个白名单索引生成 `$signed(32'(index))` 副本。原 RTL 保持不变。已穷举全部有效二进制索引值；这不证明 X/Z 四态等价（Icarus 对两种转换的未知值行为有差异）。原 RTL 四态回归由 Icarus 单独执行，结构报告不冒充门级等价证明。

发现的实际问题：原 baseline/opt 的二维 W、bias 数组被收集成 8R/8W 或 16R/16W 存储。单纯在代码注释中称它们为 bank，并不能保证工具保留 bank 边界。新 `kwt_linear_engine_banked.sv` 在每个 generate lane 内定义一维 W/bias 数组，保持数值与时序协议，形成 8 lane 的 17 块或 16 lane 的 33 块独立同步 1R/1W 逻辑存储。装载与计算互斥，之后仍须接入指定单口宏包装和读写选择逻辑，不能把逻辑 1R/1W 直接当成已完成宏映射。

原结构计数（不含 memory_dff 合并进读口的寄存器）：8 lane 的组合/流水版本分别为 481/740 bit；16 lane 为 865/1380 bit。乘积流水增加 32×LANES+3 bit，分别为259/515 bit。完整 payload SRAM 容量不变。面积是否下降、最差路径是否满足150 MHz以及能耗是否改善，仍需要实际标准单元映射、指定宏、有效 SDC 与完整窗口活动。

正式状态：指定 SRAM 映射、门级等价/综合后功能、STA、mm² 面积、功耗与 E203 SoC 仍未通过。泛化结构统计不能代替这些结论。
