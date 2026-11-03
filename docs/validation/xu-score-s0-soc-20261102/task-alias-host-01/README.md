# xu SRAM pin alias采集接入本地验证

4项host测试通过，无跳过。使用真实私有SRAM模型做prepare-only和真实RISC-V固件链接；完整336宏/22512位的归一化handoff活动来自明确标记的合成SAIF，不是VCS采集。验证原始SAIF不可变、完整映射/unknown保留、静态DTCM严格控制、缺位拒绝、源或mapping改动拒绝、仅显式选项追加observer和debug_region+cell。

复现命令与实际源/厂商模型身份在run.json，厂商内容与固件二进制未提交。实际VCS绑定/端口对照和完整SoC首任务证据必须另存，不能从本测试推导实际覆盖、功耗、能量或资格。
