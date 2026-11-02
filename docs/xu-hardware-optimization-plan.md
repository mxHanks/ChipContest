# xu 硬件接口优化实施计划

本轮在已验收的软件最优版本上独立评估两项硬件扩展：H1 完整 bias 缓存、H2 固定连续结果窗口。先分别与同一 B0 比较，再测试组合；以同服务器真实12层总周期和完整 VCS 验收决定是否保留。新增寄存器扩展现有 ABI，旧地址、旧固件及其数值语义继续兼容。面积、时序和功耗另按实际证据交付，不用仿真周期代替 PPA。

## 1. 工作树与 B0

- 本轮工作树：`/home/mxhanks/Projects/ChipContest-xu-optimize-hw`，分支 `codex/xu-optimize-hw`，从 `499ba54bd57db81c058ab5efe25def226ec6dd15` 创建。
- B0 执行源码为 `8a7640787423a73a0751454de47893406f85e604`；`499ba54` 仅在其后加入软件实验与验收交付证据。B0 配置固定为 **`bias-dtcm / -O2 / both-unroll-no-masks`**。
- B0 真实12层总周期为 **25,251,416**：layer0 为2,104,281，layer1–11各2,104,285。完整软件阶段 VCS 验收与独立重放均通过，304,128个结果、608,256次输出写字逐字正确。证据见[软件阶段交付](validation/xu-fw-optimization-20261102/README.md)、[原始最终结果](validation/xu-fw-optimization-20261102/server-json/acceptance/real12/result.json)。
- B0 E203 gitlink 为 `e36d34a52e6eef93fd0bdfed1b13009e1056bea3`；后续硬件子模块修改必须在带 `xu` 的功能分支提交，主仓提交对应新 gitlink，同时保留其与 B0 的差异。
- 原 `/home/mxhanks/Projects/ChipContest`、`ChipContest-platform-eval`、`ChipContest-xu-optimize-fw` 与原服务器副本、历史证据保持原状态。新增实验使用独立副本及不存在的输出目录，不覆盖旧日志。

早期 `f0f27b4` 的28,416,892周期只作历史软件参考；本轮硬件收益一律以25,251,416周期的 B0 为分母。先复核已归档原B0的原始结果、完整日志哈希和加载镜像，再在新RTL上以旧接口模式重放全部B0层，核对逐层周期、镜像和执行文件身份；不一致时先定位，不进入硬件收益判定。不为相同历史证据额外重跑原RTL。

## 2. 不变边界与允许扩展

固定8 PE、signed16 X/W、signed40 bias、signed48 Y和精确整数累加，不改变舍入/饱和规则。固定原始48个向量文件、W bank 映射、99行×32组调度、每组64个MAC有效拍、每任务重新装载W/X/bias、层间不复位，以及完整Y退休后ACK。保持W/X行缓冲、MAC流水、任务数、共享RAM、全局modulo-7背压、TB时钟和ITCM装载方式。

主指标仍为每任务首次共享输入/参数读取接受至最后Y写响应退休，12个窗口求和。缓存上传、控制写、CPU搬运与全部新增任务准备均在该窗口内；H1上传放在完整W装载之后、首行X装载之前。不得把上传或缓存使能预放到TB装载阶段以获得收益。原首个W_BANK/W_ADDR两笔写仍按原边界排除。

允许在原4KiB MMIO窗口内增加下列地址，原`0x000–0x03c`全部保持原义。未在本轮定义的偏移仍沿用原读0、写忽略行为。统一使用4字节对齐的32位访问；新增寄存器的有效位、字节掩码、复位值、busy写入行为和读回语义须在实现及接口文档中逐项固定并测试，不引入未记录的自增或隐含提交。

| 偏移 | 扩展 | 本轮约定 |
| --- | --- | --- |
| `0x040` | CACHE_CTRL | 选择完整bias缓存路径；固件上传前写0，上传后写1。复位必须默认关闭，使旧固件无需变化即可工作 |
| `0x044` | CACHE_ADDR | 选择完整bias缓存中的列0–255；逐列显式写，不使用地址自增 |
| `0x048` | CACHE_LO | 所选列bias的bits31:0 |
| `0x04c` | CACHE_HI | 所选列bias的bits39:32，写数据低8位有效；缓存保留精确signed40位模式 |
| `0x050` | CAPABILITY | RO，统一扩展能力常量 `0x58550003`；固件使用对应能力检查，不用该常量替代实际功能回归 |
| `0x080 + lane*8` | RESULT_WINDOW_LO[lane] | RO，lane=0..7，当前8路结果的bits31:0，地址解码固定选择lane |
| `0x084 + lane*8` | RESULT_WINDOW_HI[lane] | RO，bits47:32零扩展到32位；最后地址为`0x0bc` |

