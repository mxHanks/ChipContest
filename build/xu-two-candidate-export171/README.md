# xu171：S2e/S2c只读证据快照与安全取回

Python 3.6标准库，仅写新证据包、临时快照和导出失败说明；不启动、停止、重试或修改任何实验。
本工具尚未远程部署或运行，主线程统一操作服务器。所有包均标 `NOT_QUALIFIED`。

服务器只需上传单个 `exporter171.py`，运行：

```sh
python3 -B "$HOME/Desktop/exporter171.py" \
  --out "$HOME/Desktop/xu-score-optimization-20261102/xu-server-two-candidate-20261105-171.tar.xz"
```

默认B为`~/Desktop/xu-score-optimization-20261102`，D为`~/Desktop`；可显式传
`--base B --desktop D`。同名输出或旧`.partial171`存在时拒绝覆盖；后续快照使用新输出名。
成功打印`XU171_READY`及原包字节数、SHA256、载荷文件数和字节数。按原grid70方法传输后，
必须使用该次打印的真实SHA，先check再解包新目录：

```sh
python3 -B build/xu-two-candidate-export171/check_unpack171.py check \
  --archive /absolute/path/xu-server-two-candidate-20261105-171.tar.xz --sha256 ACTUAL_SHA256
python3 -B build/xu-two-candidate-export171/check_unpack171.py unpack \
  --archive /absolute/path/xu-server-two-candidate-20261105-171.tar.xz --sha256 ACTUAL_SHA256 \
  --out /absolute/path/new-evidence171
```

固定白名单收集：

- 原控制150目录的state/events/SUMMARY/控制日志、所有原注册；164及170新三个job的runs日志/回执。
- B内168/170注册回执，以及D内170部署小回执、固定登记JSON/command JSON和脚本。
- 164完整state与12个task summary，失败说明保留；不打包压缩pin中间正文。
- 167 state、原完整生成TB、runtime C/headers、adapter plan与原生编译/仿真日志；不打包DUT网表、库或模型。
- 166 preflight/full12两目录result/prepared/execution/summary、inventory小报告/TSV/JSON/日志、逐层PT日志/Tcl/bridge receipt和原生`.rpt`。
  `sram-pins-before/after.rpt`始终只流式计算身份，不拷正文。

任何白名单文件超过默认16MiB也只记录有界流式SHA，不拷正文。巨大报告按打开时观察到的长度读取，
不会追逐持续增长的EOF；可能花数分钟读盘，但不用许可证，不一次载入巨大报告，也不运行EDA。
库、模型、manual、凭据、git、symlink、特殊设备均不在正文导出范围。

`snapshot171.json`逐文件记录source路径、fd读取前后及路径末次metadata、实际观察字节数/SHA和时刻。
每份副本明确是live snapshot；metadata不变也**不表示terminal冻结**，更不表示资格通过。
源文件被原子替换、增长或截短时仍可保留本次已读取字节，并明确标metadata改变。
`/proc` PID/startticks/argv是独立观察，不能只凭state或旧PID声称进程存活。
未出现的阶段文件列入`missing_at_observation`；source拒绝/失败列入`rejected_sources`；
失败实验原文照常保留，不筛掉失败status。

包内`manifest.json`对**全部已打包正文**逐字节绑定SHA/长度/集合，不包括其自身；外层打印的原包SHA绑定manifest本身。
本地checker先验证所有正文再建立新解包目录，拒绝路径穿越、绝对/非规范路径、符号/硬链接、目录或稀疏成员、
重复/未列文件、重复JSON键、文件父子冲突、超限包和SHA/长度不一致；解包时逐文件再次校验，
不调用`tar.extractall`。可省略`--sha256`作包内一致性检查，此时报告明确外层SHA未获指定值验证。

导出异常保留`.partial171`和`.failure171.json`；解包后异常保留目录和`EXTRACTION_FAILED171.json`，不删除失败证据。
解包成功写`checked171.json`。该校验只证明返回字节与包内声明一致；资格、native结果、源terminal及历史链仍须独立审查。

本地复现：

```sh
python3 -B build/xu-two-candidate-export171/test_export171.py
```

22项本地检查覆盖完整往返、外层SHA、所有要求组与12层summary、失败原文、巨大pin只哈希、
live增长截面、source链接/特殊文件拒绝、恶意tar路径/链接/成员/JSON/manifest/SHA和不覆盖。
测试只使用临时合成目录与本机自身`/proc`观察，不代表真实服务器取回或任何EDA验收通过。
