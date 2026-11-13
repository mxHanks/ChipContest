# 64PE合规32位整改候选

这是针对2026-11-13答疑的独立整改工程，**尚不是正式验收通过版本**。保留64PE/INT16/bias40/41位有界累加/RNE9/Y32，恢复原32位SystemBus共享路径、完整装载计时和真实清零。新生产选择`XU_MATRIX_DMA`＋`XU_MATRIX_DMA_SYSBUS32`。

- `structure/`：活跃预处理、原CPU/mem_fab身份、仲裁协议和完整SoC XML。
- `dma/`：32位DMA完整12任务、错误/背压/复位及换参数恢复。
- `validation/`：CPU清零→真实source装载→启动→完整Y响应退休；含全部等待/gap的总窗口。
- `numeric/`：任意指定本地WAV manifest或明确`--dev`整数输入，数值/模型/向量身份，不继承旧固定silence精度。
- `x-macro/`：隔离的16颗X SRAM宏候选；未通过CPU/选型前不安装。
- `ppa/`：同库/同原SDC的离线封存包及未来集中原生采集流程；准备成功不代表面积/时序通过。
- `timing/`：旧211项违例分类、真实局部修复与失败取证、新候选完整修复流程。

总计划/状态分别见`docs/s3-y32-compliance-repair-plan.md`与`docs/s3-y32-compliance-repair-results.md`。硬件需对应本分支子仓；旧`XU_MATRIX_DMA64`不能作为此模式的合规实现。主工作目录另一方案的任何精度、PPA或门级结果均不继承。
