# S3-Y32 提前请求下一组 bias：开发实测报告

2026-11-09。本轮完成一个低成本调度优化：当前组完成INIT取bias后，在MAC运行期间提交下一组bias demand。完整12层304,128个Y32输出逐位一致；含真实清零总周期 **5,908,104→5,874,840，减少33,264拍／0.5630233%**。payload减少0.6514076%，真实clear周期保持不变。收益来自消除组间需求握手空拍；没有提高每拍MAC数量。

父基线`f8c5c9ee631a9c3cbf62015dff98bad6939400f4`，E203原基线`0f852a35741881400a7e10b4760bdb8f300245ae`，父子分支`codex/s3-y32-bias-demand`。旧基线来自`build/packed-clear-20261109/packed-full12`；新候选单层`build/bias-demand-20261109/pilot-task0`，正式集成重新编译完整12层`build/bias-demand-20261109/full12`。先导与full12测量输入171源SHA完全一致，source_drift为空。

## 为什么选这一项

旧基线fifo_full_wait=0，READY_WAIT=23,859，busy=3,168×68，mac_fire=3,168×64。结果生产端仍有等待，增加FIFO并不能直接解决。并行2/4/8路RNE可把capture从8拍降至4/2/1拍，但可能主要转移为下一组READY等待。这里只做了只读评估，没有实现或测量并行RNE，也不将局部理论省拍当成任务收益。

原自动调度只在`!running`时提交bias demand。新逻辑在`active && running && !takeBias && produced < 31`时用独立request tag请求`produced+1`。计算选组仍是当前produced，INIT后take仍在同一边沿，原bias必须稳定到该边沿结束；补充tag所有权断言。组31不请求越界tag0。原BiasSramPrefetch／两个bias槽、MAC／结果FIFO／NICE传输保持。

只修改`src/main/scala/linear/LinearAutoGroupCore.scala`及其生成`LinearAutoGroupCore.sv`；新增两个真实RTL测试文件。其余11个本次生成依赖字节相同，171测量源仅一个SV变化。CPU／LSU／BIU／仲裁／在途配置、固件main/accel/header／fences／错误检查、TB／清零helper／数值模型／输入／golden保持。仍是8PE、8lane内部256bit结果、NICE snapshot后拍POP和32bit串行LSU写。

## 实测结果

| 每层指标 | 旧PACK32＋READY | 新next-bias demand | 新减旧 |
|---|---:|---:|---:|
| Payload：首source VALID至最后Y响应 | 425,540 | 422,768 | −2,772 |
| 真实参数清零 | 66,802 | 66,802 | 0 |
| 主口径合计 | 492,342 | 489,570 | −2,772 |
| 清零至首请求gap，另列 | 102 | 102 | 0 |
| READY_WAIT驻留边沿 | 23,859 | 21,186 | −2,673 |
| writeback阶段 | 196,713 | 196,614 | −99 |
| other阶段 | 22,470 | 19,797 | −2,673 |
| shared_stall | 17,780 | 17,681 | −99 |

其余阶段每层w_load114,714、x_load71,280、bias_load10,760、compute_wait9,603不变；busy215,424、MAC_fire202,752不变。每层MMIO读2／写12,330，共享读15,040／Y写25,344，starts/dones各3,168；NICE请求/响应/OITF各99，snapshot/POP各3,168，status/result总线poll为0。以上计数为各自观察口径；READY_WAIT、阶段和stall可能重叠，不能相加算收益。

全部12层均为相同周期。payload **5,106,480→5,073,216**；clear801,624不变；总和 **5,908,104→5,874,840**。clear-to-source gap两侧均1,224，另列；计入gap时净省仍33,264拍。首请求VALID到accept均1拍，已计入payload。

真实清零每层仍有W16,384／X64／bias768个物理字、legacy8值及原staging清零；PACK32公共命令W8192／X32，写8252、读8、命令/响应8260。新调度不改变真实清零工作、完成响应或NICE idle条件。

## 调度、数值与兼容性验证

真实SRAM/MAC专用测试用同一TB分别运行冻结原SV和候选，各7完整行／224组。逐tag0..31恰好一次demand／launch／take／done，候选每行31次RUN期间提前请求；bias从launch至真实INIT采样保持且tag正确。连续启动间距实测 **69→68拍**，done均为launch+67。最初把预期写为省2拍的汇总失败已保留；正确边沿分析只省1拍。31×99=3,069是固定连续生产模型可删除的组间拍数，整层只实测省2,772，不能替换为理论数。

