# xu 全SoC DC/PT可回放入口

入口`tools/scripts/xu_soc_ppa.py`准备`xu_soc_ppa_top`完整数字设计，包含CPU、固定互连/外设、加速器、ITCM/DTCM和512KiB共享SRAM。当前工具链准备和host guards不是实际DC/PT通过证据。映射宏总数固定336：ITCM32、DTCM32、shared256、weights16；小FIFO/debug阵列和bias/X寄存器继续计入标准单元。

已知实际库路径及独立核对的SHA后，优先使用可执行配置生成器；占位符须替换为服务器的真实值：

```bash
python3 tools/ppa/xu_soc_implementation.py \
  --root /absolute/source/root --out /absolute/new/config \
  --standard-cell-db /absolute/standard_cells.db --standard-cell-sha256 VERIFIED_STD_SHA256 \
  --sram-db /absolute/RAMSP1024X16.db --sram-sha256 VERIFIED_SRAM_SHA256
python3 tools/scripts/xu_soc_ppa.py prepare \
  --root /absolute/source/root --implementation /absolute/new/config/implementation.json \
  --out /absolute/new/candidate --allow-unqualified-mapping
python3 tools/scripts/xu_soc_ppa.py run --root /absolute/source/root --out /absolute/new/candidate
```

生成器固定E203子仓`f49a5fc914971426bd4530db39e270a84b41139f`，核对当前顶层、CPU、加速器、互连和TCM/shared实例连接，生成inventory、implementation、mapping-proof及generation JSON。标准单元/SRAM库分别绑定角色和外部提供的SHA；哈希不符即拒绝，不用现场计算的新值替代输入值。输出目录不能已存在。默认运行当前源码的clock reviewer（Tcl轻量检查，无RTL或STA通过声明）；也可用`--clock-review /absolute/clock-review.json`复用真实审查，所有被审查源码SHA均须仍匹配。不会复制或综合vendor仿真模型，也不会访问远端。

映射证明始终初始化为`UNREVIEWED`，八项mapping检查及mapped-netlist equivalence均为`NOT_RUN`，产生十项明确资格缺口。必须以实际原始证据逐项更新，开发DC/PT执行不会自动改成PASS。门级等价的PASS还须有真实log及netlist SHA；缺门级等价不允许成为无缺项配置。

在实际服务器源码路径执行inventory，按输出模板填写真实绝对文件路径及SHA256：

```bash
python3 tools/scripts/xu_soc_ppa.py inventory --out /absolute/new/inventory
```

`implementation-template.json`中两个已知behavioral RAM定义分别替换为`xu_sirv_sram_adapter.sv`、`xu_weight_sram_adapter.sv`，新增source包含`xu_soc_ppa_top.sv`和`xu_shared_icb_sram.sv`；不把vendor仿真模型放进DC文件表，不用contract仿真模型代替时序/功耗库。库记录必须带`role=standard_cell`或`role=sram`：只有标准单元库进入`target_library`，两类库都进入`link_library`/PT `link_path`。路径与源SHA均绑定到同一配置；同角库身份、EMA=010/EMAW=00资格仍须真实资料与模型证据。

按`docs/xu-full-soc-clock-review.md`先生成真实clock review。保存implementation草稿后，生成绑定当前映射源码的资格模板：

```bash
python3 tools/scripts/xu_soc_ppa.py review-template \
  --implementation /absolute/implementation.json --out /absolute/new/mapping-review
```

模板全部是`NOT_RUN`，总体为`UNREVIEWED`，不预填PASS。根据真实vendor模型、byte mask/read-hold/bank/collision/ICB/whole-SoC RTL日志逐项填写，并另行核实SRAM PVT时序资格。每项PASS必须有实际raw log及SHA。`mapped_equivalence`默认仍是`NOT_RUN`，RTL映射对照不能改写为门级等价完成。

尚缺资格证据时，允许明确的开发测量：

```bash
python3 tools/scripts/xu_soc_ppa.py prepare \
  --implementation /absolute/implementation.json \
  --out /absolute/new/candidate --allow-unqualified-mapping
python3 tools/scripts/xu_soc_ppa.py run --out /absolute/new/candidate
```

该开关只允许缺项状态诚实保留到`prepared.json`/`execution.json`的`qualification_gaps`；不会放宽源SHA、库角色、336宏、真实顶层/CPU/加速器/互连身份或时钟检查。没有开关时，缺映射/PVT证据会拒绝准备。`run`记录`EXECUTED_NOT_QUALIFIED`，不产生比赛合格状态。

生成的DC脚本保留被SDC/宏检查引用的层级，禁boundary optimization并用`compile_ultra -no_autoungroup`。设置`set_fix_hold [all_clocks]`要求工具尝试hold修复，PT仍必须报告真实最小slack；这行命令本身不证明hold通过。具体优化限制和前物理互连估算应随候选记录，后续若改变综合方法，须重测同一候选的时序/面积/功耗。

DC/PT脚本都用Tcl `catch`停止错误，Python还检查退出码、Error/Fatal及唯一完成marker；空/缺报告不会当作通过。PT核查150MHz/32.768kHz/10MHz主时钟和保守divider时钟，输出setup/hold、所有violators、analysis coverage、clock endpoint与recovery/removal/gating/pulse-width报告。`timing-slack.tsv`和`execution.json.timing_review`会明确记录负setup/hold、无clock端点及report错误；即使两种slack均非负，状态也只是`REPORT_REVIEW_REQUIRED`，必须继续检查untested、clock/CDC/reset覆盖、库单位/角、门级等价和全部资格缺项。

`power --activity /absolute/activity.json`要求同一冻结配置的12任务完整数值验证、真实log与首输入/最后Y响应退休边界。它产生12个独立PT进程，每次`read_vcd -time`只传一个start/end pair，逐任务保存六类activity/power/units报告。不能把24个边界传给一次`read_vcd`，也不能将不同任务功耗不加权平均后乘平均时间。此入口只执行功耗分析，不自动审查annotation或给出能量：按`xu_soc_activity.py energy`的manifest逐任务绑定真实coverage/SRAM review，最终计算`sum(P_task * duration_task)`。

所有`prepare`产物、输入source、原始映射/clock review及库身份在运行前后重新核对。工具源码修改后要重新prepare，禁止把旧netlist与新SDC/活动结果拼成同一候选。准备目录不覆盖现有log；失败后保留原目录用于审查，修正后生成新目录。

host guards复现：

```bash
python3 -m unittest discover -s tests/host -p test_xu_soc_ppa_flow.py -v
python3 -m unittest discover -s tests/host -p test_xu_soc_implementation.py -v
```

这些guards检查开发资格缺项、库角色/宏与层级守卫、错误/marker、Tcl错误停止及负hold/缺clock的报告状态；不模拟出任何DC/PT PASS。
