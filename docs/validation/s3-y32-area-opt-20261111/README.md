# 2026-11-11 面积优化仿真候选证据

本目录交付A/B本机筛选结果与未执行的PPA输入身份。不是面积优化定稿或STA通过记录。发布48位回退父d60e0e0、子a80dd184保持。

完整12任务304,128输出精确一致，主口径428,915拍，逐层/真实clear/gap/固件区间和总线工作量均与回退相同。见cpu-validation-summary.json、独立review和仓库结果页。

sim-candidates-r1.tar.gz 为607文件delta封存包，14,917,124 bytes；SHA256 885d595a33b6dbfb682f5e9555f15872ac63521654bcf0a3b36556cabbd028bd。包括生成器源码/补丁、默认及特化SV、原始仿真日志、ELF/image、完整几何/AST和数值证明、比较工具及复现入口。共享来源是仓库已发布冻结包docs/validation/s3-y32-4k-20261110/frozen-delivery.tar.gz（SHA464bea138c254d842b1db656da0e8feb42e04e509f9ab85d92e0cd30736b543f）。

解压到新目录后执行python3 REPLAY.py，只核对身份；--prepare-only可用上述baseline archive恢复与实测逐SHA一致的CPU源码和向量，A/B均已独立实测此准备步骤。显式--run才重编/仿真；保留截止与全新out检查。

candidate-package-review及independent-frozen-synth-packages只证明候选输入冻结及同compile条件，不是综合结果。PT恢复工具15项自检为结构/解析检查，不是原生PT测量。R5基线映射原件已在服务器生成，报告查询由负责人停止并保留FAILED；完整回传未完成，因此此处未伪造原始网表/叶单元报告。r5-transfer-incomplete记录102/3745分块停滞。后续须取回并复核原件。

库面积单位/官方SRAM计价、候选映射面积、实际150MHz时序及正式比赛资格未验证。所有本目录原件身份见SHA256.json；source manifests保留测量时绝对路径，不以当前HEAD重写历史。

基线原生PPA后续取证：pt-r4-native.tar.xz含全部46项PT输出，文件身份核验通过，实际setup−10.668ns/hold−0.135ns、211项违例，时序未闭合；review/triage保留674个宏CEN/RET1N的逐项归类及其他未测检查。r5-leaf-native.tar.xz含32.5MB完整leaf清单、完整DC日志/面积/引用报告和mapped.sdc；整archive710284B的SHA已核验。mapped.v/ddc仍仅在服务器保存，尚未在本地验证其文件字节；所有缺项继续明示。此前R5失败原状态保持FAILED/1，不能将补充报告取证改写为原collector通过。
