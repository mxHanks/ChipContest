# 64PE 原SystemBus32整改版：紧凑证据快照

本包保存**已执行的本机功能和开发精度证据**。选定硬件 child `bde23ba9d06c57f6536d9992b3cd3427daccd9f8`，文档/验证工程 parent `c3c8eb53b4d6a13fa1f0b9997088cf5515b8999e`，分支 `codex/s3-y32-compliance-20261113`。它不是全资格签核包；新PPA和官方统一样本结果不在本包中。

## 已经证明的范围

| 项目 | 本机实测 |
|---|---|
| 真实公开音频导出12任务、真CPU装载/调度/读回 | 304,128个Y32逐位一致；3,568,690拍，包含真实clear、全部source载入、CPU调度/等待/衔接 |
| 首source VALID至末Y写响应 | 3,556,103拍；source载入1,515,973拍、真实clear12,336拍、DMA窗口2,039,579拍 |
| 分层 | 第0层297,389拍；其余11层各297,391拍；开发整数向量与真实音频向量逐层周期相同 |
| 两个首请求等待用例 | DMA首读/加载source首写分别延迟31拍，各297,423拍；完整等待计入，输出正确 |
| 真实清零 | 每任务W16,384＋bias768＋X16,384＝33,536次16位实际写零；非零前态、缓存/状态/暂存观察器通过 |
| X SRAM候选 | 核心60组合、DMA完整12、读写错误、末Y响应扣留97拍、三阶段在途复位后换参数完整恢复76,032输出 |
| 公开600开发精度 | 599原validation WAV＋1显式合成零silence；12层182,476,800值；最大层NRMSE0.0131066%，最大单样本层0.0195337%；fsum独立重算一致，无裁剪 |

吞吐约 **504.3868 task/s** 仅以150MHz假定换算。没有使用旧DMA64的约4k结果；未通过同版本STA前不能称实际150MHz频率。公开600为自选开发数据，**不是组委会统一600验收**。600评测执行软件数值模型；硬件执行其中固定导出的12个性能任务，不声称硬件已跑完600×12任务。导出12任务最大NRMSE为0.0133897%。

生产选择同时定义 `XU_MATRIX_DMA`、`XU_MATRIX_DMA_SYSBUS32`、`XU_MATRIX_X_SRAM`；外部32位/mask4，CPU/DMA与验证source均经原SystemBus/mem_fab/共享端点。生产禁止DMA64和测试loader端口。64PE为8行×8列，共享W/bias；99尾行3路。X有效2KiB、物理32KiB，内部宏33、PPA全SoC宏353。FIFO5248bit、bias预取640bit仍是实际数据暂存，未假定小缓冲有规则豁免。

## 内容和边界

`evidence.tar.xz`解开后包含：

- 两套12任务向量、唯一冻结CPU source182文件及小型ELF/image；保留source/ELF/image/向量/模拟器和工具版本身份，模拟器二进制不打包。
- CPU单层、完整12、真实音频完整12和两项wait31的原始simulation.log/result.json；DMA错误/复位/背压日志、核心60例日志/收据及小型恢复实际输出。
- 原600条逐样本误差记录、12/600开发评测收据、样本清单、环境重建/变量恢复与公开归档来源校验。
- parent/child补丁、parent提交时的验证工程快照、安装/选择清单、结构检查、旧弱日志被当前门槛拒绝的记录。
- 官方规则提取文字及SHA身份；`qualification-status.md`逐条列18问和本科要求的证据与缺项。

没有音频归档/WAV、venv/TF安装、FST、庞大编译目录、EDA工具/库或凭据。完整推理复现需按已封存音频/模型SHA取得原始依赖；组件和CPU向量已经包含。补丁用于审阅和恢复字节，不能假定重新`git am`后committer身份与Git对象SHA必然相同。`repository-snapshot`固定为parent c3c8eb5，不包含之后PPA启动器修订；新PPA结果另行归档。

旧 `final-audit-r1` 和 `historical-parent-docs`是历史原件，生成时尚未完成的CPU12/音频链/安装等描述不改写；最新事实以本快照的实际收据和逐条状态表为准。

本机活动工程实际含289个RAMSP模型＋2个CPU逻辑RAM接口，PPA配置含353宏。CPU64宏活动映射、全SoC功耗和能耗尚未验证，不能把已有FST当353宏功耗结果。所有新增逻辑和内部33宏都应计费；named charge和全SoC标准单元＋33宏保守上界是两个独立口径，不可相加。面积单位、官方宏价、≤2.25mm²、完整150MHz STA、综合后功能与最终官方样本仍待验证。

## 复核与复现

在本目录先校验外层归档，然后安全提取到新目录：

```sh
sha256sum -c SHA256SUMS
mkdir extracted
tar -xJf evidence.tar.xz -C extracted
python3 -B verify_evidence.py extracted/evidence
```

`verify_evidence.py`先检查包内逐文件SHA和大小，再用封存CPU强门槛解析原始日志并逐字段核对保存的结果；核对同一source/binary/ELF/向量身份、物理clear、完整事务、等待和计时边界；最后对原600误差记录重新fsum聚合。**此复核不运行新的仿真/推理，也不证明新的STA、面积、等价或功耗。** CPU逐位一致是原测试台完整公开读回比较的结果，复核器不从日志重建每个硬件输出。

新的CPU实验可在对应仓库与工具环境中按`repository-snapshot/experiments/s3-y32-compliant32/validation/README.md`执行：

```sh
python3 -B experiments/s3-y32-compliant32/validation/run_cpu_xmacro.py \
  --out build/compliant32-reproduce-task0 --tasks 1 --rows 8 --warmup --jobs 2 \
  --vectors PATH_TO_EXTRACTED/evidence/build/compliant32-20261113/numeric/public-validation-600-evaluation-r1/vectors
python3 -B experiments/s3-y32-compliant32/validation/run_cpu_xmacro.py \
  --out build/compliant32-reproduce-full12 --tasks 12 --rows 8 --warmup --jobs 2 \
  --vectors PATH_TO_EXTRACTED/evidence/build/compliant32-20261113/numeric/public-validation-600-evaluation-r1/vectors \
  --replay-from build/compliant32-reproduce-task0
```

这些是未来复现命令，不是本打包过程新执行的实验。原运行的完整参数、编译命令和版本保存在各result.json。冻结源码在`build/compliant32-20261113/cpu-public-audio-full12-r1/source/`；最新硬件/软件交接应随新PPA完成后再次定稿，不能把本功能证据快照冠以“全部合规通过”。
