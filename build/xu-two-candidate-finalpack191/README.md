# xu191：两候选后续诊断统一归档

前台同PID调用逐字节冻结的171导出引擎；只导出177、186和190两阶段的诊断报告、输入回执、原生错误、总控状态与注册。
不启动EDA，不写实验输入，不覆盖173已生成的原171包。全部保留NOT_QUALIFIED。

固定路径：`B/two-candidate-finalpack-20261105-191/state.json`；原包`B/xu-server-two-candidate-final-20261105-191.tar.xz`。
job等待177、186、190 full12全部terminal后由同153总控启动；失败及缺失阶段同样归档，不能当作通过。
native=true沿用一个资源槽，避免与尚存活的原worker重叠。每个runtime/注册冻结SHA，未自行登记。

只允许json/log/tsv/csv/tcl/rpt等诊断后缀；不返回库、模型或RTL正文。两份SRAM pin报告始终仅流式哈希；其他大于16MiB报告也只哈希。
源文件读取按初始长度，保留fd前后、路径metadata、时间和遗漏清单。拒绝symlink，拒绝覆盖，源错误保留为失败。
生成的是live snapshot，未自动赋予终态或资格。原171安全验包器可直接验证新包全部路径、成员集、SHA和长度。

本地检查及生成：

```sh
python3 -B build/xu-two-candidate-finalpack191/test191.py
python3 -B build/xu-two-candidate-finalpack191/build191.py
```
