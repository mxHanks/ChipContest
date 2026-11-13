当前可用状态：三轮真实原生文档与属性探针已完成，`native-adapter.tcl` 和 `docs/validation/s3-y32-final-20261113/formal-prep/api-contract.json` 已审并绑定；不是待填模板。只有API准备及本地合成门禁测试通过，未读本轮设计、未match/verify。用户现优先原1064.35开发候选，本374流程保留且不借用/转移证据。

实际后续命令使用已审adapter及三轮原生文档拼接：

```sh
python3 experiments/s3-y32-final/formal/prepare.py --package /absolute/same374-final-package --native /absolute/same374-DC-output --api-contract docs/validation/s3-y32-final-20261113/formal-prep/api-contract.json --adapter experiments/s3-y32-final/formal/native-adapter.tcl --probe-log docs/validation/s3-y32-final-20261113/formal-prep/native-api-combined.log --out /absolute/NEW/formal-ready
```

采集器写实际 `coverage-native.tsv`（所有字段UTF8十六进制，不执行工具输出），原生结束后由 `normalize.py` 生成coverage.json。不存在/未知API、native Error（即使Tcl RC0）、列表格式/计数不符、宏/引脚缺失均明确失败。当前collector严格要求374个实际可配对宏；若FM消除物理宏，保存原件并另行逐宏审查/版本化适配，不能补写计数。全部not-compared其他类型、PGPin、匹配/最终两个unread统计独立导出；native成功而归一化尚未通过会标记COVERAGE_PENDING，保留原件，不伪造proof。旧模板仅供以后移植参考。

# 最终 DMA4/storage21 的 RTL → mapped 准备与门禁

仅适用于 `sysbus32-dma4-storage-sram-374-final`，顶层 `xu_soc_sysbus32_ppa_top`，同一密封包159个RTL、同序 `rtl.f`、六项生产defines，以及该包本轮DC自己的 `mapped.v` / `mapped.ddc` / 已flush的 `final.svf`。不读取当前工作树替代reference；不包含TB、generic SRAM、旧353/S2的map/SVF。不继承旧42,338点、17个unmatched或511个unread例外。本目录的准备/审查均默认离线；本轮尚无原生FM通过。

## 可立即执行的只读API阶段

`api_probe.tcl` 只调用标准Tcl的 `info`、FM的 `help/man`，不读设计/库、不match、不verify、不改变HDL策略。候选命令不存在或man失败均原样保留；探针完成不意味着API签名已审核。

可靠历史入口来源为 `docs/handoff-evidence/s2e155-state.json` 的 `frozen_before` / `frozen_after`：

- 原argv0 `/eda/synopsys/fm/fm_2020.09-SP5/bin/fm_shell`，5713字节，SHA256 `4c502a4490b6eb1e27c9196732db1bc4f12488297bfa458f1e00e70c971e6e48`。
- 实际旧原生日志为 `Version R-2020.09-SP5`。这是历史身份，当前必须重新hash入口实际字节，记录 `readlink -f`；允许厂商symlink，执行仍保留原入口名。
- 该state本身SHA256 `3474d4aaf4801ead290534a25fefcb6cab8d4613ff2191edef71900f7fec6952`。

主session在新、自有目录保存探针、完整stdout/returncode、launcher当前SHA/bytes/resolve/version。实际调用是 `fm_shell -f api_probe.tcl`。在原生max-core API确认前，由主session采用Linux affinity限制到所授权的两个CPU；本探针不自行改变affinity或猜 `set_host_options` 参数。只读采集可在CPU12尚未结束时执行；FM设计验证须等待同包CPU12、DC完成及资源串行空闲。

```sh
python3 experiments/s3-y32-final/formal/review_probe.py --log /absolute/native-probe.log --out build/NEW/probe-review.json
```

探针完整性已经本地Tcl解析；真实原生支持、文档和签名仍需由新日志确认。`help`存在不是签名证明，探针status也不能自动变成可执行adapter。

## 后续实际验证的两个先决关口

先离线核对源包，准备探针：

```sh
python3 experiments/s3-y32-final/formal/prepare.py --package build/s3-y32-final/ppa/production-r1 --out build/NEW/formal-prep
```

若未给同包DC结果/已审API，输出明确 `verification_tcl_emitted=false`，不会生成能够偷偷开始read/match/verify的脚本。

收回真实help/man后，填写 `adapter.template.tcl` 的四个procedure，并建立 `api-contract.json`（schema见 `api-contract.template.json`）。每条资源/报告API签名必须来自该原生probe，记录精确adapter/probe SHA和launcher身份，不能靠命令名推测。模板主动报错，不能作为已审adapter。适配层必须：

1. `final_fm_configure_resources {maximum_cores report_dir}`：以已证API设置并报告实际最多2核。
2. `final_fm_configure_assumptions {report_dir}`：选择并完整报告实际HDL、auto_setup、undriven、case、mismatch策略。没有默认继承 `hdlin_unresolved_modules black_box`，禁止泛化未解析模块；不新增cut/dont_verify、用户match或强制常数。
3. `final_fm_collect {phase report_dir}`：在linked/matched/verified阶段采集原始报告，verified时写 `coverage.json`。必须保留资源、假设、unmatched、matched、failing、aborted、unverified、dont_verify、constants、unread、全部blackbox/引脚、guidance及HDL mismatch共13个角色。缺失或不支持即失败，不能写空报告/0统计。
4. `final_fm_assert_boundaries {report_dir expected_count expected_cell}`：实际枚举两个full top的opaque边界及全部端口，拒绝任何非RAMSP或未解析黑盒；在verify前核对实际对应关系。若FM优化移除原本物理存在的宏，必须保存原生清单与逐宏不可观察性证据，不能补写常数374。

