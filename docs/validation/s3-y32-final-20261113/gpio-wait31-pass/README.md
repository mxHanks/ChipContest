# GPIO374独立两项wait31通过

两个case保留同一生产159源/6defines、binary、固件和向量身份，完整物理clear及25344个Y写/CPU读回全部通过。冻结checker的原始日志独立重放结果在summary.json，原始receipt及各case日志/收据均在本目录。

DMA首次端点读取、CPU首次端点加载分别强制31拍；实测目标等待均为31拍。总窗口相对基线各增35拍，包含真实总线/CPU相位开销，未删减等待。该配置是GPIO374独立证据，不是1064原N3候选，不触发其DC。
