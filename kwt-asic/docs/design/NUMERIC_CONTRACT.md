# 候选数值契约 fixed16_acc48_v1

日期：2026-10-15，Asia/Shanghai。状态：**功能原型候选**。本文为软件/RTL 联调定义一个明确可测试的格式，不是永久数值冻结，也不证明比赛真实 KWT 数据的 3% NRMSE 门槛、时序或面积已经通过。量化尺度尚未标定；后续由训练划分无梯度标定及验证划分结果决定是否采用或修订。

## 运算、布局和位宽

```text
Y[r,c] = bias[c] + sum(k=0..63, X[r,k] * W[k,c])
r = 0..98, c = 0..255
```

| 张量 | 形状 | 整数码 | 文件次序 | 实数解码 |
|---|---|---|---|---|
| X | 99×64 | 有符号16位 | 行优先，索引 r×64+k | X_code × 2^x_exp |
| W | 64×256 | 有符号16位 | 行优先，索引 k×256+c，不转置 | W_code × 2^w_exp |
| bias | 256 | 有符号40位 | 按输出通道 c | bias_code × 2^(x_exp+w_exp) |
| Y | 99×256 | 有符号48位 | 行优先，索引 r×256+c | Y_code × 2^(x_exp+w_exp) |

`x_exp` 和 `w_exp` 都是**显式整数指数**，每个层配置单独提供，无默认尺度。此版本为每张量一个尺度，不做每通道或每元素尺度。偏置和输出尺度严格等于 X/W 尺度乘积，因此偏置整数可以直接与乘积相加。

每次点积先将 bias 符号扩展到48位，然后按 k=0..63 依次计算16×16位带符号精确乘积，符号扩展并累加到48位。乘法、MAC中间及输出均**不舍入、不饱和、不截位、不取模**。所有输入整数码必须在指定有符号范围内，越界为调用错误，不静默修正。

范围证明：任意乘积的绝对值 ≤2^30，64项乘积绝对值之和 ≤2^36；偏置绝对值 ≤2^39。任意部分和绝对值 ≤2^39+2^36<2^40，远小于有符号48位边界2^47。合法输入不发生累加溢出，Y无需饱和。软件用Python任意精度整数执行确定顺序，再检查48位范围；RTL应实现同一运算，不能依赖隐式无符号扩展。

12个编码器层分别提交对应权重、偏置和尺度。`LayerParameters` 以0..11编号，对数据深复制为不可变元组，避免外部列表修改造成层间污染。软件计算无隐藏缓存，不从上一层隐式继承参数。各层输入必须来自该层第一前馈线性层位置，不把前一层硬件线性输出直接当下一层输入。

## 编码与解码

浮点/有理数编码：`q = saturate_signed_B(RNE(real / 2^exp))`。

- RNE为最近偶数舍入，正负半整数都遵守同一规则，例如1.5→2、2.5→2、-1.5→-2、-2.5→-2。
- 编码完成舍入后饱和到 `[-2^(B-1), 2^(B-1)-1]`；这是输入/权重/偏置格式转换，不是MAC中间饱和。
- 使用 `Fraction` 精确表示传入浮点的实际二进制值进行缩放与舍入，避免浮点中间运算改变半整数判定。NaN/Inf、布尔值、复数、文本输入均拒绝。
- `decode_exact` 返回精确 Fraction；`decode_scalar` 返回binary64，拒绝溢出到非有限值及非零数下溢成0。48位整数可以在binary64有效精度内精确表示，普通模型尺度的解码无额外整数精度损失。
- 不自动为输入选择尺度；当前合成向量可以仅使用整数码，但真实精度评测必须记录实际尺度、转换脚本版本、权重和样本哈希。

## 软件接口

模块：`model/fixed16_acc48.py`，只依赖Python标准库。

