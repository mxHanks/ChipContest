# xu S2e actual120：完整12任务RTL活动与逐bit复核

actual120已经返回完整12个固定FFN1任务，顶层原状态为`COLLECTED_12_TASKS_REVIEW_PENDING`、`taskset_complete=true`。12个独立VCS进程均有唯一`SOC_PASS tasks=1 outputs=25344 writes=50688`，共304,128个数值输出、608,256次Y写。**这是完整12任务RTL活动采集及原件保真复核；完整150MHz STA、mapped任务仿真/活动注入、SRAM内部功耗及全SoC单任务能量仍未通过，不授予比赛评分资格。**

`payload.tar.xz`实存完整125原包，不做成员删减或重新压缩：8,171,768字节，SHA-256为：

```text
ebfba2f46193dca30362ccce4fbbe602be238abd21a316240da0da2f828fbf10
```

原包包含88项正文、合计465,539,700字节，以及其内嵌manifest。88项包含12对raw/normalized SAIF、每task结果/normalization/原生日志/向量identity收据、完整顶层结果、固件构建收据、原observer及mapping、VCS构建/版本日志和driver。`omitted125-bodies.json`为空；本目录`payload-manifest.json`逐字复制原清单，离线checker独立核对内外清单、成员集合、大小及每份正文SHA。原包不是服务器完整源代码或工具链镜像：实际tensor、ELF、工艺库及全部服务器源码正文未进入这88项，不能仅凭本地收据声称重读了它们。

## 同一候选、原始向量与own109证明

冻结main为`5bf123bfead8f2a37f97f3234d4e40ce8201aae9`，child为`a0767db69628ef30e53de2d1e93dd0360c0ccf76`；本次归档没有修改Chisel、RTL、ABI、数值格式或向量。配置SHA为`53e44a6600d99ae3e527a96317dd8bb13c427d4b4e6eea8705aa757ed30fd7fe`。同服务器GCC10.2/VCS2020，HF名义150MHz、LF32768Hz、精度1fs。

12个原始层分别通过`global_task_id=0..11`送入独立进程；每个进程仅有一个`simulator_layer=layer_00`，所以日志中的`TASK_PASS layer=0`不会被误判为重复使用第0层向量。checker核对每份input-manifest的global/original/simulator层映射、四个tensor的original/materialized SHA与顶层对应层收据，12层完整identity摘要为`6ba79d709925d22258d0624a53198e2f7d5926d8bdbe82699def9f9728459dca`。原native TB完成逐输出golden检查，日志保存于完整原包；本地不重新执行未返回的tensor正文。

本活动绑定S2e自己的mapped SHA `0cfac0b5e99ec05301ec8c0efde38ef2c96790dd1243e84727687b15b25c09d0`及独立109收据SHA `79c011fc965b620cd39954405ade0b9759e4a409a90b33ad6c683eea3f18594f`。`proof109-state.json`保存[114归档](../xu-score-server-progress114-20261105/README.md)中109原件的逐字副本，checker核对其native证明上下文与120收据完全相同。原native full-SoC Formality为42,338 passing点；原89误报状态仍保留，SRAM黑盒及其它证明限制也不被升级。绑定自己的FM身份不等于门级活动注入或时序已通过。

## 逐层窗口、清零和搬运

每层真实活动区间均为首个source REQUEST（同周期ACCEPT）到最终Y响应退休的`[begin,end)`：开始cycle1,403,992/tick9,359,950,000,000fs，结束cycle2,272,335/tick15,148,903,333,333fs。每层868,343 elapsed周期，868,344 inclusive诊断周期，持续5,788,953,333,333fs。固件读数868,419采用另一边界。

| 原始层 | elapsed周期 | inclusive周期 | 物理结果读 | 输出 | alias bit比较 | 非alias保留 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 868343 | 868344 | 38016 | 25344 | 22512 | 114927 |
| 1 | 868343 | 868344 | 38016 | 25344 | 22512 | 114927 |
| 2 | 868343 | 868344 | 38016 | 25344 | 22512 | 114927 |
| 3 | 868343 | 868344 | 38016 | 25344 | 22512 | 114927 |
| 4 | 868343 | 868344 | 38016 | 25344 | 22512 | 114927 |
| 5 | 868343 | 868344 | 38016 | 25344 | 22512 | 114927 |
| 6 | 868343 | 868344 | 38016 | 25344 | 22512 | 114927 |
| 7 | 868343 | 868344 | 38016 | 25344 | 22512 | 114927 |
| 8 | 868343 | 868344 | 38016 | 25344 | 22512 | 114927 |
| 9 | 868343 | 868344 | 38016 | 25344 | 22512 | 114927 |
| 10 | 868343 | 868344 | 38016 | 25344 | 22512 | 114927 |
| 11 | 868343 | 868344 | 38016 | 25344 | 22512 | 114927 |
| 合计 | **10420116** | **10420128** | **456192** | **304128** | **270144** | **1379124** |

