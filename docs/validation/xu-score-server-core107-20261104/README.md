# xu 实际107：S2e原生映射证明通过，原driver误报保留

本归档为服务器实际107原始tar.xz：**49,904字节**，SHA256 `b21734f9957a35feeb847b8a5d2a03c1934c2f3ff7e5270001822e9630faeb58`。13项payload合计1,066,360字节，逐项身份见[payload-manifest.json](payload-manifest.json)。归档包含实际89的完整`fm.log`、`verify.tcl`、状态、unmatched报告、面积报告、prepared/execution，以及93终态。没有改写原日志、原89状态或生产代码，没有重跑DC/FM。

## S2e实际Formality成功，错误在driver判定

实际89原生`fm.log`为99,524字节，SHA256 `db12cfc23725e1ebfbacad6d8c4a0253487cb066ac47eea41b9e5648d789b174`。其完整原生结论为`Verification SUCCEEDED`、**42,338 passing compare points**，returncode为0，无Error/Fatal，且只有一个成功marker。完整own-SVF证明包含17个reference unmatched寄存器及511 unread；SRAM内部为库黑盒，不能因此宣称SRAM宏内部功能已证明。

原producer误判可对实际原件精确复现：`re.findall(r'^XU_S2E_FULL_SOC_FORMALITY_PASS\s*$', text, re.M)`返回的元素末尾包含换行，原实现却与不含换行的字符串比较。因此原`formality/state.json`为FAIL，原campaign为`EXECUTED_FORMALITY_FAILED_NOT_QUALIFIED`。这两个失败状态原样保留；不能把它们解释为42,338点不等价，也不能静默改成PASS。后继独立109将修复解析并重新审计当前文件身份，原107仅证明原件内容与此误判机制。

实际证明绑定自己的mapped SHA `0cfac0b5e99ec05301ec8c0efde38ef2c96790dd1243e84727687b15b25c09d0`和default.svf SHA `1a00803ebb654285dad15c76978fe1da50dd9732860f6af82a9a2d9117e668a9`；159项frozen输入before/after相同，campaign的15项工具/约束输入和完整源码身份before/after相同。冻结生产main为`5bf123bfead8f2a37f97f3234d4e40ce8201aae9`，child为`a0767db69628ef30e53de2d1e93dd0360c0ccf76`。本小归档没有159项输入的全部正文，本地校验不冒充服务器当前重新哈希。

## 同库综合面积

原生`area.rpt`的完整加速器层级（接口、内部逻辑及16片权重SRAM）报告**295,000.3804 µm²，约0.2950004 mm²**，占2.25mm²限额约**13.11%**。整个数字SoC报告3,365,957.200429 µm²；这不是比赛加速器面积限额的分母。面积按报告本身的小数精度登记，没有补造额外精度，也没有借用S2c面积。

独立综合面积与实际42,338点证明不构成完整比赛资格。PT仍报告max −20.834667ns、min −21.917278ns以及no_clock/report-command问题；没有把原pre-CTS propagated结果改写为150MHz通过，尚无S2e正式全SoC能量。

## 93实际抽取已完成

93终态为`EXTRACTED_24_ORIGINAL_REPORTS_NOT_QUALIFIED`，12个任务、24份完整原生报告、540,288个pin block。107快照确认93 worker、89 campaign及106 exporter三个具体PID均已退出，而非只凭RUNNING标签推断。132,850,844字节的106大归档仍在服务器，SHA `902f269f03d477c72064ba39633e3e57c51d4b240fca9e347eb0b48fd6d252a5`；其compact行正文没有进入107，本地不能据107状态宣称已重放全部540,288行。native X属性、输入TX、活动来源及全SoC能量仍需独立审查。

## 核验和复现

```bash
python3 docs/validation/xu-score-server-core107-20261104/check-evidence.py
python3 docs/validation/xu-score-server-core107-20261104/check-evidence.py \
  --extract /absolute/path/new-xu-core107
```

[实际导出脚本](tools/status107.py)逐字保存。它只能在服务器尚不存在107归档时执行；复跑应另用新编号输出，不能覆盖实际107或原89。离线核验的PASS只覆盖本归档身份、原生成功与driver误判，以及明确列出的面积/终态事实。
