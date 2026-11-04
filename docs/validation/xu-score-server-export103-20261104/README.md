# xu 实际103：未约束复位路径、清理95和映射模型警告审查

本目录保存服务器实际103的**原始tar.xz，不重新打包、不改写日志**：342,100字节，SHA256 `23edcf303dcc05b0ce120185bf2751dc1920a1e9bea7a1cb4388d5c8bc282ef2`。内有110项payload、23,145,122字节，另有原始内部manifest。逐项路径/大小/SHA见[payload-manifest.json](payload-manifest.json)。31项已安装工具帮助/手册正文没有返回，其身份记录保留在原始`omitted103-bodies.json`。厂商标准单元及SRAM模型正文没有进入本归档。

这些是各实验自己的原始状态和限定快照，**不是新的功能、150MHz时序或能量资格证书**。本项未改Chisel、生产RTL、网表或约束。

## 101：端口方向已澄清，非同义重复UDP仍需审查

冻结输入为S2c mapped SHA `9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892`，标准单元原模型SHA `9ceaac7085f267c9a2da19d86aa9d88ddb25894df4b2485e32d13e04d0e46581`，RAM原模型SHA `81b55d87d5e6821d44037d6f0290ec89c9edb9582eb1932957f181aefc300d51`，实际审查前后六项输入相同。

源码解析检查了127,548个定义内实例声明，148个实例共省略952个端口，**全为output**：7个标准单元省略7个output，141个mapped层次实例省略945个output。没有被解析为省略的input/inout。它澄清了原97的148项TFIPC，并非952次不同的输入悬空；它仍是语法/方向证据，不能单独证明完整功能一致。

实际VCS `+lint=TFIPC-L`编译return0、无Error，剩下2项OPD。原始日志明确两次声明均由**后一个声明覆盖前一个**：

|primitive|前/后定义起始行|完整token数|结论|
|---|---:|---:|---|
|`udp_tlatrf`|101797 / 101923|122 / 122|排除注释空白后完整定义token SHA相同|
|`udp_tlatrf2`|101830 / 101946|187 / 207|完整定义token SHA不同，不能当作重复文本忽略|

两种`udp_tlatrf2`的token SHA分别为`10a2ff2b145e4c21241c3ab168f22abfbc4c80622fda5e3504ed273ff092536f`、`9238d2a6e0acff10c328d304c2ac0da0e70f0d3cf0b223743257188a2dbbf27b`。本原件只含定义行号、token数量/哈希，没有两个表的逐行语义、调用这些primitive的具体cell名单、这些cell的mapped实例路径，也没有行为探针。因此，当前可证明的是**原VCS选择后定义且两定义不相同**，尚不能证明其具体功能差异被本设计触发，亦不能证明没有影响。尤其不能把“无Error”升级为mapped runtime已通过：101明确`runtime_simulation_executed=false`。

后续需对同一原库做只读依赖和行为审查，分别记录普通/functional条件编译分支，识别实际reachable cell后，再比较独立重命名的两个原始UDP在确定输入序列、未知态和事件顺序上的响应。不得为消除警告静默删掉某份定义、换模型或假定先定义才正确。此处不复制厂商truth table正文。

## 94：显示了两条实际PMU恢复数据路径，但没有恢复slack

只读94使用实际reset61网表`502a29a0f990d2b1f9394b80da35639cfbb81b9021ad01355f96ab1465dc7597`、两SS库、原SDC及proposal，前后SHA一致。三次PT均return0和唯一marker；diagnosis原有**两条SEL-005**原样保留，不能描述为全程零错误。

16项显式起点查询与86一致：HF外部reset→五个async端点的recovery均`count=0/NO_PATH_UNKNOWN`；同五端点removal有路径；LF watchdog→三个AON端点recovery有路径，30516.769531ns。仅临时开启已安装手册支持的`timing_report_unconstrained_paths`报告开关并恢复，没有改频率、加false path或调整引擎时序窗口。新的原生报告显示：

