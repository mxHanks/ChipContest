# xu S2d 双 X 缓冲服务器独立实验

服务器完整12层结果：**双缓冲11,859,141周期，同RTL自动分组11,842,200周期**，增加16,941周期，**慢0.143056%**。全部304,128结果/608,256个Y写字通过。该服务器结果与本机筛选的约0.95%收益不同，保留两者各自工具链和原始证据；不能用本机收益代替服务器结论。目前不按吞吐保留S2d，是否有能耗优势仍需其自身面积/全SoC能耗数据。

冻结主 `3af4db98b893edd2103771fa132d69350b82ba96` / E203 `dd692c190dadafd9baa6dffe8514a3f684e7fbf5`，独立分支 `codex/xu-s2d-doublebuf`。相对S2c生产Chisel修改为：

- `src/main/scala/GenerateRTL.scala`：增加可选双缓冲生成入口。
- 新增 `src/main/scala/linear/LinearBufferedComputeCore.scala`：两套64×16 X bank，单套原32KiB逻辑W/8PE，选择拥有权的X bank供计算；没有复制W阵列。
- 新增 `src/main/scala/linear/LinearDoubleBufferCore.scala`：两行描述符、bank所有权和带行/组标签的结果FIFO。行计算完成可释放X bank，结果消费仅在POP响应退休后推进，允许下一行装载与上一行结果写回重叠。

旧生成SV默认字节和原有S2c接口保留；手写wrapper增加可选DB_CAP/CTRL/Xcursor/packed提交/row-submit/POP与结果窗口，固件预装下一行并校验组合row/group标签，保持signed16 X/W、signed40 bias、signed48 Y与共享槽格式。reset不冒充物理SRAM清零。具体设计及本机初版负收益/改进版对照在候选 `docs/validation/xu-s2d-doublebuf-20261103`，独立保留。

| 层 | 同RTL auto | doublebuf | doublebuf减auto |
| --- | ---: | ---: | ---: |
| 0 | 986,850 | 988,259 | +1,409 |
| 1–11（每层实际运行） | 986,850 | 988,262 | +1,412 |
| 总计 | **11,842,200** | **11,859,141** | **+16,941** |

服务器使用同 SiFive GCC-Metal10.2.0-2020.12.8、VCS Q-2020.03-SP2-6_Full64、-O2/both-unroll-no-masks。两种schedule分别bias-hw-doublebuf-window与bias-hw-autogroup-window；主/子、154个实测RTL/TB源、固件源、runner/contract、工具、fixture、48向量、同一simulator声明SHA逐项相同。每层仍shared读23232、写50688、START/done3168、8lane MAC有效拍202752；DB的MMIO写15499、auto15497，新增enable/disable均在窗口内。DB每层99提交/3168 POP退休，实际计算与X上传重叠4680周期、计算与写回149360周期，但重叠不等于减少同样多窗口周期。完整PERF和activity原文在comparison和raw中。

四项mandatory direct VCS均真实执行且保留compile/simulation日志：DB验证4行/128组/1024个signed48 lane、双类重叠、满FIFO、bank所有权、背压、最终POP/新submit边界，131次launch/done、accepted=retired=11862；原auto、packed、stream direct也全部通过。host报告Ran59/skipped4，跳过的是Icarus辅助后端，不能用其代替上述强制VCS；numeric42、vectors12、doctor、legacy5、synthetic1/2、新DB real12和同RTLauto real12九步全部PASS。

本目录117个唯一原payload来自291288-byte传输包，SHA256 `f78ba592a0ce0ef285dbafdce5368eb636b36cfdfd7d36e9a688d9a8bed479a9`。只读check-evidence核全部原字节和清单、185个冻结Git源、每次154实测源、77份声明日志、TASK/PERF/DB/AUTO/SOC、四direct实际计数及后端、全部同RTL身份和服务端比较文件，独立重算固定304128整数输出；52种实际日志缺失/重复/计数/POP/重叠/FATAL破坏均拒绝。

未取回ELF、装载镜像、模拟器二进制或实际server向量文件；其原声明SHA不冒充本地重哈希。开发TB为4ns HF/66ns LF，首shared接受到最后Y响应退休；候选正式clear/request、150MHz mapped时序/等价与全SoC能耗仍需独立执行，不能据此赋予比赛资格或分数。新同库PPA已另建目录，结果不在此提前填写。

```bash
python3 docs/validation/xu-score-s2d-server-20261103/check-evidence.py
```

同版本工具链与冻结checkout、新输出目录复现九步中的标准八步：

```bash
python3 tools/scripts/server_accept.py --sim vcs --cross-prefix "$xu_cross_prefix" \
  --firmware-schedule bias-hw-doublebuf-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks --out "$xu_new_db_out"
python3 tools/scripts/e203_soc.py --mode real --tasks 12 --sim vcs \
  --cross-prefix "$xu_cross_prefix" --firmware-schedule bias-hw-autogroup-window \
  --firmware-opt=-O2 --firmware-experiment both-unroll-no-masks --out "$xu_new_auto_control_out"
```

四direct的精确VCS编译/运行argv在原direct日志首行，必须另行执行；完整验收argv在原state。原cross-prefix `/storage2/2026contest/server4/s4_23usr/Desktop/xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf-`。部署归档704583 bytes/SHA `1ffdc053c925690fc243f945fb6036e65bb331102ffedc781c9e2c57e981dee5` 的身份与启动记录保留在raw，输出全新、不覆写历史失败或负结果。
