# xu S0 开发数值资格评测 — 2026-11-02

完整原始validation划分4,445条样本、12个独立FFN1层已实际重跑PASS。逐层合计1,351,848,960个输出值的误差统计，最差层聚合NRMSE为 **0.01328069%**，最差单样本层为 **0.01954010%**，均低于3%。原signed16/40/48与尺度(-11,-16,-27)保持不变，没有用测试划分调参。

每层输入来自同一个固定FP32 KWT模型的对应FFN1激活，分别量化计算；没有把前一层的量化误差传播到后续层。该口径对应本科独立前馈线性任务，不证明量化完整编码器的精度。分类器仍为FP32参考，只用于检查，不计硬件吞吐。

这不是组委会未公布的官方600样本，也不声明这4,445条均做过RTL仿真。RTL验收仍须按正式12性能任务及独立组件向量执行，不能把整数golden匹配当作浮点NRMSE为零。

| 层 | 聚合NRMSE（%） | 最差单样本NRMSE（%） | 样本数 |
| --- | ---: | ---: | ---: |
| 0 | 0.01071503 | 0.01244468 | 4445 |
| 1 | 0.01072289 | 0.01455784 | 4445 |
| 2 | 0.01161255 | 0.01434121 | 4445 |
| 3 | 0.01246074 | 0.01659188 | 4445 |
| 4 | 0.01328069 | 0.01686089 | 4445 |
| 5 | 0.01262344 | 0.01768926 | 4445 |
| 6 | 0.01300848 | 0.01954010 | 4445 |
| 7 | 0.01273097 | 0.01524554 | 4445 |
| 8 | 0.01316404 | 0.01621478 | 4445 |
| 9 | 0.01264088 | 0.01550913 | 4445 |
| 10 | 0.01277544 | 0.01552404 | 4445 |
| 11 | 0.01183058 | 0.01416055 | 4445 |

原始[result.json](result.json)与[独立复算](independent-verification.json)保留逐层SSE/reference energy/count、样本清单、模型/数据/实现身份和全部范围限制。标准库审计器从完整samples.jsonl独立重算，而不导入推理或数值实现；它证明证据内部一致，不替代从音频重新推理。

固定KWT源码/checkpoint为237e4097，104份源/权重文件逐字节核验，恢复后162个模型参数逐项与checkpoint一致。TensorFlow 2.4.0是明确记录的上游2.4.0rc1替代版本，未称为exact rc1认证。新隔离Python3.8.20环境中43个锁定依赖逐项核installed RECORD和实际文件；[前](environment-before.json)/[后](environment-after.json)包清单哈希一致。完整推理本次数值循环133.40秒、含初始化139.78秒。

Speech Commands V2原始归档实际下载2,428,923,189字节，SHA256 `af14739ee7dc311471de98f5f9d2c9191b18aedfe957f4a6ff791c709868ff58`，安全解包并绑定实际WAV字节。采样保留原AudioProcessor顺序、unknown与静音语义；新机器应通过sampling.json重放文件枚举顺序。

独立重导silence产生的48份整数向量与历史固定夹具完全一致，见[silence-identity-check.json](silence-identity-check.json)。数值单测42/42通过，其中新增8项证据语义/范围反例；没有修改历史数据或覆盖原实验日志。

[原始证据归档](xu-validation-evidence.tar.xz)含完整samples.jsonl、sampling.json、消耗文件身份、原始运行/审计日志和环境收据。包大小2663700字节，SHA256 `a7e7c651fc75d6d8853ca3e9a6edbafa1b9477be52eb4caad63765787b145109`；[严格成员清单](archive-manifest.json)核每份原始字节。原始音频、外部checkpoint和虚拟环境只留build/外部源码目录，不随仓库发布。

复现使用本仓新增的`tools/model/bootstrap_kwt_environment.sh`在新目录恢复43包锁定环境，再运行现有prepare/evaluate工具。所有输出目录须不存在：

```bash
cd /home/mxhanks/Projects/ChipContest-xu-score-opt
bash tools/model/bootstrap_kwt_environment.sh /新的绝对路径/xu-kwt-env
python3 tools/model/prepare_speech_commands.py \
  --archive /已核验原始归档/speech_commands_v0.02.tar.gz \
  --output /新的绝对路径/speech-commands-v2
/新的绝对路径/xu-kwt-env/venv-kwt/bin/python tools/model/evaluate_kwt_dataset.py \
  --source /包含固定237e4097权重的外部KWT目录 \
  --data /新的绝对路径/speech-commands-v2 --batch-size 32 \
  --replay-sampling /解包路径/xu-validation-evidence/validation-full-01/sampling.json \
  --output /新的绝对路径/validation-full
python3 tools/model/verify_kwt_evaluation.py \
  --evaluation /新的绝对路径/validation-full --repo "$PWD" \
  --source /包含固定237e4097权重的外部KWT目录 \
  --out /新的绝对路径/independent-validation.json
```

归档内numeric-job-state.json记录实际分阶段命令和全部返回码；实际环境/数据路径保留于原始result，不与上述新目录复现示例混同。
