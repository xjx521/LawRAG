# ADR-005：重排（Rerank）用云端 API + 抽象成接口

> 状态：已采纳 · 2026-09-11

## 背景

两阶段检索的第二步是**重排**：粗召回 top-20 → cross-encoder 精排 → 取 top-5 进 prompt。

gowork 阶段（Day53）已经验证过重排的必要性，但也暴露了一个关键教训：

> 当时因为没装 cross-encoder，用本地 Ollama `qwen2.5:7b` 当重排器，结果**把正确答案「年假政策」从第 1 名挤到了第 2 名**——小模型重排帮倒忙。

这说明：**重排器的质量直接决定重排的价值**。用错模型比不重排更糟。

## 备选

| 方案 | 优点 | 缺点 |
|------|------|------|
| **A. 云端 rerank API**（硅基流动 `BAAI/bge-reranker-v2-m3`） | 质量有保证；不占显存；延迟可控 | 要 API Key；断网不能用；有调用成本 |
| B. 本地跑 cross-encoder | 完全离线；零成本 | `bge-reranker-v2-m3` 约 **568M 参数**，和 LLM 抢显存；本地 CPU 跑很慢 |
| C. 用 LLM 当重排器（Day53 做法） | 不用额外模型 | **实测会帮倒忙**，7B 模型排序能力不可靠 |
| D. 不做重排 | 最简单 | 召回噪音直接进 prompt，规格表第 3 条答不上 |

## 决定

**选 A：云端 rerank API，但抽象成 `Reranker` 接口。**

```python
class Reranker(Protocol):
    def rerank(self, query: str, docs: list[str], top_n: int) -> list[tuple[int, float]]: ...
```

三个实现：

| 实现 | 用途 |
|------|------|
| `SiliconFlowReranker` | 默认，走云端 `BAAI/bge-reranker-v2-m3` |
| `LocalReranker` | 装了 cross-encoder 时用，完全离线 |
| `NoopReranker` | 不重排，**作为评估的对照组**（要证明重排确实有用，必须有这个基线） |

### 为什么坚持要抽象层

因为**评估实验需要切换重排器**。论文实验章要对比"有 rerank vs 无 rerank"，如果重排是硬编码的，就没法一次只改一个变量。

`NoopReranker` 不是"以防万一"，是**实验设计的一部分**。

### 关于模型选择

`BAAI/bge-reranker-v2-m3` 是 gowork 阶段就调研过的目标模型（约 568M 参数，输出 [0,1] 分数，比 bi-encoder 的余弦相似度更适合做**阈值过滤**——因为分数有明确语义）。

**⚠️ 长度限制**：上下文约 **1024 tokens**。法律条文里的列举式长条（如《劳动合同法》第 46 条列了 7 种情形）可能超出。**M2 拿到语料后必须先跑 `len()` 分布统计**（P50/P90/P99），再决定是否需要对超长条文做特殊处理。

## 代价

- **联网依赖**：rerank 挂掉会拖垮问答链路。→ 必须有超时 + 降级（`tenacity` 重试 → 失败则 fall back 到 `NoopReranker`，并在 trace 里记录降级事件）
- **API Key 管理**：`SILICONFLOW_API_KEY` 必须进 `.env`，`.gitignore` 已盖住，提交前 `git status` 确认
- **成本**：rerank 按 token 计费。每次问答调一次，评估跑几百次会累积。→ trace 里要记 rerank 调用量
- **断网演示风险**：答辩现场没网 → 提前准备好 `LocalReranker` 或切 `NoopReranker`，**演示前必须演练一遍离线路径**

## 面试怎么答

> "重排你用的什么模型？为什么不用本地的？"
>
> 用 `bge-reranker-v2-m3`，走云端 API，但我抽象成了 `Reranker` 接口，三个实现可切。
>
> 选云端是因为这个模型 568M 参数，本地跑会和 LLM 抢显存。而我在上一个项目里踩过坑——当时用 7B 的通用 LLM 当重排器，结果**把正确答案从第 1 名挤到第 2 名**，比不重排还差。那次之后我明确了：重排器的质量直接决定重排的价值，不能随便拿个模型顶。
>
> 而且我把"不重排"也做成了一个实现类，因为**评估的时候我需要这个基线**——不然我凭什么说重排有用？得拿数据说话。
>
> 代价是断网就不能用。所以我准备了降级路径：重试失败就 fall back 到不重排，trace 里记录这次降级。演示前会演练离线场景。
