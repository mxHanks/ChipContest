# 原始公开音频验证

该流程自行取得公开 Speech Commands V2 原始数据，避免依赖已删除旧目录。它使用原KWT `kws_streaming/train/base_parser.py` 指向的 [TensorFlow Google Storage归档](https://storage.googleapis.com/download.tensorflow.org/data/speech_commands_v0.02.tar.gz)，不训练、不微调、不改变原音频、模型或既有数值尺度。

原归档2428923189B；MD5为`6b74f3901214cb2c2934e98196829835`，SHA256为`af14739ee7dc311471de98f5f9d2c9191b18aedfe957f4a6ff791c709868ff58`，后者来自 [TensorFlow Datasets公开校验表](https://raw.githubusercontent.com/tensorflow/datasets/master/tensorflow_datasets/datasets/speech_commands/checksums.tsv)。下载约2.43GB；本机只提取原KWT speaker-hash分组算法判为validation的WAV及许可/README/样本列表，排除训练和testing音频。逐成员拒绝绝对路径、`..`、符号/硬链接、特殊节点、重复项和异常大文件，记录所有选中文件SHA。r1提取9981个未修改validation WAV。

```sh
python3 -B experiments/s3-y32-compliant32/numeric/public_audio/acquire_validation.py \
  --out build/compliant32-20261113/numeric/public-audio-NEW

build/compliant32-20261113/numeric/runtime/venv/bin/python -B \
  experiments/s3-y32-compliant32/numeric/create_validation_manifest.py \
  --data build/compliant32-20261113/numeric/public-audio-NEW/data \
  --count 600 --output build/compliant32-20261113/numeric/validation-600-NEW.json

build/compliant32-20261113/numeric/runtime/venv/bin/python -u -B \
  experiments/s3-y32-compliant32/numeric/export_audio_manifest.py \
  --source /home/mxhanks/Projects/migration-v0.2/vendor/kwt1-237e4097 \
  --manifest build/compliant32-20261113/numeric/validation-600-NEW.json \
  --output build/compliant32-20261113/numeric/validation-600-evaluation-NEW \
  --batch-size 8 --threads 1
```

所有输出名必须新建。解释器恢复参见相邻`runtime/README.md`。manifest使用原说话人哈希validation分组、自选固定随机种子、原文件SHA；未知词按原wanted-label规则映射。600样本=599个原WAV+1个**明确标记**的合成零silence，包含12类；不把真实WAV改标成silence，不因数值评测改变校准尺度。

随后将音频评测输出中的`vectors/`传给`validation/run_cpu_xmacro.py`，复用已验证CPU二进制执行真实SystemBus装载、计算、完整Y32写回及逐位验证。y/y32始终仅oracle，不作为DUT输入。可以换入任何后来指定的合法原WAV清单，不锁定旧silence哈希。

## 本次实测（r1）

- 原archive SHA与发布者表逐字节一致；原KWT104源文件、162变量checkpoint恢复验证通过。
- 12样本与600样本均完成12层原FP32激活→冻结INT16/bias40→RNE9/Y32，精度门槛通过、无裁剪、输出有限。
- 600样本各层聚合最大NRMSE **0.0131066325%**；最差单样本层 **0.0195336884%**；导出的12任务最大 **0.0133896631%**。
- 参考FP32分类准确率97.6667%只证明参考模型输入链，不是硬件完整编码器分类成绩。
- 原始证据`build/compliant32-20261113/numeric/public-validation-{12,600}-evaluation-r1/`含每样本/逐层误差、环境、模型/音频/向量SHA；具体CPU全12结果另列。

**这是自选公开validation开发验证，不是组委会最终抽取的600条正式样本验收。** 不把样本数相同当成正式评测通过。