- PMU `erst_reset_r_reg/SDN`：HF输入至端点的数据到达时间0.8927571774ns；原生报告明确`Path Group: (none)`、`Path is unconstrained`。
- PMU `erst_reset_r_r_reg/SDN`：数据到达时间0.8930612803ns，同样明确未约束，没有recovery slack。
- 三个AON的同类report返回`No paths with slack less than 0.0000000000.`。这是该报告设置的结果，不能据此补出五项查询缺失的slack，或宣称任何未分析路径安全。

本次证明原工具确实能显示两条PMU数据路径，不能把`get_timing_paths`为空解释为路径不存在。原始decimal周期下，有限枚举的LF第11沿与前一HF沿相距`13012441/500000000ns = 0.026024882ns`，所以不能假设解除总有一个30.5µs LF周期裕量。这个有限相位见证不是所有相位的分析、recovery slack或任意异步解除安全证明。完整资格仍需复位同步器结构、适用条件与物理时序范围相结合的独立证据。

## 95：明确删除20个无负载组合单元，min-cap降至17

输入是实际79 mapped `5a1e30ca4c9f14a8eabb349575a9f3069038c15ec38577edeacf0c9613cfa048`。20项native `is_sequential=false`，每项完整输出集合只有自己这一leaf连接、父design实例唯一，全部preflight后才执行删除，没有递归扩张。DC/PT各return0、唯一marker、errors=[]。

新mapped SHA `a38717c9f775148c54f748343c77da9cf3bf593fec72e5bfc706ee5f3043ce59`。min-cap由20降到17、0 max-cap；44项新上游中恰好17项source-only，与17个min-cap pin集合一致。五项reset removal仍违例，最差min slack −0.121483ns；总coverage 294473项、267344 met、5 violated、27124 untested未闭合。该链是50→63→73→79→95，**不含reset61的40个反相器**，未取得此最终链独立Formality。不能把95的17 min-cap与另一分支的0 removal拼为一个候选结果。

## 100、93、89：保留失败和快照边界

- **VPI primitive100失败**：reference已经报`native_memory_geometry`，随后`physical_port_tag_or_readback` fatal，状态`FAIL_PRIMITIVE_NOT_QUALIFIED`、cases=[]。未通过正参考，不能解释为负例成功，更不能作为mapped preload已验证。原始TB、C、编译和仿真日志均保留。
- **原生pin抽取93当时仍运行**：返回task00–05六份summary及state，只有**6/12**，没有把正在增长的compact rows正文收入本次快照。103通过`/proc/144236/cmdline`确认worker确实存活且命令匹配；仅stream state的RUNNING标签不足以证明存活。六份summary报告每phase22512个pin block、所选属性原始值前后一致；原件同时说明“before”属性getter会触发lazy activity/power propagation，不能解释为两个同步引擎快照、已测Q绝对状态或已证annotation source。后续terminal93须另存新快照。
- **S2e PPA89当时尚无campaign state**：bootstrap状态表示已启动，bootstrap PID为152796、**campaign PID为156772**。103观测bootstrap已退出；campaign目录当时没有state。这个快照既不证明campaign完成，也不证明campaign死亡；尤其不能拿bootstrap PID消失来判campaign失败或重启。需对具体campaign PID/实际终态另作核实。

## 复现

离线核验覆盖原始tar、110项字节/SHA和上述有限声明；`PASS`仅指证据一致性，不指芯片资格：

```bash
python3 docs/validation/xu-score-server-export103-20261104/check-evidence.py
python3 docs/validation/xu-score-server-export103-20261104/check-evidence.py \
  --extract /absolute/path/new-xu-raw103
```

实际执行入口的原字节副本在[tools](tools)，对应服务器Desktop上的`launch_min_cell_cleanup95.py`、`launch_reset_unconstrained94.py`、`xu_mapped_warning_audit101.py`。重跑时必须使用新的输出目录/编号，不能覆盖这些原始实验。原始网表、库和输入SHA需匹配；本归档不携带受限厂商模型，不提供用替换模型获得通过的流程。
