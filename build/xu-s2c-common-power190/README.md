# xu S2c common clock-method power190

本目录只为用户保留的 S2c 对照方案增加一次共同分析方法的功耗实验。没有修改生产
Chisel、RTL、固件、向量、MMIO ABI、数值格式、SDC、库、功能模型或测试平台。
所有终态仍是 `NOT_QUALIFIED`。当前为本地实现/host checks，尚未运行服务器190。

旧57的 S2c 与旧130的 S2e 都使用 all-clock propagated 方法。新166对 S2e final155
改用原404c7d SDC、primary-clock contract 检查和45037c forwarded-clock scope。
因此166不能直接和旧57算能耗降幅。190保留 S2c own9c16 网表与原57活动，单独重新
测量这个共同 clock method；它不借用 S2e 映射或功能证明。

`power190.py campaign --task-ids 0` 先做真实 task0，只有成功且原件重核通过后才允许
`--task-ids all --preflight-root ...`。完整12层与 task0 使用同一个 runner，失败保留，
输出必须是新目录，没有 restart/resume 覆盖路径。同目录 flock 拒绝并发执行。

输入和输出守卫：

- 冻结原57 prepared `cb363beafeac51329aab8f04843999021c17cf05dd22a1d1f3ee505ceb70a103`
  和 execution `45acb972f44b2a3009dca012836db6f2bde0a95d1de538d085fa27f882c6a3b9`。
  367项原输入，以及自己的 PPA source files、FM frozen inputs、脚本、日志和面积报告实际重核。
  这些是本次实验使用的文件身份检查；没有声称重新证明完整 Git 工作树或官方资格。
- 自己的原42338点完整 FM 日志、SVF/映射冻结回执和 PPA execution 相互绑定。面积来自
  own9c16 原报告：加速器 `0.2948018380 mm²`，全 SoC `3.365797600429 mm²`；
  2.25mm²只约束加速器面积。原FM条件和原mapped VCS fatal仍保留。
- 新 native PT inventory 在共同 clock method 下重新导出336宏/22512 pins，严格等于
  原20的完整 TSV/JSON（包括文字中的点、方括号、方向和实际库绑定），不作 dot→slash 猜测。
- 各层原 mapped SAIF 逐字节复制，SHA必须不变。完整22512 measured pin集合、每位
  T0+T1+TX+TZ+TB=6604373333334fs、未知bit-ticks重算；所有12层仍有5280个Q带TX，
  其中4256个Q整窗TX。TC=0或native x_probability=0不能改称已知物理Q。
- 每层原57 Tcl只允许三处精确变换：allprop/update变为166相同scope/update、SAIF
  路径指向逐字节副本、completion marker变为本次唯一值。其余原方法字节保留。
- 真实 native PT版本/rc/唯一marker、全27份报告、before/after完整22512 pin与336宏
  名单均检查。大报告流式扫描和SHA，不整份载入内存。超时保留pid/命令/实际rc/log身份。
- 结果保存 `prepared.json`, `execution.json`, `summary.json`, `result.json` 与
  `output-manifest190.json`；失败也生成清单。原任务990656 cycles及真实窗口用于P×t，
  不外推task0为完整12层、不含测量窗外33697次clear写的能量。

服务器只由现有153总控注册并启动，不直接手动运行。部署目标改为新的 `~/Desktop/xu-s2c-common-power198/`，旧190目录不覆盖。部署文件恰为下面9个：

```text
power190.py
frozen130.py
references190.json
run190.py
jobs190.py
command-preflight190.json
command-full12_190.json
manifest190.json
frozen-fm190.json
```

`run190.py` 在同一PID内执行冻结命令，进程原argv只含本job唯一输出路径，避免full12的
preflight参数被总控误认为另一个活进程。两个job均native=true，沿用总控单槽：
`s2c_common_preflight190` 等 `s2e_coverage186` terminal，
`s2c_common_full12_190` 等 task0 success。不增加许可证并发，不重新启动166或177。

固定输出：

```text
B=/storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102
B/s2c-common-scope-preflight-20261105-190
B/s2c-common-scope-power12-20261105-190
```

可审查的底层复现命令（实际调度仍交原总控）：

```sh
python3 -B "$HOME/Desktop/xu-s2c-common-power198/power190.py" campaign \
  --task-ids 0 --out "$B/s2c-common-scope-preflight-20261105-190"
python3 -B "$HOME/Desktop/xu-s2c-common-power198/power190.py" campaign \
  --task-ids all --preflight-root "$B/s2c-common-scope-preflight-20261105-190" \
  --out "$B/s2c-common-scope-power12-20261105-190"
```

`B`须在所用shell中按上方绝对路径设定；服务器tcsh建议由总控读取JSON而不粘贴shell变量。
默认PT和LC均为同一服务器原路径。唯一成功状态分别为
`EXECUTED_TASK0_COMMON190_DIAGNOSTIC_NOT_QUALIFIED` 和
`EXECUTED_12_COMMON190_DIAGNOSTIC_NOT_QUALIFIED`；失败
`FAIL_COMMON190_NOT_QUALIFIED`。

本地复核：

```sh
python3 -B build/xu-s2c-common-power190/test190.py
python3 -B build/xu-s2c-common-power190/check_metadata190.py
python3 -B build/xu-s2c-common-power190/power190.py --help
```

19项host checks包含实际69/22原件的12层Tcl逆变换逐字节相同、原native日志、未知Q统计、
负向守卫、报告完整性、超时回执和明确标注的合成生命周期。`check_metadata190.py`额外把
返回的69/09/22实际元数据联接；未返回的服务器文件hash被明确mock，这一步仅检查字段
兼容，不能冒充服务器输入重hash或EDA执行证明。服务器190结果仍待总控真正执行。

`make_manifest190.py`只用于经审查后主动重建本地冻结命令/manifest；不部署、不自动调用。


198接续修正：192在任何注册动作之前严格SHA检查发现 live aggregate
`candidate-formality-campaign-20261103-01/state.json`已改变，因此未注册任何job。
现在把09已归档的原始whole-state正文逐字节放入`frozen-fm190.json`（349702B，SHA
`dadd3bb693a3ae17bf92682d9586fa1ba07e6ead468465e07b67fa91eabea5dd`）。
references保留原路径/SHA的历史身份，但不再把可追加的live汇总文件列为冻结输入。
新的隔离198 runtime自身严格冻结该正文；ownS2c原run、native日志、SVF、mapped9c16、
所有原RTL及面积证据仍独立实际重hash。没有使用新汇总state替换历史证明或放松SHA。
job IDs与输出190目录均不变；新的entry/command/job frozen bytes必须重新审查后登记。
外部冻结清单另无可变汇总state；57的terminal capture23 result仍按原6eea4b… SHA严格核对，
如果该原件变化仍会拒绝，不会自动忽略或恢复。
