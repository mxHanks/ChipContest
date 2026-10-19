# SRAM Adapter的核心与ICB功能入口

本入口连接分阶段simulation源计划、原语/bank通过证据、真实线性核心与ICB协议回归。原计算RTL、Golden、旧TB、旧runner及旧backend配置保持不变；本入口不运行CPU、官方SoC或ASIC综合/PPA。

## 前置与运行

先用[原语/bank入口](OFFICIAL_SRAM_CONTRACT_RUNNER.md)产生同一清单/Adapter字节的完整报告，再交给新入口。`FILES_VERIFIED`只核材料文件，不允许跳过这个前置。

```bash
source env/activate.sh
# 当前真实包缺失：exit2/BLOCKED，不启动HDL
python3 -B scripts/verify/run_sram_adapter_system.py

# 当前工作区已接受的开发原语报告；开发夹具必须显式选择
python3 -B scripts/verify/run_sram_adapter_system.py \
  --development-adapter \
  --primitive-report artifacts/runs/20261018T051921.108279Z-official-contract-afdf0cfe/result.json
```

该开发报告不是源码包或其他电脑默认具备的文件。缺少时，先运行原语入口的`--development-qualification good`，把其输出的新报告路径传给`--primitive-report`；不得创建假的PASS报告代替。

真实文件到位后，依次运行：

```bash
python3 -B scripts/verify/run_official_sram_contract.py --manifest configs/official-sram-package.json
python3 -B scripts/verify/run_sram_adapter_system.py \
  --manifest configs/official-sram-package.json \
  --primitive-report <上一命令真实输出的result.json路径>
```

两条命令间不能更换清单、Adapter、功能源或被绑定的Wrapper/工具。helper重新核验canonical身份、全部原生状态/日志、8正常+15拒绝/8 binary及其当前SHA，精确核对同包与BACKEND=3编译参数；只改JSON的PASS字段不能通过。默认缺包、缺前置或损坏前置均不启动EDA。旧READY不被设置，旧选择器不因本入口改动。

`--suite core|icb|both`可选择范围，默认both。每次独立run保存源码/工具/前置报告身份，向量和binary在消费前绑定、结束复核；编译最多2线程，长命令有原生超时与退出记录。

## 实际执行范围

| 阶段 | 模型与数据 | 必要验收 |
|---|---|---|
| real12 | BACKEND3、双结果buffer/乘法流水；固定checkpoint对应12层参数及静音输入导出；Verilator两态 | 12×25344=304128逐位结果、12层装载切换、背压、3次reset/3类非法装载、内部读写守恒 |
| signed41-range | BACKEND3；精确41位累加两端点，Icarus四态 | 2×25344=50688结果及相同控制/队列检查；不是额外官方性能任务 |
| ICB | BACKEND3真实核心，旧bus stimulus：X/W全0、signed bias；Icarus四态 | 完整25344+abort4输出，86保持周期、命令/响应/reset丢弃总账、最终空状态 |

核心向量先由现有导出验证器重核原来源并重算Python Golden，再原字节复制到新run目录；极值向量由原数值模型生成。没有修改模型、舍入或把必需计算转移到软件。

旧ICB marker的25348为固定打印值，因此新增独立top直接观察真实posedge的`engine_y_valid&&engine_y_ready`。它还拒绝未知控制/有效payload及背压变化；末尾必须满足：

```text
accepted_outputs = 25348
response_holds = 原TB protocol_checks = 86
accepted_responses = 原TB transactions >= 193889
accepted_commands = accepted_responses + 1
reset_discarded_responses = 1
```

多出的一条命令是最后被reset丢弃的pending ID响应，不强行凑成命令响应相等。旧TB仍负责数据、index/last、LO/HI pop、abort、ACK和状态检查。ICB的零乘积向量主要证明协议；非零/真实参数计算由上面的核心阶段证明，不能称ICB已跑真实12层或CPU写回。

## 接受边界

开发模式BACKEND3内部仍是显式逻辑夹具，报告始终`official_validation=NOT_RUN`、`official_ppa=BLOCKED`、`cpu_soc=NOT_RUN`。真实源模式即使功能阶段PASS，也仅是所供模型和所测core/ICB功能，不证明供应商来源、全部模型行为、正式平台或PVT。

当前不支持的include/外部数据/SDF/DPI消费由材料helper保守拒绝，词法扫描不是完整HDL依赖闭包或安全证明。若真实模型读延迟或Q保持不同，应先正确适配并重验，不靠放宽检查。核心12层为静音smoke，非完整validation/官方600样本；RTL周期与ICB局部窗口不作为比赛完整性能。后续仍需真实宏、CPU/正式SoC接入、指定库/角及全路径150MHz、全部新增面积和完整窗口功耗。

## 本轮已执行结果

[来源索引](runs/sram-adapter-system-20261018.json)复核1346个唯一文件，原1096文件记录及索引本体不变；[独立审查](reviews/20261018-sram-adapter-system-review.md)重新核对原语前置、原生state/log、binary、48份真实复制向量和8份范围向量。4个CLI资格化及262项主机检查通过。完整开发入口完成304128+50688核心输出，ICB独立观察25348输出、193939命令/193938响应、86保持和1次reset丢弃。

另以独立四态小探针强制有效响应数据为X，以及在任务前提前`$finish`：两次原生exit1，首个故障分别由新monitor的UNKNOWN_RESPONSE_PAYLOAD和INCOMPLETE检出，均没有正常PASS。探针只验证这两条检查器路径，不进入正常源集。

真实12层Verilator构建保留76条WIDTHEXPAND、4条WIDTHTRUNC、4条UNSIGNED，共84条；未报告UNOPTFLAT或阻断错误。4条截断提示来自32位CHECKS参数作为逻辑条件，当前均取1；4条unsigned来自零容量段和BASE=0的常量地址比较。宽度扩展仍保留原报告，不声称lint零警告或全输入证明。Icarus另有7行constant-select sensitivity提示。当前通过的是所测数值/协议；原源及数值模型未为消除警告而改写，正式综合/库验收仍须独立进行。
