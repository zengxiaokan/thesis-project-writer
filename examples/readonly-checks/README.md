# 只读检查小样稿与实际复跑

本例使用 [base/](base/review/consistency.json) 下的合成Markdown、来源片段、图源和JSON登记。文本中的计数是人为构造的核算材料，`tests/plan.md` 是计划说明，均不是现实项目测试报告。图像仅用于本地路径检查，不是界面截图或内容/清晰度验收。

## 可直接运行的检查

在技能仓库根目录使用现有Python3.8或以上运行，无第三方依赖：

```text
python -B scripts/check_consistency.py --root examples/readonly-checks/base --manifest review/consistency.json
python -B scripts/check_evidence_changes.py --root examples/readonly-checks/base --manifest evidence/claims.json
```

两个检查器都只输出JSON。当前登记范围没有发现问题：正文图表ID及引用完整、图片存在、三张表合计正确、权威稿指纹匹配；同口径的正文/摘要计数可比，历史的不同版本、批次、对象、方法和请求单位不会与当前用例数合并判矛盾。源代码块里的演示ID和待确认标记不参加正文检查。

退出0仅表示已检查且可支持的范围没有检出问题。普通自然语言数字/引用、论文论证、图的语义、字体清晰度及Word页面没有由此通过验收；覆盖与跳过范围见报告及[一致性指南](../../references/consistency-checks.md)。

## 在临时副本中植入问题

[复跑脚本](../../scripts/run_readonly_example.py) 先复制合成小样稿，在它自己创建的临时目录内植入问题，再分别调用检查器；不会改动base素材或真实论文。默认仅输出JSON：

```text
python -B scripts/run_readonly_example.py
```

只有显式给出下列参数才更新公开观察文件：

```text
python -B scripts/run_readonly_example.py --output examples/readonly-checks/observation.json
```

[实际观察](observation.json) 保存工具和复跑脚本指纹、实际运行环境、问题位置及复核目标。本次覆盖：

| 临时场景 | 植入内容与实际结果 |
| --- | --- |
| 正常对照 | 两个检查器均零发现；历史批次和不同单位未产生数字冲突 |
| 不一致稿 | 检出重复ID、预期ID缺失、悬空引用、缺图、待确认标记、目录缺项、表格合计错误、同口径数字冲突、权威稿指纹变化，并给文件/行定位 |
| 状态来源变化 | C-STATE进入需复核，列出关联正文、流程图源及测试说明；C-CATALOG的已登记来源未变化 |
| 来源重命名 | 原路径仍报告失效，同指纹新文件只列为可能候选，不替换登记；另一来源仍保持未检测到变化 |

每次审查调用前后比较全部文件的字节、修改时间和文件清单，实际观察均保持一致；base素材也保持一致。只读不保证操作系统访问时间不变，也不是持续并发替换文件时的原子隔离。

这证明的是本次明确场景下的定位、口径分组、影响提示及文件保护行为。源指纹变化不是主张错误判定，“来源未变”也不证明正文语义正确；后续应回查所指向的材料。没有实际渲染Word、执行项目测试或完成全篇内容验收。