连续窗口是旧结果寄存器的固定地址别名，不移动结果、不自动递增、不弹出结果，也不暗含START/ACK或额外状态转移。旧RESULT_INDEX/LO/HI继续可用，并应与窗口对同一组结果逐字一致。连续窗口高字仍须由固件执行signed16→signed32扩展，不改变Y格式。

## 3. H1：独立完整 bias 硬件缓存

以Chisel为新增硬件的可维护源，生成SystemVerilog后接入E203。建议以独立缓存/包装模块连接原计算核，保留原8槽bias输入作为兼容路径；不手工修改生成RTL来代替Chisel实现。完整缓存逻辑容量为 **256×40=10,240 bit**，可按8 bank×32列组组织，使`group*8+lane`的8个signed40偏置同时可用。实际寄存器/存储器推断方式及其复位、读延迟和面积以生成与综合结果为准，不能把逻辑位数直接当作SRAM宏面积。

新缓存只取代每组的bias MMIO装载，不改变原点积核的X/W/乘加/结果链。缓存使能后，group选择对应8个bias；确保原INIT周期所需bias稳定，不因缓存增加未计入的启动拍或错组数据。上传期间关闭缓存路径，每任务覆盖全部256列后才使能；禁用时8槽旧路径、旧BIAS_INDEX/LO/HI读写和旧程序保持原行为。

H1固件调度为 **`bias-hw / -O2 / both-unroll-no-masks`**：

1. 原ID/busy/能力检查与完整W装载后，在计时窗口内写CACHE_CTRL=0。
2. 对列0..255逐列写CACHE_ADDR，然后从`const volatile`共享bias读取低/高原始字并写CACHE_LO/HI，共512次共享读、768次缓存上传MMIO写。
3. 写CACHE_CTRL=1，然后按原row→group遍历；每行装X、每组设置GROUP、W1C、START、带超时轮询，结果仍使用旧8次INDEX/LO/HI回读路径。
4. 不使用2KiB bias DTCM副本，不依赖上一任务或夹具常量；不同时启用H2。`BIAS_UNROLL`在硬件bias路径不生效，但保留同一源码及已固定的编译优化配置。

至少覆盖缓存关闭的旧路径、所有列与组边界、signed40最大/最小/正负值、高字符号位、低/高字写入顺序、复位默认、连续两任务bias不同，以及上传后改GROUP时的选择。新增控制busy行为须明确测试，旧地址busy写语义不随本轮修改。

## 4. H2：独立固定连续结果窗口

H2固件调度为 **`bias-dtcm-window / -O2 / both-unroll-no-masks`**，继续使用B0的2KiB DTCM bias缓存及每组旧8槽bias装载，禁止同时使用H1上传路径。每组done后按lane0..7读取固定窗口低/高字，保持每lane `LO读→Y低字写→HI读→符号扩展→Y高字写`，Y地址严格递增。

窗口响应必须遵守原ICB单响应槽的接受/退休时序，受阻时数据和valid稳定；同拍退休旧响应并接受新命令时，响应数据属于正确的被接受地址。固定lane来自本次命令地址，不依赖RESULT_INDEX残值。检验连续读取、乱序直接地址读、旧/新读口交错、lane0/7边界、写窗口无作用、busy/done变化与连续任务结果更新。

H1、H2分别完成synthetic2、本地real1和服务器real12后，才运行 **`bias-hw-window / -O2 / both-unroll-no-masks`** 组合。两个独立实验均与同一B0比较，组合再与较优独立项比较；没有收益、回归或失败均保留记录。最终配置必须同时正确且总周期严格较低；若均无收益则保留B0。

运行期可让同一份扩展RTL同时具备两种硬件能力，通过固件调度分别启用：B0-new-RTL关闭缓存并保留旧结果读口，H1仅启用缓存，H2仅用固定窗口，组合同时使用。此时独立性能实验衡量新接口路径的启用效果，不能据此声称独立硬件模块的PPA增量；实际PPA应将完整旧包装及计算核与完整新硬件比较，并明确两种门电路在所有运行中是否都存在。

