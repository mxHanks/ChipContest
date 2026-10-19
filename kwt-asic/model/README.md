# 新比赛数值模型

此目录保存 KWT 第一前馈线性层的软件数值模型和误差评测契约，不复制旧 Attention CLI 为比赛模型。

`fixed16_acc48.py` 实现候选功能格式 `fixed16_acc48_v1`：X/W为有符号16位、bias为40位、Y为48位；长度64点积和99×64乘64×256加偏置均为精确整数累加。编码使用显式2的幂尺度、RNE和饱和，MAC中间无舍入/饱和。提供逐层跨样本NRMSE、固定宽hex向量和源输入哈希。只依赖Python标准库，支持Python3.8及以上。

契约见 `docs/design/NUMERIC_CONTRACT.md`；运行 `python3 -m unittest discover -s tests -p test_numeric_model.py -v` 检查边界、随机点积、完整形状和误差统计。

这是候选原型，不是永久格式冻结。下一步核对12层真实权重与对应前馈输入，以训练划分标定、验证划分评估；各层输入必须来自其 Attention+残差+第一 LayerNorm 之后。合成向量单测、单个真实权重/静音冒烟检查都不代表600样本比赛精度门槛通过，具体运行状态以根目录 `PROGRESS.md` 为准。
