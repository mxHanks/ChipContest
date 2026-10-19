# 外部模型与数据

`configs/project.json` 固定模型来源。2026-10-15已把最小官方推理源码和best_weights子集按字节保存为 `vendor/kwt1-237e4097/` 并纳入发布包，来源/许可证/哈希见 `docs/runs/kwt-vendor-manifest.json`。临时下载缓存放 `data/downloads/`，中间导出放 `data/generated/`，受限材料放 `data/private/`；后三类不进入源码发布包。

每项记录URL、完整提交、许可证、SHA256和用途。Speech Commands V2下载体积较大，本轮不下载全量音频。训练集仅做无梯度标定，验证集调试，测试集不得调参。真实checkpoint和labels已导入，实际层输入导出与评测状态见PROGRESS；单条零波形只作导出/RTL功能冒烟，不代表验证集精度。
