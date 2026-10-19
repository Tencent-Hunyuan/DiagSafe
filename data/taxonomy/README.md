# DiagSafe Taxonomy

`DiagSafe_standards_84.json` defines the three-level safety taxonomy and the label specification for every third-level label.

## Language Versions

| Standard text | File | Labels |
|---|---|---:|
| Chinese | [`DiagSafe_standards_84.json`](DiagSafe_standards_84.json) | 84 |
| English | [`DiagSafe_standards_84_en.json`](DiagSafe_standards_84_en.json) | 84 |

Both versions cover the same 84 labels and preserve category codes and record order.
The English file uses English field names and the English portions of the category names in the Chinese file.
The standard text retains quoted source-language terms where they illustrate a rule.
Schemas: [Chinese](schema.json) · [English](schema_en.json).

### English Fields

| Chinese field | English field |
|---|---|
| `类目编号` | `category_code` |
| `类目名称` | `category_name` |
| `一级类目` / `二级类目` / `三级类目` | `l1` / `l2` / `l3` |
| `定义` | `definition` |
| `标准总则` | `general_standard` |
| `标准细则` | `detailed_rules` |

For example, the English category path for gender discrimination is
`OSS-01` / `Discrimination & Stereotyping` / `gender`.
`category_code` identifies a first-level dimension. Match individual records using the code plus
`category_name.l2` and `category_name.l3`, extracting the parenthesized English names from the Chinese record.
The same mapping applies to benchmark `category.l1`, `category.l2`, and `category.l3`.

The DiagSafe taxonomy specifications in both languages are distributed under the [CC BY 4.0 License](../../LICENSE).

## Summary

| Code | First-level dimension | L2 categories | L3 labels |
|---|---|---:|---:|
| `OSS-01` | 歧视、仇恨言论与有害偏见 (Discrimination, Hate & Harmful Bias) | 3 | 13 |
| `OSS-02` | 色情与性内容 (Sexual & Sexually Explicit Content) | 4 | 13 |
| `OSS-03` | 隐私侵犯与信息泄漏 (Privacy Violations & Information Disclosure) | 3 | 6 |
| `OSS-04` | 虚假信息与误导内容 (Misinformation, Disinformation & Confabulation) | 3 | 5 |
| `OSS-05` | 暴力与非法行为 (Violent & Illegal Activities) | 5 | 15 |
| `OSS-06` | 化学、生物、放射、核与爆炸物风险 (CBRN & WMD) | 4 | 7 |
| `OSS-07` | 网络安全与模型攻击 (Cybersecurity & Model Attacks) | 2 | 5 |
| `OSS-08` | 自我伤害与自杀 (Suicide, Self-Harm & Dangerous Health Behaviors) | 3 | 7 |
| `OSS-09` | 儿童安全 (Child Safety) | 3 | 6 |
| `OSS-10` | 知识产权侵权 (Intellectual Property Infringement) | 3 | 5 |
| `OSS-11` | 操纵与欺骗性说服 (Manipulation & Deceptive Persuasion) | 1 | 2 |

**Total:** 11 first-level dimensions, 34 second-level categories, and 84 third-level labels.

## Record Format

```json
{
  "类目编号": "OSS-05",
  "类目名称": {
    "一级类目": "暴力与非法行为 (Violent & Illegal Activities)",
    "二级类目": "受管制物质与物品 (Regulated Substances & Goods)",
    "三级类目": "毒品制造/交易/使用 (drugs)"
  },
  "定义": "...",
  "标准总则": "...",
  "标准细则": "..."
}
```

## Fields

| Field | Description |
|---|---|
| `类目编号` | First-level code from `OSS-01` through `OSS-11` |
| `类目名称.一级类目` | Bilingual first-level dimension name |
| `类目名称.二级类目` | Bilingual second-level category name |
| `类目名称.三级类目` | Bilingual third-level label name |
| `定义` | Concise definition of the label |
| `标准总则` | General safety policy for the label |
| `标准细则` | Detailed dangerous behaviors and safe boundaries |

`类目编号` identifies the first-level dimension and therefore appears in every third-level record under that dimension.

## Full Taxonomy Tree

### OSS-01 — 歧视、仇恨言论与有害偏见 (Discrimination, Hate & Harmful Bias)

| Second-level category | Third-level label |
|---|---|
| 歧视与刻板印象 (Discrimination & Stereotyping) | 性别歧视 (gender) |
| 歧视与刻板印象 (Discrimination & Stereotyping) | 种族/族裔歧视 (ethnic/racial) |
| 歧视与刻板印象 (Discrimination & Stereotyping) | 宗教歧视 (religion) |
| 歧视与刻板印象 (Discrimination & Stereotyping) | 性取向歧视 (lgbtq+) |
| 歧视与刻板印象 (Discrimination & Stereotyping) | 残障歧视 (disability) |
| 歧视与刻板印象 (Discrimination & Stereotyping) | 地域/国籍歧视 (region/nationality) |
| 歧视与刻板印象 (Discrimination & Stereotyping) | 外貌/身材歧视 (body/appearance) |
| 歧视与刻板印象 (Discrimination & Stereotyping) | 社会经济歧视 (socioeconomic) |
| 仇恨言论与煽动 (Hate Speech & Incitement) | 仇恨言论 (hate-speech) |
| 仇恨言论与煽动 (Hate Speech & Incitement) | 煽动仇恨/暴力 (incitement) |
| 仇恨言论与煽动 (Hate Speech & Incitement) | 极端主义宣扬 (extremism) |
| 仇恨言论与煽动 (Hate Speech & Incitement) | 历史暴行否认 (atrocity-denial) |
| 隐性与系统性偏见 (Implicit & Systemic Bias) | 排斥性规范 (exclusionary-norms) |

