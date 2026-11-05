# xu211：自动回传209的独立本地审查

结论：当前`aa37599`的209本地审查通过，可由根线程的原153总控受控登记；本审查没有远程操作、原生EDA或资格晋升。原9项fixture独立重跑通过，另12项integration检查通过。

逐字节比较191实现：除191→209身份/namespace、唯一native_query207 job与native-query-replay-20261105-207输出root、以及四份208登记原件来源之外，其余逻辑完全相同。`exporter171.py`仍严格固定SHA9c72cfa8...，singlePID、读取前后输入冻结、16MiB界限、symlink/源拒绝、freshout/noclobber与失败原件保留均未改动。四份208为B下registration/install JSON、Desktop/xu-native-query-control208下register208.py/frozen-jobs208.json；是本项目登记代码与回执，没有库/模型正文。

真实运行fixture的209→冻结171引擎生成xz归档，再实际调用safe171.inspect与fresh unpack，逐文件bytes/SHA匹配。验证模型/库/RTL/SAIF/SDC/SDF/C/PDF等来源正文排除、报告保留、>16MiB仅稳定bounded SHA、blocked parent/软链接拒绝且失败原件保留、四份208正文原样保留、缺失显式missing而非伪造、208软链接拒绝、其它候选根目录未读取。

job固定唯一`native_query207` terminal依赖、native=true占原单槽、direct argv唯一209 output、process_contains=result namespace一致、state.json成功/失败终态与实现一致，两个frozen_inputs分别入口与原171引擎。原171/191包无覆盖路径。

原先e3a2698版本亦曾通过9项integration。第一次211 namespace比较误将冻结SHA内部的字符191改为209，导致测试本身失败；已精确保留冻结SHA，失败日志保留为independent211-attempt01.log。aa37599增补208回执后重新跑完全部当前检查；未改root209原件。

复现：

```sh
cd /home/mxhanks/Projects/ChipContest-xu-score-opt
python3 -B build/xu-query-autopack209/test209.py
python3 -B build/xu-review209-211/review211.py
```

这些是本地fixture，不是207已运行/209服务器已归档的证据。后续仍须检查实际总控/worker与回传manifest。
