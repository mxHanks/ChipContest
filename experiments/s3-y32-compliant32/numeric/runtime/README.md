# KWT 独立旧版推理环境

本目录只恢复项目已有的环境门禁：Python **3.8.20**、
`tensorflow-cpu==2.4.0`、`numpy==1.19.5`。不修改系统 Python、全局包、
固定数值模型或原 KWT 源码，不下载 Speech Commands 数据集，不训练或启动 EDA。

在仓库根目录执行：

```bash
python3 experiments/s3-y32-compliant32/numeric/runtime/bootstrap_runtime.py
build/compliant32-20261113/numeric/runtime/venv/bin/python \
  experiments/s3-y32-compliant32/numeric/runtime/check_runtime.py
```

所有运行时、下载、pip 缓存和报告写入
`build/compliant32-20261113/numeric/runtime/`。脚本把 CPU 亲和限制到一个可用核，
TensorFlow、OpenMP、BLAS 线程均限制为 1，禁用 GPU。bootstrap 需要主机 Python 3.12+
和网络；不会使用 sudo 或向用户/系统 site-packages 安装包。

`check_runtime.py` 默认读取已经固定的
`/home/mxhanks/Projects/migration-v0.2/vendor/kwt1-237e4097`，也可传 `--source`。
它先调用项目已有的 `source_inventory` 校验 104 个原文件，再导入原模型和原音频输入模块，
构造禁用训练和增强的原 KWT，恢复原 checkpoint，并调用已有
`verify_all_model_values` 比较完整模型的每个变量值。临时另存的权重只用于恢复证明，随后删除。
它没有向模型提供 WAV、合成音频或特征，不生成样本、标签、精度或官方 600 结果。

检查结果为 `runtime-check.json`；`PASS_RUNTIME_AND_ORIGINAL_CHECKPOINT_RESTORATION`
只证明环境可导入且原 checkpoint 恢复完整。真实 Speech Commands V2 音频验证和官方
样本清单认证仍需相应输入。

## 来源与复现记录

- CPython 来自发布者 [Astral python-build-standalone 20241002](https://github.com/astral-sh/python-build-standalone/releases/tag/20241002)，
  使用官方发布 API 确认资产名，并逐字节核验发布者的 `.sha256`：
  `285e141c36f88b2e9357654c5f77d1f8fb29cc25132698fe35bb30d787f38e87`。
  这是第三方 CPython 构建，其版本与 [Python 官方 3.8.20 发布](https://www.python.org/downloads/release/python-3820/)一致；
  不声称复原了已删除旧 venv 的二进制身份。
- [TensorFlow CPU 2.4.0 官方 PyPI 元数据](https://pypi.org/pypi/tensorflow-cpu/2.4.0/json)仍提供
  `cp38-cp38-manylinux2010_x86_64` wheel，其 SHA256 为
  `cd4c741dae26c3da19c5f4195f16c8ccea9dcff0fcc07e5d77660fa9d2f7a1d6`。
- [NumPy 1.19.5 官方 PyPI 元数据](https://pypi.org/pypi/numpy/1.19.5/json)提供同平台 wheel，
  本次选择 `manylinux2010_x86_64`，SHA256 为
  `a9d17f2be3b427fbb2bce61e596cf555d6f8a56c222bd2ca148baeeb5e5c783c`。
- `tensorflow-addons==0.12.1` 的 TF 2.4 / Python 3.8 兼容范围来自
  [TensorFlow Addons 官方兼容矩阵](https://raw.githubusercontent.com/tensorflow/addons/v0.13.0/README.md)。
  其他兼容约束见 `requirements.txt`，并不假称它们来自已丢失的旧 venv freeze。
- `python-download.json` 保存 CPython 版本、URL、SHA256 和字节数；
  `pip-install-report.json` 保存此次实际安装包的版本、下载 URL 和发布归档 SHA256；
  `installed-freeze.txt` 记录实际安装集合；`pip-check.log` 记录依赖一致性结果。
  `requirements-lock.txt` 若存在，则 bootstrap 使用全部锁定版本和归档哈希复现安装。
  每次 pip 操作的独立报告保留，重复运行不会把有下载记录的主报告覆盖成空报告。

原 KWT `requirements.txt` 请求的是 TensorFlow **2.4.0rc1**；现有冻结项目明确接受
`tensorflow-cpu==2.4.0` release。这里恢复这一已有门禁，不声称 release 与 rc1
逐位相同，也没有擅自换用更高版本 TensorFlow、模型或预处理。

## 2026-11-13 实际执行结果

独立环境安装与 `pip check` 通过；完整 40 个包的发布归档均已记录 URL/哈希并生成
`requirements-lock.txt`。带全部哈希的 bootstrap 重复执行通过，原始下载报告仍保留。
原 KWT 的 104 个文件校验、12 层模型构造、162 个模型变量恢复和逐值比较均通过，
参数集合 SHA256 为 `cb301bdce082a3183b83eaa25ba34ced6549a9c60876c61a1772f34a91d7f69f`。
TensorFlow 的对象引用及线程配置警告没有隐藏，完整保存在 `runtime-check.json` 和日志；
恢复检查仍要求全模型的键、形状、数据类型和值精确相等。

额外用恢复后的解释器运行现有 `check_environment.py`，报告为
`environment-restored-r1.json`：所需 Python/TF/NumPy 已满足，唯一剩余缺项是
Speech Commands V2 音频及样本清单。该报告的退出码 2 和
`BLOCKED_INPUTS_OR_ENV` 来自音频输入缺失，不再是 Python 环境缺失。
