# xu：198不可变FM原件接续修正的独立审查

结论：本地修正审查通过，可由既有153总控登记；没有执行远程或原生EDA，仍是NOT_QUALIFIED。审查提交`0ef03c6`。上次194对实现和返回原件的审查并未证明服务器可变全局FM汇总仍保持原SHA；根线程随后报告192在任何register之前被该严格SHA守卫拒绝。这个失败不能被删改成通过。本次另加不可变原件接续，192原运行时及失败证据保持独立。

原09返回的**whole FM state**为349,702字节，SHA `dadd3bb693a3ae17bf92682d9586fa1ba07e6ead468465e07b67fa91eabea5dd`。新增`frozen-fm190.json`与它逐字节完全相同，没有挑选、重排或重新生成内容。实际输入部署到新目录`~/Desktop/xu-s2c-common-power198/`，旧服务器190目录不覆盖。`references190.json`将旧path/SHA/bytes保留在`fm_state_original`作为历史provenance，实际读取/冻结/前后重核的是新目录的同字节snapshot，未对live state放宽SHA，也未采用后来的映射或结果。

相对原`2d61547`，runner仅改变两处函数：runtime完整成员表增加snapshot；source_context在原检查全部保留的基础上增加snapshot路径/原SHA/尺寸二次校验及返回历史身份。其余所有函数AST完全相同，包括原57的367输入、own native FM日志/SVF/mapped/source、PPA面积、336宏22,512pin原生inventory双射、SAIF/未知、同166时钟方法、task0→full12、原报告完整性和失败守卫。

独立枚举source_context真正递归读取的原始输入：367 original57、7 prepared context、159 own native记录、153 PPA source、1 inventory TSV、84 task记录，去重共**601条路径，0条state.json**。只有显式外层refs额外引入跨候选FM汇总；替换后未发现第二个跨候选mutable state。剩余JSON属于本候选的终态activity23/firmware/normalization/vector manifest、inventory20、own PPA execution和57逐层bridge/measured等，原SHA继续严格校验。这是本地路径及元数据审查，601份服务器正文仍必须由worker实际逐字节重核，若有改变仍应失败。

新runtime8个成员加manifest共9文件，入口SHA `941d99e641ceee571a57b7f6076094197de7253fdcc0bc3692398a543c50ad13`，manifest SHA `e76076333133432ad233aebb4ea86cdd5f7057c2bf63cd787e442538c5b9cb31`。两job的ID、output190、依赖、终态、result和process_contains完全不变，仅argv/runtime前缀从190换成198。job frozen_inputs因runtime成员和显式fm_state同路径重复snapshot一次（16行、15唯一路径），两份bytes/SHA完全一致；原153和登记wrapper允许相同记录，没有冲突或身份歧义。

19项190检查独立重跑通过；metadata join通过但对未返回服务器正文明确mock，未当成native验收；194独立task0正例/8负例和same-PID输出检查再次通过。完整原47份证据/12层同166方法检查在新runtime上也重新通过。`review198.py`从原提交直接重建允许变化并逐字节比较，检查snapshot与原09、完整manifest、job不变字段、全部原始递归输入路径；重跑结果与`review198.json`逐字节一致。Python3.6运行时grammar检查通过。

复现（输出必须是不存在的新文件）：

```sh
python3 -B /home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-review190-194/review198.py --out /tmp/xu-review198-new.json
python3 -B /home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-s2c-common-power190/test190.py
python3 -B /home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-s2c-common-power190/check_metadata190.py
python3 -B /home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-review190-194/test194.py
```

S2c仍使用自己的9c16映射和0.2948018380mm²面积，未借S2e155/baseline116图。没有新增功耗/能耗结论、改善百分比、资格或评分。
