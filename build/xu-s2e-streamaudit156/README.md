# xu own130 原生pin流式独立审计156

仅审计真实S2e own130终态原件，不调用EDA工具，不修改RTL、网表、DB、SAIF、原报告或130回执。固定130 `prepared.json` SHA `99b5f66b5388395a6d5b70c3ad0c6482fd346d148b6715596c4c9499f205ed5c`、`execution.json` SHA `f9ae8ff27792632f857004b971fb1d206002f510ca97e41d9b66ddb9f142bc66`。逐层窗口固定为本次实测5788953333333fs、868343 elapsed cycles；未使用旧112的6604373333334fs。

```sh
python3 -B /SERVER/Desktop/xu-campaign-batch154/streamaudit156/audit156.py \
  --campaign /storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/s2e-full-soc-power12-20261105-130 \
  --out /storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/s2e-native-pin-streamaudit-20261105-156
```

`--out`必须为全新且位于原campaign之外的目录；重复运行不覆盖旧结果，失败也保留`state.json`和`failure.txt`。总控150/批次154使用唯一output_root作为`process_contains`，`result_state=out/state.json`。成功状态`STREAM_AUDITED_24_ORIGINAL_REPORTS_NOT_QUALIFIED`，失败状态`FAIL_DIAGNOSTIC_NOT_QUALIFIED`。没有自动恢复或重跑，未完成尝试需保留后另开输出。

`manifest156.json`包含全部文件的相对path/bytes/SHA；`runtime_files`是部署必需的六项。入口在运行前后验证冻结runtime及manifest身份，原130两份回执SHA在`receipts156.json`冻结。部署可只复制runtime_files和manifest，测试/README不属于runtime。

执行顺序：

1. 完整重哈希130冻结的554输入，并检查12层完整终态、原native return code、唯一完成标记、同PT版本及prepared前后身份。
2. 每层重新读取原observer mapping、native336宏/22512 bit-pin inventory、原bridge回执、measured receipt以及canonical和mapped SAIF正文。独立重建完整宏/bit双射，逐pin比较全部统计，包括TX/TZ/TB/IG，验证全部非迁移信号及header保持，重算unknown、Q-positive/full-window摘要及130原逐bit比较SHA。
3. 每相原生file/default/propagated/no_switching_activity报告均stream hash/parse并保存完整before/after身份。只匹配原保存的driver-pin列；不由load pin缺席推断未注释。
4. `primary156`逐行提取每个原pin block的选定属性、原字节位置/文本、diagnostics及完整block SHA，写`native-before/after.jsonl.xz`。800MB原生属性报告从不read_text/read_bytes整体载入。
5. `replay156`使用另一套块解析器从原报告逐块重新读完全部字节，逐block hash、selected属性/类型/原文本/位置、diagnostics、分类、source membership和统计摘要全部对照primary输出；每块限制2MiB。前后SHA必须与真实130原artifact匹配，原报告尾部不得有未覆盖字节。
6. 每层每相最多保存四个原native block及对应compact JSONL样本，附原报告身份和byte range。12层完成后再重哈希554输入、global inventory、130回执和自身runtime。

输出`task_XX/summary.json`、xz compact、原block样本、顶层`state.json`。真实完成须24原报告、540288 native pin blocks全部通过。`before/after`仅指显式`update_power`之前/之后；getter本身可能触发lazy propagation或power计算。`x_probability=0`不能证明物理Q已知，所有结果始终NOT_QUALIFIED；本审计不解除STA/RDC、综合后私有功能、SRAM when/internal_power及比赛能耗资格门。

本地host检查与语法检查：

```sh
python3 -B -m unittest discover -s build/xu-s2e-streamaudit156 -p 'test_*.py' -v
python3 -B build/xu-s2e-streamaudit156/check_bundle156.py
```

这些检查使用synthetic fixture，不能代表真实130报告已经审计；实际审计状态以服务器全新输出目录的原state及日志为准。
