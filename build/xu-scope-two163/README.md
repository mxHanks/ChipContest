# xu：仅保留 S2e 主方案与 S2c 对照

本工具由已审 `xu-defer-pe160/defer160.py` 最小复制。根据用户最新明确范围，历史八候选 `baseline_h1_h2`、`s1_h2_only`、`s1_sram_bias`、`s2b`、`s2d`、`pe32`、`pe64`、`compact32_128` 的原 activity145/power146 共16项注册不再追加评测。保留 S2c `mapped_private147`，S2e `s2e_power130`、`s2e_timing155`、`s2e_streamaudit156` 及其他非目标原行。后续修复批次161不属于本工具，也不应部署。

先验证服务器UID、固定153控制器文件SHA、release154.json本体SHA及16个原jobs文件SHA，再验证正在运行控制器的 PID/start_ticks/完整argv，以及每一份注册与state绑定。持注册锁，仅向精确匹配的控制器单PID发送SIGTERM；不发送进程组信号，不终止worker。确认旧控制器出生实例结束并取得控制器锁后，完整保存原state字节、全部注册、events和summary及逐文件哈希到独立新目录。

16目标中，原terminal、已启动、存活或已有result/output/run痕迹的行逐字段保持原样。仅确认从未启动的非terminal行，使用冻结153已有终态 `ADOPTED_TERMINAL_REVIEW_PENDING` 阻止未来调度，并附 `DEFERRED_BY_USER_NOT_QUALIFIED` 行政policy身份。所有原worker结果、日志、注册均不修改；没有伪造成功或资格。已启动评测自然结束。

最后用完全相同路径、SHA及out恢复冻结153，绝不init，不重试worker。恢复失败时保留原PID及receipt，先检查同一PID，不重复启动控制器。snapshot/policy/receipt独立位于原out相邻的 `unified-experiment-control-20261105-150.scope-two163-*` 新目录。

本机检查：

```sh
python3 -B -m unittest discover -s build/xu-scope-two163 -p 'test_scope163.py' -v
```

服务器检查与执行：

```sh
python3 -B "$HOME/Desktop/xu-scope-two163/scope163.py" inspect
python3 -B "$HOME/Desktop/xu-scope-two163/scope163.py" apply
```

固定服务器路径和UID，不能传入其他目录。重复执行保留既有行政terminal行。脚本自身未远程执行；本bundle只证明工具本机检查通过，所有实验结论仍为NOT_QUALIFIED。
