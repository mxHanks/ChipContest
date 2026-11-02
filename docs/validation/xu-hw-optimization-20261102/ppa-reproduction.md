# xu 服务器工艺库面积 / STA 复现

原始综合使用服务器 SMIC40 RVT SS/0.99V/125°C 标准单元库与相同工艺角 RAMSP1024X16 SRAM 库，顶层 `accel_icb_slave`。完整源集含 MMIO、计算、X缓冲、权重SRAM及候选的bias缓存/结果窗口，排除CPU、系统互连和共享RAM。原输出保持只读。

交付[复现归档](artifacts/xu-ppa-reproducibility.tar.xz)为原始113文件中的104份原样字节及清单，SHA256为 `784ca438ee2c381e67755191a76b3d487ff51c81b6b43312bc0c72bae614743b`。省略工具手册全文与重复汇总的9项仍保留原SHA和服务器路径，未含工艺库/厂家模型或mapped netlist。原始失败attempt、修正后的Tcl、约束、adapter及报告/日志保留。原传输包SHA为 `8fc6a127069934bb21227b865918c45aeb74f4f7739b7c24b34b32ee5a4c31f3`，与派生选择不同。

在有本次报告交付物、原冻结RTL和已安装工艺库的服务器执行以下Bash命令；所有新目录均须尚不存在。`xu_report` 指向本报告所在目录，可从带报告的工作副本复制到服务器，不要求覆盖实验执行源码。

```bash
xu_report=/绝对路径/xu-hw-optimization-20261102-report
xu_replay=/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-ppa-reproduce-01
mkdir "$xu_replay"
tar -xJf "$xu_report/artifacts/xu-ppa-reproducibility.tar.xz" -C "$xu_replay"
python3 "$xu_report/evidence-tools/ppa/xu_prepare_ppa_replay.py" \
  --subset-root "$xu_replay/xu-ppa-reproducibility" \
  --out "$xu_replay/new-comparison" --run
```

该工具先验证归档严格内层清单、源集与工艺库SHA，将原Tcl的读入路径改为新RTL副本，将PT读入改为**本次新综合生成**的 `mapped.v/mapped.sdc`，所有输出都在新目录。顺序执行每侧 `dc_shell -64bit -f synth.tcl` 和 `pt_shell -f audit.tcl`。环境设置 `SYNOPSYS_LC_ROOT=/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5` 并prepend其bin，避免旧PT-063启动错误。原DC/PT版本分别为 T-2022.03-SP5-5 / T-2022.03-SP5-1。

默认从 `/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/frozen-fw-rtl`、`frozen-hw-rtl-02`恢复精确输入。若重建时没有这些冻结目录，可改用已含旧/新提交的E203仓库对象，附加参数：

```bash
  --old-submodule /绝对路径/包含e36d34a对象的E203仓库 \
  --new-submodule /绝对路径/包含f49a5fc对象的E203仓库
```

工具从精确Git对象读取生成RTL，adapter来自交付归档，每份源仍须与原manifest逐字匹配。新服务器另需安装相同EDA工具、许可、Library Compiler和相同哈希工艺库，不能以开发Nangate脚本替代。

`--run` 才启动真实EDA；不带该选项仅准备文件。交付的[本地复现准备检查](ppa/reproducibility-preflight.json)只验证24份RTL恢复、源路径/新输出隔离、Tcl语法和失败反例，明确没有新增DC/PT执行。原始服务器综合/STA执行证据在归档内，不将本地桩检查当作服务器工具实跑。

面积/STA独立复算：

```bash
python3 "$xu_report/evidence-tools/xu_verify_ppa.py" \
  --paired "$xu_report/ppa/paired-exact-summary.json" \
  --out "$xu_replay/independent-ppa-verification.json"
```

该脚本仅核报告原字节SHA、同库/同约束/原计算RTL身份和数值，不运行EDA。原约束、无提取RC/未指定wire load、保持时间违例与未测检查范围均见主报告及原始coverage报告。活动功耗的波形来源和实际PT命令另外保留，不由此面积/STA回放工具执行。
