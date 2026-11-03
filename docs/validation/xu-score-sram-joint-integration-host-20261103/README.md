# xu 独立 S2c 同窗口 SAIF / SRAM 联合采集入口：开发验证

代码 producer `5bf2a531070bb13551175f6d1b84184c1f250107` 的新入口9项实测11.993秒通过，未跳过。它完成实际 RISC-V 固件和C/VPI编译、336个端口注册及22,512条alias路径的真实elaboration、真实回调/边界守恒与篡改拒绝、工具所有tracked blob/mode隐藏改动拒绝、实际CLI拒绝错误inventory；新增原始PT表集合比较测试有7种破坏案例。所有 old collector/common/frozen guard 字节未改。

成熟冻结候选11项已在87.083秒通过，日志和42个输出完整保留；没有为本次文档重复它们。该套执行99行/所有3168组真实wrapper结果、9个数据或协议故障、实际复位链故障、22512-bit alias与未知值保留、绝对LF相位和原件校验。`development-negative` 保留前一次76.087秒运行中4项工具dirty guard拒绝：运行期间工具树未提交，失败是正确拒绝该来源；工具提交后全套通过，原始失败没有重写。

实际服务器 PT inventory20 的 raw TSV/JSON336宏、22512 pin/direction在本地离线逐集合核对一致，原件身份在 `raw/actual20-table-json-comparison.json`。这只是已有实际导出原件的比较；本机没有伪造工艺DB/netlist的 positive prepare。真实 DB、指定S2c映射网表和导出原件仍须在服务器原路径逐字节验证；SDC只作为绑定输入，不声称inventory导出已分析时序。

正式任务入口和源码说明见 `evidence-tools/xu_candidate_joint_task_activity.md`。工具必须来自本独立分支的干净已提交checkout，DUT必须为 d276b55 / child49a9436；不能拿加入其它PPA profile的root树代替。SAIF/联合统计若存在真实字段差异会保留并标记 NOT_QUALIFIED，不将raw改写或宽容阈值作为通过。转换守恒不表示VCS/SAIF/PT条件语义一致；微基准23及完整同配置能耗、时序仍另行审查。

复现：

```sh
XU_S2C_SOURCE_ROOT=/path/to/frozen-s2c \
XU_JOINT_COLLECTOR_TEST_EVIDENCE="$PWD/build/new-joint-tests" \
python3 -m unittest discover -s tests/host -p test_xu_candidate_joint_task_activity.py -v

XU_S2C_SOURCE_ROOT=/path/to/frozen-s2c \
XU_CANDIDATE_ACTIVITY_TEST_EVIDENCE="$PWD/build/new-frozen-tests" \
python3 -m unittest discover -s tests/host -p test_xu_candidate_task_activity.py -v
```

`manifest.json` 对本目录除自身外所有文件保存逐字节SHA256与size；所有原始日志空白保留。