[per-layer.csv](per-layer.csv)保存每层原log、raw SAIF、normalized SAIF与独立per-bit比较摘要的完整SHA、精确tick、清零及输出计数。[verification.json](verification.json)保存独立重放的逐层结果。此处10,420,116采用明确的elapsed区间；此前开发窗口10,420,140是另一边界，不能将两个测量混写成同一结果。

每层source请求前，CPU实际接受33,697次legacy零写；内部实际零提交W16,384、X64、bias256，FIFO逻辑所有权复位且空。最后零写在source请求前98周期；清零阶段在SAIF窗口之外，未假装已测其能量。每个任务是新进程，没有跨层cache复用，也没有将FIFO payload寄存器的逻辑空所有权描述为所有物理FF清零。

窗口内每层重新提交W16,384（8,192次pack32）、X6,336（3,168次pack32）、bias256；99行，3,168次start/done/POP，结果FIFO最终为空。结果读取为25,344个legacy字及12,672个paired-HI字，共38,016次物理读，对应50,688个逻辑字。checker逐项核对每份原日志的这些计数、清零/边界、LF/HF静态时钟marker与唯一SOC_PASS。

## 全12层raw→normalized逐bit保真

checker使用逐字归档的公开`tools/scripts/xu_soc_activity.py`只读SAIF reader，从每份raw/normalized重新解析全部信号；没有调用或绕过需要服务器绝对路径源码上下文的producer guard。

对每层独立重建336宏×67bit的22,512项双射，逐bit比较全部dwell、TC、IG等测量统计，重算alias名称和per-bit摘要，并确认114,927条非alias原信号逐项不变、没有额外删除/增加，normalized共137,439条。12层总计270,144项bit比较及1,379,124条非alias保留。所有SAIF均保持1fs timebase和原duration；TX/TZ/TB没有置零、推断或填充。

每层alias未知停留合计26,076,600,970,238,528 bit-ticks，完整保留。它不是原生mapped注入成功的证据，也不能推导未知部分零功耗。后续仍需实际mapped注入覆盖与来源解释、Liberty内部功耗、同一候选完整时序以及全SoC单任务能量；本归档没有新增功耗/能耗数值。

## 离线复核和服务器复现

完整重放约需要70秒及约466MB临时磁盘空间，逐任务释放SAIF解析数据：

```sh
python3 docs/validation/xu-score-s2e-activity120-server125-20261105/check-evidence.py
python3 docs/validation/xu-score-s2e-activity120-server125-20261105/check-evidence.py \
  --extract /absolute/path/new-xu-s2e-activity120
```

第二条要求目标不存在，保留完整88项原正文。默认检查支持文件manifest、原包和每项SHA、12层实际边界和数据计数、own109绑定、向量identity收据及12对SAIF的完整测量双射；PASS范围仅限这些已返回原件。

[reproduction-commands.json](reproduction-commands.json)保存原collector、VCS build、固件build及12条真实runtime argv。服务器已有冻结源码/109 tools/89 mapped/109 proof/104 task00 proof时，新运行使用新输出目录：

```sh
python3 "$HOME/Desktop/xu-score-optimization-20261102/ChipContest-s2e-activity-tools-109/tools/ppa/xu_s2e_activity_server.py" tasks12 \
  --source-root "$HOME/Desktop/xu-score-optimization-20261102/ChipContest-s2e-74" \
  --ppa-root "$HOME/Desktop/xu-score-optimization-20261102/s2e-ppa-campaign-20261104-89" \
  --formality-root "$HOME/Desktop/xu-score-optimization-20261102/s2e-own-formality-audit-20261104-109" \
  --task00-proof "$HOME/Desktop/xu-score-optimization-20261102/s2e-formal-activity-task00-20261104-104" \
  --out "$HOME/Desktop/xu-score-optimization-20261102/s2e-formal-activity12-repro-UNUSED"
```

该producer先核对同一源码、自己的mapped及109 proof、原task00，再detach采集；不会把本地SAIF保真重放当作服务器源码guard。不要覆盖原104/120/125或因观察超时重启原进程。8份相关公开producer/reader工具与原task00归档字节相同，身份见`tools-manifest.json`；它们不是完整服务器依赖镜像。