然后在实际远端路径重新执行prepare（已知旧 `-vcs` 语法要求source-package路径不含空白），同一包必须已绑定真实GPIO CPU12，DC `execution.json` 必须完成且原始hash/全部输出一致：

```sh
python3 experiments/s3-y32-final/formal/prepare.py --package /absolute/final-CPU12-bound-package --native /absolute/same-DC-output --api-contract /absolute/api-contract.json --adapter /absolute/reviewed-native-adapter.tcl --probe-log /absolute/native-probe.log --out /absolute/NEW/formal-ready
python3 experiments/s3-y32-final/formal/run_once.py --preparation /absolute/NEW/formal-ready
```

默认第二条只审查，不访问厂商工具/库。主session后续显式加 `--run --out /absolute/NEW/fm-run` 才会执行；如存在同账户其他EDA作业，需要具体 `--coordination-note`，从不停止别人作业。同一团队自己的DC/PT/FM保持串行。wrapper重新hash实际launcher及两库，保留原argv0；生成Tcl首先配置max2，再读取同map guidance/库/同159源/top，match，导出未匹配及边界核对，然后verify，最后导出所有报告。成功marker故意叫 `VERIFY_SUCCEEDED_NOT_ACCEPTED`。

目前仅支持原生DC同map自身 `final.svf`。若之后采用ECO map，该旧绑定会被拒绝；必须另封含原compile→每个ECO的完整SVF和输入/输出map链，适配并重新审查后再验证，不能把旧map通过冒充ECO后结果。

## 原生覆盖导出与最终审查

`coverage.json` schema为 `final374-fm-native-coverage-v1`，必须由已审adapter用已证原生API/完整报告生成（不是手填旧计数）：

- `collector_complete=true`，`api_contract_sha256`；`raw_reports` 为13个role→`{sha256,bytes}`；`report_provenance` 同13个role→`{phase,commands:[精确原生命令名],returncode:0}`。假设变量读取可标记 `TCL_VARIABLE_INVENTORY`。
- `compare_counts` 包含passing/failing/aborted/unverified/unread。失败/aborted/unverified必为零，不可通过例外免除。`guidance_counts` 为accepted/rejected/unsupported/unprocessed/total，逐项列出未接受guidance。
- `point_lists` 每项为`{id,evidence_reports:[role]}`。必须完整列出 `unmatched_reference`、`unmatched_implementation`、`unmatched_primary_reference`、`unmatched_primary_implementation`、`match_unread_reference`、`match_unread_implementation`、最终verify的 `unread`、`dont_verify`、`constants`、`cuts`、`hdlin_mismatches`、`guidance_not_accepted`、`assumptions`、`macro_omissions`，及三个空列表failing/aborted/unverified。匹配时unread与verify时unread是不同统计，不能互相替代。assumptions另含 `actual_value`，必须列出源码规定的七项HDL/undriven/auto_setup变量。
- `unresolved_modules=[]`、`unexpected_black_boxes=[]`；`resource_limit={max_cores:2,native_report_role:"resources"}`。
- `physical_macro_boundaries`逐一列出374个唯一物理宏及itcm32/dtcm32/shared256/W16/bias1/X16/result21分组。配对项为`{canonical_path,group,cell_ref:"RAMSP1024X16",disposition:"PAIRED_OPAQUE",reference_path,implementation_path,ports}`。ports必须正好Q/CLK/CEN/WEN/GWEN/A/D/EMA/EMAW/RET1N，方向/宽度见common.py；每位`{reference_pin,implementation_pin,evidence_id,status}`必须有原生对应证据，输入为VERIFIED_COMPARE_POINT或VERIFIED_CONSTANT，Q为MATCHED_OPAQUE_OUTPUT。constant必须对应已审constant条目。只有经原生证据逐宏审查的PROVED_UNOBSERVABLE项可解释FM消去；不能隐藏DMA/core/fabric。

审查决定文件schema为 `final374-fm-coverage-decisions-v1`，绑定实际coverage SHA。每个非空例外/假设/constant条目都有唯一`{category,id,decision:"ACCEPTED_WITH_REASON",reason,reviewer,evidence_reports}`，理由至少30字符且引用所有相关原始报告；没有继承旧例外、通配接受或只看PASS。macro内部电路不在opaque边界proof范围。

```sh
python3 experiments/s3-y32-final/formal/review_native.py --preparation /absolute/formal-ready --run /absolute/fm-run --decisions /absolute/coverage-decisions.json --out /absolute/NEW/fm-review.json
```

门禁同时核对唯一实际 `Verification SUCCEEDED`、唯一实际terminal marker、完整新top、动态passing点数/完整结果表、末轮0F/0A/*P/0U、matching与verify的独立unread、全部raw报告/输出SHA、实际2核与库/工具/map/source身份。Tcl echo里的PASS/FAIL字符串、旧S2日志、空报告或只有常数统计不能通过。

最终接受状态只表示同冻结RTL→同map的逻辑在已审SRAM opaque边界上一致；不证明SRAM内部、150MHz STA、面积计费、功耗或官方最终样本资格。

## 本次已取得的原生API证据

2026-11-13新只读探针RC0，完整log SHA256 `11675552d88095cd0d3790a6200e432e9b29e33758a29f537e3bc032d95d0dfd`，launcher重新核对仍为上述SHA，Linux affinity[0,1]。文档确认 `set_host_options -max_cores`、无参数 `report_host_options`，以及所有候选report命令存在；`get_object_name`不存在，应使用已文档化的 `get_attribute ... full_name`。这些是新API文档事实，尚未完成实际source/map的match/verify。小原件位于docs/validation/s3-y32-final-20261113/formal-prep。
