# xu VCS micro34：第三方头文件分类的本地回归

本证据只证明编译选项会把 VCS include 目录归类为 system header，同时保留自身 C 源码的 `-Werror`。不构成实际 VCS 执行、活动语义一致、功耗或能量验收。

实际服务器 micro23 使用 `-I` 时，被第三方 `vpi_user.h` 的旧式函数指针声明触发 `-Werror=strict-prototypes`；micro23 原件保持不动。新 micro34 helper 使用 `-isystem`，输出独立目录 `vcs-joint-micro-saif-20261103-34`。自身的 `-Wall -Wextra -Wshadow -Wstrict-prototypes -Werror` 均保持不变；依赖扫描继续用 `-M`，因此实际 system header 字节仍会进入执行前后冻结校验。

微基准的 C、独立 owner/port probe 和 SystemVerilog 均与 micro23 字节相同；只改 helper 中的新目录、输入文件名和 include 分类。成熟缓存 C SHA256 为 `cbeadf216665fc0b212ab3e239f299f4c83a64f59df561d8715414e854ed8cb1`。四个 mode、native SAIF、owner/actual-port 回调、未完成负例和完整输入冻结不变。不得据此修改 Icarus 或 VCS 的事件数，也不得补造 delta 或 edge。

本地四项检查使用人工合成的旧式函数指针声明，未复制第三方头文件：

1. 使用 `-I` 时第三方声明确实报 `-Werror=strict-prototypes`。
2. 使用 `-isystem` 时该声明可编译。
3. 使用 `-isystem` 时自身 C 源码的同类警告仍被 `-Werror` 拒绝。
4. 使用 `-M` 时第三方 system header 仍出现在依赖表。

原始日志在 `raw/`，helper 与复现脚本在 `evidence-tools/`。复现会向执行目录写新日志，应先复制工具到独立工作目录；不得覆盖历史原件：

```sh
python3 - <<'PYRUN'
from pathlib import Path
import shutil, subprocess, tempfile
source = Path('docs/validation/xu-score-vcs-micro34-header-host-20261103/evidence-tools').resolve()
out = Path(tempfile.mkdtemp(prefix='xu-micro34-header-check-'))
shutil.copytree(str(source), str(out / 'tools'))
subprocess.run(['python3', str(out / 'tools/host_header_class_check.py')], check=True)
print(out)
PYRUN
```

实际 VCS 校准仍需服务器执行新 helper，然后按同一窗口逐 pin 比较 native SAIF、联合统计和独立 probe；本回归没有证明这些语义。
