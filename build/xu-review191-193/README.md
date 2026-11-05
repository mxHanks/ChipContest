# xu193：独立审查191终态诊断打包器

审查目标固定为191增强提交 `83012fd`，对应 `finalpack191.py` SHA256 `2de3d0cafe75c2e73f13795990a05ea1255b30bfb554e3c625b1a1684210ae2a`。结论：**本地检查通过，无阻断发现**；尚未执行服务器191打包或据此宣称实验/评分资格通过。

原191的9项测试独立重跑通过；另外7项独立检查直接使用真实Snapshot171与Safe171验包器：真实191包可以执行SHA绑定的`inspect`和全新目录`unpack`，每个解包文件SHA与manifest一致。验证了固定83012fd字节/manifest、原171引擎SHA、诊断报告保留、库/模型/RTL/SAIF/SDF/SDC/C/Python/PDF源后缀排除、大报告仅流式哈希、blocked目录拒绝、symlink拒绝及具体拒绝路径回执。

selector只选177、186、190预检/full12四个固定诊断根；动态替换的是冻结171模块的`select`和`JOBS`，由同PID直接调用`export`。未启动EDA、未修改原实验输入或原171包。只返回允许诊断后缀的报告及原生错误；在这些冻结生成目录内，vendor `.lib/.db/.v/.sv`正文不被选中。后缀筛选不是任意文件内容的净化器，审查没有把“任意字符串安全”当作证明。

191 job为native=true，使用原总控同一资源槽，三个依赖均为terminal：177、186、190full12；只有当前输出根出现在argv和process_contains，避免另一个job被误认成自身。成功只表示诊断原包导出，不把上游失败当作通过。缺失阶段仍记录missing，原生失败结果正文仍保留。

对任何rejected source均FAIL是合适的保守策略：拒绝发布一个可能被误解为完整的包，并保留源原件。83012fd已为Snapshot返回的rejected列表持久保存`source-rejections191.json`，在symlink实测中确实保存了bad.rpt完整源路径。blocked archive组件由171的safe_name在打开文件前直接拒绝，此时具体组件保留在state.error中而非rejected列表；同样不发布包，原源文件未改动。existing archive、既有输出/partial不被覆盖，失败191/171状态保留。

保留两份审查过程失败日志：attempt01发生于191按建议增强而固定112ad1a字节校验仍指向旧提交；attempt02是独立测试错误地假定blocked组件进入Snapshot.rejected，现已按原171真实先验校验路径修正。两者均未修改191实现，最终83012fd原9项与独立7项全通过。

复现（仓库根目录，Python3标准库；无服务器、无凭据）：

```sh
python3 -B build/xu-two-candidate-finalpack191/test191.py
python3 -B build/xu-review191-193/review193.py
```

`review193.json`保存审查文件、原引擎与验包器SHA以及测试计数；`manifest193.json`绑定本审查全部文件。生成包是live snapshot，必须检查source metadata、omitted与missing；本地fixture不会验证服务器当前输入是否存在或上游native资格状态。
