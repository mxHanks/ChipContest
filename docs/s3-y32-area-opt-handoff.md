# 64PE面积优化候选 handoff

2026-11-11。A/B的完整本机仿真与同条件综合输入已冻结；尚未根据实测面积/时序选型。软件联调继续使用已发布父d60e0e00d79051747b8adcfa39fca273a6e7e309、硬件子a80dd184536e0f2312c62768d5acf4ba1b01c34e；本轮没有改生产gitlink。

A是ACC41；B是ACC41＋引擎结果/FIFO41。均保留公开raw48和最终Y32，描述符/MMIO、数据布局、8行模式、fence、完成/错误排空、总线和CPU核配置均不变。完整99行任务、每任务独立参数、真实物理清零及响应退休规则保持。原软件启动步骤见[s3-y32-4k-handoff.md](s3-y32-4k-handoff.md)。

完整12任务均304,128个Y32逐位正确、428,915主周期（含12,336真实clear），gap516另列，含gap429,431，固件完整区间429,720。每层和所有等待/事务计数均与发布版一致；单行及source-stall控制一致。约4196.64task/s以假定150MHz换算，实际频率未认证。

[结果](s3-y32-area-opt-results.md) · [状态](s3-y32-area-opt-status.md) · [证据/复现包](validation/s3-y32-area-opt-20261111/README.md)。delta封存包包含607个文件，SHA885d595a33b6dbfb682f5e9555f15872ac63521654bcf0a3b36556cabbd028bd；从已发布baseline archive恢复A/B的源码/向量均已逐SHA核对。

服务器基线R5完成映射后卡在额外报告查询；保留原FAILED/1及owner-stop原件。完整回传未完成，VNC会话在认证前卡住，用户指示稍后重试；不更改凭据、不重启或终止他人资源。独立只读PT r4已完成且46项输出SHA核验通过，最差setup−10.668ns、hold−0.135ns，时序未闭合。A综合已于17:30:52启动（2核），B小包输入已逐SHA通过等待串行。完整leaf原件3小包均已回传并逐项独立重算通过。

继续执行时先读上海时间，不能在2026-11-11 23:59后启动新实验。先恢复原VNC，核对自有作业和映射原件；取metadata/关键报告，再以≤256KiB独立SHA文件返回所需大文件，每份核验落盘并断开，最后核对完整文件SHA。保留30MB原始archive，不从未完成102块拼装冒充原件。恢复后先运行严格PT recovery r3，再按单作业≤2核串行候选A/B综合，保留相同compile/SDC/DB/宏及计费边界。

PPA准备包位于本地build/area-opt-20261111：A candidate-synth-a-r1/candidate.tar.gz（SHA26d4f1c17ba76223e94d5c2e0100a9b32f1886feca7c74d548e3c116408aa7b7），B candidate-synth-b-r1/candidate.tar.gz（SHA41c474f5cbc35870995773867c8a6921ed9f0ef41c954d8aebcbe5369e4c7c09）。PT恢复包pt-recovery-r3.tar.gz（SHA48d23086cfb268894584d357c9dbc54116ab709c75c92ec53c8b85ce609afba1）。仅宽泛报告查询在映射后明确标记缺项，时序路径约束未修改；需独立PT补查。

候选最终选型须依照实测映射面积和关键路径；声明位数减少448/1792位不等于面积收益。比赛2.25mm²上限、官方SRAM计价/库面积单位、实际150MHz和平台宽口资格仍未验证。等同条件结果选型后，再安装唯一硬件版本、固定父子提交并更新GitHub正式handoff；当前本轮候选尚未推送。
