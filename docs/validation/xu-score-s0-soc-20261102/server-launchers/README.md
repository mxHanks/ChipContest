# xu S0 服务器实际启动器

本目录原样保存本次授权服务器调用的实际Python启动器，凭据不在脚本或仓库内。`s0e.py`部署e998479到独立服务器clone、创建campaign-01；实际因Python3.6 keyword和DC空布尔属性失败。`s0f.py`部署ac85d6a、创建campaign-02；VCS对照与DC独立运行，当前完整结果尚需收取。`s0p3.py`为DC约束完整Tcl加载修正664186d创建第二个独立clone及campaign-03-ppa，避免修改仍在跑的VCS源目录。

目录中状态查询器仅查看自己的输出和`/proc`命令行。所有EDA子进程stdin关闭；长任务脱离图形终端进程组并保留driver log。源码/bundle SHA和Git commit均在启动时核对，已有目录拒绝覆盖。

这些启动器面向原服务器的特定路径，调用`python3 ~/Desktop/<启动器> start`。再次执行必须选择新的目录及独立clone名，并审查其bundle/commit绑定；不能直接覆盖本次日志或把当前状态文字当作完成证明。原始运行结果将另行补录。运行前阅读`docs/xu-full-soc-ppa-execution.md`及`tools/ppa/xu_soc_ppa_harness.md`。

真正可重放的通用入口是仓库工具；启动器仅封装本次实际部署/命令，不能替代数值日志、时序覆盖、面积、能量和综合后功能证据。
