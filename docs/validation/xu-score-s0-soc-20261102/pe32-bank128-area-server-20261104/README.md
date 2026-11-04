# xu：紧凑32PE权重小宏的实际面积

指定库综合的新增**加速器、接口和内部SRAM面积为0.5752035631mm²**，占2.25mm²上限25.5646%；完整SoC单元面积为3.646156552727mm²，范围不同，不能与加速器预算直接比较。

同服务器原32PE/1024宏组织为0.5186033811mm²。紧凑128宏组织面积增加 **10.913963%**，两者完整12层开发周期均为11376501。因此这次物理W容量从64KiB降到32KiB没有换来面积收益，尚不能决定全SoC能量的取舍。没有按容量减半推算面积，也不将小宏候选记为最终保留项。

实际DC在综合前后、PT在链接后各核对四组宏：ITCM32、DTCM32、共享256个RAMSP1024X16；新增W为128个RAMSP128X16，共448宏。W为32个bank，每bank四片128×16，逻辑与物理均32768字节、无padding。三个真实库角色和固定SHA在原implementation中，SRAM仅进入link库，标准单元target库独立。

主仓固定`f75880d4f06ccb7f1c16115bee501f53d9a2abb7`、child固定`52cfbea1f79f10e44f7d1696f54015797f886b96`；actual PPA producer固定`24567100fd02a7b7350ba877b7bb0ba7ebf36be0`，源profile为`s3-pe32-bank128`。完整2637个源blob/mode/链接与gitlink的不可变Git复核及指定模型VCS、三项完整12层对照见[前置验收](../../xu-score-s3-pe32-bank128-server-20261103/README.md)。本目录复制其源清单和复核receipt，并将PPA完整主/子树摘要与之再核对。

生产Chisel变更为`src/main/scala/GenerateRTL.scala`、`src/main/scala/linear/XuParallelCore.scala`、新增`src/main/scala/memory/Sram128x16.scala`；原32PE默认组织保留，同步返回选片及1周期读延迟保持。PPA用与指定宏direct完全相同的128 SRAM adapter，SHA `13e1077201f8eb751d34eee718b34d350cc5dfbc58cf0d853933b010c29faa79`。

## 资格边界

原网表SHA256 `7a69a1219561ca7a2e162ac84007f9fb32f34264132d1e6999e34c990cabe628`；分析SDC为`404c7de9a4ef56d624e64407a501df63d8040159171ea2a88bfcc70294a3de98`。工具为DC T-2022.03-SP5-5、PT T-2022.03-SP5-1。原始全propagated、未CTS视图max/min slack为−22.328501/−26.211073ns；364509个检查中235855 met、96510 violated、32144 untested。check_timing、全部coverage、负slack和不支持的`report_exceptions -verbose`原诊断保留，不能将工具退出0解释为150MHz合格。

本次尚无该候选映射网表的Formality或完整工艺宏全SoC回放，也没有同配置全SoC单任务能量。此前指定128宏定向VCS不是SRAM内部等价证明或mapped完整SoC运行。尚未证明的mapping/时序资格按原execution列出，没有使用原32PE、baseline或wrapper的功耗替代。

## 哈希与复现

原export53为1128868字节，SHA256 `13ee20401b85fd3d7d241e77fa8dca908e73b02d08c90687265ec953e6af9f05`，全部168项逐项验证后只选择本候选81项原件，共65887582个原始字节。大文件仅作可逆XZ压缩，`selected-manifest.json`同时记录存储和原始身份。164个prepared源文件身份全部在原receipt中，其中25份正文被取回重新哈希；其余正文未冒称下载。一个clock collector的constraints报告未导出，明确列于verification；主STA及其他原报告仍完整保留。

`evidence-tools/`保存实际producer的Git字节，checker重算宏组Tcl与配置、真实工具日志、三库身份、完整源清单摘要、唯一完整accelerator scope面积、单位证明及全部报告SHA。库、mapped.v和SVF本体未下载，网表身份是实际服务器receipt声明，不声称本地再次哈希缺失字节。单位依据同库既有LEF/Liberty尺寸核对，旧单位证明中历史2.5mm²不是本项目现用上限；这里只使用其μm²→mm²转换，本次预算明确2.25mm²。

```sh
python3 check-evidence.py --out /absolute/new-bank128-area-review.json
```

服务器在同冻结source、实际库及全新工具目录复现：

```sh
python3 "$xu_tools/tools/ppa/xu_bank128_ppa_server.py" \
  --producer-root "$xu_tools" --source "$xu_candidate" \
  --acceptance "$xu_actual_vcs_acceptance" --out "$xu_new_ppa_out" \
  --weight-sram128-db "$xu_actual_128_ss_db"
```

原三次generate/prepare/run的完整argv保存在原state。该入口先重读原VCS全部门禁与官方128模型path/bytes/SHA，不能以dummy DB prepare或单项定向测试替代实际前置验收。父工具提交和实际三库SHA详见原`implementation/implementation.json`与[工具说明](../../../xu-bank128-ppa.md)。
