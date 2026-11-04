# xu actual S2c 全 12 task 活动导出审查

`review.json` 是实际 export53 的只读离线审查结果。63 个原件均逐一核对固定原始 export manifest 的字节数和 SHA256，审查前后复核；这里不复制 raw 文件，不改历史 result，也不调用或修改 PT runner。

结果为 `EXPORTED_12_TASK_LOG_RECEIPT_CONSISTENCY_PASS_SAIF_CONTENTS_NOT_REPLAYED`。总 result、12 份 task result、12 份 simulation log、12 份 normalization receipt、12 份 input manifest 一致；canonical configuration SHA 和全 12 input-manifest SHA 可重算匹配。12 次均为独立 `TASKS=1`，global task 0–11 对应各原始层，simulator 本地层均为 0。每层 25,344 outputs，99 rows，3,168 starts/dones/pops，实际 W/bias/X 上传为 16,384/256/6,336。

每层 source REQUEST / ACCEPT 为 cycle 1,403,985、tick 9,359,903,333,333；final Y response RETIRE 为 cycle 2,394,641、tick 15,964,276,666,667。物理窗口 `[begin,end)` 为 990,656 elapsed cycles、6,604,373,333,334 fs；legacy/formal inclusive 均为 990,657，firmware diagnostic 为 990,728。12 层 elapsed 合计 11,887,872 cycles，窗口合计 79,252,480,000,008 fs。分层性能分项、autogroup、scope toggles / unknown dwell 及 24 份 server-only SAIF identity 均保留在 JSON。

各层实际 accelerator clock 已观察 reset 后才 ready；33697 次 CPU legacy zero-clear 的全部内部 W/bias/X commit、FIFO 初态和 upload/result 检查日志均通过。clear 在 source REQUEST 前完成，位于 task SAIF 之外；最后一次 clear write 到 source REQUEST 间隔 91 cycles。clear 阶段没有独立 SAIF 或能量数据。

每层 receipt 声明 336 宏（shared 256、ITCM 32、DTCM 32、weights 16）、22,512 alias bits、137,439 normalized signals。DTCM 的 96 条已知静态控制记录与宏列表、窗口 dwell 一致，同时内部 unknown dwell 被保留；不能推出 DTCM 功耗为零。

**24 份 raw/normalized SAIF 原文没有 export。** 本审查只核对日志、receipt 和服务器文件 path/bytes/SHA identity 的一致性，无法独立解析 SAIF、重算 toggle/dwell、重放 normalization 或证明逐 bit 等价。48 个张量的原件及 materialized 副本、仿真 binary、firmware ELF/image、mapped netlist、SDC 原文也不在该 63 文件导出中，相应身份只作声明交叉核对。这是一份真实 silence sample 的 12 个独立 FFN1 layer 活动证据审查，不构成官方精度、equivalence、STA、mapped PT annotation、Liberty power、全 SoC energy 或比赛资格结论。

重放（输出路径须不存在）：

```bash
python3 tools/ppa/xu_joint_activity/xu_s2c_activity12_review.py \
  --original-dir /home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-score-resume-20261103/next-results-export-53/s2c-formal-activity12-20261103-23 \
  --out /tmp/xu-s2c-activity12-review.json
```

默认 manifest 为原件目录上一级的 `manifest.json`，固定 SHA256 为 `dd5f1135a7a593e0027f991bea82ddfbfabfc4e557c0b732543755fa1258c20f`。`review.json` 内列明全部 63 原件 SHA256、原件绝对目录及 checker SHA256。已在真正的全部 12 task 输入上运行 checker，无合成替代数据。
