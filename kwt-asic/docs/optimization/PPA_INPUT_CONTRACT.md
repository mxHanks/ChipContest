# PPA 证据接收与门槛检查

`scripts/synth/check_ppa_budget.py` 接收指定工艺实际报告的整理结果，复核文件 SHA-256、声明的分析上下文、面积分类、150 MHz 时序条件和完整任务窗口功耗。它不运行综合、STA 或功耗工具，不解析任意厂商报告，也不验证提交者是否诚实抄录报告。**本工具的 PASS 只表示这些接收检查通过；`official_physical_acceptance` 始终为 `NOT_RUN`。** 仍须评审原始报告、官方库授权/版本、约束合理性、综合网表和前后功能一致性。不能仅凭填完 JSON 获得比赛验收结论。

当前指定标准单元库、SRAM 宏模型及官方 E203 完整窗口结果缺失，因此项目实际 PPA 仍为 **BLOCKED**。测试中的文件、库名和数值全部是临时目录中的合成夹具，不能引用为本项目面积、频率或功耗。

依据：[U09/U11–U13/U24–U28](../requirements/UNDERGRAD_REQUIREMENTS.md)、[SRAM 面积预算](SRAM_AREA_BUDGET.md)。比赛面积上限是 `≤2.25 mm²`，当前用户要求更严格的 `<2.25 mm²`，工具执行后者。功耗没有在这里臆造一个瓦数门槛；输出完整窗口能耗供合格候选比较，不能证明已经达到最优。

## 先生成缺材料模板

在工程根目录执行：

```bash
python3 scripts/synth/check_ppa_budget.py --template \
  --config-id opt_1x8_pipe1 --output /tmp/kwt-ppa-input.json
python3 scripts/synth/check_ppa_budget.py --input /tmp/kwt-ppa-input.json \
  --output /tmp/kwt-ppa-result.json
```

第一条生成模板，退出码 0。第二条在未填写材料时应返回 `BLOCKED`、退出码 **3**，面积/功耗/时间等未知量保持 `null`。缺项不得以零替代。`--config-id` 必须来自当前 `configs/optimization-area-budget.json`；此 ID 仅标识候选，不自动证明它已按该容量方案映射。相对证据路径默认相对于工程根目录；也可用 `--root` 指向保留相同需求/预算目录的工程副本。输出不得覆盖输入、声明的证据文件或检查器本身。

| 状态 | 退出码 | 含义 |
|---|---:|---|
| PASS | 0 | 必需文件/声明齐备，声明互相一致，算术与门槛满足 |
| FAIL | 2 | 内容哈希不符、混用配置、重复计数、已知违反门槛、格式非法等 |
| BLOCKED | 3 | 缺文件/测量/模型/覆盖证据，无法作出合格结论 |

同时出现 FAIL 与 BLOCKED 时返回 FAIL。`metrics_usable_for_comparison` 仅在 PASS 时为 true；失败结果中仍可能有局部算术值，不得据此宣布候选合格。输出保存输入与检查脚本哈希、命令、核对过的证据列表。指定 `--output` 时控制台最后一条 JSON 含 `PPA_INTAKE_COMPLETE` 和退出码。

## 文件与上下文绑定

每个文件引用必须是 `{"path":"实际文件路径","sha256":"64 位小写十六进制"}`。检查器读取真实文件、拒绝空文件和哈希不一致，并在检查末尾再次计算摘要。它不会把“存在某个路径”当作内容已经验证，也不会把哈希正确等同于报告内容正确。

`artifacts` 的必需原件包括：冻结配置、完整映射网表、SDC、官方工艺来源说明、12 任务清单、面积/时序/功耗报告、SAIF 或 VCD、活动覆盖报告、宏/标准单元实例清单、约束覆盖报告、时钟报告、完整窗口轨迹。`configuration` 应包含 RTL/驱动/数值格式版本、模块参数、宏布局、工具命令和全部依赖哈希，不能只是一个配置名称。

`libraries.setup/hold/power` 各自提供 `corner_id`、`process`、`voltage_v`、`temperature_c` 和 `standard_cells` 文件列表。setup、hold、power 可以使用各自规定的角；要求的是**每份报告绑定同一套角清单**，不是强迫所有分析使用同一个角。内部 SRAM 与复用共享 SRAM 均必须列出功能模型以及 setup/hold/power Liberty 文件，且其 `corner_ids` 与对应分析角一致。宏如果需要不同命名方式，应在来源说明中明确对应关系并统一逻辑角 ID。

`analysis_conditions` 要提供互连模型、负载模型、工具版本、要求覆盖的模式/角清单的文件引用。多角流程应在这些文件与原始报告中完整列出各角，提交汇总最坏值；当前 JSON 不自行解析多角 STA 报告。`all_required_modes_and_corners_covered=true` 必须经过报告审核后才能填写。

三组 `area/timing/power.binding` 和各 `artifact_bindings` 均需要以下值：

```text
configuration_sha256 = artifacts.configuration.sha256
netlist_sha256       = artifacts.netlist.sha256
sdc_sha256           = artifacts.sdc.sha256
run_id               = 顶层 run_id
analysis_context_sha256 = canonical_hash(analysis_context(input))
```

全部生成报告的绑定还包含 `window_sha256 = canonical_hash(input["window"])`。`power.window_sha256` 同样绑定完整窗口。`canonical_hash` 使用本脚本公开的函数：UTF-8 JSON、键排序、紧凑分隔符、拒绝 NaN/Infinity。`analysis_context` 纳入工艺声明、各角库文件/电压/温度、负载/互连/工具、实际内部宏及共享 SRAM 模型和官方工艺来源文件。填写完证据后可通过 Python 导入脚本调用这两个函数；修改任何被绑定内容都需重新分析或审核来源，不能为了通过检查器机械重算摘要。报告内实际网表、SDC、角和窗口仍需人工或相应工具适配器核验。

