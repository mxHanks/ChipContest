# 完整 validation 的 FFN1 开发精度评估

2026-10-15 已完成 Speech Commands V2 的固定上游完整 validation：**4,445 条输入 × 12 层**，每层独立计算 `99×64×256+b`。`fixed16_acc48_v1` 的最大逐层聚合 NRMSE 为 **0.0132799%**，最大单样本单层 NRMSE 为 **0.0195401%**，全部 X/W/bias 裁剪数为 0。运行耗时 **82.28 秒**，退出码 0，日志有完整结束标记。

这是 **new-KWT 软件数值开发验证 PASS**。没有把量化误差逐层传入后续模型，没有全验证集 RTL 回放，也没有将 TensorFlow 2.4.0 兼容环境称为精确的官方 2.4.0rc1 环境。官方 600 任务、最终竞赛精度冻结、SoC、指定库面积/时序/功耗仍为 NOT_RUN。

轻量结果：[validation-full.json](../runs/optimization-v1/validation-full.json)。原始证据目录：`artifacts/runs/20261015T100218Z-kwt-validation-full/`；包含命令、实际退出码、完整日志、完整采样清单、每个样本的逐层误差、输入和源码 SHA、独立复核日志。

## 评估口径

- 使用官方固定提交 `237e4097afd4f6851e0b82f0a8d65c2dfe8eae30` 的 `AudioProcessor(flags)`，整体构建 training/validation/testing，再调用原 `get_data(batch, offset, flags, 0, 0, 0, 'validation', 0, 0, session)`。不独立重写随机抽样，不改变三个分区共享的随机流。
- 记录实际 `gfile.Glob` 枚举顺序；全量运行回放冒烟保存的顺序，并要求当前文件成员集合一致。validation 包含 371 个 unknown、371 个 silence。每个非 silence 文件再次用上游 `which_set` 验证归属。
- 固定提交的 silence 分支实际不执行解码，保留初始化的零数组和标签 0。脚本保持此行为；371 条 silence 的实际 16,000 个 float32 零采样 SHA 均核对，未把占位训练 WAV 当作真实输入。
- 使用真实 FP32 模型的每层 FFN1 输入及 Dense 输出。12 组 hooks 只构建一次计算图；batch=32，尾批 29 条补零到 32，统计时只取真实 29 条。运行结束图操作数仍为 5,212，未逐批重建图。
- 全部 162 个模型变量通过原 checkpoint 与模型重新保存后的 key、shape、dtype 和逐值一致核对；FFN1/LN1 参数另行核对。保留上游 checkpoint trackable alias 警告，完整参数值复核通过后才推理。
- 尺度由 checkpoint 的 W 最大绝对值及 `8×maxabs(LN1.gamma)+maxabs(LN1.beta)` 决定，不使用 validation 调参。本轮 12 层均为 X 指数 −11、W 指数 −16、bias/Y 指数 −27。
- float32 精确转 float64 后按二的幂缩放、`rint` ties-to-even、饱和编码到 int16/40；int64 点积保存精确整数和，不作中途截断。首条输入的 12 层 X/W/bias/Y 均与规范 Python `Fraction` 编码及整数线性层逐元素相同，其中输出核对 304,128 个。
- 全量软件共计算 **1,351,848,960 个输出值**。这个计数不表示已进行相同规模的 RTL 仿真。
- 每样本保存 SSE、参考能量、NRMSE、峰值误差和实际波形 SHA。逐层先累加 SSE/参考能量，再计算 `sqrt(SSE/N)/max(sqrt(reference_energy/N),1e-8)`，不平均样本 NRMSE。原始数据、模型、实现源码在结束时重新核对 SHA。

## 结果

层号为 0–11；以下误差单位均为百分比。

