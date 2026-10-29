# 只读论文一致性检查

`scripts/check_consistency.py` 对指定 Markdown 和可选登记检查明确可判的对象，只向标准输出交 JSON，不修正文、改编号、选择最新稿、更新基线或写日志。无需数据库、联网或第三方 Python 包，支持 Python 3.8+。

## 最小使用与旧稿接续

```text
python -B <技能路径>/scripts/check_consistency.py --root "<论文工作区>"
python -B <技能路径>/scripts/check_consistency.py --root "<读取根目录>" --document chapters/chapter-5.md
python -B <技能路径>/scripts/check_consistency.py --root "<读取根目录>" --manifest review/consistency.json
```

`--root` 必须明确指定，限制所有文件读取范围；根目录及有关路径不支持符号链接/Windows Reparse Point。文件与 JSON 内路径均相对此根目录。图片路径相对所在 Markdown 解释，但仍必须留在根目录内。`--document` 可重复，提供时替代登记的 documents；省略 documents 时仅发现 `chapters/**/*.md`，不扫描全机或整个软件项目。发现过程跳过链接目录，显式选择的越界/链接路径作为输入错误处理。

`--manifest` 不自动加载；旧稿可以只选文档，不要求改目录或迁移登记。未配置的合计、比较、章节与权威稿指纹会列为未检查，不当成通过；无可读 Markdown 范围会明确报告。若正式稿是 Word/PDF，继续使用作者约定的权威稿和文档工具；本程序可检查其文件指纹，不抽取内容或验收页面。

退出码：`0` 为在实际检查范围内未检出问题，`1` 为有发现，`2` 为配置、路径或执行错误。参数语法错误由命令行帮助报告；有效调用的内容/输入问题以 JSON 输出。需要留报告时由调用者将标准输出保存到明确的审查位置，避免覆盖被查材料。

## 明确的定义与引用

可在 Markdown 的图表定义旁添加不影响正文显示的稳定标记：

```markdown
<!-- thesis:id FIG-501 -->
![核心处理流程](../figures/export/FIG-501.svg)

正文说明本次操作的条件及结果。<!-- thesis:ref FIG-501 -->
```

定义与引用分别处理，正式的“图5-1”等编号仍按学校与既有目录约定维护。登记索引不自动算第二个定义；若 JSON entities 指向同一 ID 的同一文档行，与标记去重。不同位置定义同一个 ID 则报重复。只在图表索引里有名字、没有明确图表定义时，不靠索引文字推断它已存在。

代码围栏和行内反引号中的示例不参与检查。普通“如图一”、裸数字参考文献 `[3]`、不同宿主生成的标题锚点以及自然语言的数值，不被猜成稳定引用。这些仍由正文、文献或页面审查处理。需要旧稿兼容时，可在 manifest 中登记实际定义和引用行，不必重写正文。

## 完整登记示例

```json
{
  "schema_version": 1,
  "documents": ["chapters/chapter-5.md", "chapters/chapter-6.md", "chapters/abstract.md"],
  "expected_ids": ["FIG-501", "TAB-601", "TAB-ABS"],
  "entities": [
    {"id": "FIG-501", "kind": "figure", "document": "chapters/chapter-5.md", "line": 8}
  ],
  "references": [
    {"id": "FIG-501", "document": "chapters/chapter-5.md", "line": 12}
  ],
  "required_sections": [
    {"document": "chapters/chapter-5.md", "heading": "5.3 异常与事务"}
  ],
  "table_checks": [
    {
      "id": "current-results",
      "document": "chapters/chapter-6.md",
      "anchor": "TAB-601",
      "label_column": 0,
      "value_column": 1,
      "sum_of": ["通过", "失败", "阻塞"],
      "total": "合计",
      "value_type": "integer",
      "non_negative": true,
      "unit": "cases",
      "tolerance": "0",
      "context": {"version": "v2", "batch": "regression-A", "object": "functional-cases", "method": "count"},
      "comparison_id": "functional-results",
      "metrics": [{"metric_id": "test.total", "row": "合计"}]
    },
    {
      "id": "abstract-results",
      "document": "chapters/abstract.md",
      "anchor": "TAB-ABS",
      "label_column": 0,
      "value_column": 1,
      "sum_of": ["通过", "失败", "阻塞"],
      "total": "合计",
      "value_type": "integer",
      "unit": "cases",
      "tolerance": "0",
      "context": {"version": "v2", "batch": "regression-A", "object": "functional-cases", "method": "count"},
      "comparison_id": "functional-results",
      "metrics": [{"metric_id": "test.total", "row": "合计"}]
    }
  ],
  "authority": {
    "path": "output/thesis.docx",
    "version": "author-confirmed-v2",
    "hash_mode": "bytes",
    "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  }
}
```

