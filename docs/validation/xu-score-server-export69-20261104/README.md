# 服务器实际原件包69

本目录无损保存435份实际原件，共1,373,952,701字节。原始tar.xz为52,689,120字节，SHA256 `a02b3c1e156c90e03dec98d07c855a479f7da34d383e5f57106dd43267cb0f47`。逐文件原始路径/大小/SHA见[original-manifest.json](original-manifest.json)。多个后续审查共用此不可变原包，避免重复存储12层完整活动来源列表。**归档完整不代表比赛资格通过。**

包含以下终态原件：

- 清理50完整RTL Formality：41462 passing，508 unread；176冻结输入before/after相等。
- 紧凑32PE三库完整RTL Formality：52334 passing（22464 BBPin、144 Port、29687 DFF、39 LAT），511 unread；346冻结输入before/after相等。SRAM内部仍是黑盒边界。
- 清理63：实际删除187个全部输出无接收端的组合单元，min-cap从187降至53，max-cap为0；5项原reset removal与27124 untested仍保留。其网表为独立从50派生，未包含reset61插入。
- S2c原网表完整12任务PT：全SoC报告、活动来源/覆盖、宏报告、每任务原生pin状态、prepare/execution输入SHA和诊断能量；全部为`NOT_QUALIFIED`，不能代入评分。
- actual36 sidecar的完整服务器流式读取回执及672条原始边界：稀疏子集/流平衡审查通过，非完整轨迹或能量资格。
- 新整数事务API的真实VCS一宏正例和拒绝例，以及独立deploy记录；不等于新全SoC采集通过。
- [reset61网表/SVF实际身份](actual61-current-identities.json)，替代存在人工转录歧义的截图读取。

本包不包含原始/normalized/mapped SAIF、12.3GB sidecar全文、网表、二进制SVF、工艺DB的全部正文；相应身份在服务器回执中绑定。不能把服务器before/after记录说成本地已重新读取未导出的正文。原始日志、空文件和尾空白均保留。

本机已对整个源包和435份展开原件严格核验，随后再次以独立流式checker重放。约需读取1.37GB展开字节，默认不落盘：

```bash
python3 docs/validation/xu-score-server-export69-20261104/check-evidence.py
# 如需全部原件，指定尚不存在的新目录：
python3 docs/validation/xu-score-server-export69-20261104/check-evidence.py \
  --extract /absolute/path/new-actual69-directory
```

各实验的资格边界、逐任务数值和复现命令仍应结合对应专门审查；这里的PASS只表示原件一致性。
