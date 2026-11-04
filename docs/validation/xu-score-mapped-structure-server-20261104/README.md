# xu 实际97：映射网表真实VCS结构探测

**真实服务器VCS完成了映射网表的结构探测。** 实际S2c原网表`9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892`、原RAMSP1024X16模型和原工艺库RVT标准单元模型共同编译、展开并运行至1fs，返回0。原生VPI精确核对336个宏、22512个pin bit、288个ITCM/shared预加载memory句柄，以及共享/加速器ICB命名接口。实际总模块数127549；每宏10端口/67bit，内部memory均256×64。escaped实例按真实handle匹配，未把名字中的点或方括号猜成层级。

**此结果仅证明结构与句柄可用。** 探测不驱动运行时钟、不写memory、不执行固件/任务、不采SAIF；不能认定功能、清空、数值、150MHz、活动或能量通过。原始TB不能直接换文件列表：有60类ACCEL内部路径、288条RTL层级预加载以及EXU/clock私有依赖。接下来需先证明相同vendor模型下VPI预加载和采样，再迁移task00的真实接口观察、同一clear/上传/结果窗和golden比较，之后才考虑12任务。

**实际build有150条警告，未隐去：2条OPD及148条TFIPC。** OPD来自RVT文件内部两组UDP重复声明；TFIPC包括映射层级/单元的少端口连接。现有结构PASS不证明这些警告均无功能影响。进入task00前需审查缺失端口方向、真实使用与重复UDP定义身份；不能把未连接输入一概当作无害。

模型提取90也已实际完成：只从服务器原始13.8GB的`/storage1/admin_public_dir/SMIC40_2025/S40.tar.gz`选择4个RVT Verilog成员，未改动库，输入压缩包stat前后相同。普通RVT模型2198450字节、1270个module、无include依赖，SHA256 `9ceaac7085f267c9a2da19d86aa9d88ddb25894df4b2485e32d13e04d0e46581`。本包只返回路径/成员/哈希/定义名称等元数据，不返回任何厂商模型正文。其余neg/pg版本身份在原始state中保留。

另保留属性解析失败的真实92定位：task00 `sram-pins-before.rpt`的第29块、offset906580–937158、`EMAW[0]`原文完全没有`relative_toggle_rate`，但constant_value=0、toggle_rate=0、static_probability=0、x_probability=0均存在。原块30578字节，SHA `20ffe78ab5914f75ee8fb58ed8b4138bfbcfa2fc5b29bd51663afc07377b0683`。完整原报告806159122字节的SHA在定位前后均为`a4d189cbc16c6f5cb36197f93566edd6eb76a009393002916ee0f98139566def`。这证明是原PT省略属性，未修复88、未补造relative=0，也不把此单块当完整24报告审查。

[原始98包](payload.tar.xz)35464字节，SHA `940fd1f01f23a32e023b4d1b1d98a32f330430663ebb40bebc7f4e1c7e64d944`；21项原字节共576557字节，[逐项清单](original-manifest.json)。实际编译、运行日志、C源、生成fixture、库提取身份及失败块都保持原样。原网表及厂商模型正文、编译生成二进制不在本包内；复现依赖同一服务器原件。[入口](tools/launch_mapped_probe97.py)固定原始输入及helper SHA，禁止重用已存在输出。

```bash
python3 docs/validation/xu-score-mapped-structure-server-20261104/check-evidence.py
python3 docs/validation/xu-score-mapped-structure-server-20261104/check-evidence.py \
  --extract /absolute/path/new-xu98-directory
```

实际服务器执行命令（复现前更换全新输出97目录编号）：

```bash
python3 "$HOME/Desktop/launch_mapped_probe97.py"
```

本次无生产Chisel、RTL或固件改动，不改变正式评分状态。