## 面积与存储宏

总增量面积按 Decimal 算术相加：

```text
A_incremental = area.core + area.new_interface
              + Σ(area.macros[i].count × area.macros[i].per_instance_area)
A_incremental < 2.25 mm²
```

标准单元逻辑分核心与新增接口，包含所有新增寄存器、译码、拼接、FIFO、控制、搬运/写回和时钟门控逻辑。`area.reused` 单列 E203、共享 SRAM、固定互连及外设，避免它们进入增量预算。新增互连必须归入核心或新增接口，不能挂到“复用”项下豁免。

每个面积项提供 `value`、`unit`（只接受 `mm2` 或 `um2`）、`unit_basis` 文件引用和 `instances` 列表。Liberty `area` 单位必须由指定库说明确认，再转换；不能默认都是 µm²。`instances` 必须使用互不重叠的叶实例路径，禁止重复实例及同时列父层级/其子实例。`inventory_complete=true` 必须与完整网表实例清单核对，检查器只核对已提交的列表，不会自行证明网表无遗漏。

每种内部宏的记录形状如下，所有 `null` 均须由实际映射结果填写：

```json
{
  "cell_name": null,
  "count": null,
  "instances": null,
  "per_instance_area": {
    "value": null, "unit": null,
    "unit_basis": {"path": null, "sha256": null}
  },
  "functional_model": {"path": null, "sha256": null},
  "libraries": {
    "setup": {"path": null, "sha256": null},
    "hold": {"path": null, "sha256": null},
    "power": {"path": null, "sha256": null}
  },
  "corner_ids": {"setup": null, "hold": null, "power": null}
}
```

同型号所有实例合在一项，`count` 必须等于列表长度。宏面积不能已经含在核心综合面积里又重复相加。`area.reused.shared_sram.models` 使用相同的 `cell_name/instances/functional_model/libraries/corner_ids` 结构，面积来自其外层 `shared_sram` 项。所有共享 SRAM 实例必须被模型覆盖。

允许新增接口或固定外设面积为零的特殊情形必须有非空 `zero_justification`、相符的空实例清单及原始报告依据；核心、内部宏、E203、共享 SRAM 和互连面积必须为正。逻辑 bit 数、宏容量、候选宏数量及泛化门数都不能填入这些物理面积字段。

## 时序、任务窗口与功耗

时序要求频率 150 MHz，时钟周期 `1000/150 ns`（允许 1 fs 的表示误差），setup/hold WNS 均非负；违例、未约束端点/IO、未时钟寄存器、未解析单元、无效例外、transition/capacitance/fanout 违例均必须明确为零。正 slack 若缺约束覆盖证据仍不能通过。约束人工评审和全部模式/角覆盖声明必须为 true。

完整窗口使用半开区间 `[start_cycle, end_cycle)`，从第一项任务输入/参数开始装载到最后一项全部写回完成。`included_phases` 包含 `parameter_load/input_load/cpu_schedule/compute/writeback`。`tasks` 恰好包含 12 项、层号 0–11 各一次，任务 ID 不重复，时段有序且不重叠。每项记录 `task_id/layer/start_cycle/end_cycle` 和四个必需 true 声明：`cache_cleared_before_load/includes_all_loads/includes_cpu_schedule/writeback_complete`。窗口首尾必须与第一/最后任务对应；任务间空隙仍计入总时间，不能通过排除调度、总线等待或写回应答来提高分数。任务清单原件还应携带输入/权重/偏置身份、逐任务误差和位一致结果，数值正确性由独立验证流程负责。

功耗按七个互斥域相加：核心、新接口、内部 SRAM、E203、互连、共享 SRAM、固定外设。每域有 `dynamic/leakage/unit/instances`、活动对象总数及已标注数。单位仅接受 W/mW/uW；两类功耗均不得缺失，零值必须有 `zero_justification` 和报告依据。所有域的实例集合必须与面积库存完全对应；面积豁免不豁免功耗。活动覆盖要求所有应标注对象均被覆盖；未覆盖对象不能使用默认零开关率。对象资格/常量/理想网络的排除标准须在活动覆盖原件中说明。

`full_hierarchy_covered`、`activity_matches_mapped_netlist` 必须 true。检查器复核活动/功耗报告绑定完整窗口，但不会自行读取波形证明声明，应在报告审核中检查时间尺度、活动截取、层级映射、时钟/复位及 SRAM 活动是否正确。功耗必须是这个完整窗口的平均值，不能拿 compute-only 功耗乘完整时间。

```text
T = (end_cycle − start_cycle) / 150000000
P = Σ各域(dynamic + leakage)
E_task = P × T / 12
throughput = 12 / T
```

## 工具回归

```bash
python3 -B -m unittest discover -s tests -p test_ppa_budget.py -v
```

测试覆盖严格面积边界、单位换算、缺材料、实际文件篡改/空文件、面积重复/父子重复、宏数量、PVT/角/网表混用、setup/hold、约束覆盖、全窗口尾部/任务重叠/层覆盖、缓存清空、活动窗口、E203 漏算、SRAM 模型缺失、活动覆盖、无依据零功耗、非法数值/重复 JSON 键和输出保护。所有合成测量只用于证明检查器能够拒绝错误输入，不能替代真实 PPA 报告。