## 5. 精确事务契约与观测器调整

每任务原窗口内MMIO写156,326由W32,774、X12,672、bias76,032、GROUP/W1C/START9,504和RESULT_INDEX25,344构成。H1以770笔写（CTRL两次+ADDR/LO/HI各256次）替代76,032笔旧bias写；H2仅去掉25,344笔RESULT_INDEX写。CACHE_CTRL两次均在窗口内，不能因阶段分类或报告漏掉。

| 每任务工作量/事务 | B0：bias-dtcm | H1：bias-hw | H2：bias-dtcm-window | H1+H2：bias-hw-window |
| --- | ---: | ---: | ---: | ---: |
| W / X / bias共享读 | 16,384 / 6,336 / 512 | 相同 | 相同 | 相同 |
| 共享读总计 | 23,232 | 23,232 | 23,232 | 23,232 |
| 旧bias槽MMIO写 | 76,032 | 0 | 76,032 | 0 |
| 完整缓存ADDR/LO/HI写 | 0 | 768 | 0 | 768 |
| CACHE_CTRL写 | 0 | 2 | 0 | 2 |
| RESULT_INDEX写 | 25,344 | 25,344 | 0 | 0 |
| 窗口内MMIO写总计 | **156,326** | **81,064** | **130,982** | **55,720** |
| 结果MMIO读（不含轮询） | 50,688 | 50,688 | 50,688 | 50,688 |
| Y共享写字 / 输出数 | 50,688 / 25,344 | 相同 | 相同 | 相同 |
| START / done | 3,168 / 3,168 | 相同 | 相同 | 相同 |
| MAC有效拍 / MAC总数 | 202,752 / 1,622,016 | 相同 | 相同 | 相同 |

MMIO总读仍包含实际STATUS轮询，不能固定为B0的76,032次；能力检查若同原ID/busy检查位于首W读前，明确记入固件指令与mcycle身份，不混入窗口事务。完整12层共享读为278,784、Y共享写字608,256、输出304,128、MAC有效拍2,433,024及MAC总数19,464,192；四配置MMIO写分别为1,875,912、972,768、1,571,784、668,640。

现有TB只识别旧bias写`0x028/0x02c/0x030`和RESULT_INDEX写`0x034`开始writeback，直接运行扩展会使阶段归因错误。新增观测仅识别新事件，不能驱动DUT或改变总窗口：

- H1的`CACHE_CTRL/ADDR/LO/HI`写归bias阶段，上传源共享bias读也沿用bias分类；建议该阶段从CTRL=0接受开始，至CTRL=1响应退休结束，使上传与使能控制均被覆盖。不能仍按旧BIAS_INDEX=7结束缓存上传阶段。
- H2读取`0x080–0x0bc`的对齐窗口地址时进入writeback；只靠旧RESULT_INDEX写将漏掉窗口路径。最终每组Y写响应退休仍结束writeback，沿用既有共享响应元数据。
- 响应元数据仍先处理旧响应退休、后记录同拍新命令；不能把当前寄存器索引误当退休命令的索引。新增缓存阶段收尾同样携带被接受命令的元数据。
- 如果包装模块改变MAC层级，只更新观察路径到相同8 PE共享使能；不改变有效拍定义。保留busy、done、START、共享/MMIO stall和六阶段互斥覆盖检查。
- 观测器更新后先证明B0总周期与原阶段统计不变。报告注明扩展地址的分类规则和TB哈希；阶段仅辅助归因，不将其误称为纯传输时间。

运行器、摘要及完整验收共享新增schedule及工作量契约；旧baseline/bias-dtcm历史报告继续可复算，未知schedule或计数错配必须失败。硬件实验需要独立执行身份：B0子模块pin、候选子模块pin、Chisel源/生成RTL/安装RTL/TB/固件/脚本/向量/工具哈希，以及显式调度和编译参数，不能沿用软件driver“全部RTL必须等于f0”的旧冻结检查冒充硬件比较。

## 6. 实验与验收顺序

