# xu 全SoC电气修复49实测归档与50/54/55待执行工具

49已在原150MHz全SoC、原SS库和原SDC场景下实测：56个实际cell同family drive sizing后，PT max_capacitance违例56→0。
min_capacitance仍1404；五个reset removal违例及裕量不变；coverage仍294512 total、267380 met、5 violated、27127 untested。
49的状态是 `EXECUTED_NOT_QUALIFIED`：新mapped版本的完整全SoC FM仍未执行，不能称完整时序/电气/功能一致性已qualified。
50清理、54完整FM、55 reset buffer只有host检查和待执行源码，没有新的DC/PT/FM结果，也没有正在运行的新EDA任务。

42仅在proposal解析阶段失败，原件只有driver.log、proposal.log、state.json三份；旧parser无法解析实际min_capacitance报告的行顺序。
42没有进入实际DC/PT sizing，不能把它列为一次实际cell修复结果。49使用修正后的parser，原repair.tcl、执行日志和实际sized-cells.tsv均在本目录。

## 字节原件、来源与审核

| 组 | 原件数 | 用途 |
| --- | ---: | --- |
| actual49 | 27 | export51完整返回的49 scripts、DC/PT日志、报告与状态 |
| actual42 | 3 | export51完整返回的proposal失败日志与状态 |
| baseline14 | 14 | 原09 mapped下的PT对照，逐项比较capacitance/reset/coverage |
| topology35 | 6 | 原09所有1460 cap相关pin的真实跨hierarchy all_connected -leaf查询 |
| palette41 | 7 | 相同冻结原输入下真实库pin全集与1460 source pin记录 |
| successful09 | 3 | 原成功09全SoC FM的state、verify.tcl、fm.log；只是后续FM的冻结参考 |

`source-bindings.json`逐文件记录原始字节数/SHA256、已收manifest条目、private build来源、仓库存储路径与压缩后SHA256。
`provenance/source-*-manifest.json`保留各次已收export的原manifest字节。
大于64KiB的原件用lossless XZ保存；解压后的字节必须匹配原SHA256，原文件未被改写。
本目录`.gitattributes`对evidence禁用文本转换和diff，保留EDA原始空白，不对原件做whitespace修正。没有复制或修改真正mapped RTL、原SDC或库。
`manifest.json`绑定本目录所有交付文件；`audit.json`是checker从归档原件重新推导的事实，且默认检查与当前推导结果完全相同。

在root仓库执行标准库checker：

```sh
python docs/validation/xu-score-electrical-repair-20261104/tools/xu_check_electrical_evidence.py
```

checker校验60个原件及其已收manifest，49的两次实际DC/PT完成标记、log/script/report SHA，56条实际sizing及库family，
capacitance精确集合、五个reset端点与slack、所有coverage类别，35/41冻结输入与全部output记录，以及本目录工具/host记录的source SHA。
它不会执行EDA，也不会删除逻辑。现有50的5种host Tcl控制流记录及55的实际端点/palette/生成Tcl语法记录保留在`host-checks/`；它们不是EDA证明。
54在本地只检查了Python语法与冻结链构造源码，没有执行完整FM。

原49 mapped.v、mapped.ddc、repair.svf没有包含在export51返回的27份原件中。
`5df0b568d1751d19388edb33d244f8b19051a9fa7c77b24a2e023bf1e2ee4b4c`是实际服务器state记录的mapped SHA；
本地checker不能重算未收回网表或SVF的字节。待执行helper会在服务器直接重算并锁定这些文件。

## 实际49范围

| 检查 | 14原对照 | 49实测 |
| --- | ---: | ---: |
| PT max_capacitance violated pins | 56 | 0 |
| PT min_capacitance violated pins | 1404 | 1404，exact pins/limits/zero loads相同 |
| setup负路径报告 | 0 | 0，原SDC场景 |
| reset removal负路径 | 5 | 5，exact端点和slack相同 |
| All Checks total / met / violated / untested | 294512 / 267380 / 5 / 27127 | 完全相同 |
| 新mapped全SoC FM | — | 尚未运行 |

五个reset的startpoint全为`io_pads_aon_erst_n_i_ival`；LF rising-edge removal检查中，PMU两项为−0.12148283、−0.11847966ns，AON catch三项各−0.04010564ns。
完整端点、实际库reference与pin见`audit.json`。
原SDC SHA为`404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98`，
原proposal Tcl SHA为`45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e`；仍是pre-CTS ideal clocks、70 first-D cuts及6 forwarded output clocks的已有范围。
没有通过新增false path、load、库限值或reset waiver消除违例。

35/41查询针对原09 mapped SHA `5610f32b23220c87d39b45f24133adbf867d7faeb7284eed5f75d84b77ef4fca`，并不是49后拓扑的替代证明。
35显示1404个原mincap输出跨hierarchy仅自身；41库输出全集进一步支持1404个完整cell候选，含3个固定PLIC unused registered priority flop。
原RTL/source推理保存在`provenance/plic-unused-priority-source-proof50.json`；它不等于完整FM，live interrupt信号不在删除候选中。

