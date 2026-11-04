# xu 实验116本地交付与115只读复核归档

本目录归档的是 **116服务器运行前的本地准备、14项本地检查，以及115只读复核**。
它不包含116服务器执行或完成证据。所有结果保持 `NOT_QUALIFIED`。
原handoff与README中的 `READY_FOR_ONE_INDEPENDENT_SERVER_RUN_NOT_EXECUTED`
措辞原样保留，仅表示归档时该本地交付的范围，不能据此判断当前服务器进程状态。

压缩包 `xu-timing116-local-original-bytes.tar.xz` 保存78份原件、24,908,686字节，
压缩后263,804字节，SHA256：

```text
1afaa781fa6899b4aa7a988184c6e4bf780bb8c3330ebf2d267a0bc754cce7a2
```

`manifest.json` 逐份记录原相对路径、原绝对路径、字节数与SHA256。压缩包包含：

- 116冻结worker、launcher、原本地checker、README、handoff和祖先复核JSON。
- `local-check116-final/` 全部原件，包括14项结果、生成Tcl、人工进程正反例及日志。
  较早版本 `local-check116/` 没有打包，不能用来替换最终worker的检查结果。
- 115只读说明、复核JSON与其全部11份实际输入，以及reset资格复核说明。
- 49/50/63/73/79/95六祖先原state、DC/PT日志及脚本；FM49原state、日志和模板；
  95补充hold/删除预检原件，61插入脚本与原日志，FM66原日志与脚本。
- 原61生成器和115讨论UART候选时使用的UART/FIFO源文件，均未修改。

116最终两份上传文件身份：

|文件|字节|SHA256|
|---|---:|---|
|`xu_timing_combined116.py`|49426|`8b6a464d94377a5df8bc1fac78b61eae1e5852c801ff453be2b8d4937d29d860`|
|`launch_timing_combined116.py`|2090|`bb738012d0f45545bd5ac73f7d948137d80c8ffee753e0e07cbd63ddd229f7b2`|

服务器预定命令为 `python3 -u "$HOME/Desktop/launch_timing_combined116.py"`。
本归档checker不会运行该命令。已启动的实验应读取其原state/PID，launcher遇到既有
输出目录会拒绝重启，不能删除旧目录规避。

从任意目录验证压缩包及逐份原件：

```sh
python3 /home/mxhanks/Projects/ChipContest-xu-score-opt/docs/validation/xu-score-timing116-local-20261105/check-evidence.py
```

仅用归档输入，重放原14项本地检查：

```sh
python3 /home/mxhanks/Projects/ChipContest-xu-score-opt/docs/validation/xu-score-timing116-local-20261105/check-evidence.py --replay
```

checker先核对整包和全部原件，再独立核对handoff/launcher/tool哈希、六祖先实际
DC/PT日志和脚本绑定、FM49的169文件before/after回执，以及115原PT报告的27124条
untested计数、pin角色和336宏各31条非激活模式计数。重放时只在临时目录解压，
保留原相对目录布局、不改原脚本；已归档的final输出不复制到重放输出位置，
由原checker新建结果。临时目录退出后移除，原压缩包和历史结果不变。
原14检查及生成Tcl必须与归档结果一致。此命令已实际运行成功，输出保存在
`verification-local116.json`。

14项本地检查覆盖95实际17个source-only候选和5个reset端点、原日志/脚本身份、
reset片段除名称外与61一致、Python3.6语法、有界预检护栏、无新增约束、Tcl完整性、
危险selector拒绝、失败/被修改祖先拒绝及人工进程返回与成功标志门控。
它没有调用DC/PT/FM；人工进程日志不是服务器结果，Tcl完整性不证明native集合语义，
本机Python运行时也不等同服务器Python3.6。

115明确95与61来自不同映射分支，不能将95的17项min-cap和61的removal归零拼成一份
合格实现。116计划在95同一映射上有界清理、reset缓冲并重新完整FM/PT，仍保留两条
recovery UNKNOWN及其它覆盖缺口。即使其原生流程执行完，也需按最终实际报告判断，
不能把诊断完成视作时序通过。

本包不包含完整mapped/SVF正文、169份服务器原输入或工艺库正文；这些只能在服务器
由worker重新核对。baseline95的方法也不能代替S2e自身映射的时序、电气、面积和能耗
资格。没有新增Chisel修改、评分结论或功耗合格声明。
