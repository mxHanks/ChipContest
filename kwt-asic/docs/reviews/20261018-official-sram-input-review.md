# 官方材料预检独立只读审查

2026-10-18。独立代理只读检查代码、文件分类测试、原生命令/报告/SHA，未跑EDA或修改生产源码；主代理整理本页。

## 原接入缺口

旧选择器将功能仿真与完整PPA材料绑在一起，综合复用功能源，同一Liberty跨角色被拒绝；旧开发CLI未接通official。旧READY只检查存在性，内存配置探针可用错误模块名/Markdown技术文件得到backend3选择结果，**不是设计编译或功能PASS**。旧默认BLOCKED仍正确，本轮没有将其改为READY。

## 新工具及必要修复

独立预检按simulation/synthesis/timing/ppa分阶段，输出各用途源集，保留Liberty角色并去重文件依赖。所有PASS/FILES_VERIFIED均限定文件身份/分类，不解析HDL/Liberty、不同意来源真实性或功能/PPA。实际官方模型/Adapter/编译与回归仍未完成。

只读探针发现含NUL和超长路径会使早期实现直接抛异常，现已捕获为角色FAIL并保存完整结果；新增两项测试。原20项分类测试加路径2项通过，未通过正则假装验证模块声明。缺包、错误类型/路径/哈希和重复RTL拒绝；互斥用途允许共享条件编译文件，setup/hold/power允许同一Liberty。

## 原生与来源复核

最终证据为`artifacts/diagnostics/20261018-official-sram-intake/final/source-bound/result.json`：

- 9个CLI和host/verify共11条原生命令，退出序列为`2×5, 0, 1×3, 0, 0`，native/log/SHA/PID身份和完整标记核验一致。
- 5个真实空清单case全部BLOCKED；非HDL私有分类夹具只在simulation得到FILES_VERIFIED，库存及更高阶段仍BLOCKED。wrong SHA、NUL和超长路径均明确FAIL，无Traceback或空报告。
- 所有CLI保留`official_validation=NOT_RUN`和`official_ppa=BLOCKED`；226主机测试真实Ran226/OK。没有官方硬件任务、HDL仿真或EDA。
- v3相对v2仅新增独立输出目录及首条命令前保存7项源身份/输入SHA/初始报告；canonical identity与最终输入/产物一致。不能回填声称v2已预冻结。
- 初次驱动因宿主盘拒绝NUL保留日志名而失败，旧失败保留；后续仅改日志标签及独立输出目录，没有通过跳过NUL路径拒绝用例获得通过。

旧参考里程碑596条记录SHA仍一致。新增工具不改冻结旧Make、选择器、RTL、Golden或回归producer；文档明确旧官方CLI尚未接通。验收仅为文件预检工具，官方功能和正式PPA继续阻塞。
