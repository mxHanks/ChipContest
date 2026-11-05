# xu 数值交付契约：fixed16_acc48_v1

本轮以 `ddcf6cc5ea9119b3dd162249be8c4521eef45da2` 为平台基线，恢复兼容的软件数值链。负责人标识：xu。固定8PE、INT16输入/权重、INT40偏置、INT48结果及现有MMIO ABI；只恢复软件和元数据，不迁入旧分支的硬件、SRAM或工艺文件。

## 运算与编码

```text
Y[r,c] = bias[c] + sum(k=0..63, X[r,k] * W[k,c])
r = 0..98, c = 0..255
```

| 张量 | 形状 | 有符号整数位宽 | 行优先地址 | 实数解码 |
| --- | --- | --- | --- | --- |
| X | 99×64 | 16 | `r*64+k` | `code*2^x_exp` |
| W | 64×256 | 16 | `k*256+c`，不转置 | `code*2^w_exp` |
| bias | 256 | 40 | `c` | `code*2^(x_exp+w_exp)` |
| Y | 99×256 | 48 | `r*256+c` | `code*2^(x_exp+w_exp)` |

浮点/有理数转换为 `saturate_signed_B(RNE(real/2^exp))`。RNE为最近偶数舍入，正负半整数规则一致。标准库模型以Fraction表示输入浮点的真实二进制值；NaN/Inf、布尔、复数和文本拒绝。bias使用X/W尺度乘积，直接与乘积相加。

MAC全部为精确带符号整数，不在乘法、中间累加或输出时舍入、饱和、截断或取模。每项乘积绝对值≤2^30，64项绝对值之和≤2^36，bias绝对值≤2^39，所以任意部分和绝对值≤2^39+2^36<2^40，可由48位安全表示。不得根据当前checkpoint较小的实测幅值缩窄通用INT40偏置契约。

`.mem`每行一个固定宽补码hex字：X/W为4位，bias为10位，Y为12位，无地址标记、注释或未知态。现有固件保持X/W的32位槽低16位、bias的低32/高8位和Y的低32/高16位符号扩展写回规则，详见[现有平台集成说明](e203-integration.md)。`y.mem`仅供检查器对照，不能作为CPU或硬件输出。

## 静态尺度与12层参数

`model/kwt-static-scales.json`保存逐层尺度、实际checkpoint张量名、参数界和来源身份。尺度选择只依赖固定checkpoint：

```text
X_bound = sqrt(64)*max(abs(LN1.gamma)) + max(abs(LN1.beta))
W_bound = max(abs(W))
exp     = 最小的整数 e，使 bound <= 32767*2^e；零界使用 e=0
```

这是一层一个X尺度和一个W尺度，样本无关；不按任务最大值、验证集或测试集重新选尺度。当前固定checkpoint的12层均得到 `x_exp=-11`、`w_exp=-16`、`bias_exp=y_exp=-27`。因此当前正式接入的解码是 `Y_code*2^-27`，无需新增硬件尺度寄存器。通用模型API仍允许显式指定其他尺度用于合成测试；导出和数据评估入口会重新由参数算界并核对冻结元数据，不允许静默改变交付配置。

各层独立更换W/bias及对应X。X必须取该编码器层Attention、残差和第一LayerNorm之后的真实第一前馈输入，不能把前一个硬件线性输出当下一层X。推理关闭训练、增强和Dropout，不修改checkpoint或模型结构。

## 软件接口与本机检查

`model/fixed16_acc48.py`只依赖Python 3.6及以上标准库。为适配服务器Python 3.6.8，以不可变namedtuple替代原dataclasses；编码、精确累加、解码及NRMSE算法保持不变。

| API | 用途 |
| --- | --- |
| `Fixed16Scales(x_exp,w_exp)` | 显式尺度，无默认值 |
| `encode_scalar` / `decode_exact` / `decode_scalar` | RNE+饱和编码、精确Fraction或有限binary64解码 |
| `dot64` / `linear99x64x256` | 检查完整形状、整数范围并精确计算 |
| `quantize_linear_inputs` / `decode_output` | 完整张量转换 |
| `LayerParameters` / `validate_layer_set` | 深复制、不可变、无隐藏层缓存，要求0..11恰好各一层 |
| `ErrorSums` / `LayerNRMSE` | 非空、有限、逐层跨样本误差统计 |
| `read_hex_mem` / `write_linear_mem_vectors` | 固定宽hex及带SHA、形状、尺度的manifest |

仓库根目录运行：

```bash
python3 -m unittest discover -s tests/numeric -v
```

检查覆盖正负RNE ties及邻点、饱和、极值/随机点积、40位偏置、完整矩阵方向和末元素、参数独立性、缺层/非法输入、NRMSE聚合及hex往返。另用现有夹具的48个文件核对全部12层304128结果，并将软件结果重新写为hex逐字节比较；它证明与现有整数夹具兼容，不证明新的浮点数据精度或服务器RTL已通过。

