# 新比赛仿真

`tb_kwt_linear_engine.sv` 驱动完整X/W/bias装载、DUT计算和输出核对。向量由 `model/fixed16_acc48.py` 生成；软件golden另以独立点积遍历交叉检查。DUT计算每个输出，TB不替代硬件计算。

运行 `make linear`（12组不同合成参数）和 `make linear-four-state`（2任务四态）。覆盖完整99×64×256+b、正负/零/极值/精确相消、99行尾、连续重装、回压稳定性、计算中复位及非法/重复地址。结果写独立artifacts/runs目录，轻量报告副本在docs/runs。当前功能配置为8lane；合成数据只证明已测功能，正式3%门槛需实际KWT数据。

原FPT参考仿真继续使用 `make rtl` 与 `scripts/verify/run_checks.py` 的显式文件集。两类结果不能互相替代。
