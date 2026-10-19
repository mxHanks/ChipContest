# 固定真实权重的静音冒烟向量

`kwt-silence-v1/` 是由 `scripts/model/export_kwt.py` 实际运行固定KWT最佳checkpoint导出的只读回归输入。原始模型文件位于 `vendor/kwt1-237e4097/`，Apache-2.0许可证随上游文件保留。

输入是一秒16kHz的全零波形。上游软件完成MFCC与12层推理，提取各层第一前馈Dense的实际输入和浮点结果；DUT只接收该层量化X/W/bias，必须自行计算全部输出。`y.mem`仅由testbench读取核对，不能进入综合文件集、驱动或正式评测输入适配代码。

`make linear-real`不依赖TensorFlow，核对源/向量哈希、全形状、12层顺序和软件golden后回放RTL。迁到新目录时通过显式`--source-root vendor/kwt1-237e4097`指定新路径，仍要求同一SHA。manifest保留当次实际来源、TensorFlow版本和旧绝对路径作为追溯信息。

重新从checkpoint生成：先`make setup-kwt`，再`make export-kwt`；输出为新的artifacts目录，不覆盖本fixture。正式精度评估需要正确数据划分的样本集合；此单一静音波形只用于导出链和真实12层换参的功能验证。
