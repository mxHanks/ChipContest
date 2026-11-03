# xu 基线正式清空及首请求十二任务活动

实际服务器在冻结 E203 `f49a5fc914971426bd4530db39e270a84b41139f` 上完成 **12个独立VCS进程**，每进程只运行一个真实层任务。collector主提交 `26f14f64c4f0d58822412932f365d086ed0d273c`；后续仅工具/文档更新未改变捕获绑定的RTL、固件、observer或helper字节。状态为 `COLLECTED_12_TASKS_REVIEW_PENDING`，不是功耗或比赛资格通过。

每任务先由CPU通过原接口执行并被动核验 **33697次零清写**：W16384、完整256个40bit bias、8个legacy bias、64个X；禁用缓存、排空响应且idle后才允许首个源请求。本任务W/bias/X全部重新读取及装载在窗口内，没有跨任务复用。清空之外、首请求前的两个原始W目的设置独立计数；清空过程不计入本任务SAIF。

正式窗口为首个输入/参数源 **REQUEST** 至最后Y写响应 **RETIRE**，物理区间[begin,end)。十二任务各自实际 **1,370,856 elapsed cycles**、**9,139,040,000,000 fs（9.13904ms）**；inclusive诊断另记1,370,857，不混用。总elapsed为 **16,450,272周期**、**109.66848ms**。这与历史开发accept窗口16,510,344周期属于不同固件/物理宏/窗口配置，不据此声称新硬件加速或拼接面积能量。逐任务见CSV与result。

HF名义150MHz用1fs精度误差界计时，LF32768Hz，逐任务原日志含静态时钟控制检查。每层完整25344个输出/50688个Y字与固定向量一致，W/X/bias完整实际上传、3168次START/done及202752个8lane MAC有效拍被原严格检查器重验。336个物理SRAM宏（shared256/ITCM32/DTCM32/W16）与22512 pin observer状态、TX未知保留在服务器原SAIF；DTCM静态被单独观测，没有按零功耗处理。

本地取回13个唯一原payload（完整result及12份simulation log），每份大小/SHA匹配原export清单。原始raw/normalized SAIF、模拟器、ELF、镜像与实际服务器向量仍在服务器；本地仅重新验证其声明身份和实际日志，**没有在这里重新哈希完整SAIF或证明PT映射/Liberty/unknown转换**。每任务的原SAIF/归一化SAIF SHA与源身份在原result中保留。完整clear范围、标准单元覆盖、全SoC150MHz时序及最终能耗仍为待审。

```bash
python3 docs/validation/xu-score-s0-soc-20261102/clear-request12-server-20261103/check-evidence.py
```

该只读检查器核全部源helper身份、12份TASK/PERF/clear/request/retire与1fs时间关系，以及60个真实日志破坏拒绝。实际采集复现须冻结上述源、同SiFive GCC10.2/VCS2020和原厂商模型、全新输出目录：

```bash
python3 tools/ppa/xu_soc_task_activity.py --out "$xu_new_activity12" \
  --vendor-model "$xu_vendor_model" --netlist "$xu_frozen_mapped_v" \
  --constraints "$xu_exact_analysis_sdc" --cross-prefix "$xu_cross_prefix" \
  --clear-task-before-window --sram-pin-alias --task-ids 0,1,2,3,4,5,6,7,8,9,10,11 \
  --firmware-schedule bias-hw-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks
```

完整argv、工具/固件/source/model/向量身份均在原result。传输包516768 bytes，SHA256 `eb4aaacd2438ba0f6902c572795c6841548099a69320d6351f416a0c7d643de8`；其中91项完整清单与本目录13项选择清单保留，原字节未改。