## 待执行工具与复现

`tools/`保留最终50、54、55源码、实际49准备helper与修正parser，以及用于说明42失败的旧helper/parser。
这些本地helper的源SHA绑定不能代替原执行证据；49实际执行以归档repair.tcl、sta.tcl及其日志/状态为准。
完整安装手册40留在private build；Git只保存`provenance/installed-command-bindings40.json`内的原SHA、字节数、installed版本`T-2022.03-SP5-5`及必要用途说明。

以下命令都在原服务器、原冻结输入仍存在时运行。把50、54、55及`analyze_cap_palette41_v2.py`原样放到Desktop。
helper异步启动并拒绝覆盖已有output目录；先检查服务器是否已有同名output，不能重跑覆盖本次归档原件。

```sh
python ~/Desktop/launch_min_cell_cleanup50.py
python ~/Desktop/launch_electrical_formality54.py 49
# 50实际DC/PT有终态后，再运行对应FM；49、50的FM各有独立目录：
python ~/Desktop/launch_electrical_formality54.py 50
# 独立reset实验，可先以actual49为parent；50为parent需其真实终态及exact五违例：
python ~/Desktop/launch_reset_buffer55.py 49 4
python ~/Desktop/launch_reset_buffer55.py 50 4
# 对完成DC/PT的相应55版本完整FM：
python ~/Desktop/launch_electrical_formality54.py 55-49-4
python ~/Desktop/launch_electrical_formality54.py 55-50-4
```

50锁定actual49 mapped SHA、实际49 repair.tcl/DC log、原RTL/SDC/库身份。
全部1404候选先做exact实例/reference、完整输出集合、每个输出跨hierarchy leaf receiver和唯一parent design预检；全部通过后才删。
`post-cleanup-upstream.tsv`实际查询受影响的存活上游driver，记录新悬空；不递归盲删，不清理hierarchical ports。
仍须检查新的DRC、完整原约束PT与coverage，并完成54的全SoC FM。

54锁定原成功09 FM状态和全部158项原RTL/SVF/template输入及两份原SS库。
SVF顺序是default→08→09→49→可选50→可选55，每个后继mapped输入SHA必须绑定前一版本。
49与50可以各自独立执行FM；PASS仍标`VERIFIED_REVIEW_PENDING_NOT_QUALIFIED`，不代替电气审查。

55的五个sink直接来自所选实际parent的hold报告；缺少原exact五项就拒绝执行，需先检查新的实际报告。
actual41 palette只有CLKINV单输入/单输出候选且PT Boolean function是ABSENT；没有根据名称把它当作已证明buffer。
采用实际`CLKINV0_12TR40`的I/ZN拓扑与dont_use=false记录，再由安装DC的`insert_buffer -inverter_pair`原生验证inverter功能。
默认每sink4pair、总计40个真实库cell；逐段回溯验证完整链、单独目标sink、原driver及新增cell数量。
最终PT必须给出全max/min、全部DRC/coverage及五个sink各自recovery/removal报告，缺失路径会失败；数量4并不是声称时序已满足。

如需重放49的原DC/PT脚本，应使用新的空工作目录，不向原49写结果。以下是服务器上的重放示例；原绝对冻结输入必须仍有效：

```sh
xu_electrical_base="$HOME/Desktop/xu-score-optimization-20261102"
xu_electrical_replay=$(mktemp -d "$xu_electrical_base/xu-electrical49-replay-20261104.XXXXXX")
cp "$xu_electrical_base/full-soc-cap-size-repair-20261103-49/repair.tcl" "$xu_electrical_replay/repair.tcl"
cp "$xu_electrical_base/full-soc-cap-size-repair-20261103-49/sta.tcl" "$xu_electrical_replay/sta.tcl"
export SYNOPSYS_LC_ROOT=/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5
export PATH="$SYNOPSYS_LC_ROOT/bin:$PATH"
(cd "$xu_electrical_replay" && dc_shell -f repair.tcl >dc.log 2>&1 && pt_shell -f sta.tcl >pt.log 2>&1)
```

重放是新的实验，必须保留新日志、重算全部输入/输出SHA、复核全部报告，不能把旧state当作新运行收据。
42的历史失败可由归档proposal.log直接检查；没有必要再次运行失败parser来验证49。

reset release本质异步。原SDC以HF为参考给raw reset 0 input delay、用LF作recovery/removal检查，原0.1ns uncertainty保持。
插入mapped delay和完整FM只验证这个已有SDC场景及逻辑等价，不证明所有异步release相位的安全性、reset协议或MTBF。
原PMU两级异步置1和AON三级catch共享raw async reset的RTL没有被修改。