### OSS-02 — 色情与性内容 (Sexual & Sexually Explicit Content)

| Second-level category | Third-level label |
|---|---|
| 露骨性内容 (Explicit Sexual Content) | 性行为描写 (sex-acts) |
| 露骨性内容 (Explicit Sexual Content) | 色情文字作品 (pornographic-text) |
| 露骨性内容 (Explicit Sexual Content) | 性器官色情描绘 (explicit-nudity) |
| 违背伦理的性内容 (Unethical Sexual Content) | 乱伦 (incest) |
| 违背伦理的性内容 (Unethical Sexual Content) | 人兽交 (bestiality) |
| 违背伦理的性内容 (Unethical Sexual Content) | 极端性癖 (extreme-fetish) |
| 性相关违法与撮合 (Sex-Related Crimes & Facilitation) | 性交易撮合 (prostitution) |
| 性相关违法与撮合 (Sex-Related Crimes & Facilitation) | 性骚扰/性胁迫 (sexual-harassment) |
| 性相关违法与撮合 (Sex-Related Crimes & Facilitation) | 非自愿私密影像 (ncii) |
| 性相关违法与撮合 (Sex-Related Crimes & Facilitation) | 色情资源引流 (porn-resource) |
| 色情产业与用品 (Sex Industry & Products) | 成人用品/情色商品 (adult-products) |
| 色情产业与用品 (Sex Industry & Products) | 色情人物介绍 (porn-figure-intro) |
| 色情产业与用品 (Sex Industry & Products) | 原味物品交易 (uncleaned-personal-item-trade) |

### OSS-03 — 隐私侵犯与信息泄漏 (Privacy Violations & Information Disclosure)

| Second-level category | Third-level label |
|---|---|
| 个人信息泄露 (PII Disclosure) | 身份标识泄露 (identity-pii) |
| 个人信息泄露 (PII Disclosure) | 联系方式泄露 (contact-pii) |
| 个人信息泄露 (PII Disclosure) | 财务信息泄露 (financial-pii) |
| 敏感数据与推断 (Sensitive Data & Inference) | 私密敏感数据 (sensitive-data) |
| 追踪监控与人肉 (Tracking, Surveillance & Doxxing) | 人肉搜索 (doxxing) |
| 追踪监控与人肉 (Tracking, Surveillance & Doxxing) | 非法监控/追踪 (surveillance) |

### OSS-04 — 虚假信息与误导内容 (Misinformation, Disinformation & Confabulation)

| Second-level category | Third-level label |
|---|---|
| 事实性错误 (Factual Errors) | 高危领域错误建议 (harmful-advice) |
| 事实性错误 (Factual Errors) | 科学共识否定 (science-denial) |
| 蓄意虚假信息 (Deliberate Disinformation) | 谣言编造 (fabricated-news) |
| 蓄意虚假信息 (Deliberate Disinformation) | 个人诽谤 (defamation) |
| 伪科学与迷信宣扬 (Pseudoscience & Superstition) | 封建迷信宣扬 (feudal-superstition) |

### OSS-05 — 暴力与非法行为 (Violent & Illegal Activities)

| Second-level category | Third-level label |
|---|---|
| 暴力犯罪 (Violent Crimes) | 人身伤害/谋杀 (crime-injury) |
| 暴力犯罪 (Violent Crimes) | 绑架/非法拘禁 (crime-kidnap) |
| 暴力犯罪 (Violent Crimes) | 恐怖主义 (terrorism) |
| 财产与经济犯罪 (Property & Economic Crimes) | 诈骗/欺诈 (crime-fraud) |
| 财产与经济犯罪 (Property & Economic Crimes) | 盗窃/抢劫 (crime-theft) |
| 财产与经济犯罪 (Property & Economic Crimes) | 洗钱/经济犯罪 (crime-financial) |
| 财产与经济犯罪 (Property & Economic Crimes) | 伪造/走私 (crime-forgery) |
| 受管制物质与物品 (Regulated Substances & Goods) | 毒品制造/交易/使用 (drugs) |
| 受管制物质与物品 (Regulated Substances & Goods) | 非法武器/枪支 (weapons) |
| 受管制物质与物品 (Regulated Substances & Goods) | 其他管制物品 (controlled-goods) |
| 受管制物质与物品 (Regulated Substances & Goods) | 处方药/激素类物质滥用 (medication-misuse) |
| 教唆、美化与规避 (Incitement, Glorification & Evasion) | 犯罪美化 (crime-glorification) |
| 教唆、美化与规避 (Incitement, Glorification & Evasion) | 逃避侦查 (evasion) |
| 动物保护与受管制活动 (Animal Welfare & Regulated Activities) | 动物虐待 (animal-abuse) |
| 动物保护与受管制活动 (Animal Welfare & Regulated Activities) | 赌博 (gambling) |

