# 数据 Schema

> 一份 schema，三个来源。**来源不同，去向不同。**

---

## 1. 目录与去向

| 目录 | 内容 | 入库 | 说明 |
|---|---|---|---|
| `data/raw/` | 原始下载/导出 | ❌ | 只读，脚本可重放 |
| `data/synthetic/` | 合成/公开数据 | ✅ | 可提交，注意体积（< 5 MB） |
| `data/private/` | 公司脱敏数据 | ❌ **永不** | 只在本机存在 |
| `data/splits/` | 切分产物 | ❌ | 由脚本生成，可重建 |

---

## 2. 记录格式（JSONL，一行一条）

```json
{
  "id": "synth-000123",
  "text": "我上周买的耳机，一直没发货，能退吗",
  "label": "退款",
  "created_at": "2026-03-14T09:12:00",
  "source": "synthetic",
  "locale": "zh-CN",
  "notes": "同时含物流意图，主诉求为退款"
}
```

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `id` | string | ✅ | 全局唯一，前缀标来源 |
| `text` | string | ✅ | 已脱敏；长度 4–2000 字符 |
| `label` | enum | ✅ | `退款` / `物流` / `其他` |
| `created_at` | ISO8601 | ✅ | **切分唯一依据** |
| `source` | enum | ✅ | `public` / `synthetic` / `private` |
| `locale` | string | | 默认 `zh-CN` |
| `notes` | string | | 歧义、多意图时必填 |

---

## 3. 切分规则

```
按 created_at 升序：
  train ← 前 70%
  val   ← 中 15%
  test  ← 后 15%（冻结）
```

硬约束：

1. `test` 只读，写完记 hash 到 `eval/golden/MANIFEST.json`
2. 同 `id` 去重；near-dup（n-gram Jaccard > 0.9）只保留一条
3. val/test 不做上采样；train 可对长尾上采样
4. 合成数据不得由 test 改写而来
5. 切分函数必须可复现（同输入 → 同输出）

---

## 4. 脱敏规则（`private` 数据）

| 类型 | 处理 |
|---|---|
| 手机号 / 身份证 | 正则替换为 `<PHONE>` / `<ID>` |
| 姓名 / 地址 | 保留结构，替换实体 |
| 订单号 | 替换为 `<ORDER>` |
| 金额 | **保留**（对退款类判断有价值） |

脚本：`scripts/sanitize.py`（P1 实现），需可幂等重跑。

---

## 5. 体量控制

- 单文件 ≤ 5 MB，超出按来源/月份分片
- `synthetic/` 总量控制在 20 MB 内
- 大文件用 `.jsonl.gz`，但**评测用的 golden set 必须是明文**，方便 review
