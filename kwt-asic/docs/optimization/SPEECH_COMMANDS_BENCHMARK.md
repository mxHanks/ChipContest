# 真实语音 benchmark 入口

2026-10-15：官方 `speech_commands_v0.02.tar.gz` 已完整下载、校验和解压。归档2,428,923,189字节，SHA256为 `af14739ee7dc311471de98f5f9d2c9191b18aedfe957f4a6ff791c709868ff58`，与[TensorFlow Datasets官方校验清单](https://raw.githubusercontent.com/tensorflow/datasets/master/tensorflow_datasets/datasets/speech_commands/checksums.tsv)一致。下载使用[Google公开源](https://storage.googleapis.com/download.tensorflow.org/data/speech_commands_v0.02.tar.gz)。归档保留下载时的 `.part` 后缀，但已通过完整长度和SHA校验，不是未完成的数据。

解压位置 `data/speech-commands-v0.02/`。共105,841个文件，含105,835个WAV，展开3,339,983,636字节；README/LICENSE等原始文件保留。每文件大小与SHA在 `source-files.json`；准备报告为 `preparation.json`，轻量副本在 `docs/runs/optimization-v1/speech-data-preparation.json`。数据不打入工程源码检查点。

`scripts/model/prepare_speech_commands.py`先核对归档长度/哈希，再检查全部成员类型和路径，只写新目录，拒绝越界、符号链接、重复路径及覆盖。它登记源数据文件，不生成最终KWT评测采样清单。

首条非静音开发冒烟选取 `yes/026290a7_nohash_0.wav`，由固定KWT代码的原始 `which_set` 判定为validation，按同类别验证样本文件名排序取第一条。没有按误差筛选样本或调整尺度；PCM16按32768归一化到float32，按16000样本补零/截断，MFCC及模型推理由既有官方模型导出链执行。选择入口为 `scripts/model/select_validation_waveform.py`，需项目 `.venv-kwt/bin/python`。

该单样本的12层导出、默认8路banked回放均通过；304,128个RTL结果逐位一致，最大层NRMSE为 **0.0141389%**，12层X/W/bias裁剪均为0。它仅加强非静音链路冒烟，不证明全验证集或官方600样本3%门槛，也不是典型语音功耗测量。TF CPU2.4.0相对官方2.4.0rc1的兼容环境差异仍保留。

原始记录：`artifacts/runs/20261015T091234Z-speech-smoke/` 包含选择、导出、源码与数据身份；RTL记录 `artifacts/runs/20261015T091307.519749Z-engine-bench-0e6c3eb5/result.json`。最新轻量记录见 `docs/runs/optimization-v1/speech-smoke.json`。

下一步应使用固定上游 `AudioProcessor.prepare_data_index` 构造完整开发清单，记录实际文件枚举顺序和随机种子59185。wanted_words顺序、unknown选取、silence占比和处理必须遵循固定代码，不能替换成TFDS默认静音切片或不同划分。训练划分用于无梯度标定，验证划分用于精度/调试，测试划分不用于选择尺度或架构。逐层累计全部样本SSE、参考平方和与元素数，再求NRMSE；12个性能任务另逐任务检查。当前尚未完成这一全量评估。