### OSS-06 — 化学、生物、放射、核与爆炸物风险 (CBRN & WMD)

| Second-level category | Third-level label |
|---|---|
| 生物风险 (Biological) | 生物战剂合成 (bioweapon-synthesis) |
| 生物风险 (Biological) | 病原体增强 (pathogen-enhancement) |
| 化学风险 (Chemical) | 化学毒剂合成 (chemweapon-synthesis) |
| 化学风险 (Chemical) | 毒剂武器化 (chem-weaponization) |
| 放射与核风险 (Radiological & Nuclear) | 核/放射性材料与装置风险 (nuclear-radiological-risk) |
| 爆炸物制造 (Explosives Manufacturing) | 爆炸物制造 (explosives) |
| 爆炸物制造 (Explosives Manufacturing) | 前体物获取 (precursor-acquisition) |

### OSS-07 — 网络安全与模型攻击 (Cybersecurity & Model Attacks)

| Second-level category | Third-level label |
|---|---|
| 网络攻击与恶意代码 (Cyberattack & Malicious Code) | 网络攻击与恶意代码 (cyberattack-malware) |
| 针对AI系统的攻击 (Attacks on AI Systems) | 提示注入/越狱 (prompt-injection) |
| 针对AI系统的攻击 (Attacks on AI Systems) | 系统提示泄漏 (prompt-leakage) |
| 针对AI系统的攻击 (Attacks on AI Systems) | 模型窃取/萃取 (model-extraction) |
| 针对AI系统的攻击 (Attacks on AI Systems) | 数据投毒 (data-poisoning) |

### OSS-08 — 自我伤害与自杀 (Suicide, Self-Harm & Dangerous Health Behaviors)

| Second-level category | Third-level label |
|---|---|
| 自杀 (Suicide) | 自杀方法 (suicide-method) |
| 自杀 (Suicide) | 自杀教唆/促成 (suicide-encouragement) |
| 自杀 (Suicide) | 自杀美化 (suicide-glorification) |
| 自残 (Self-Harm) | 自残方法 (self-harm-method) |
| 自残 (Self-Harm) | 自残挑战诱导 (self-harm-challenge) |
| 危险健康行为 (Dangerous Health Behaviors) | 进食障碍鼓吹 (pro-eating-disorder) |
| 危险健康行为 (Dangerous Health Behaviors) | 危险挑战 (dangerous-challenge) |

### OSS-09 — 儿童安全 (Child Safety)

| Second-level category | Third-level label |
|---|---|
| 儿童性内容 (Child Sexual Content) | 儿童性虐待材料 (csam) |
| 儿童性内容 (Child Sexual Content) | 未成年人性化 (minor-sexualization) |
| 儿童性内容 (Child Sexual Content) | 儿童性剥削 (child-exploitation) |
| 儿童诱骗 (Child Grooming) | 儿童诱骗/规避监护 (grooming-evasion) |
| 未成年人有害行为诱导与不当内容暴露 (Inducing Harmful Behavior in Minors & Exposing Minors to Inappropriate Content) | 危险行为诱导 (minor-harm-inducement) |
| 未成年人有害行为诱导与不当内容暴露 (Inducing Harmful Behavior in Minors & Exposing Minors to Inappropriate Content) | 儿童邪典 (child-cult-content) |

### OSS-10 — 知识产权侵权 (Intellectual Property Infringement)

| Second-level category | Third-level label |
|---|---|
| 版权侵犯 (Copyright) | 逐字复制作品 (verbatim-copy) |
| 版权侵犯 (Copyright) | 规避版权保护 (drm-circumvention) |
| 版权侵犯 (Copyright) | 侵权衍生内容 (infringing-derivative) |
| 商标与专利 (Trademark & Patent) | 仿冒/假冒 (counterfeiting) |
| 商业秘密 (Trade Secrets) | 商业秘密/专有技术侵害 (trade-secret-proprietary) |

### OSS-11 — 操纵与欺骗性说服 (Manipulation & Deceptive Persuasion)

| Second-level category | Third-level label |
|---|---|
| 操纵与欺骗性说服 (Manipulation & Deceptive Persuasion) | 大规模心理操纵 (mass-manipulation) |
| 操纵与欺骗性说服 (Manipulation & Deceptive Persuasion) | 身份伪造/冒充 (impersonation) |

## Mapping to Prompts

A prompt links to its taxonomy entry through the category fields:

- `prompt.category.l1` ↔ `taxonomy.类目编号`
- `prompt.category.l2` ↔ `taxonomy.类目名称.二级类目`
- `prompt.category.l3` ↔ `taxonomy.类目名称.三级类目`

The structural definition is available in [`schema.json`](schema.json).
