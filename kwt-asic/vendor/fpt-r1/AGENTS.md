# 声算 FPT 本科赛题工作区

先读00_START_HERE.md、PROGRESS.md、DECISIONS.md和赛题范围，执行tools/verify_bundle.py核对导入材料。用户当前目标是本科KWT-1前馈线性加速器，不能从旧FPT文档推断为继续四簇GQA或原服务器任务。

- reference/是保留字节的参考。新实现放src/model/sim/soc/constraints等目录，记录来源与修改；不要直接改参考文件来使旧测试通过。
- 原因果、GQA、RoPE、S=D=128、AMD浮点和DDR接口不是本题既定要求；位宽和数值策略由精度/面积实验证据选择。
- 仿真mock不是可综合RTL；外部路径仅是来源。没有依赖时明确NOT_RUN，不伪造PASS或复制旧成绩。
- 大行为仿真优先Verilator/C++；适当保留四态检查。一个代理推进；新的并行或重任务须按届时用户授权与资源情况决定。
- 未授权连接/操作原FPT远端运行、硬件编程、push或Git提交。新比赛源码/模型的本地编辑与验证按用户任务推进。
- 在PROGRESS.md记录明确目标、实际结果、缺项和最多五个下一步；DECISIONS.md区分Accepted/Proposed。功能、数值、SoC、综合、时序、功耗分别报告。
