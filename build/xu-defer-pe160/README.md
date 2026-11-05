# xu：仅暂停现有32PE/64PE后续实验

用户希望不再优先考虑当前32PE、64PE两组。该一次性工具只处理已冻结153总控下的四项注册：`activity145_pe32`、`activity145_pe64`、`power146_pe32`、`power146_pe64`。compact32/128及其余候选不在范围内。

先验证服务器UID、控制器原文件SHA、PID/start_ticks/完整argv及全部冻结注册，四目标还匹配154原注册SHA。持注册锁，只向控制器单PID发送SIGTERM；不发送进程组信号，也不终止任何评测worker。拿到原控制器锁后，完整复制原state字节、所有注册、原events和summary到新目录并保存哈希。

四目标中，原terminal、已启动或存活、已有result/output/run痕迹的行逐字段保持不变。仅确认从未启动的非terminal行，使用旧总控已有终态`ADOPTED_TERMINAL_REVIEW_PENDING`阻止未来调度，并明确附`DEFERRED_BY_USER_NOT_QUALIFIED`行政policy身份。没有伪造worker结果或成功状态，未写入原worker结果目录。活动已启动的64PE继续自然完成；其尚未启动的功耗可同时暂停，避免停控等待。

随后恢复相同路径、相同SHA的153入口及相同out，绝不init，不改注册或重试worker。异常时，只在确认原控制器已经停止且worker绑定仍匹配后尝试同入口恢复。若恢复确认失败，保留原PID、独立receipt和日志，先检查该PID，禁止再次启动控制器。

本机检查：

```sh
python3 -B -m unittest discover -s build/xu-defer-pe160 -p 'test_defer160.py' -v
```

服务器检查及执行（固定原始目录，不能传入另一个实验目录）：

```sh
python3 -B "$HOME/Desktop/xu-defer-pe160/defer160.py" inspect
python3 -B "$HOME/Desktop/xu-defer-pe160/defer160.py" apply
```

receipt位于原out相邻新建`unified-experiment-control-20261105-150.defer-pe160-*`目录。每次调用独立留痕；重复执行会保留已有行政terminal行，不重启、覆盖或重做任何实验。所有结论仍为NOT_QUALIFIED。
