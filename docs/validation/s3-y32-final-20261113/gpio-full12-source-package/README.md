# GPIO374独立封包（未运行EDA）

`gpio374-cpu12-bound.tar.gz`是实际CPU12 PASS绑定的完整离线生产源包，554723字节。
本目录审计全部196个成员的路径、常规文件类型和sealed catalog逐文件SHA，确认无
厂商DB/lib/alib、凭据/env、原始向量/数据集、cache或链接。它不属于1064原N3候选。

解包后根为`candidate/`，含完整159项编译源、6项defines、原始约束、generic仿真宏模型、
固件ELF/image、CPU12收据/原日志/冻结checker和全部源目录。`allowlist-audit.json`
固定每个成员SHA、包SHA及配置。包内`controls.py`可核验离线输入与CPU12绑定；
没有任何GPIO374 DC/PT运行结果，也不会触发N3综合。

不包含原始音频/矩阵向量或厂商库。重新仿真须另提供完整PASS收据所列相同hash的
公开开发向量；仅检查原始log/源签名不需要这些外部数据。综合还需另有合法厂商库和工具。
