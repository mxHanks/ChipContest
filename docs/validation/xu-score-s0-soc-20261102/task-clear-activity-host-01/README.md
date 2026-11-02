# xu request窗口与公共MMIO清空的本地证据

这组证据限于本地host、Icarus和真实RISC-V工具链检查。没有运行VCS，没有完整SoC任务执行或实际SoC SAIF/PT结果，也不证明正式缓存政策、STA、能量或比赛资格。

`unittest.log`保存13项测试原始结果，`run.json`保存精确命令、host Python版本、厂商模型路径/SHA和测试前后源码未变化检查。运行入口为：

```sh
XU_TASK_ACTIVITY_VENDOR_MODEL=/absolute/private/RAMSP1024X16.v \
XU_TASK_ACTIVITY_TEST_EVIDENCE=/absolute/new/evidence-directory \
python3 -m unittest discover -s tests/host -p 'test_xu_soc_task*activity.py' -v
```

- `clear-mmio-*.log`与`tb_xu_collector_clear_mmio.sv`：对真实加速器RTL执行公共MMIO的33,697次清空写，再单独执行原任务两次目的设置；逐项检查全部W/X/bias物理存储为零及8-lane signed小算例。mode0通过；mode1缺W写、mode2不完整字节mask、mode3非零W写、mode4未排空W/X strobe均预期fatal。
- `clear-request-*.log`与`tb_xu_clear_request_probe.sv`：调用collector实际clear/request/payload观察器，首个source request阻塞3周期后仍完成16,384 W、256 bias、6,336 X、99行及3,168 START；改址、撤回valid、窗口前payload数据写和缺少第二目的设置均预期fatal。探针使用简化mock与固定步进，不能当作完整SoC时序或SAIF测量。
- `passive-probe-*.log`：保留默认payload observer正例和缺W、缺bias、缺X、错误W数值、窗口前上传五个破坏负例。其余host检查使用真实12层fixture映射，以及合成SAIF检查global/local ID、窗口时长、336宏、静态DTCM声明、缺宏/缺控制/未知控制拒绝；合成SAIF不是实测活动。
- `clear-firmware-build.json`、`firmware-*.log`、`firmware.dump`与`xu_clear_main.c`：真实`bias-hw-window/-O2/both-unroll-no-masks` RISC-V wrapper构建和内存审计；记录原main、实际编译源、helper、工具链及ELF/image的SHA。原main由wrapper绝对路径include，未编辑。ELF/image本身不进入本证据目录。
- `clear-partial-prepare-result.json`：真实global task7映射为本地layer0，状态严格为`PARTIAL_PREPARED_NOT_SIMULATED`；所有12层的304,128个Y先经独立整数golden核验。`--netlist`在该prepare-only测试中是明确标记的合成身份占位文件，不被模拟，不作为PPA证据。结果中的`analysis_sdc_sha256`绑定实际传入SDC字节，不冒充DC `mapped.sdc`身份。
- `clear-full-soc-336-compile.log`、`clear-full-soc-source-sha256.json`与`tb_xu_soc_task_clear_activity.sv`：用原始私有厂商模型对完整生成336宏SoC TB做Icarus elaboration；只用`XU_TASK_ACTIVITY_HOST_CHECK`屏蔽Icarus不支持的SAIF系统任务。状态仅为`ELABORATED_NOT_SIMULATED`，不能推出VCS宏引脚记录完整。

`tested-source-sha256.json`绑定测试时仓库源文件，`sources/`保留本次collector、两个host测试和用法文档快照。`manifest.json`绑定本目录全部证据（排除自身）；临时目录路径保留原文。厂商模型只记录路径/SHA，未复制源字节；模拟器和固件二进制均不提交。Python3.6仅通过grammar检查，未使用真实Python3.6解释器运行。
