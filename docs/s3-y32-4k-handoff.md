# 64 PE／真实64位搬运候选联调 handoff

2026-11-10。本交付为 **64 PE＋共享W/bias＋真实64位搬运的仿真定稿**。主仓库和硬件子仓库通过独立分支发布，16PE联调版作为回退保留。
用户指定本轮先本机仿真，达到瓶颈后定稿，再集中综合；今天23:59上海时间停止新增实验。
最终功能、周期、面积、时序、正式资格分别判定，不用其中一项替代其他项。

## 版本与选择

- 回退：父 `655713b304597ca5b2810a0940ac3f1850072d63`，E203子 `45e61b6101ad6f0aaa7583098294ffb1550f1f2d`。
- 候选硬件：E203子分支 `codex/s3-y32-4k-candidate`，提交 **`a80dd184536e0f2312c62768d5acf4ba1b01c34e`**。
- 主仓库发布分支 [`codex/s3-y32-4k-goal`](https://github.com/mxHanks/ChipContest/tree/codex/s3-y32-4k-goal)；硬件发布分支 [`codex/s3-y32-4k-candidate`](https://github.com/mxHanks/e203_hbirdv2/tree/codex/s3-y32-4k-candidate)。本轮发布已获用户明确授权，主仓库以gitlink固定上述硬件提交。
- 新构建同时定义 `XU_MATRIX_DMA`、`XU_MATRIX_DMA64`。不定义新宏时保留原默认／32位DMA接口。四个修改模块在这两个旧构建模式的预处理代码均与回退一致。
- 42个CPU核文件逐文件SHA无变更；CPU、LSU、BIU及原在途配置不改。

## 获取交付与结果等级

```sh
git clone --branch codex/s3-y32-4k-goal --recurse-submodules https://github.com/mxHanks/ChipContest.git ChipContest-4k
cd ChipContest-4k
git submodule status
```

硬件子模块应固定在`a80dd184536e0f2312c62768d5acf4ba1b01c34e`；按主仓库gitlink检出，不用子仓库的后续分支头替换本次证据对应版本。

- 完整CPU12任务：304,128个Y32全部正确，含真实clear共428,915拍。
- 按假定150MHz换算：4,196.64task/s；含gap4,191.59；CPU固件完整同步区间4,188.77。
- 同源独立重建复测一致；这些是功能/周期证据，**面积、实际150MHz时序和正式比赛资格未验证**。
- [完整结果](s3-y32-4k-results.md) · [原始日志及审计](validation/s3-y32-4k-20261110/README.md) · [正式验收待办](s3-y32-4k-acceptance.md)。

## 可下载复现包

[封存包 frozen-delivery.tar.gz](validation/s3-y32-4k-20261110/frozen-delivery.tar.gz)，5,656,296B，438个文件；包含冻结RTL、固件ELF/image、12组向量、原始日志、工具身份、必要补丁及未执行的综合输入包。

SHA256：`464bea138c254d842b1db656da0e8feb42e04e509f9ab85d92e0cd30736b543f`。

以下步骤只验证交付身份，不启动仿真或综合：

```sh
sha256sum docs/validation/s3-y32-4k-20261110/frozen-delivery.tar.gz
mkdir -p build/4k-handoff
tar -xzf docs/validation/s3-y32-4k-20261110/frozen-delivery.tar.gz -C build/4k-handoff
python3 -B build/4k-handoff/delivery-final-r2/REPLAY.py
```

包内CPU RTL/ELF/image/原始可执行模型与已经独立重建复测的版本一致。`REPLAY.py`默认仅核对哈希；本轮用户要求先发布、不继续测量。未来显式`--run`才仿真，`--rebuild`还会重编冻结RTL，需要另行明确新的实验时间范围。包内文档保留封存时状态，最新发布说明以本handoff及仓库结果页为准。

## 硬件顶层接入

1. 同时定义`XU_MATRIX_DMA`与`XU_MATRIX_DMA64`，编译`rtl/e203/perips/`中的新模块和原有生成依赖。新增入口为`xu_matrix_dma64`、`xu_dma64_shared_arb`、`xu_shared_icb_sram64`、`LinearTileDmaCore`及`TileWeightBankArray`／`TileWeightBank`／`TileXRowBuffer`。
2. 将`e203_soc_top`的`EXTERNAL_SYSMEM`设为1，连接`ext_sysmem_cmd/rsp`：地址32位、数据/响应64位、mask8位，并传递新的`ext_sysmem_cmd_is32`。CPU32事务的半字选择与mask由外围适配保留；DMA内部宽事务的is32为0。
3. 真实共享端点使用SoC导出的`shared_mem_clk`和`shared_mem_rst_n`，与受测外围保持同一时钟/复位合同。共享容量512KiB、256宏不变，64深度bank×4条16位lane；一次DMA事务同时访问4条lane。
4. [CPU测试台](../experiments/s3-y32-4k/validation/tb_dma64_soc.sv)包含完整功能接线；[集中综合包装](../experiments/s3-y32-4k/ppa/xu_soc_dma64_ppa_top.sv)提供无测试host的端点连接示例。后者目前只做过本地接口预检，不代表综合或时序通过。

旧默认构建及32位DMA构建使用原路径。软件联调应明确选中新构建及真实共享端点，再按下述ABI提交任务；不得把开发用HOST ready/ACK握手当作新生产端口。

## 固定数据合同

每任务 X[99][64]×W[64][256]+bias[256]，共1,622,016次完整MAC、25,344个Y32。
X/W signed16、bias signed40、内部signed48及最终RNE(acc/512)不变；最后99行的尾tile只计算3行。
每任务真实清零并重新装入独立参数。全部输出写响应退休后才完成，首次错误中止并排空，不自动重试部分写回。

保留原共享内存源布局：X每32位槽低16有效，W每32位连续两个INT16，bias每64位槽为符号扩展40位，Y每32位一个结果。
描述符必须8字节对齐且位于0xa0000000～0xa0080000；Y不得与X/W/bias重叠。
默认地址X=0xa0000000，W=0xa0008000，bias=0xa0018000，Y=0xa0020000。
宽口在一次物理访问中处理两个32位字，不在末端拆成两次串行事务。

## 软件启动顺序

1. 将该任务独立X/W/bias提交到真实共享存储，执行 `fence iorw, iorw`。
2. MMIO基址0x10042300，写CTRL(+0x04)=1，轮询STATUS(+0x08)：ERROR为0且BUSY为0、CLEAR_DONE为1。
3. 写+0x10/+0x14/+0x18/+0x1c四个描述符地址，再执行fence。
4. 写CTRL=0x802启动8行模式；CTRL=2是同搬运路径的一行对照。
5. 轮询STATUS，先检查ERROR；只有BUSY=0且DONE=1才可读取输出。再次fence，随后消费Y。
6. 出错读取+0x0c错误码（1=总线响应错误，2=bias内部提交错误），停止提交并终止本任务；继续等待BUSY=0，确认硬件已排空承诺/在途事务。重新运行必须先完整清零，不能在BUSY仍为1时立即重试CLEAR或START。

STATUS bit0=BUSY、bit1=DONE、bit2=ERROR、bit3=CLEAR_DONE。ID(+0x00)=0x444d4131。
新构建CAPABILITY(+0x4c)=0x00084001：最大8行、总线64位、原X32槽布局。
该寄存器只在已知新构建中读取；旧模块该偏移未定义，不可无异常处理地盲探。
旧双行CTRL=0x102应与旧构建配套；旧接口回退通过保留的旧构建实现。
完整固件示例见 `experiments/s3-y32-4k/validation/dma64_main.c`。
示例HOST ready/ACK仅为公开fixture握手，不属于生产任务协议。

## 硬件资源与观测

64PE=8行×8列，共享一套16颗W宏和1颗bias宏；共享512KiB仍256颗宏，仅重排为64深度bank×4条16位lane。
X双缓冲2KiB；两槽raw48结果768B；DMA另有256位Y快照、40位bias暂存、64位停顿请求数据及地址/控制元数据。
CPU32通过外围仲裁保留高低半字和mask语义。DMA保持一笔有序在途请求，无CPU内部扩容。
所有受测外围和真实共享端点使用同一导出的fabric时钟/复位。

每任务真实DMA事务：W4096读＋bias256读＋X3168读＋Y12672写，共20,192次接受和响应；3168次八结果POP。
8行模式MAC step=26,624；一行模式202,752。
清零逐地址核对W16,384＋bias768＋X1,024，共18,176个16位写，并检查ACC、结果、FIFO、缓存和DMA快照归零。
+0x38仅统计W/X共17,408次，不能将它当全部物理清零工作。

## 当前证据及不能借用的结论

- 核心单元完整12层304,128个raw48结果通过，背压、1～8行、尾行、极值、复位/中止通过。
- 真实256宏通道通过，W/bias4352次64位读用5078拍，持续吞吐约1.167拍/64位事务。
- 同最终RTL的DMA模块R2完整12层304,128个RTL Y32通过；模块计数428,905拍，不能冒充CPU完整12口径。末Y响应真实扣留97拍期间不提前完成；读/写错误、复位、持续背压通过。
- CPU R1单任务含真实clear=35,742拍，gap43另列，全部25,344Y32通过公开写/读回核对；按假定150MHz约4,196.74task/s。
- 最终CPU R2完整12任务已通过：304,128个精确Y32，主周期428,915拍、含gap429,431拍；逐层35,742/35,743拍均低于37,500。最终权威结果见 `docs/s3-y32-4k-results.md`，不使用模块计数替代。

本轮目标：CPU完整12主周期≤450,000，各任务≤37,500；gap及CPU同步另列。
旧16PE基线1,514,236拍、约1,188.72task/s（同样按假定150MHz）。
面积≤2.25mm²、实际150MHz完整STA、库面积单位/SRAM官方计价、共享宽口修改的正式平台资格仍待验收。
任何未完成项均不能写成已通过；无新面积或实现频率结论。探索阶段未启动综合。

## 复现入口

- 核心：`experiments/s3-y32-4k/core/README.md`。
- 真实通道：`experiments/s3-y32-4k/fabric/README.md`。
- DMA模块：`experiments/s3-y32-4k/dma-test/README.md`。
- 真实CPU：`experiments/s3-y32-4k/validation/README.md` 与 `run_cpu.py`。
- 执行合同：`docs/s3-y32-4k-goal.md`，技术计划：`docs/s3-y32-4k-plan.md`。
- 原件：`build/parallel4k-20261110/`，每轮独立目录，不覆盖旧日志。

输入/输出/程序/模型/源码/工具身份以各轮receipt和冻结source为准，不凭当前HEAD猜测旧运行身份。
CPU公共fixture写入、输出毒化及逐字公开读回均排在既定计时窗口外；完整参数/X/Y受测DMA访问、真实clear计入主口径。
ITCM程序预加载是沿用的启动装载例外；任何任务张量或结果不允许层次写DUT数组。

本轮交付边界经用户明确：等待现有服务器仿真结束，本轮先交付仿真定稿。综合/STA输入已准备，尚未执行；若待服务器空闲时已超过今天23:59，不能自动开启新的实验。

最终原始寄存器/缓冲账本见 `experiments/s3-y32-4k/inventory/README.md`：总30,993bit，较回退净增21,580bit，SRAM容量不增。该值只用于资源清单，不能当面积结果。
