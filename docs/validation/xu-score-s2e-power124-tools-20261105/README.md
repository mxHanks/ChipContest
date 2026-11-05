# xu S2e124：冻结功耗工具与实际早期失败

本目录原样保存124工具、23项聚焦host检查以及actual129返回的真实启动/失败原件。**124确实启动过协调器，随后在第一任务收据检查处退出；没有进入自己的PT inventory或12任务功耗运行，也没有能量或评分结果。** 不能将原launch的`STARTED_NOT_QUALIFIED`当成成功终态。

`payload.tar.xz`为28,184字节，SHA `c4f7186a2cbdc7bbfd16d9af9ee7fb23621901a05193d1c55261f5b3db2de339`；17项载荷的逐文件身份见`payload-manifest.json`。原producer为45,800字节，SHA `2349b11ec32e63c71ff70497c8d6d124ec99024bec73b75239944993bd58bc58`；服务器冻结执行副本与本地原件逐字相同，未回写修复。

## 实际失败及原因

`server124/driver.log`只有原启动JSON和唯一错误：

```text
FAIL: ValueError: normalization raw/output identity differs
```

原launch PID为133531；actual129进程快照明确记录其已不存在。三份服务器原件的字节/SHA与原129 manifest逐一对应。源129原包为57,416字节，SHA `0ab784c48fed419fbd70d5862a9f2be6bd8a2d82b550b6ed9ad05bffaea3b82b`；这里只选择124三份原件及来源manifest/快照，不审查伴随的123/128实验。

actual120的task00原收据也完整保留：`task.raw_saif`只包含`path/sha256`，`normalization.raw_saif`额外包含`bytes=25568880`。它们的path、SHA完全相同，但Python整dict相等判定为false。124把合法的两种身份表示误拒，并非真实活动正文不一致。修复另立130；本目录不覆盖或改写124。

## 已有检查与范围限制

`delivery/`保留最初交付的driver、launcher、23项host收据/log、manifest和README。原README/独立交付检查是在启动前写的历史原字节；其中“尚未执行服务器”的时间状态已被本页的实际early failure更新。

23项检查包含actual120完整任务元数据、原109 clean模块及本地冻结S2e源码guard、actual57日志/功耗parser、actual120 task00的22,512pin未知dwell输入布局、冻结common Tcl和篡改负例。**这些检查未执行完整服务器`check_report`，所以未发现合法raw收据字段形状差异；23项PASS不能描述成124端到端通过。** 使用actual57的报告仅测试parser，未与S2e活动拼接为能耗数字。

独立只读审查还记录了124的Tcl绑定边界：生成后记录脚本SHA，但run没有从原own89上下文再次重建Tcl；若同时改prepared及Tcl，仅重核两者身份不足以证明语义绑定。新130把重建检查加到了run guard。`independent/xu_s2e_power124_readonly_check.py`是额外只读检查程序，其server campaign模式未在124执行；本归档只运行过它的交付字节模式。

工具保留原source/own89/109/120检查、full-DUT strip path、真实SAIF TX/TZ/TB及原生pin/annotation/Liberty报告计划；没有填零未知活动，没有驱动Q，没有修改Chisel、RTL、DB、网表或SDC。PT getter的`x_probability=0`与物理Q已知、toggle coverage与file注释率仍是不同概念。124没有执行到这些PT测量，不能授予任何能耗或150MHz资格。

## 复核

```bash
python3 docs/validation/xu-score-s2e-power124-tools-20261105/check-evidence.py
python3 docs/validation/xu-score-s2e-power124-tools-20261105/check-evidence.py \
  --extract /absolute/path/new-xu-power124
```

默认校验逐字核对全部17项载荷、原handoff/23检查收据、服务器执行副本、唯一错误、PID缺失快照，以及实际120收据的字段形状原因。PASS只覆盖这些事实，不代表重跑PT或原件未返回正文的重哈希。

完整重跑23项host检查还需要本工作树已有的actual125活动正文、actual57原报告和clean原109工具checkout；程序会在新临时目录复制冻结工具，只链接只读fixture目录，不修改生产guard：

```bash
python3 docs/validation/xu-score-s2e-power124-tools-20261105/check-evidence.py \
  --rerun-host --workspace-root /home/mxhanks/Projects/ChipContest-xu-score-opt \
  --frozen-tools /home/mxhanks/Projects/ChipContest-xu-score-opt/build/xu-s2e-power124/frozen-tools109
```

这条归档重跑已实际通过23项。它保留了原检查的覆盖范围，也会继续漏掉124的整dict比较错误；该已知错误由本归档原件和新130的完整12任务身份形状测试覆盖。不要重新启动或删除原124输出；新功耗测量使用独立130编号。
