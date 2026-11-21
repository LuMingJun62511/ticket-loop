# 01 · 架构

> 目标：**一条可替换每一段的流水线**，而不是一个写死的脚本。

---

## 1. 分层映射

用 L0–L4 的语言描述，避免「AI 产品」这个模糊词：

| 层 | 本仓库对应 | 具体模块 | 交付什么 |
|---|---|---|---|
| **L0** 模型 | `src/cs_agent/train`, `serve` | LoRA 0.6B、量化、推理服务 | 一个能干活的模型端点 |
| **L1** 编排 | `src/cs_agent/agent`, `router` | 置信度路由、重试、兜底 | 「下一步做什么」的决策 |
| **L2** 连接 | `src/cs_agent/serve/clients.py` | 大模型 API、内部工具 | 被调用的能力 |
| **L3** 应用 | `scripts/`, `app/` | CLI / 单页 | 一个能用的结果 |
| **L4** 治理 | `src/cs_agent/eval`, `obs` | golden set、指标、trace、成本 | 「跑得对不对」的证明 |

> 这个项目最大的价值：**一层不缺，且层与层之间有明确契约。**

---

## 2. 数据流

```
                     ┌──────────────┐
   raw (csv/jsonl) → │  ingest      │ → 清洗 / 脱敏 / 去重 / near-dup
                     └──────┬───────┘
                            ↓
                     ┌──────────────┐
                     │  split       │ → 按时间切 train/val/test + 分层 + 冻结 hash
                     └──────┬───────┘
                            ↓
        ┌───────────────────┼───────────────────┐
        ↓                   ↓                   ↓
   ┌─────────┐        ┌──────────┐        ┌──────────┐
   │ train   │        │  eval    │        │  serve   │
   │ LoRA    │        │ harness  │        │ 压测/路由 │
   └────┬────┘        └────┬─────┘        └────┬─────┘
        ↓                  ↓                   ↓
   adapter 权重      指标报告            QPS/P95/成本
        └──────────────────┴───────────────────┘
                            ↓
                      docs/reports/
```

---

## 3. 模块与契约

每个模块只暴露一个函数或一个类，输入输出都是**普通 dataclass / dict**，方便替换。

### 3.1 `data`

```python
class Ticket(NamedTuple):
    id: str
    text: str
    label: str          # 2–3 类之一
    created_at: datetime
    source: str         # public | synthetic | private
    split: str          # train | val | test

def load_raw(path: Path) -> Iterator[dict]: ...
def clean(raw: dict) -> Ticket | None: ...
def split(tickets: list[Ticket], by: str = "time") -> Splits: ...
```

**关键约束**：`clean` 必须幂等；`split` 必须可复现（固定 seed + 时间边界）。

### 3.2 `eval`

```python
def run(model: Callable[[list[Ticket]], list[Prediction]], goldens: list[Ticket]) -> Report: ...
```

`model` 是一个 callable —— 所以 **baseline / 小模型 / 大模型 / 路由后系统，用的是同一个 harness**。
这是本项目最重要的一条设计：**评测不绑定实现。**

### 3.3 `train`

```python
def build_dataset(...) -> Dataset: ...
def train_lora(cfg: TrainConfig) -> Path: ...   # 返回 adapter 目录
```

### 3.4 `serve`

```python
class Endpoint(Protocol):
    def predict(self, batch: list[Ticket]) -> list[Prediction]: ...

class LocalVLLM: ...      # 小模型
class RemoteAPI: ...      # 大模型
class Mock: ...           # 压测用，固定延迟
```

**三种实现同一个 Protocol**，所以路由层不需要知道背后是谁。

### 3.5 `router`

```python
def route(t: Ticket, small: Endpoint, big: Endpoint, threshold: float) -> Prediction: ...
```

### 3.6 `agent`

```python
def handle(t: Ticket, deps: Deps) -> Outcome: ...
# Outcome: 分类 + 回复 + 是否转人工 + trace
```

### 3.7 `obs`

```python
@dataclass
class Trace:
    ticket_id: str
    steps: list[Step]     # 每步的 model / tokens / latency / cost
    outcome: str
```

---

## 4. 三条不能破的规则

1. **eval 不依赖实现**：换模型不改评测代码。
2. **数据不进代码**：路径走配置，`private/` 永不入库。
3. **每次实验留痕**：模型名、数据 hash、参数、指标，写进 `eval/reports/*.json`。

---

## 5. 技术选型（当前，可改）

| 位置 | 选择 | 理由 |
|---|---|---|
| 包管理 | uv | 已有；能管 Python 版本 |
| 训练 | transformers + peft + trl | 生态最稳，资料多 |
| 推理 | Ollama（先）/ vLLM（后） | 6GB 上 Ollama 更省事 |
| 大模型臂 | DeepSeek API | 便宜、中文好 |
| 数据 | JSONL | 简单、可 diff、可审计 |
| 指标 | 自写 + scikit-learn | 不引入重框架 |
| 观测 | 自写 JSONL trace | 先能看，再谈 Grafana |

> 刻意不用 LangChain / LlamaIndex：这个项目要看清每一层，框架会遮住它。
