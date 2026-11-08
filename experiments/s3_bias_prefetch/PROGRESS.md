# P3 bias SRAM 与双组预取独立原型

主线完整12任务正在验证；本目录不参与当前主线构建。

- [x] 读取真实 BiasBankCache、Sram1024x16、核心 INIT 供数和旧 MMIO mask/read 协议。
- [x] 编写单 SRAM adapter：5字节mask/RMW、同步回读、稳定响应、计算期间写互斥。
- [x] 编写两组 8×40 暂存：request/tag/take、下一组预取、epoch/失效、clear/reset。
- [x] Python 参考与3项测试通过；bash入口语法检查通过。
- [x] 编写自检 TB：3072参考事务、响应同拍换手、物理SRAM地址/值、全32组、预取/失效/clear/reset。
- [ ] root 在 Linux 运行 RTL 测试；记录首轮红绿反馈，修复后复验。
- [ ] 迁移并验证真实 Chisel 模块与主线 MMIO/scheduler（当前未修改）。

验证入口：`bash experiments/s3_bias_prefetch/run_linux.sh /absolute/output/directory`。

目标最终迁移到真实 Chisel 模块。此 SV 原型不代表主线 P3 完成，也不提供面积/时序结论。
