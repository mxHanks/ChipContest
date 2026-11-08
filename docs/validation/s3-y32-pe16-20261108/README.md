# 16 PE 单层筛选证据

2026-11-08。[中文结果](../../s3-y32-pe16-single-layer.md)。原第 0 层同条件对照：8 PE direct payload 453,259，16 PE 成对原型 469,191（+3.5150%）；含清空 651,662→667,594（+2.4448%）。全部 25,344 个输出正确；只完成单层，未综合。

- `baseline-task0/`、`pe16-task0/`：原始 plan/result/clear recipe 和原生单层日志。
- `comparison.json`：独立显式 8→16 PE loader 的比较；`compare_pe16.py` 固定审核过的物理计数及逐文件 SHA 差异，保留输入、工具、时钟、复位、清空、固件和规范命令核验。没有冒用原生产 8 PE 报告器的 PASS。
- `source-changes.json`、`pe16-prototype.patch`：在主 `33409e3`／E203 `d74d520` 基础上的可回退实验差分。Chisel、生成 SV、实验观察器／契约和 campaign JSON 观察扩展都明确记录，固件／NICE／CPU 不变。
- `pe16-generated-manifest.json`、`pe16-generate.log`：生成入口与 SV 字节身份。生成不是综合。
- `wrapper-smoke/`：真实 32 组／256 lane 数值、舍入、背压、错误与复位检查通过。`wrapper-smoke-original40-fail/` 保留首次等待预算不足的失败；`wrapper-diagnostic/` 证明第 43 次就绪。最终小夹具有界 64 次查询，NICE 的 poll_limit=2 保持；正式 campaign 的原 watchdog 与固件未变。
- `archive.json`：完整两组 saved campaign 压缩包的大小与 SHA；`archive-verify.json` 为独立解包后重新严格比较通过的收据，物理计数、固件身份、源码差异与总计均与原件相同。
- `sha256.json`：本目录收录文件摘要，不含自身和 README；原日志和补丁字节保留，行尾不转换。

这些是 Git 用紧凑摘录，完整冻结源／向量／ELF／镜像／原生模拟器保存在工作树 `build/pe16-20261108/`。便携归档为该目录下 `pe16-single-layer-evidence.tar.gz`，10,826,644 字节，SHA256 `6cd8b570f55e8b804bd7d3d65ff59de5d089f151cfdc859a19139103afcf1ece`。解包顶层为 `pe16-single-layer/`，可只读重验：

```bash
python3.12 -E -B pe16-single-layer/experiment/compare_pe16.py \
  pe16-single-layer/baseline-task0/result.json \
  pe16-single-layer/pe16-task0/result.json
```

比较器会从传入目录检查文件字节，保留原日志中的绝对路径，毋须编辑原结果。

源码重建先在独立 checkout 应用 `pe16-prototype.patch`（新增文件已包含），再运行：

```bash
python3.12 -E -B tools/ppa/s3_task_campaign.py --repo REPO --out NEW_OUTPUT \
  --bias-kind sram --schedule bias-hw-autogroup-y32-packed16-nice-direct-window \
  --simulator verilator --cross-prefix /usr/bin/riscv64-unknown-elf- \
  --platform-clocks 150mhz --startup-profile external-reset --layers 0
```

本实验硬件未集成主分支，只提交说明与证据。结论仅适用于两槽 FIFO、成对计算、顺序偏置准备的这一原型。新增寄存器／PE／控制与布线的面积、时序、能耗未测，二态开发 PASS 不代替正式 VCS/门级/STA。清空政策和 FIFO payload 物理清零资格仍待整机验收。
