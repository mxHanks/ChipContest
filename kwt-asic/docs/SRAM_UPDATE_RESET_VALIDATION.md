# SRAM不同值覆写与复位门控补测

2026-10-18。上一轮8场景的Adapter入口明确留下“同地址不同值覆写”和“reset期间持续高enable”两个缺口。本轮新增独立TB/runner补齐这些开发场景，原RTL、Golden、旧TB、根Make和已冻结的Adapter入口没有修改。

## 复现

```bash
source env/activate.sh
# 行为模型与FF fallback：16场景，8组对照
python3 -B scripts/verify/run_sram_update_reset.py
# 显式加入开发逻辑Adapter：24场景，8组三后端对照
python3 -B scripts/verify/run_sram_update_reset.py --development-adapter
```

后端0/2使用当前行为/FF功能实现，后端3只使用显式开发夹具，不是官方宏。新入口没有接入真实官方材料，也未运行核心、E203、综合或PPA。各次运行创建独立`artifacts/runs/*-sram-update-reset-*/`，保留运行前输入/工具身份、原生命令、日志、binary SHA和最终复核。原生退出0、精确唯一完成标记、所有固定计数与后端签名一致才接受。

## 实际覆盖

原语：16×128/1024/4096。bank：16×3136/3200/2048、40×32、41×512。

每种形状选首末地址以及实际4096/1024/128深度片边界的两侧。全部地址先通过接口写入A并读回，再改写全宽补码B并读回；包括40/41位逻辑字的每一位翻转。检查器不依赖初始Q，也不使用整块清零或backdoor装载。

随后依次验证：reset低时写enable连续高，每个探测地址跨2个posedge，释放后payload不变；reset低时读enable连续高且切换地址，Q保持且valid=0；使能先撤销再释放、读enable已高时释放、写enable已高时释放的第一拍。最后先取得有效响应，再在两个posedge之间产生短reset，确认没有时钟沿时valid已清零而Q/payload保留。

| 形状 | 探测地址数N | 每后端分组检查数 |
|---|---:|---:|
| 三种原语、40×32 bank | 各2 | 各25 |
| 16×2048 bank | 4 | 41 |
| 16×3136、16×3200、41×512 bank | 各8 | 各73 |

固定分组计数为：覆写`2N`、reset写`3N+2`、reset读`2N`、无时钟沿reset`N+3`、释放`4`。每后端360，显式三后端共1,080；这些是五组计数，不包含TB中的其他辅助断言。三后端实际汇总为覆写216、reset写372、reset读216、无时钟沿reset180、释放96。8组数据签名均一致，各次读取另逐位检查预期值和四态valid，签名不替代逐项核对。

默认两后端另实跑16场景/720分组检查。它验证默认CLI与两后端范围，不与三后端的重复场景相加声称新增覆盖。

## 检查器的实际故障敏感性

```bash
python3 -B scripts/verify/run_sram_update_reset.py --development-adapter --inject-fault overwrite-dropped
python3 -B scripts/verify/run_sram_update_reset.py --development-adapter --inject-fault reset-write-leak
python3 -B scripts/verify/run_sram_update_reset.py --development-adapter --inject-fault reset-read-leak
```

三项均应退出1/FAIL。runner在自己的唯一输出目录生成原语私有副本，原源文件不改；故障仅在16×128、BACKEND=3原语场景执行，不把它们记作正常设计PASS：

| 私有故障 | 原生仿真结果 | 实际检出位置 |
|---|---|---|
| 忽略同址后续写 | exit1 | `overwrite-B`，地址0实际253c、预期dac3 |
| Adapter写enable去掉reset门控 | exit1 | `payload-after-reset-write`，地址0实际253c、预期dac3 |
| Adapter读enable去掉reset门控 | exit1 | `reset-read`，valid仍0但Q实际dac3、应保持02f0 |

故障运行均真实编译成功后在数据/保持检查失败，不能以“任何非零退出”替代指定诊断。未修改原存储器使负例通过。

## 结果与边界

[来源与运行索引](runs/sram-update-reset-20261018.json)记录5个原生CLI、246主机测试及静态入口；独立审查另核原生state/log和来源链。原830文件来源索引及其冻结实现保持不变。

这是现有开发存储契约的四态功能补测，非全部地址/所有序列的形式证明。没有供应商非法碰撞保证、真实宏引脚或电气验收；同bank同拍读写仍禁止。短reset仅证明数字行为，不证明工艺最小脉宽或恢复/移除时序。官方模型、指定PVT、完整150MHz/面积/功耗继续BLOCKED，官方功能NOT_RUN；模型到位后仍须按真实契约重跑并完成官方核心/CPU链。