覆盖两个结果槽满时保留FIFO head并停止producer、邻接行更换bias、INIT／已接受lookahead且存在未回SRAM读／满FIFO三类reset、末组31后无pending／无wrap、随后的768字逐地址真实清零、manual cached START及再次新行。没有force、层次写入内存或伪造done。正式树双侧独立重放通过。

现有autogroup、cached/manual、READY、bias SRAM、真实SRAM/register双variant capability回归均通过。READY包括实际MAC的合法上下界、正负ties、bundle/commit/写响应/完成背压、旧MMIO POP竞争，以及418项READY错误/超时/复位单元场景。register变体只作兼容性验证，完整SoC结果来自SRAM变体。

## 严格证据核验

独立验证器锁定旧full12 result SHA和171源map，只接受`LinearAutoGroupCore.sv`的审定SHA pair：`ebc9c411a6318000369f6c466381767a469bb9d33454e4c955df713c728f9ab4`→`7d3c0f9acb6adc19c65c35360f9595fd625a68764560322c1fd3900cb650f18a`。保留旧严格loader的原始日志、全部输出判定、物理工作／clear／窗口／末响应、生成C/TB、输入／golden、工具／时钟／复位和source drift检查。

固件loaded ELF段及1002字节image相同。原ELF SHA可能因GCC的非加载local ABS STT_FILE `ccXXXXXX.o`临时对象名不同而变化；验证器只解析并规范化该唯一字符串的6个随机字母数字，明确证明不在PT_LOAD内，规范化后要求整个ELF字节SHA相同，其余metadata亦不允许变化。生成C只规范化冻结main的精确include路径，不改变受测原件。

严格单层以完整旧12层原件验证后显式投影原layer0，不冒称12对12；正式完整比较单独覆盖0..11。各轮20项损坏证据负例包括CPU源、未审定pair、manifest、数值marker、clear物理工作/时序、TB、固件image和额外ELF字节；旧fixture harness预期错误留作失败诊断，不计PASS。最终单层与完整12对12严格比较均PASS；pilot和full12分别20项负例全部拒绝。`verification/complete-map-revalidation.json`从完整原件重算两份对照，除运行路径外全部结果一致；`full12-comparison.json` SHA256为`e0e5e11e4fa53d3f6b65cdb678279bde8e728724e42ea54a2f6cda9ea8c2c5c8`。

## 复现与回退

生成SV：

```sh
scala-cli run . --server=false --jvm system -M GenerateRTL -- LinearAutoGroupCore
```

正式同条件完整12层，输出目录必须新建：

```sh
python3.12 -E -B tools/ppa/s3_task_campaign.py \
  --repo "$PWD" --out /absolute/path/to/new-bias-demand-campaign \
  --bias-kind sram --clear-profile packed16-mmio \
  --schedule bias-hw-autogroup-y32-packed16-nice-direct-stream-ready-window \
  --simulator verilator --cross-prefix /usr/bin/riscv64-unknown-elf- \
  --platform-clocks 150mhz --startup-profile external-reset \
  --layers 0,1,2,3,4,5,6,7,8,9,10,11
```

仅测试调度：`python3.12 -E -B tests/e203/test_bias_demand_schedule.py -v`；可选`XU_BIAS_DEMAND_LOG_DIR`保留日志，`XU_BIAS_DEMAND_BASELINE_RTL`必须指向SHA锁定的旧SV以重放69→68对照。

[goal计划](s3-y32-bias-demand-plan.md)、[紧凑证据](validation/s3-y32-bias-demand-20261109/README.md)和`build/bias-demand-20261109/handoff/README.md`记录Git身份、原始日志／失败索引、归档SHA及新路径只读重验。回退在干净副本将父仓切回`f8c5c9ee631a9c3cbf62015dff98bad6939400f4`并将E203切回`0f852a35741881400a7e10b4760bdb8f300245ae`。不要在有未保存修改的副本强制回退。

## 资格与限制

DEVELOPMENT_PASS_POLICY_PENDING、clear政策REVIEW_PENDING、FIFO payload physical zero UNPROVEN继续保留。两态Verilator保留Chisel procedural assertions，vendor SVA仍按原配置禁用；150MHz只是测试台刺激，不是STA或映射频率资格。未综合，未测面积／能耗／PPA，未运行正式VCS／门级／官方验收。没有官方分数或部署结论。新组合逻辑的面积／时序成本尚未映射评估。

只读RNE并行评估、先导fixture/harness失败与最终验证分开保留。主工作区及以前封存材料未改写；没有推送、PR或外发。