这里的路径、行号和示意指纹都要替换为实际登记，不能将此示例视为材料已核实。`entities`、`references`、`expected_ids`、`required_sections`、`table_checks`、`authority` 都可按需省略。已登记的文档内容项目必须指向本次选中的可读文档，不能暗中扩大扫描范围。未知顶层字段及重复 JSON 键报输入错误，以免字段拼错后被误当成已检查。

## 表格核算与比较边界

工具只解析单层 Markdown 管道表。定位使用唯一稳定 `anchor`，或用 `line` 指定从1开始的表头行，二者只能选一个；标记后可留空行，随后应是表头和分隔行。列索引从0开始，`sum_of` 指定参与求和的行标签，`total` 指定合计行标签。标签必须唯一，缺失/重复行、混合单位、空白、破折号、含说明或不符合声明类型的单元格都报无法核算，不能当作0。

实际单元格必须是普通十进制数字；`integer` 要求数值为整数，`decimal` 允许小数。默认允许有符号的整数/小数，计数等需要非负时显式设 `non_negative:true`。使用 Decimal 运算，不以浮点近似判断合计；`tolerance` 以同一单位显式登记，默认0，不自作舍入或换算。逗号千分位、百分号、公式、合并单元格、HTML/复杂嵌套表及正文中的数字不在自动核算范围。

`metrics` 从同一真实表格读取指定行的观察值，只有显式的 **comparison_id + metric_id + unit + 完整context** 相同才比较。context 至少要有非空的 version、batch、object、method；额外上下文字段也参与精确匹配。不同版本、批次、对象、方法或单位的值不会因数字不同报矛盾，也不自动换算为同一单位。登记不完整时比较列为跳过，合计本身仍可核算。

例如，旧批次的40次HTTP响应与当前批次的12项功能用例不是同一观察；同版本同单位的源库存与目的库存也不是同一对象。`comparison_id` 表明作者实际要比较的是同一项主张，不能仅凭字段都叫“总数”就共用它。数字匹配仅证明本次显式登记的观察一致，不证明来源、口径或正文结论本身正确。

## 其他检查的含义

- 图片检查支持常见行内 Markdown 图像路径、平衡或转义括号（如 `chart(1).svg`、`chart\(1\).svg`）、`<含空格路径>`、可选标题、中文、URL编码与片段。本地文件存在只说明文件可访问，不说明图像清晰度、中文显示、图文一致或正式页面合格；远程/内嵌图像不联网检查，单列未验证。括号不平衡等目标语法会报告无法检查，不截断路径后误报缺图；其他复杂图像语法标记跳过。
- `required_sections` 精确比较 Markdown 标题文本，检查的是指定正式目录项是否出现，不判断该节是否有实质论证。标题层级、Word自动目录及页面仍需相应审查。
- 待确认/TODO/FIXME 是出现位置提示，需结合语境判断是否未解决，不自动删除或替作者确认。
- authority 中的 version 是作者登记值，不按文件时间推断哪个稿最新。`bytes` 对完整字节计算 SHA-256；`text-lf` 仅将 CRLF 归一为 LF 后计算，适合文本，不能据此说 Word 内容相同。缺文件、缺基线、指纹变化分别报告；变化只提示复核版本和同步方向，不认定稿件错误或覆盖任何稿。

报告含每个发现的 code、path/line（若可定位）、说明与必要比较细节；coverage 列明已读文件、图表定义、表格与比较数量、未配置项、跳过项和限制。`no_findings_in_checked_scope` 不能解读成“全文一致性或学校格式全部通过”。