```python
from model.fixed16_acc48 import (
    Fixed16Scales, encode_scalar, decode_scalar, dot64,
    quantize_linear_inputs, linear99x64x256, decode_output,
    LayerNRMSE, write_linear_mem_vectors,
)

scales = Fixed16Scales(x_exp=-10, w_exp=-12)  # 示例，不是标定结果
x_q, w_q, b_q = quantize_linear_inputs(x_real, w_real, bias_real, scales)
y_q = linear99x64x256(x_q, w_q, b_q)
y_real = decode_output(y_q, scales)
metrics = LayerNRMSE()
metrics.update(layer_id, y_real, y_float_reference)
partial_report = metrics.report(require_all_layers=False)
```

主要入口：

| API | 返回/用途 |
|---|---|
| `encode_scalar(value, bits, scale_exp)` | RNE+饱和整数码 |
| `decode_exact(code, bits, scale_exp)` / `decode_scalar(...)` | 精确Fraction/有限binary64 |
| `dot64(x64, w64, bias)` | 精确带偏置48位整数结果 |
| `linear99x64x256(x,w,bias)` | 严格完整形状的 `list[list[int]]`，无NumPy依赖 |
| `quantize_linear_inputs(x,w,bias,scales)` | 完整形状编码后的三个张量 |
| `decode_output(y,scales)` | 严格99×256有限解码输出 |
| `LayerParameters(layer_id,weights,bias,scales)` | 独立不可变层参数；`.compute(x)` 执行线性层 |
| `validate_layer_set(parameters)` | 必须恰好12层，按0..11返回，无重复或缺层 |
| `ErrorSums.update(decoded_flat,reference_flat)` | 通用非空等长向量的跨样本统计；不是竞赛形状检查入口 |
| `LayerNRMSE.update(layer_id,decoded,reference)` | 严格99×256样本，按层独立积累 |
| `LayerNRMSE.report(require_all_layers=True)` | 缺层报错；逐层NRMSE及最大值，明确仅针对已提供样本 |
| `write_hex_mem(path,values,bits)` / `read_hex_mem(path,bits,expected_count=None)` | 单词/行固定宽二进制补码hex，返回文件信息/整数列表 |
| `write_linear_mem_vectors(directory,x,w,bias,scales=None)` | x/w/bias/y.mem及含SHA-256、形状、尺度的manifest |

## 误差汇总规则

每层维护 `sum_error_sq`、`sum_reference_sq`、元素数 `count` 和样本数 `samples`，跨该层所有已提供样本累积：

```text
error_rms     = sqrt(sum_error_sq / count)
reference_rms = sqrt(sum_reference_sq / count)
NRMSE[layer]  = error_rms / max(reference_rms, 1e-8)
final_NRMSE   = max(NRMSE[0], ..., NRMSE[11])
```

**不能先求每样本NRMSE再平均。** 例如参考值分别1和100，解码值分别2和100，正确汇总为 `sqrt(1/10001)`，不是0.5。分母下限作用于reference RMS，不能作用于平方和或均方。

空样本、错误形状、NaN/Inf及binary64统计溢出拒绝，失败更新不会改变既有统计。平方和以 `math.fsum` 汇总本样本并累积，报告保持样本数和元素数供复核。12层统计各自独立；完整性还需要调用者核对样本manifest、每层样本覆盖和固定配置，API不会凭层数推断已完成600条官方评测。每个性能任务独立3%门槛也须另行记录，不能只看整体均值。

## 仿真文件和验证边界

`.mem` 每行一个固定宽小写hex字：X/W为4位，bias为10位，Y为12位。负数用对应位宽的二进制补码。地址次序见布局表；不插入地址标记、注释或未知态。输出文件为软件参考结果，仅供testbench对照，DUT仍必须自行计算。

单测入口：`python3 -m unittest discover -s tests -p test_numeric_model.py -v`。覆盖RNE正负ties/邻点、饱和、极值累加、100组确定种子随机点积、完整矩阵方向/末行末列、独立层参数、编码解码、跨样本NRMSE、缺层/空/非有限输入及hex往返。全部使用合成数据；PASS不能推广为真实KWT精度、RTL通过、E203通过或PPA合格。
