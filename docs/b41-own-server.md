# B41 自有服务器工作区

已通过只读检查确认 t7920（自有服务器）上的冻结输入根目录为：

```text
/work/leo/chipcontest-xu-own155-diagnosis-20261105/
```

其中已找到：

- `b41-strict-input-r1/`
- `b41-followup-input-r1/`
- `b41-validation-sequence-r1/`

`GATE-PREFLIGHT.md` 不在 t7920 staging；本机交接副本位于：

```text
docs/validation/xu-b41-handoff-20261112/reports/s3-y32-area-opt-synthesis-20261111/GATE-PREFLIGHT.md
```

本机副本 SHA256：

```text
ec904f5356e67e5c2650b6c1e10ef0398d12299940eaff628978f8cee1d17dfd
```

官方 RDserver04 工作区不是 t7920 staging。官方根目录仍为 `/tmp/xu-b41-close-20261111-r1`，入口通过 VNC `ic4h22.nicu.cn:15923`；FTP `icdesigns0.nicu.cn:18888` 当前连接池返回 421。普通编译、打包和可迁移回归默认在自有服务器完成，只有需要官方网表、工艺库、官方回执或官方 EDA 槽位时才走官方入口。

本轮 official32 构建包已传到自有服务器：

```text
/work/leo/chipcontest-xu-own155-diagnosis-20261105/b41-official32-20261112/official32
```

远端已核对 341 个 RTL 文件和关键 SHA 与本机一致。t7920 当前未安装 Verilator 或 Icarus，因此编译回归仍在本机执行；远端目录作为自有 staging 和后续传输工作区。
