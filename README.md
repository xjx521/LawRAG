# LawRAG

**面向法律法规领域的检索增强生成（RAG）系统**

> 不是"能跑的 demo"，是一个有评估体系、有时效性处理、有条款级引用校验的生产级 RAG 系统。

---

## 这个项目解决什么问题

通用 RAG 系统能"上传文档、提问、给答案"。但在法律领域，这不够用：

| 问题 | 通用 RAG | LawRAG |
|------|---------|--------|
| **法条会废止** | 不知道，可能引用失效条款 | 每个 chunk 带公布/施行/失效三个日期，提问时抽时间做窗口过滤 |
| **法条会部分废止** | 粒度到不了"款" | 粒度做到**款**：能回答"第 32 条第 1 款已废止，但整条仍有效" |
| **模型会编引用** | 标了引用但没人校验 | 后端**三层校验**：法规存在？条款存在？该版本当时有效？不通过则拒绝回答 |
| **不知道效果好不好** | "我感觉还行" | 评估集 + `Recall@5` / `MRR` / `Hit@1` / **`Citation F1`**，改一次参数跑一遍 |

---

## 架构

```
┌─────────────┐      HTTP/SSE      ┌──────────────────────────────────┐
│  Streamlit  │ ─────────────────► │           FastAPI                │
│   前端      │ ◄───────────────── │   api → services → core → models │
└─────────────┘                    └──────────────────────────────────┘
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    ▼                         ▼                         ▼
            ┌───────────────┐        ┌───────────────┐        ┌───────────────┐
            │   MySQL       │        │   ChromaDB    │        │    Ollama     │
            │  (真相源)      │        │   (索引)       │        │ qwen2.5:7b    │
            │  chunks 原文   │        │  向量检索      │        │ bge-m3        │
            │  评估集/追溯   │        │               │        │ + 云端 rerank │
            └───────────────┘        └───────────────┘        └───────────────┘
```

**铁律：向量库是索引，不是真相源。** `chunks` 表里的原文才是权威数据——换 embedding 模型要全量重算、索引损坏要重建、导出评估集要原文，都靠它。

### 检索链路

```
用户提问
  ├─ 抽到条款号？ → 是 → SQL 精确查 article_no（绕过向量检索）
  │                └ 否 ↓
  ├─ 抽到时间？   → 是 → 只保留时间窗口内有效的版本
  ├─ 粗召回 top-20：BM25（jieba 法律词典） ∥ 向量（bge-m3）
  ├─ RRF 融合（按名次融合，绕开分数量纲不同）
  ├─ Cross-Encoder 精排 → 分数阈值过滤
  ├─ token 预算裁剪
  └─ 生成（强制引用）→ 引用三层校验 → 落 trace
```

---

## 技术栈

| 层 | 选型 | 为什么不选别的 |
|----|------|--------------|
| 后端 | FastAPI | 原生异步、自动文档、类型校验 |
| 前端 | Streamlit | 答辩要演示；前端不是本项目重点 |
| 关系库 | MySQL + SQLAlchemy 异步 + Alembic | — |
| 向量库 | ChromaDB（`VectorStore` 抽象） | 够用且熟悉；十万级文档换 Qdrant 只改实现类 |
| LLM | Ollama `qwen2.5:7b`（`LLMProvider` 抽象） | 零成本、可离线、答辩不翻车；可切云端 |
| Embedding | `bge-m3`（1024 维） | 中文 RAG 事实标准 |
| Rerank | 云端 `bge-reranker-v2-m3`（`Reranker` 抽象） | 568M 参数本地跑太重；`NoopReranker` 作评估基线 |
| 分层强制 | `import-linter` | 分层靠自觉一定会烂 |

---

## 快速开始

