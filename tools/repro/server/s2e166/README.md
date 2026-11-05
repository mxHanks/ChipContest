# xu: S2e155 同图全 SoC 功耗接续166

状态：本地可执行 adapter；未部署、未运行服务器 PT，不含新的能耗结论。
本目录只服务用户保留的 S2e 主方案，S2c 仍独立验收。所有输出强制
`NOT_QUALIFIED`；native PT 成功和诊断能量不能解除 SRAM 未知 Q、条件功耗模式、
完整150MHz时序覆盖和门级功能方面的资格缺口。

`power166.py` 提供同一条 `prepare → verify → run` 路径；`campaign` 顺序完成准备和运行。
支持 `--task-ids 0` 原生 preflight，以及 `--task-ids all` 的完整12层；full12必须提供已真实
成功的 `--preflight-root`。该先验重新检查task0的实际PT日志、完整报告SHA、原输入前后SHA、
同capture和同target身份；失败或仅准备完成的task0不能触发full12。每项保存
`result.json`、`prepared.json`、`execution.json`、`summary.json` 和原日志报告。

身份与方法的守卫：

- 原`frozen130.py`逐字节保留 SHA `95caa5fab255c5126e5b51f6f0b06c9bf63283f9bbf89dd310202abc87515d46`。
  调用原130完整capture守卫，逐层重放120原始SAIF归一化；实际109工具、生产源、固定四张量、
  固件、仿真选项、窗口及own89/109完整FM均重新检查，未修改原模块全局或文件。
- capture始终是120/own89/109，原映射SHA `0cfac0b5…`。target单列155终态
  SHA `3474d4aa…`，最终网表`3440182e…`，own89→155hold→155final三段有序SVF。
  155的204冻结输入、原134五阶段接续、155三次native及完整42,338点FM均从原件核查。
  155 FM脚本必须与own89完整模板按这三SVF/目标图精确重建后逐字节相同。
- 使用155原SDC及冻结`xu-ts16.tcl` scope，显式去掉130的全时钟propagated覆盖。
  inventory和power均从固定模板语义重建；报告保留实际时钟、单位和活动来源。
- 对155独立运行原生336宏/22,512pin inventory，再把完整capture测得pin activity逐位映射到该图。
  mapping双射、实际库绑定、TX/TZ/TB与时间窗须不变；没有重新运行仿真或初始化DUT。
- 面积取155自己原DC层次报告：加速器`0.3003096339 mm²`，全SoC`3.373696204286 mm²`。
  2.25mm²限制只和加速器子树比较。禁止将旧130能量拼接155面积。

服务器复现命令（仅由既有campaign154总控注册启动，避免重复native）：

```sh
# B = /storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102
# D = /storage2/2026contest/server4/s4_23usr/Desktop
python3 -B "$D/xu-s2e-final-power166/power166.py" campaign \
  --activity "$B/s2e-formal-activity12-20261105-120/result.json" \
  --source-root "$B/ChipContest-s2e-74" \
  --tool-root "$B/ChipContest-s2e-activity-tools-109" \
  --ppa-root "$B/s2e-ppa-campaign-20261104-89" \
  --formality-root "$B/s2e-own-formality-audit-20261104-109" \
  --target-root "$B/s2e-own-timing-repair-20261105-155" \
  --task-ids 0 --out "$B/s2e-final155-power-preflight-20261105-166"

python3 -B "$D/xu-s2e-final-power166/power166.py" campaign \
  --activity "$B/s2e-formal-activity12-20261105-120/result.json" \
  --source-root "$B/ChipContest-s2e-74" \
  --tool-root "$B/ChipContest-s2e-activity-tools-109" \
  --ppa-root "$B/s2e-ppa-campaign-20261104-89" \
  --formality-root "$B/s2e-own-formality-audit-20261104-109" \
  --target-root "$B/s2e-own-timing-repair-20261105-155" \
  --task-ids all --preflight-root "$B/s2e-final155-power-preflight-20261105-166" \
  --out "$B/s2e-final155-power12-20261105-166"
```

`--formality-root`已按原130 prepared核对，是自己的109根，不能借baseline。
其余默认PT/LC路径与服务器原工具链相同；CLI会重新检查实际文件、SHA和工具版本。
preflight success=`EXECUTED_TASK0_DIAGNOSTIC_NOT_QUALIFIED`，full12 success=
`EXECUTED_12_DIAGNOSTIC_NOT_QUALIFIED`，任意失败=`FAIL166_NOT_QUALIFIED`。
总控依赖必须按成功状态触发，`process_contains`用各自唯一输出路径。

本地复核：

```sh
python3 -B build/xu-s2e-final-power166/test_power166.py
python3 -B build/xu-s2e-final-power166/verify_manifest166.py
python3 -B build/xu-s2e-final-power166/power166.py --help
```

33项hostchecks覆盖actual159的155终态、原生FM统计、原89→155精确FM模板、面积解析、
模板时钟/双射几何、负向守卫、task0/full12合成worker生命周期与失败后停止。
模板测试使用明确标识的本地占位`.db`，从不启动EDA；生命周期测试用模拟执行器。
它们不代表服务器inventory/映射/功耗通过。完整服务器preflight及full12仍待真实执行。

原生每层`sram-pins-{before,after}.rpt`可很大；各报告以流式SHA/逐行诊断扫描，未在主runner
中一次性载入完整大报告。所有原报告保留，实际未知Q不得以native`x_probability=0`改称已知。
失败目录不覆盖、同一输出不重启，使用flock拒绝同目录同时执行。不存在自动绕过失败、恢复native
中断或宣告评分资格的分支。没有新增生产Chisel、RTL、MMIO ABI或数值格式变更。
