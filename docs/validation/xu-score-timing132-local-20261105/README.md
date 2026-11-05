# xu132：冻结只读采集器、真实126失败原件与本地红绿反馈

本目录归档132上传原字节、actual126失败的完整export131包，以及13项机制检查和10项
回归。**本目录不包含132服务器终态证据**。根任务随后观察到132执行完成；其原件
应在独立server135归档审查，不能由这里的主机检查推断。全部保持 `NOT_QUALIFIED`。

|上传原件|字节|SHA256|
|---|---:|---|
|`tools/xu_timing_coverage132.py`|39436|`d40a163adf3fe13cbce0a9ecee9258929a07eb53068781a7ce9054694c152f91`|
|`tools/launch_timing_coverage132.py`|2339|`aa7fae3cf83b0892cf4c542572e87c91bd7c1ea6c51b6438ee4304bdc2eade2d`|

actual126失败终态SHA `e6b6bd0e…237fa`，两次native PT分别rc0/marker1与rc1/marker0。
原日志2017条SEL-005和最终第二级PMU `erst_reset_r_r_reg/Q` 缺失均保留。mapped116
明确该DSNQNV只提供QN；5个reset输出精确为Q、QN、Q、Q、Q。literal macro mode pin
2016条无net对象，另有第一级PMU D literal；原调用点主机重放能复现两种症状。

132使用已安装native `pin.net` collection、记录空net/clock集合并在命名前判断空集合，
核对每个reset唯一真实输出；缺省arrival/slack标ABSENT，不改变保存/传播设置。
每行flush使失败原件保留完整行；原126未关闭文件导致部分TSV尾行截断，原字节保留，
不能把截断表补齐后冒称native结果。

actual131还完整保存336宏2688条mode/CLK/CEN记录和10832条period详情：10416 inactive
constant_disabled、416数值MET、0 violated。336宏有HF clock，80宏另有PLL，所以
256宏各32项、80宏各33项。132修复数值slack而无文字“met”的原生格式，按
(pin、clock、condition)和实际CLK.clocks核对，正负slack及原summary交叉验证；舍入0
保持未知，无限/缺值拒绝。该结论只涉及116映射的宏min-period，不能晋升全SoC资格。

完整原包`xu-server-coverage-progress-20261105-131.tar.xz`为305944字节，SHA256：

```text
64f1b81c1615bfe0708c902342ebb5551baa5eb67358307c9ebdf4d6816398b3
```

内部manifest49项载荷、21058148字节全部重新验证。原包含伴随128/130观察，本目录
只核验伴随原字节，不解释其功能或功耗。private-manuals正文原导出已排除，保留
installed-options.json字节/哈希；没有改写工艺手册或原报告。

只读核验工具、131全部原件、actual126脚本/log/36项输出及本地结果：

```sh
python3 /home/mxhanks/Projects/ChipContest-xu-score-opt/docs/validation/xu-score-timing132-local-20261105/check-evidence.py
```

独立重跑原13项机制+10项回归，输出目录必须不存在：

```sh
python3 /home/mxhanks/Projects/ChipContest-xu-score-opt/docs/validation/xu-score-timing132-local-20261105/run-hostchecks.py \
  --out /tmp/xu132-new-archive-hostchecks
```

适配器从本目录131包、相邻已提交122包及126属性fixture重建临时输入树；原5个Python
工具按原字节复制，不重写代码或数值。实际116 mapped/STA/coverage/state全部验哈希。
原13项结果逐字节相同，10项红绿反馈按结果与输入哈希核对；其reset/display输入明确
标成ARTIFICIAL，只有macro/period部分使用actual131原件。未执行本机EDA。

`original-delivery/`保留最初README/handoff和最终本地receipt；其中“未执行”是当时的
交付状态。后来的server132结果独立审查。本地修复未修改Chisel、RTL、MMIO ABI、
数值格式、向量或任何时序约束。所有原131警告、缺路径与失败仍保留。

历史服务器复现命令，已有132目录时只读观察原PID/state，不重启：

```sh
python3 -u "$HOME/Desktop/launch_timing_coverage132.py"
```

两份冻结上传文件位于Desktop，输出`full-soc-coverage-rdc-20261105-132`。132仍是同一
116原SDC/scope和ideal-clock场景，只临时切换并恢复文档支持的report DISPLAY选项。
不加clock、case、cut、exception、propagation或horizon；reset物理安全、UART、模拟
metastability、全SoC150MHz、S2e本身及评分均未由此获得资格。
