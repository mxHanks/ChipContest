# xu173：原总控内自动收尾归档

服务器runtime只有`export_job173.py`一个文件，Python3.6标准库。
它在**原Python PID内**导入 `~/Desktop/exporter171.py`（SHA固定为
`9c72cfa8ef45b0b2cfba865af1914728077e63a4fb62c940ad7dacaa81300263`），调用其只读`export`，
不另建进程、不启动/停止/重试实验。原171、166/167和已部署170均不修改。

`two_candidate_autopack173.json`通过原153总控追加登记：

- `s2c_unknown167` terminal；`s2e_final155_power12_166` terminal；`s2e_streamaudit164` success。
- `native=true`沿用本用户单实验槽位；direct前台worker，`process_contains`为唯一173输出根。
  argv中只有本job自己的out，不泄漏其它job的output marker。
- 输出根：`B/two-candidate-autopack-20261105-173`，状态为`state.json`。
- 最终包：`B/xu-server-two-candidate-20261105-171.tar.xz`。输出根/包均要求全新，不覆盖旧包或失败目录。
- 成功：`EXPORTED_TWO_CANDIDATE_PACKAGE_NOT_QUALIFIED`；异常：`FAIL_AUTOPACK173_NOT_QUALIFIED`。
  记录wrapper/171输入前后SHA、同PID、实际原包字节数/SHA与171返回值；导出失败和已有原包保留。
  这里只表示诊断证据包已生成，**不表示功能、150MHz或能耗资格通过**。

主线程部署此目录的wrapper、job JSON、register173.py，另将固定171单文件放在D根。
只执行登记器；总控在依赖满足后自行启动worker：

```sh
python3 -B "$HOME/Desktop/xu-two-candidate-autopack173/register173.py"
```

`register173.py`先核对原153源码SHA、真实controller PID/startticks/uid/argv和原控制目录，
再检查scope163双候选/零信号零重启回执、实际170登记回执与三个原注册及冻结runtime。
它只调用原153带flock/fsync的原子`register`，新ID只能逐字节幂等，绝不直接launch/init/信号。
登记前后重核新runtime、原170注册、scope/170回执和真实controller identity。
新173登记小回执写`B/two-candidate-autopack-registration-20261105-173.json`。

总控实际使用的worker CLI（用于复现说明；不要绕过总控手动启动第二份）：

```sh
python3 -B -u "$HOME/Desktop/xu-two-candidate-autopack173/export_job173.py" \
  --out "$HOME/Desktop/xu-score-optimization-20261102/two-candidate-autopack-20261105-173"
```

取回包后按171的`check_unpack171.py`用173 state中的实际包SHA验包、再解包新目录。
171包内副本仍是明确的live source快照；source metadata不变不冒充terminal冻结。
其巨大pin原报告仅有界流式SHA，不搬库、模型、manual或凭据。

本地复核：

```sh
python3 -B build/xu-two-candidate-autopack173/test_autopack173.py
```

10项hostcheck仅在`/tmp/xu173-MOCK-ONLY-*`使用合成exporter，检查同PID、输入SHA、失败状态、
原包/原输出不覆盖、改输入/假包身份拒绝、原153 job校验与不直接launch。
本地加载真实171仅检查固定SHA与可导入性，不调用真实export，不写production输出。
mock生成的41字节文件明确为MOCK，不能作为native、真实证据包或资格证明。

本交付尚未远程部署/登记；由主线程统一部署。首次登记后，无需模型额度也可由原153持续等待并执行。
