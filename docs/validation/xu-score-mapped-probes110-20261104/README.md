# actual110：服务器原生VPI与重复UDP诊断归档

本目录归档 actual105、actual108 在同一比赛服务器、VCS `Q-2020.03-SP2-6` 上执行后返回的原始字节。两项实验已终止，未修改原工艺模型。**这些结果用于建立后续映射网表仿真的可信基础，不是完整SoC功能、150MHz时序、活动覆盖或能耗验收。**

归档 `payload.tar.xz` 为 25,432 字节，SHA-256：

```text
ee7d293f161c855481d253cb0af8edcde82174f9da98e491157edffe0d179949
```

`payload-manifest.json` 列出46个载荷文件，共882,860字节；压缩包还包含同一份内部清单。清单覆盖原始状态、编译和仿真日志、公开探针源码及实际生产工具。原始日志空白未改写。服务器私有的标准单元库、SRAM模型、重命名UDP片段和仿真二进制没有导出；清单不是这些缺省文件的替代品。

## actual105：原生SRAM预装与观察

输出：`~/Desktop/xu-score-optimization-20261102/vpi-vendor-preload-primitive-20261104-105`。

- 只读诊断枚举普通名称和转义层次名称的两个真实厂商宏，各256个64位内部存储字。实际VCS将存储报告为 `vpiRegArray=116`、字报告为 `vpiReg=48`；512个字的行索引、归属、完整名称和唯一性检查通过，诊断分支写入次数为0。
- 正例仅对每个宏的第3行写入一次，按 `row[4*b+k]` 打包4个16位逻辑字。8次物理读回、4次关闭读使能时的保持检查通过，Q以自然未知态启动；未将Q或其它内部触发器强置为已知值。
- 两宏实际逐位上升/下降次数分别为14/12与14/11，与参考计数一致；各有16次X→二进制转换和4次向量通知。这验证的是该有限序列，不能据此推断全任务的全部边沿或静态概率。
- 错误列打包、交换宏标签两个突变均由实际物理端口读回拒绝。两项错误仿真的进程返回码仍为0，所以校验器同时检查原始 `Fatal`/错误标记及没有PASS标记，不能只看退出码。

四分支的期望与实际结果为：`diagnostic_only PASS`、`reference PASS`、`wrong_bit_column_packing REJECT`、`swapped_handle_tags REJECT`。这解决了 actual100 中原生类型假设造成的失败；actual100原始失败证据保持独立，不被本目录覆盖。

## actual108：两个重复UDP的原始行为

输出：`~/Desktop/xu-score-optimization-20261102/mapped-udp-review-20261104-108`。原普通标准单元模型SHA为 `9ceaac7085f267c9a2da19d86aa9d88ddb25894df4b2485e32d13e04d0e46581`，对应S2c映射网表SHA为 `9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892`。

| UDP | 两份定义 | 有限序列步数 | 第一/最后定义输出差异 | 原库输出/最后定义差异 |
| --- | --- | ---: | ---: | ---: |
| `udp_tlatrf` | token完全相同 | 16,641 | 0 | 0 |
| `udp_tlatrf2` | token与表项不同 | 107,521 | 3,668 | 0 |

`udp_tlatrf2`的原库输出与第一定义也有3,668步不同。因此，不能将重复声明视为完全等价的文字重复。原库在这些实际采样步中表现为最后声明，符合VCS的覆盖警告。探针自然Q=X启动，每步输入后等待1ns；没有替换用于SoC的原库模型、压制notifier或引入SDF。有限序列相等不能证明完整状态等价；实际不等则构成该序列的反例。

源解析器在默认、`FUNCTIONAL`、`functional`和两个符号同时开启这4种条件选择下，都报告两个重复UDP的直接调用单元数和映射可达实例数为0。**这仍是特定解析器的结果，不能单独据此声称全库、全设计或运行时绝无调用**；例如未覆盖的语法形式必须由独立词法出现次数或运行时证据继续核查。本归档保留该限制。

## 本地复核与服务器复现

```bash
python3 docs/validation/xu-score-mapped-probes110-20261104/check-evidence.py
python3 docs/validation/xu-score-mapped-probes110-20261104/check-evidence.py --extract /tmp/xu-probes110-verified
```

第二条命令要求目标目录不存在。校验器逐项检查压缩包、内部/外部清单、46个文件的字节数及SHA，核对原始状态、原生日志、实际结果和以上范围声明；不会重新运行EDA工具。

载荷 `tools/` 保留实际服务器使用的生产脚本，VCS完整参数保存在各原始 `state.json`/`result.json` 内。原实验启动命令为：

```bash
python3 "$HOME/Desktop/launch_vpi_primitive105.py"
python3 "$HOME/Desktop/launch_udp_review108.py"
```

启动器拒绝覆盖已有输出。复现须使用具备上述固定SHA输入的干净服务器快照，或者为新实验明确分配新目录并保存新生产脚本身份；不要删除或覆盖原105/108证据目录来重跑。标准库和宏模型需从服务器原授权位置读取，凭据不属于归档。

实际导出脚本为本目录 `tools/export110.py`；`live110-observation.json` 表明导出时两个工作进程均已不存在，状态均为上述终态。该观察只描述这次导出时点。
