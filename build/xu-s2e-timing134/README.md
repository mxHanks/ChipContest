# xu134：S2e自己原网表的时序/电气/reset独立修复实验

本包仅为本地准备及host检查。没有执行服务器DC/PT/FM，没有S2e时序通过或比赛资格结论。
全部输出状态保留`NOT_QUALIFIED`。只允许创建
`~/Desktop/xu-score-optimization-20261102/s2e-own-timing-repair-20261105-134`及其launch目录；
已存在则拒绝，不覆盖89、109、116、130及其能量输入。

适用性：116可复用的是受限原生检查/删除算法与五个精确reset端点的拓扑检查，
不能借用它的mapped、SVF或`default→08→09→49→50→63→73→79→95→116`证明链。
116起点95已经独立做过hold、gating、max-cap和1404单元清理；S2e89没有这些祖先。
S2e89原propagated负slack不能用116的有限ideal/forwarded场景替代。

运行134会依次：

1. 重新冻结S2e自己的89/109收据、main `5bf123b…`、child `a0767d…`、实际4138份验收、
   159份原FM输入、两份原DB及原150MHz SDC；own mapped必须为`0cfac0b5…`，
   own default.svf必须为`1a00803e…`。保留89原driver FAIL及109独立审计。
2. 在自己的89原网表运行新的DC拓扑/库表及PT精确电气/setup/hold/coverage/reset诊断。
   不从baseline的17/1404等计数选择单元。
3. 从自己89做原生`compile -incremental_mapping -only_hold_time`，内部gating hold目标
   0.12ns；输出自己的`hold.svf`。然后再次独立DC/PT盘点。
4. 仅对新PT测出的max-cap选择同family、同pin集合、至少5%负载裕量的实际库候选；
   每项在DC再检查pin/function signature、`get_alternative_lib_cells`原生兼容和许可。
   没有合法候选、格式变化或超过边界则停止，保留诊断。
5. 对实际min-cap、完整输出均无接收者、`is_sequential=false`、无inout且owner唯一的
   初始单元做原生复核后删除；最多24轮/8192单元，只向上游扩展。每轮全部预检后才修改。
   三个历史PLIC unused priority寄存器若在S2e仍存在，**不会删除**：它们不满足非时序门槛。
   其余有接收者/shared owner/未知分类的min-cap亦保留到`unresolved_mincap`，不造负载。
6. 从新PT再次核对真实库`CLKINV0_12TR40`的dont_use=false及I/ZN拓扑；在S2e自己网表
   精确核对五reset端点的ref、唯一owner、单原driver。每端点插4对反相器，共40单元；
   原生验证每条8单元纯串链、每段无额外接收者、原driver不变。任一检查不满足即停止。
7. 对**同一最终mapped/SVF**运行原SDC/原scope的PT和完整原RTL的own FM。唯一SVF链是
   `[own89/default.svf, own134/hold.svf, own134/repair.svf]`。不得借用116或其它分支。

所有PT都从原SDC重新建立0.1ns gating check；0.12ns只影响内部修复，不写入或放宽最终分析。
沿用SHA `45037c4a…`的既有有限scope（70个精确first-D及6个forwarded clocks），
保留全部coverage和异常报告。新的native原89盘点在第一次修改前完成；posthold新盘点在
选择max-cap和dead cell前完成，所有原件与生成脚本均before/after重哈希。

即使DC/PT/FM运行均正常，最终仍为`EXECUTED_OWN_S2E_SAME_MAPPED_DC_PT_FULL_FM_NOT_QUALIFIED`。
`remaining_electrical`、`timing`、`reset_paths`与完整coverage必须逐项审查；没有自动“0违例”晋升。
缺失recovery路径记录`NO_PATH_UNKNOWN`。未测macro模式/脉宽、UART、reset/RDC、
真实CTS、SRAM黑盒内部、全SoC能量及数值比赛资格均不能由本实验推导。

## 服务器输入及启动

将整个本目录上传到例如`~/Desktop/xu-s2e-timing134/`，保持四个Python脚本和reset Tcl相邻。
只读缺项检查与完整before检查分别为：

```bash
python3 "$HOME/Desktop/xu-s2e-timing134/xu_s2e_timing134_readonly.py"
python3 "$HOME/Desktop/xu-s2e-timing134/xu_s2e_timing134.py" --preflight-only
```

完整preflight不调用EDA、不创建134结果目录。默认精确服务器输入：

- B=`~/Desktop/xu-score-optimization-20261102`。
- B/`ChipContest-s2e-74`完整冻结S2e source；main/child工作字节、模式和gitlink检查。
- B/`ChipContest-s2e-activity-tools-109`干净、已提交的冻结工具；关键helper按本包SHA检查。
- B/`s2e-ppa-campaign-20261104-89`完整原件，包括`ppa/{mapped.v,default.svf,constraints.sdc,mapped.sdc,prepared.json,execution.json,rtl.f,dc.log,rtl/**}`和完整`formality/**`。
- B/`s2e-own-formality-audit-20261104-109/state.json`及其中所有frozen输入。
- 109记录的原89工具checkout（`ChipContest-s2e-ppa-tools-89`）、原4138文件验收目录，
  两个DB正文及其原绝对路径，均由实际109重审强制核对。
- `~/Desktop/xu-ts16.tcl`完整原scope，SHA `45037c4a36a41ec1e9184b90d84160835112f5738d53aadea9d0cb89524ad76e`。
- `/eda/synopsys/{dc/dc_2022.03-SP5-5,prime/prime_2022.03-SP5-1,fm/fm_2020.09-SP5}/bin/*_shell`和原LC环境。

本地没有这些服务器正文与EDA安装；`local-missing-server-inputs134.json`是本地缺项事实，
不能当作服务器缺项。不能只传receipt而缺DB/RTL/验收正文。新native own89和posthold
库存是运行产生的前置证据，尚不存在，不把baseline库存冒充它们。

服务器完整preflight通过后，一次性分离启动：

```bash
python3 "$HOME/Desktop/xu-s2e-timing134/launch_timing134.py"
```

launcher固定worker/reset SHA；先完整只读preflight，再建立独立launch目录，记录PID和命令。
只有spawn不代表完成。读取新134的`state.json`及各阶段完整日志；失败或运行中不得重启覆盖。
worker支持显式`--source/--tools/--original/--audit/--scope`以定位同一原件，固定输出名称/父目录和
全部身份守卫不会因此放宽。默认launcher不接参数。

## 本地验证

```bash
python3 /home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-s2e-timing134/check_host134.py
```

实际19项host检查通过：严格native cap解析/重复与格式拒绝、实测负载裕量、非时序/唯一owner/
全部输出无接收者门槛、顺序单元保留、原生sizing兼容门槛、五精确reset对、Tcl完整结构。
另用真实归档09的1460项和116的0项电气报告验证解析器格式；它们只作为parser样本，
没有被用作S2e选择输入或证明。`hostchecks134.json`明确不声称执行native S2e修复。