2026-11-01 服务器 Python 3.6.8 已实际通过34项数值检查，包含外部同名模块不能覆盖仓库整数参考的回归；导出/评估报告记录实际加载的参考模块路径与SHA。VCS真实12层回放另有独立通过记录，见 [本轮验证](validation/platform-vcs-20261101/README.md)。

## 外部模型与数据入口

本次不复制上游源码/checkpoint、Speech Commands音频或大型遗留环境。`model/kwt-source-files.json`包含上游提交 `237e4097afd4f6851e0b82f0a8d65c2dfe8eae30` 的104文件SHA256和长度。`--source`必须指向包含这些原始文件及 `models_data_v2_12_labels/kwt1/best_weights.*` 的外部目录；运行前后核对来源，缺文件为BLOCKED，字节不符为FAIL。不自动联网获取材料。

真实推理另需隔离的Python **3.8.20**、tensorflow-cpu **2.4.0**、NumPy **1.19.5**及锁文件 `tools/model/requirements-kwt-py38.lock` 中的依赖。服务器系统Python 3.6.8只运行标准库模型和交接检查。未安装或运行遗留推理环境时，不将脚本可导入或 `--help` 可用称为推理通过。TF2.4.0是历史开发环境对上游2.4.0rc1要求的明确替代，不声称字节级复现rc1。

在已具备该隔离环境和外部材料的机器上运行；输出目录必须尚不存在：

```bash
KWT_PY=/绝对路径/legacy-kwt-env/bin/python
"$KWT_PY" tools/model/export_kwt.py --source /绝对路径/kwt1-237e4097 --output /绝对路径/new-export
```

默认导出精确零静音波形的12层；`--waveform /绝对路径/audio.npy`可指定归一化、有限、16000采样点的浮点波形。输出包含严格兼容的 `layer_00` 至 `layer_11` mem、尺度、浮点参考、环境、源和实现哈希。导出成功仅代表该波形的软件链通过。目录可交给现有 `e203_soc.py --mode check-vectors` 和 `--mode vectors`；不会把软件golden放进CPU内存。

完整开发validation另需已下载的官方Speech Commands V2归档。标准库预处理入口只读取本地归档，校验既有官方长度/SHA、安全解压并保留原README/LICENSE：

```bash
python3 tools/model/prepare_speech_commands.py --archive /绝对路径/speech_commands_v0.02.tar.gz --output /绝对路径/new-speech-data
"$KWT_PY" tools/model/evaluate_kwt_dataset.py --source /绝对路径/kwt1-237e4097 --data /绝对路径/new-speech-data --output /绝对路径/new-validation
```

评估默认覆盖原始validation划分；`--limit`仅用于调试，`--replay-sampling`可固定前次枚举顺序。划分、unknown/静音处理和预处理遵循固定上游AudioProcessor。每个FFN1独立使用FP32模型的对应层输入，不把量化输出传播至后层。成功写出每样本/层误差、采样列表、数据身份与完整性统计；缺源/数据/环境返回2和BLOCKED，错误输入或精度门槛失败返回1，成功返回0。不运行官方600评测、RTL或PPA。

## NRMSE与已有证据范围

每层对全部提供样本的99×256元素累计SSE、reference能量和元素数：

```text
NRMSE[layer] = sqrt(sum_error_sq/count) / max(sqrt(sum_reference_sq/count), 1e-8)
final_NRMSE  = max(NRMSE[0], ..., NRMSE[11]) <= 0.03
```

不能先算样本NRMSE再平均。12个性能任务另需各自≤3%；数据评估还记录最差样本层误差。空样本、缺层、非有限值及统计溢出拒绝。48位整数可被binary64精确表示，当前尺度下解码有限。

平台已有静音夹具的原manifest记录单波形最大层NRMSE **0.0195108%**。旧分支 `c2e58fd9de4c653c4d7822ee5e79e4f06761edb1` 的 `kwt-asic/docs/runs/optimization-v1/validation-full.json` 记录4445条validation、最大聚合层NRMSE **0.0132799%**、最差样本层 **0.0195401%**、零裁剪。这些是历史软件证据；该分支未跟踪其完整原始samples/sampling/log文件，本次未重跑这4445条数据。官方600评测、全validation RTL回放和正式PPA仍须各自验收。

## 来源与许可

`model/xu-numeric-provenance.json`记录逐项恢复路径、原文件SHA和最小兼容改动。旧数值模型/脚本没有独立许可头，保留其项目来源；不自动为它们套用第三方许可。KWT原Apache-2.0许可证已在 `tests/e203/vectors/LICENSE.kwt.txt` 保留，外部上游源码的原版权/许可注释也须保留。新来源清单包含checkpoint身份，不额外宣称checkpoint具有独立授权声明。未导入FPT硬件、AMD IP或工艺/SRAM材料；音频数据及其许可仍随外部原始数据保留。
