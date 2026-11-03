# xu 联合采集器第三方头文件分类：完整 host 验证原件

独立代码 producer `61f74dc2741764be79194b73aff064589d9c3d6a` 的10项 host 测试实测12.582秒通过，未跳过。这里只归档 host 证据；实际 VCS 编译、活动语义、条件功耗和全SoC能量仍需服务器原件证明。

修复仅把编译选中的第三方 VPI include 目录设为 `-isystem`；自身 C 源码的 `-Wall -Wextra -Wshadow -Wstrict-prototypes -Werror` 不变。`-MD` 继续冻结 system header 依赖。合成头文件模拟旧式函数指针声明，包含实际 Icarus VPI 接口；它从未被宣称为 VCS vendor header。相同生产 C 用 `-I` 实际被拒绝，用 `-isystem` 实际编译成功；自身追加旧式函数定义仍被拒绝；编译后更改 synthetic vendor header 触发冻结检查。

`raw/` 保留30项输出原件，包括实际 GCC 编译命令、依赖身份、所有10项测试、336宏22,512端口路径实际 elaboration、真实回调边界检查和已有负例。日志路径及空白保留，不要求归档后原临时目录继续存在。`evidence-tools/` 固定生产入口、上下文、源码及测试。`recheck.py` 离线核对全目录原件和 header 分类语义；`--self-test` 对重新签名后的6种语义破坏逐项拒绝，不能靠重算 manifest 掩盖条件。

复现原测试（会执行实际 GCC/Icarus/RISC-V 固件构建，需要冻结 S2c 源树）：

```sh
XU_S2C_SOURCE_ROOT=/path/to/frozen-s2c \
XU_JOINT_COLLECTOR_TEST_EVIDENCE="$PWD/build/new-joint-header-tests" \
python3 -m unittest discover -s tests/host -p test_xu_candidate_joint_task_activity.py -v
```

离线证据复核：

```sh
python3 docs/validation/xu-score-joint-collector-header-host-20261103/evidence-tools/recheck.py --self-test
```

所有归档文件逐字节SHA256与size见 `manifest.json`；检查通过仅覆盖本段 host 声明。