```bash
# 1. 环境
python -m venv venv
venv\Scripts\pip.exe install -r requirements.txt

# 2. 配置
cp .env.example .env    # 如需修改端口/密码，改这里

# 3. 起数据库（MySQL 跑在 Docker，宿主机端口 3307）
cd docker && docker compose up -d mysql && cd ..

# 4. 建表
cd backend && alembic upgrade head && cd ..

# 5. 导入法规语料（公有领域，见《著作权法》第五条）
python scripts/import_laws.py
python scripts/parse_laws.py

# 6. 起服务
uvicorn backend.app.main:app --reload     # 后端 http://127.0.0.1:8000/docs
streamlit run frontend/app.py             # 前端 http://127.0.0.1:8501
```

**前置**：本地需装 [Ollama](https://ollama.com/)，并拉取 `qwen2.5:7b` 和 `bge-m3`。

---

## 项目结构

```
backend/app/
├── api/            # 路由层（薄，只做参数校验和调用 service）
├── services/       # 业务编排
├── core/           # ★ 内核，全部可单测
│   ├── vectorstore/    # 抽象接口 + Chroma 实现
│   ├── llm/            # Provider 抽象：ollama / deepseek
│   ├── embedding/      # Provider 抽象
│   ├── reranker/       # Provider 抽象：siliconflow / local / none
│   ├── loader/         # 按文件类型解析
│   ├── splitter/       # ★ 法律领域分块：按"条"
│   ├── retrieval/      # ★ 混合检索 → RRF → rerank → 阈值 → token 预算
│   ├── generation/     # ★ prompt + 引用 + 防幻觉
│   ├── agent/          # LangGraph 图 + 工具
│   └── observability/  # trace + token/成本计量
├── models/         # SQLAlchemy ORM
├── schemas/        # Pydantic
└── tasks/          # 任务状态机

docs/
├── PROJECT-MEMORY.md   # 详细背景与学习历程（按需读）
├── adr/                # ★ 架构决策记录——面试前通读这个目录
├── 面试弹药库.md        # 数字 / 参数 / 出处 / 已知局限
└── 任务单/              # 每个里程碑的任务单
```

---

## 文档

- **[`docs/adr/`](docs/adr/)** —— 架构决策记录。每条包含"背景 / 备选 / 决定 / 代价 / 面试怎么答"
- **[`docs/面试弹药库.md`](docs/面试弹药库.md)** —— 17 条规格表 + 所有数字的出处 + 已知局限
- **[`docs/PROJECT-MEMORY.md`](docs/PROJECT-MEMORY.md)** —— 项目背景与设计推演过程

---

## 语料与合规

- 法条原文属**公有领域**——《中华人民共和国著作权法》**第五条**：法律、法规，国家机关的决议、决定、命令和其他具有立法、行政、司法性质的文件，不适用本法
- 本项目**只取条文本身**。"法条释义""案例评析"等衍生内容有版权，不收录
- 语料来源：`Duyu/Chinese_Law`（主）、`lawtext/law-flk-vol1`（补最新）、`RanKKI/LawRefBook`（交叉校验）

---

## 免责声明

本项目为**技术演示与学术研究**用途，输出内容**不构成法律意见**。法律问题请咨询执业律师。

系统会主动拒答超出知识库范围的问题，并强制显示引用来源供核对——但**引用正确性依赖语料质量与校验逻辑，不保证 100% 准确**。

---

## 路线图

| 里程碑 | 内容 | 状态 |
|--------|------|------|
| M0 | 地基：config / 统一异常 / Provider 抽象 / 健康检查 | ⬜ |
| M1 | 数据模型：9 张表 ORM + Alembic + 知识库 CRUD | ⬜ |
| M2 | ★ 法条结构化解析 + 接入链路 | ⬜ |
| M3 | ★ 检索层：混合检索 + RRF + rerank + 条款号精确查询 | ⬜ |
| M4 | ★ 问答链路：条款级引用 + 三层校验 + 防幻觉 | ⬜ |
| M5 | ★★ 评估体系：Recall@5 / MRR / Hit@1 / Citation F1 | ⬜ |
| M7 | Streamlit 前端 | ⬜ |
| M6 | ★★ Agentic RAG：query 改写 + 反思节点 + 护栏 | ⬜ |
| M8 | 交付：Docker Compose + 架构图 + 测试 | ⬜ |
