# xu SRAM 连续联合活动：本地 C/VPI 验证

独立 producer `b2df9ff`（新增实现 `d8ac2bd` 后缓存控制投影）实测完整9项测试在2.666秒通过，无跳过。C以明确 `-Wall -Wextra -Wshadow -Wstrict-prototypes -Werror -O2` 命令编译；实际 Icarus/VPI 直接观察真实端口连续变化。所有原 collector、baseline helper 和源 guard 保持原样。

微基准覆盖256种 known控制组合的42时钟模式完整互斥分区、false遮蔽X但unknown不并入false、同timestamp三次CLK变化与两次Q NBA变化、边界事件和相同边际而不同联合相关性。standby的Q在实际 `RET1N & GWEN` 为true时仍保留未知。352个独立开放微实例共70,400个实际CLK边沿、所有67bit直接统计、全部121弧展开和Q的100ns true-condition未知驻留逐项精确核对。13种重签语义篡改、错误真实port role/precision与未完成窗口均被拒绝。

`raw` 保留原始命令/日志/输出；scale352较大统计仅作无损gzip，未解压字节的SHA/size记录在 `compressed-originals.json`。前后缓存优化的10个原始统计/sidecar输出逐字节完全相同；回执和优化前9项通过日志一并保留。

`development-negative` 保留最初开发测试中 D[0] 第二条件预期数值写错的失败：预期误把256模式中GWEN=0半程也算为true；独立按3ns初始+256ns已知true模式+1ns匹配+2ns尾段重算为262ns，false259ns，unknown3ns。修正的是测试预期，未改该统计实现或回写原失败日志。当前测试代码中的解释可复核。

本证据不表示VCS、指定vendor模型、正式任务窗口或实际mapped宏身份已经通过。尚未接入新的formal joint collector；VCS调度/SAIF事件定义/PT条件活动来源、完整STA和能量资格仍待实际验证。源码/API/复现命令与明确局限见 `evidence-tools/README.md`。

```sh
XU_JOINT_TEST_EVIDENCE="$PWD/build/xu-joint-tests-new" \
python3 -m unittest discover -s tests/host -p test_xu_sram_joint_activity.py -v
```

`manifest.json` 对其他所有交付文件逐项记录 SHA256 与字节数，不改原始空白或日志内容。
