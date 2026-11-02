# xu 真实任务活动功耗复现

本轮已在服务器完成两侧VCS真实layer0和PrimeTime averaged活动功耗分析。旧硬件/软件B0为3.19450977 mW，新硬件/组合固件为12.28540200 mW；按各自显式任务窗口计算为44.81428678 µJ与112.68686701 µJ，均未节能。库、顶层和约束与[面积/STA](ppa-reproduction.md)相同，报告为布局前估算，限制见[主报告](README.md)。

实际服务器输入根为 `/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102`：

| 输入 | 旧硬件/软件B0 | 新硬件/组合固件 |
| --- | --- | --- |
| RTL/固件源码 | `8a764078` + E203 `e36d34a` | `97b35421` + E203 `f49a5fc` |
| mapped.v / mapped.sdc | `ppa/baseline-ss-01/` | `ppa/candidate-ss-02/` |
| 原始真实layer0 VCS结果/波形 | `activity-02/baseline/` | `activity-02/candidate/` |
| 150MHz派生波形 | `activity-02/baseline/activity-150MHz.vcd.gz` | `activity-02/candidate/activity-buffered-150MHz.vcd.gz` |
| 元数据 | `activity-02/baseline/activity-scale.json` | `activity-02/candidate/activity-buffered-scale.json` |
| 精确PT运行目录 | `activity-power-exact-01/baseline/` | `activity-power-exact-01/candidate/` |

每侧数值仿真独立验证全部输出、层计数器和加载镜像，必须与正式12层验收的layer0完全一致。原始4ns时钟、10ps VCD timescale的时间戳按5/3最近tick缩放；事件文本与timescale不变，舍入最多1/3 tick。基线PT窗口为 `{43596.67 14072130.0}` ns，候选为 `{29936.670000000002 9202356.67}` ns；它们是边沿差窗口，比inclusive性能计数少一周期。

精确报告Tcl使用 `read_vcd -rtl -strip_path tb_accel_soc/dut/u_e203_subsys_top/u_e203_subsys_main/u_e203_subsys_perips/u_accel_icb_slave`，限定上述时间窗口。运行 `report_power -verbose -significant_digits 8`，实际原文同时明确dynamic/leakage单位为1 W。普通低精度报告与精确单位复跑的输入不变；[独立核验](power-verification.json)检查了这一点。

在**仍保留冻结netlist、SDC、大波形和相同工艺库**的原服务器，用以下Bash命令重新运行PT，所有输出进入新目录。`xu_report`指向复制到服务器的本次报告。原Tcl使用固定绝对输入路径；不修改既有结果。

```bash
xu_report=/绝对路径/xu-hw-optimization-20261102-report
xu_power_replay=/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-power-reproduce-01
mkdir "$xu_power_replay"
export SYNOPSYS_LC_ROOT=/eda/synopsys/lib_compiler/lib_compiler_2022.03-SP5
export PATH="$SYNOPSYS_LC_ROOT/bin:$PATH"
for xu_case in baseline candidate; do
  mkdir "$xu_power_replay/$xu_case"
  cp "$xu_report/activity-evidence/power-exact-reports/$xu_case/power.tcl" \
     "$xu_power_replay/$xu_case/power.tcl"
  (
    cd "$xu_power_replay/$xu_case"
    pt_shell -f power.tcl > pt.log 2>&1
  )
done
```

检查两个`pt.log`的工具返回状态、独立行`XU_ACTIVITY_POWER_PASS`及任何`Error:`，保留新报告日期和SHA，重新核对单位、活动覆盖、时序coverage及两侧窗口。`report_power`的clock_network分组含寄存器时钟引脚，不代表已完成CTS。

若要重生波形，在新目录恢复[固定执行源码](README.md#固定执行源码的复现命令)。旧RTL观察副本须检出上表旧提交，仅对TB/runner应用交付的[legacy-observation.patch](activity-evidence/activity-02/legacy-observation.patch)；其原/新SHA见[observation-manifest.json](activity-evidence/activity-02/observation-manifest.json)。候选直接使用冻结97b3542。两侧的实际VCS命令与环境均保留在[原始活动作业状态](activity-evidence/activity-02/job-state.json)及各自result.json，可换成新输出目录复跑；核心命令为：

```bash
python3 tools/scripts/e203_soc.py --mode real --tasks 1 --sim vcs \
  --cross-prefix /storage2/2026contest/server4/s4_23usr/Desktop/xu-platform-eval-20261101-codex/sifive-rv32-c/bin/riscv64-unknown-elf- \
  --firmware-schedule bias-hw-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks --accel-waves --out /新的候选输出目录
```

旧观察副本用`--firmware-schedule bias-dtcm`。先核对新result的完整layer0和加载image，再用[buffered转换工具](activity-evidence/helpers/xu-hw-scale-vcd-buffered-20261102.py)生成新派生波形/元数据：

```bash
python3 "$xu_report/activity-evidence/helpers/xu-hw-scale-vcd-buffered-20261102.py" \
  /新的候选输出目录/tb_accel_soc.vcd \
  --simulation-log /新的候选输出目录/simulation.log \
  --out /新的候选输出目录/activity-150MHz.vcd.gz \
  --metadata /新的候选输出目录/activity-scale.json
```

两侧均可用该转换工具，gzip头和文件SHA可与旧慢速派生不同，但事件流、原波形SHA、时间窗口和数值验收须自洽。把**新副本**Tcl中的VCD路径和显式窗口换成新元数据；如同时重做综合，mapped.v/SDC路径也须指向新一轮同库结果，并记录全部SHA。

原始失败观察补丁、受控停止的慢速候选gzip派生、首次功耗流程及其后成功重跑均保留。交付helper原文中的历史目录有防覆盖约束，不能直接把历史`start`命令当作新输出复现。正式数值结果没有因派生处理停止而失效。

交付的[97份原始小文件包](artifacts/hw-final-artifacts-01.tar.xz)SHA为`936201546c84ca002e97f139f8c9b946ae897a7adb47d300ee9c5f4c7c91b7cd`，后续[精确功耗收据](activity-evidence/power-exact-state.json)SHA为`9418210a2a834d795d0877d8157106b3b7f638f71e819e10ee6799ff4364b6ed`。大VCD只留服务器，工艺库/厂家模型/手册全文不随仓库发布。

只核验现有交付字节、单位、输入身份、波形转换元数据和能量计算（不运行EDA）：

```bash
python3 "$xu_report/evidence-tools/xu_verify_power.py" \
  --report "$xu_report" --out /新的输出目录/xu-power-verification.json
```

该审计还读取相邻软件阶段报告的`server-json/acceptance/real12/result.json`作为旧layer0参照，复制报告时需保留两阶段目录关系。它不会把未取回的大波形误称本地全文核验。