1. **B0复核**：原RTL及最优固件的历史原始JSON、日志哈希与镜像已归档，先核对这些身份。然后在扩展RTL上关闭缓存、使用旧结果读口，以原配置运行B0-new-RTL synthetic2与real12，必须逐层复现25,251,416周期和历史加载镜像SHA256。ELF完整字节及SHA256继续记录，但不要求与历史相同：编译器临时`FILE ccXXXX.o`符号可能不同而不改变加载镜像。公开此兼容回放及与原RTL历史B0的关系；再跑原SoC五项确认旧ABI兼容。新RTL若导致B0周期变化，先定位原因，不将变化隐藏在H1/H2收益中。
2. **硬件生成与定向检查**：运行Chisel缓存/包装模块测试及原计算核回归；生成RTL并记录工具、命令、源/输出SHA。生成物接入子模块并提交，禁止只有工作区覆盖而缺可恢复源。H1、H2地址/握手/符号边界定向测试独立通过。
3. **契约与本地回放**：运行host/numeric/固定12层整数核算和doctor；分别对H1、H2、组合跑连续synthetic2和real1。合成任务bias按层变化，防止陈旧缓存；每个任务仍校验全量Y顺序和退休。本地周期仅辅助筛错。
4. **同服务器独立A/B**：继续用SiFive GCC-Metal10.2.0-2020.12.8 CentOS6子集、VCS Q-2020.03-SP2-6、同夹具与激励，串行跑B0→H1→H2→组合real12。只在不存在的目录输出，不并发操作同一`make install`目录。每项公开所有12层差值、总周期、事务、阶段及代码/内存大小，按总周期严格排序。
5. **最终验收**：选中配置执行完整服务器host、numeric、真实12层整数核算、doctor、旧SoC五项、synthetic1、连续synthetic2和real12；再显式生成性能摘要，并核对最终real12与选中实验逐层一致。失败项和未运行项单列，不能只凭核心单测或单层宣布保留。

新增CLI须先实现并用`--help`核对。计划中的schedule已确定，候选调用形态如下；`xu_hw_prefix`和输出目录按本次实际服务器环境指定，所有`--out`必须尚不存在：

```bash
python3 tools/scripts/e203_soc.py --mode real --tasks 12 --sim vcs \
  --cross-prefix "$xu_hw_prefix" --out "$xu_hw_h1_out" \
  --firmware-schedule bias-hw --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks
python3 tools/scripts/e203_soc.py --mode real --tasks 12 --sim vcs \
  --cross-prefix "$xu_hw_prefix" --out "$xu_hw_h2_out" \
  --firmware-schedule bias-dtcm-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks
python3 tools/scripts/server_accept.py --sim vcs \
  --cross-prefix "$xu_hw_prefix" --out "$xu_hw_accept_out" \
  --firmware-schedule "$xu_hw_selected_schedule" --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks
python3 tools/scripts/xu_perf_report.py \
  --result "$xu_hw_accept_out/real12/result.json" --frequency-mhz 150 \
  --out "$xu_hw_accept_out/xu-performance.json"
```

在运行器明确支持新schedule前，这些只是接口约定，不能当作已运行命令。最终交付记录实际命令而不是计划变量占位；必要时增加专用硬件campaign driver，不能让原软件driver把新RTL当作冻结软件实验。

## 7. PPA 条件与最终交付

功能与周期收益不等于面积/功耗或150MHz时序闭合。H1增加10,240bit逻辑容量及读选择逻辑，H2增加固定地址结果选择；必须评估实际综合存储类型、组合路径和开关活动。只有在同一源范围、标准单元/SRAM库、PVT/RC、时钟/IO约束和活动/功耗方法下，对B0与候选完成可复现综合/STA/面积或功耗流程，才报告相应增量。

现有`area_eval.sh`的Nangate45开发综合、历史core-only工艺报告和开发行为RAM各有适用范围，不能作为完整E203平台的正式PPA。若正式库/宏/约束不可用，交付已测开发综合及其范围、时序风险和未运行项目，不编造官方宏面积、功耗或全平台时序结论。150MHz继续只作条件换算。

最终交付包括带`xu`的主仓及子模块提交、每项父提交/硬件启用范围/固件配置、B0与候选逐层/总周期/速度比、阶段和事务数、ELF/ITCM/BSS/静态栈、Chisel与生成RTL一致性，以及全部原始日志位置和SHA256。共享上传成本计入总窗口；未通过或无收益的独立项说明原因。若仍受FTP下载限制，保留服务器原始全文及哈希，原始JSON字节副本、屏幕传输、派生收据/摘录/汇总分别标识，沿用软件阶段的证据边界。

本计划不把后续DMA、X/W地址自增、外层硬件调度或PE扩展混入H1/H2。若需要这些变化，应另建独立实验和接口版本。