| 层 | 聚合 NRMSE | 最差单样本 NRMSE | X/W/bias 裁剪 |
|---|---:|---:|---:|
| 0 | 0.0107173% | 0.0124447% | 0 / 0 / 0 |
| 1 | 0.0107279% | 0.0145578% | 0 / 0 / 0 |
| 2 | 0.0116111% | 0.0143412% | 0 / 0 / 0 |
| 3 | 0.0124622% | 0.0165919% | 0 / 0 / 0 |
| 4 | 0.0132799% | 0.0168609% | 0 / 0 / 0 |
| 5 | 0.0126197% | 0.0176893% | 0 / 0 / 0 |
| 6 | 0.0130064% | 0.0195401% | 0 / 0 / 0 |
| 7 | 0.0127254% | 0.0152533% | 0 / 0 / 0 |
| 8 | 0.0131559% | 0.0157473% | 0 / 0 / 0 |
| 9 | 0.0126350% | 0.0155272% | 0 / 0 / 0 |
| 10 | 0.0127760% | 0.0155240% | 0 / 0 / 0 |
| 11 | 0.0118388% | 0.0141218% | 0 / 0 / 0 |

参考 FP32 分类模型正确 4,345 / 4,445，准确率 97.7503%；此数仅作恢复及预处理检查，**不是量化整网分类准确率**。当前任务评估独立线性层，不能据此声称量化整网性能。

32 条冒烟耗时 8.74 秒，之后全量耗时 82.28 秒（其中数值循环约 76.83 秒）。两次前 32 条样本的实际输入 SHA、逐层误差记录完全相同。独立审计重新读取 4,445 条 JSONL，重算 12 层聚合、最差样本及峰值；结果一致。13 项独立工具测试覆盖半整数 ties 及邻点、float32 次正规数/极值、饱和、非法域、int64 边界、规范模型对照、NRMSE 分母地板、非平均聚合及精度门槛失败退出码。

首次冒烟在公开 `tf.keras.backend.get_session` API 处失败，未执行数值评估；失败记录保留于 `20261015T100026Z-kwt-validation-smoke/`。修复为 `tf.compat.v1.keras.backend.get_session` 后重新完成冒烟及全量，未覆盖失败证据。

## 复现

所有输出目录必须不存在。已有数据的归档校验与解压方法见 [SPEECH_COMMANDS_BENCHMARK.md](SPEECH_COMMANDS_BENCHMARK.md)。

```bash
.venv-kwt/bin/python scripts/model/test_evaluate_kwt_dataset.py
.venv-kwt/bin/python scripts/model/evaluate_kwt_dataset.py \
  --batch-size 32 --limit 32 --output artifacts/runs/my-validation-smoke
.venv-kwt/bin/python scripts/model/evaluate_kwt_dataset.py \
  --batch-size 32 \
  --replay-sampling artifacts/runs/my-validation-smoke/sampling.json \
  --output artifacts/runs/my-validation-full
```

首次调用按上游实际枚举生成清单；后续调用使用 `--replay-sampling` 固定本次采样内容与顺序。跨机器复制时保留 Speech Commands 数据和采样清单，数据根目录可以通过 `--data` 更改。脚本固定 TF intra-op=2、inter-op=1、OMP=2、GPU 禁用；请与重型 EDA 错开运行。

顶层 `status=PASS` 要求评估完整执行、输入/源码复核、无裁剪，以及最大层聚合和最大单样本层 NRMSE 均不超过内部 3% 门槛。评估完成而精度门槛失败时保留完整结果，顶层 FAIL、退出码 1。无结束标记、异常退出或来源 SHA 不一致都不能作为 PASS。

## 对优化的意义与下一步

当前 16 位候选在完整开发验证划分有很大精度余量，可以继续评估更窄乘法器和更小存储宽度，但此次结果没有证明任何新位宽达标，也不允许在相同格式名下悄悄换数值语义。下一轮应先建立显式版本化的位宽候选，比较相同验证清单上的最差误差和裁剪，再实现对应 RTL、完整位一致、指定工艺 PPA；若无可靠收益，继续保留 16 位基线。

正式冻结还需官方许可的推理环境/预处理核验和官方 600 任务，接入 E203 后将装载、CPU 调度、总线和完整写回纳入测量；指定标准单元及 SRAM 宏仍决定面积、150 MHz 与能耗是否达标。
