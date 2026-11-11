# 64PE面积优化候选 handoff

2026-11-11 18:45（上海）。A/B完整本机仿真均通过，同条件综合及独立PT报告采集均已在服务器实际完成。候选原件回传中断，尚未完成独立PPA审计、选型或生产安装；本轮最终硬件版本尚未发布。实验进度已推送并核验：[实验进度分支](https://github.com/mxHanks/ChipContest/tree/codex/s3-y32-area-opt-20261111)，证据节点[576c944](https://github.com/mxHanks/ChipContest/commit/576c9442808482990480ccc85460c13cca5d762a)。其中包含冻结输入、原始证据及接续工具，不能据此替换软件联调版本。软件联调继续固定已发布父`d60e0e00d79051747b8adcfa39fca273a6e7e309`、硬件子`a80dd184536e0f2312c62768d5acf4ba1b01c34e`，生产gitlink保持。

A为ACC41；B为ACC41＋引擎结果/FIFO41。均保留公开raw48和最终Y32，描述符/MMIO、数据布局、8行模式、99行尾部、fence、完成/错误排空、总线及CPU核配置不变。每任务独立参数、真实物理清零和全部写响应退休规则保持。软件接口与启动步骤继续使用[s3-y32-4k-handoff.md](s3-y32-4k-handoff.md)。

完整12任务均304,128个Y32逐位正确、428,915主周期，其中真实clear12,336拍；gap516另列，含gap429,431拍，固件完整区间429,720拍。第0层35,742拍，其余11层各35,743拍；每层周期和全部工作/等待/事务计数与发布版一致。单行及source-stall控制也一致。约4196.64 task/s仅按假定150MHz换算，实际频率未认证。

[结果](s3-y32-area-opt-results.md) · [状态](s3-y32-area-opt-status.md) · [证据/复现包](validation/s3-y32-area-opt-20261111/README.md)。已封存607文件仿真delta包，SHA256 `885d595a33b6dbfb682f5e9555f15872ac63521654bcf0a3b36556cabbd028bd`；用已发布baseline archive恢复A/B源码/向量均已逐SHA核对。保留测量当时父子身份，不能用当前HEAD改写历史结果。

已核验的48位基线计费面积为523,712.858238库单位（标准逻辑368,187.943200＋17个内部SRAM155,524.915038），完整leaf已独立重算。原DC在映射后卡住的额外查询由负责人停止，保持原FAILED/1和owner-stop记录；mapped.v/ddc尚未在本地逐字节核验。基线只读PT r4全部46项输出已核验，setup−10.66794014ns、hold−0.13472039ns、211项违例，时序未闭合。旧recovery r3预检失败已被r4实际取证取代，不需要重跑。

候选A/B均已串行完成正常映射和PT采集，每项最多2核。A屏幕原生面积初值515,134.996638库单位，约比基线小1.64%；候选leaf未回传审计，因此不能将其写成已验证面积优化。B也已完成，但面积和候选时序数值未完整回传，暂不据此选型。compile、原SDC、DB、158条源路径、宏数量和计费范围保持同条件；映射后省略的两条额外宽泛查询明确记录缺项，未删除或放宽时序约束。

当前阻点是证据回传：r3原件压缩包6,260,784B、24个独立SHA分片，仅第0、1片完整；第2片25/32块后超时。完整包SHA为`4fc0a9ae3c1ae54f9e080f5ed1202a2c7862dbe9d8c44edfbc7df9f06679ca6b`，索引SHA为`7a8bd98cec644708c54a3e40064c72197fa09869314da9b74ae8618ed7a94054`。不得把未完成分片拼装成可审计原件。VNC多次TCP成功却未返回RFB握手头；用户指示等会重试，不更改凭据、不重启或终止他人资源。

恢复时按以下顺序接续：

1. 读取上海时间和自有会话状态。2026-11-11 23:59后不得启动新实验；当前无需重跑综合或PT。
2. 核对本轮自有scratch记录、服务器已完成的A/B execution、映射输出及PT输出身份。优先继续已验证分片的原件回传；若通道仍不稳定，使用已准备但尚未执行的`build/area-opt-20261111/prepare-candidate-reports-only-r4.sh`只读提取所需报告。保留r3原始包和全部传输失败，不覆盖旧证据。
3. 每片落盘检查SHA和字节数，所有片及完整包核验通过才安全解压；独立重算leaf面积并审计PT全部输出。审计入口是`build/area-opt-20261111/audit/audit_native_area.py`及`audit_candidate_pt.py`，后者使用`--variant a|b --native PT目录 --dc-native DC目录 --prepared build/area-opt-20261111/pt-recovery-r4 --area-audit 面积审计回执 --out 新回执`，不运行EDA。PT采集完成和时序闭合分别判定。
4. 用已完成完整12任务证据和同条件面积/时序审计结果选型。安装与发布前使用`build/area-opt-20261111/finalization/README.md`及只读`verify_install.py`绑定实际CPU源和安装SHA。候选仅替换硬件子仓库`rtl/e203/perips/LinearTileDmaCore.sv`；默认generic叶模块、CPU、固件、仿真observer和PPA声明前移main副本不安装。父仓库对应5份生成器源码补丁已准备，尚未应用。
5. 选型后再建立新子分支、提交唯一硬件版本，固定父子提交并更新GitHub handoff。先推子分支再推父分支，保留d60e0e0/a80dd184回退，不创建未经请求的PR。本轮最终硬件版本当前未选定、未发布；仅发布实验进度分支时，应明确其供查看证据和接续实验，不能标为生产定稿。实验进度的已核验节点见本页开头；最终硬件提交仍待选型和安装。
6. 临时VNC状态v5尚待恢复：本轮启用SendCutText=1，原值0。`build/area-opt-20261111/restore-owned-bridge-v5.sh`已准备，受当前VNC阻塞尚未执行；恢复连接后先核对自有进程/记录，只恢复本轮状态，并在交付或长期停止前关闭自有辅助连接。

实际输入为`build/area-opt-20261111/candidate-synth-a-r3/candidate`与`candidate-synth-b-r3/candidate`，242项远端manifest SHA分别为`228b0c936d6e23db99d25bbb0c32596a12e8f2f8a9a4606342ec175ca73001c1`、`a6ac0c36ecf3616cee2aa80b547f187929b48ec01fa1b4df6a50145d81a9cf3c`。只省略两份不参与编译的大XML证据，完整243项及原XML仍在本地并有独立绑定证明；不能把早期r1运输包当成实际测量输入。

比赛2.25mm²上限仍需官方SRAM计价和面积库单位证据；平台宽口资格、实际150MHz也未验证。最终交付必须分别说明功能/周期、面积收益、时序及正式资格，不得把报告采集完成写成时序通过或正式成绩。
