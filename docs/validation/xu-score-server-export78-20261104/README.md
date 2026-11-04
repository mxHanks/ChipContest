# 实际78：reset61完整FM通过及可读条件时序弧

58份实际原件共16,423,789字节，原tar.xz为264268字节，SHA256 `d115ae49c1b0949653ee14222343dbcf745a1a3680d86efaca2c6e374fc72733`。完整路径/大小/原SHA见[original-manifest.json](original-manifest.json)。原始Tcl、工具日志、原始失败祖先状态、属性索引及测量数值无损保留；工具手册仅保存身份，不打包正文。

**FM66实际通过。** 目标为reset61完成DC插入后的网表`502a29a0f990d2b1f9394b80da35639cfbb81b9021ad01355f96ab1465dc7597`；完整default→08→09→49→50→61 SVF链、原RTL、两份SS DB及217个冻结输入before/after相同。真实return0、唯一`Verification SUCCEEDED`/`XU_FULL_SOC_FORMALITY_PASS`，41462 passing（17136 BBPin、144 Port、24143 DFF、39 LAT）、508 unread。原61 PT状态仍为FAIL，未改写；FM不证明宏内部或时序资格。

**只读诊断76补足了67的可读性。** 实际lib_timing_arc属性索引为三行折行，修正解析后读到37项属性；from/to集合转换为实际pin名称，每个design/lib arc有稳定ordinal。两PMU的CK→SDN条件为`when=!D`、`sdf_cond=ENABLE_NOT_D===1'b1`，setup_rise_clk_rise弧未禁用，数值分别为−0.136499/−0.136345ns；removal弧为正，removal路径可报告。**负recovery约束数值并不自动解释为何两项coverage仍unknown**；本次没有改变量、库、SDC或添加豁免，后续应核实工具负约束处理和端点arrival，而不能把缺路径当met。全部10份sink报告保留。

**原生pin报告样本。** 从task00两份约805MB属性报告各取第一pin完整原始block，分别33660/32073字节。原文件完整SHA沿用实际execution回执；本次仅提取样本，没有重新hash全部原文件，也不能代表全部22512pin。样本显示toggle_rate double、static_probability float及x_probability等原生属性，后续全量摘要须流式读取、完整重hash并保留舍入精度限制。

人工从终端截图转录SVF哈希时曾多输入一个开头字符；未通过64位保护，FM尚未创建输出或启动。随后从原JSON准确绑定`5cfc2a56aec461f1759442308ed3212d138231738d586a2dfedeec10de39a807`才执行本次FM。错误转录没有覆盖原SVF或网表。

本目录[tools](tools)保存确切实际helper；当前完整门槛仍未闭合。离线原件核验：

```bash
python3 docs/validation/xu-score-server-export78-20261104/check-evidence.py
python3 docs/validation/xu-score-server-export78-20261104/check-evidence.py \
  --extract /absolute/path/new-actual78-directory
```

服务器实际命令（复现须更换新输出名，禁止覆盖原件）：

```bash
python3 "$HOME/Desktop/launch_electrical_formality66.py"
python3 "$HOME/Desktop/launch_reset_condition76.py"
python3 "$HOME/Desktop/xu-pins78.py"
```

清理73属于50→63→73另一分支，不包含reset61的40个反相器；33项min-cap和reset61 removal已通过不能拼接宣称同一个网表同时满足。
