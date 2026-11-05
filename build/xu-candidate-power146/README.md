# xu 通用全SoC功耗实验146

此入口接入统一总控150，覆盖inventory137冻结的八个候选：`baseline_h1_h2`、`s1_h2_only`、`s1_sram_bias`、`s2b`、`s2d`、`pe32`、`pe64`、`compact32_128`。每个候选依赖自己的138 freeze/ownFM adoption和完整145原始12层活动结果。脚本只用Python 3.6+标准库，不联网、不改RTL、宏模型、MMIO、格式、向量、网表、SDC或DB。

本地host checks通过仅表示脚本边界已检查，不能当作服务器PT、150MHz时序、SRAM功耗模型或比赛评分通过。成功终态为`EXECUTED_12_DIAGNOSTIC_NOT_QUALIFIED`；失败为`FAIL_DIAGNOSTIC_NOT_QUALIFIED`，日志保留。TX/TZ/TB及IG全部保留。原生`x_probability=0`不能证明物理Q已知；能量始终标记诊断值。

## 依赖与数据流

部署目录旁须有冻结的`xu-profile-activity145`完整bundle。146调用145只读验证，重新解析原始模拟日志、物理清零证据和逐层窗口，重新执行raw→normalized SAIF无损归一化。随后在同一服务器PrimeTime T-2022.03-SP5-1及LC_ROOT下读取本候选selected ownFM网表、同一SDC和SS DB：

1. 原生枚举完整SoC的RAMSP1024X16及RAMSP128X16实例和每个物理bit pin（分别67/64位），与实际RTL elaboration inventory建立全量双射；缺失、重复、多余、ref/group/pin差异均失败。
2. 仅按每个实际native宏的字面层次名迁移对应SAIF pin；不对网表或无关SAIF名字做全局点号替换。全部非迁移记录和所有统计值保持不变。
3. 每个原始层独立运行PT，输出全SoC功耗、层本身测得的duration×功耗诊断能量和逐pin原生before/after属性。未知输入不转成零，也不晋升资格。
4. 大型pin属性报告按行流式解析、hash和存储原始byte范围；紧凑JSONL保留每个pin块SHA、getter分类、原始SAIF统计和source driver定位。报告原文不删改。
5. 面积从本次selected网表实际链接的全部leaf和libcell area重算，分别列出全SoC及精确`u_accel_icb_slave`子树。2.25mm²诊断比较只使用加速器子树；S2d/PE32修复网表不拼接历史面积。采用库area单位为µm²的既有约定，未推断布局/填充/布线面积。

每层`task_XX/result.json`、`pt.log`、`native-state.json`、原始reports、`native-before.jsonl`、`native-after.jsonl`、`native-audit.json`保存原件及SHA。顶层`prepared.json`保存完整冻结输入及复现argv，`execution.json`保存前后SHA、12层状态，`summary.json`保存逐层cycles/W/J及本图面积。初始preflight失败也写终态回执；重复campaign拒绝改动原尝试。

## 日常入口由150统一调度

先本地核对bundle：

```sh
python3 -B build/xu-candidate-power146/check_bundle146.py
python3 -B -m unittest discover -s build/xu-candidate-power146 -p 'test_*.py' -v
```

生成八份150注册JSON（只生成，不启动、不注册）；路径替换为服务器绝对路径，`receipt-snapshot`使用已验证149下载原件：

```sh
python3 -B build/xu-candidate-power146/build_jobs146.py \
  --bundle-root /SERVER/Desktop/xu-candidate-power146 \
  --activity-tools /SERVER/Desktop/xu-profile-activity145 \
  --output-root /SERVER/Desktop/xu-score-optimization-20261102/eight-candidate-power-20261105-146 \
  --activity-root /SERVER/Desktop/xu-score-optimization-20261102/eight-candidate-activity-20261105-145 \
  --freeze-root /SERVER/Desktop/xu-score-optimization-20261102/eight-candidate-freeze-queue-20261105-138 \
  --receipt-snapshot build/xu-score-resume-20261103/queue149/eight-candidate-freeze-queue-20261105-138 \
  --jobs-out /FRESH/power-jobs146
```

生成器冻结146/145全部bundle字节及真实138回执SHA。每个job的`process_contains`是自己的唯一output_root，依赖`eight_freeze138`和对应`activity145_ID`成功。总控150统一限制native cap=1，资源不足等待，不宣称许可证有余量。失败候选保留原件，其他独立候选仍可续行。把生成的`power146_ID.json`逐项交给150已有`register --out ... --job ...`入口；无需再手动启动worker。

## 单候选复现、恢复与独立审计

完整原命令还保存在每个`prepared.json.reproduction`和生成的`power-plan146.json`中：

```sh
python3 -B /SERVER/Desktop/xu-candidate-power146/power146.py campaign \
  --profile s2d --freeze-receipt /FREEZE/s2d/freeze.json \
  --adoption-receipt /FREEZE/s2d/adopt-own-fm.json \
  --source-root /EXACT/INVENTORY137/SOURCE \
  --activity-root /ACTIVITY145/s2d --activity-tools /SERVER/Desktop/xu-profile-activity145 \
  --out /FRESH/POWER146/s2d
python3 -B /SERVER/Desktop/xu-candidate-power146/power146.py verify --out /POWER146/s2d
python3 -B /SERVER/Desktop/xu-candidate-power146/power146.py resume --out /POWER146/s2d
python3 -B /SERVER/Desktop/xu-candidate-power146/power146.py audit --out /POWER146/s2d --audit-out /FRESH/AUDIT146/s2d
```

`prepare`只准备全12层并运行原生inventory；`run`从准备件开始；`campaign`依次执行两者。`resume`只复用严格一致的既有成功层，观察记录PID/start ticks的仍存活native进程。死去的不完整native尝试不自动重跑；原日志保持。若退出码因父进程中断不可得，必须有唯一guarded native完成标记、无native错误且报告齐全，恢复回执明确标注退出码来源限制，状态仍为诊断。总控自身对孤儿任务不自动重启，需检查原件再决定恢复。

`audit`只读原始12层native报告，在新目录独立重放流式审计并对照每层诊断，既有compact文件也不覆盖。正式150MHz STA、RDC、综合后完整功能和SRAM未知活动问题另由资格链继续处理；本工具不宣称这些门已解除。
