# xu 32PE 四深度128×16权重bank 本地筛选

状态为 `LOCAL_SCREEN_PASS_NOT_QUALIFIED`，尚未保留为参赛配置。生产主提交 `c684402dc38bcc4437bf822f24d9ea4f401e1da3`，子提交 `52cfbea1f79f10e44f7d1696f54015797f886b96`；服务器指定宏测试入口追加提交 `6e59ec89c31376e6facaa77f21f2840525ec32a7`。来源为独立分支 `codex/xu-pe32-bank128`，原32PE交付 `94ce6f0`，未修改原32/64PE实验。

同主/子提交、GCC14.2.0、Verilator5.032、固定真实layer00、同wide固件及ITCM image：

| W物理结构 | 任务周期 | 实际lane MAC | 共享源读 / Y写回 |
| --- | ---: | ---: | ---: |
| 原32PE：32×1024×16，逻辑32KiB / 物理64KiB | 957,040 | 1,622,016 | 23,232 / 50,688 |
| 本候选：32×4×128×16，逻辑32KiB / 物理32KiB | 957,040 | 1,622,016 | 23,232 / 50,688 |

周期差为0，全部PERF、AUTO、PE记录相同。实际为50,688次32lane计算、99行、792次POP退休、25,344个signed48结果；两个物理变体使用不同仿真binary。固件image相同，ELF各自保存原始SHA，未假定ELF字节相等。本地TB为历史HF4ns/LF66ns，首共享读接受至最后Y响应退休，含W/bias/X上传；没有任务前正式清空及首REQUEST窗口，不是150MHz或全SoC能耗口径。预计全SoC宏结构为固定320只1024×16及本候选128只128×16，实际面积、宏数量、PVT、完整时序和能量须由同候选综合/功耗证据确认，不能直接把32KiB容量减少当成面积/能量收益。

已完成：Chisel定向测试1项；真实四态单bank测试遍历512个逻辑地址、四depth交错，含520次写、524次读、4次未初始化X读、128边界及采样地址改变后的返回depth；generated SRAM上的wide/compat wrapper各两行512结果；69项host PASS，其中2项因本地无指定RAMSP128X16模型而明确skip；42项numeric PASS；**本候选实际SoC legacy5** PASS。host的mock PASS不代替这些真实legacy日志。严格重放再独立计算两份固定向量共50,688个整数结果。20份原8/32PE生成SV和wrapper与原子 `fc3977d` 逐字节相同；全部16,384个旧W地址到 `(bank, depth, word)` 的映射穷举为双射。

`raw/manifest.json` 冻结105份原始payload（包含初次及最终host、实际驱动命令、direct、向量、ELF/image、原始工具输出）；`raw/source-files.json` 冻结1178份生产/测试/工具及子树源文件的字节、模式、符号链接目标。原文中的nonfatal下载失败、mock失败文字及指定宏缺失负例完整保留。`local-comparison.json` 由重放生成，非人工填写的性能汇总。

## 改动的Chisel

- `src/main/scala/linear/XuParallelCore.scala`：为32PE添加独立 `bank128` 几何；每个逻辑512×16 W bank由4只单1RW 128×16构成；addr[8:7]选择depth，低7bit定位word；读时寄存返回depth一拍，避免下一拍地址误选上拍Q；未选中的宏en/addr/data/write保持安静；保留原1024变体生成名称及字节。
- 新增 `src/main/scala/memory/Sram128x16.scala`：显式单1RW `SyncReadMem.readWrite`，一拍同步读；idle/write读数据不作有效值。
- `src/main/scala/GenerateRTL.scala`：独立生成 `XuParallelAutoGroupCore32Bank128`，不覆盖原入口。
- 新增测试 `src/test/scala/linear/XuParallelBank128Test.scala`，不是生产电路。

另有新手写 `xu_pe32_bank128_icb_slave.v`、固定perips实例处条件选择、runner/build-key/物理PE计数选择以及128宏适配器。MMIO数值格式、向量及原ABI保持；没有增加内存读端口。CPU、互连及共享SRAM源字节保留。

## 复现

在本分支重放，输出必须使用新文件：

```bash
python3 docs/validation/xu-score-s3-pe32-bank128-local-20261103/audit_local.py \
  --root "$PWD" --raw "$PWD/docs/validation/xu-score-s3-pe32-bank128-local-20261103/raw" \
  --out /absolute/new/xu-bank128-replay.json
python3 tools/scripts/e203_soc.py --mode real --tasks 1 --sim verilator \
  --accel-variant pe32-bank128 --firmware-schedule bias-hw-pe32-autogroup-window \
  --firmware-opt=-O2 --firmware-experiment both-unroll-no-masks --out /absolute/new/xu-bank128-real1
```

保持同命令仅改variant为 `pe32` 即原32PE同wide控制。legacy5使用 `--mode baseline --sim iverilog --accel-variant pe32-bank128` 及相同固件参数。

```bash
scala-cli test . --server=false --jvm system --test-only linear.XuParallelBank128Test
python3 -m unittest discover -s tests/e203 -p 'test_*.py' -v
python3 -m unittest discover -s tests/numeric -v
```

服务器入口强制 `XU_PE32_BANK128_WRAPPER_SIM=vcs` 和 `XU_PE32_BANK128_MACRO_MODEL=/absolute/actual/RAMSP128X16.v`。缺失模型时直接FAIL，负例见 `raw/missing-server-model-negative.log`；不能把两个本地skip填成宏验收PASS。该入口对实际指定模型分别执行全depth单bank、完整wide及compat两个wrapper，同时保留generated模型对照。模型路径与SHA写入原始compile/simulation日志。服务器完整8步acceptance、同main原32同wide full12和本候选旧auto full12控制、同库128/1024 PPA及全SoC任务能耗仍待执行；本文件不声称这些已完成。
