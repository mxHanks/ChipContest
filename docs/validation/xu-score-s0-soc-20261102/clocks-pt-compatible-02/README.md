# xu PT命令兼容与真实分析SDC身份

本地时钟源/控制检查通过；这些日志不是STA结果。实际服务器PT实验另行保存，不由host fixture模拟为合格。

PT T-2022.03要求指定master_clock时同时使用create_generated_clock -add；其get_clocks只接受名称模式，端点时钟使用pin的clocks属性查询。DC write_sdc对HF/LF周期舍入，PT和功耗分析改为source同一份原始constraints.sdc，保留精确频率及完整Tcl集合操作。

sdc_sha256继续绑定DC导出的mapped.sdc；新增analysis_sdc_sha256分别绑定实际分析constraints.sdc、prepared源身份、execution和power输入/回执。缺失、错配、符号链接和运行中改动均拒绝，失败不会写成成功。10项host测试通过，含12个独立窗口的调度检查；所有EDA mock明确为HOST FIXTURE ONLY，不提供能量或时序结论。

复现：python3 tools/ppa/xu_review_full_soc_clocks.py --out /absolute/new/clock-review --run-rtl；python3 -m unittest discover -s tests/host -p test_xu_soc_ppa_flow.py -v。生成的clock.vvp仅为本地中间二进制，不提交。
