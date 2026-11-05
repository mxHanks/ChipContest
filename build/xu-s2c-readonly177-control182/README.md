# xu182：将同S2c只读177接入原总控

本目录只登记已审查177；不直接启动PT、初始化/替换控制器、停止或重跑任何任务。
使用原153同一输出目录及单native槽位。依赖173自动归档终态和167诊断采集成功。
查询只读取S2c自己same9c16、原57时钟方法/SDC和两库；不借S2e155图或时钟方法，不改设计。

服务器部署：将177的5 runtime和manifest放入`D/xu-s2c-readonly177`；本目录的
`register182.py`和`s2c_readonly177.json`放入`D/xu-s2c-readonly177-control182`。

仅登记：

```sh
python3 -B "$HOME/Desktop/xu-s2c-readonly177-control182/register182.py"
```

job SHA为`a86e46ab86453c48e8dbf57df4ef40c3401e824448c4bb8ec0510457869bba8d`。
脚本核对原153 SHA/live PID/startticks/argv、scope163、173回执与原注册身份，
以及全部177 runtime/图/库/模型/SDC/工具的冻结SHA。注册前后均重新核对，输出目录必须全新。
原153原子register同ID仅允许逐字节幂等；不重复启动现有worker。

登记回执为`B/s2c-readonly177-registration-20261105-182.json`；任务输出为
`B/s2c-own9c16-readonly-20261105-177`，原生状态和小输出manifest都由177保存。
日常仍用`D/xu-campaign-batch154/campaign154.py status`；所有结果`NOT_QUALIFIED`。
原173最终171包在177之前生成，因此不包含新177原生结果；后续须单独取回177自己的manifest/报告。

部署、登记与原生执行是三个不同状态，必须以服务器实际回执和进程观察为准。
