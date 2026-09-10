# LawRAG 项目记忆（详细版）

> 本文件**不自动加载**，需要背景时按需读。
> 每次会话必看的是 `CLAUDE.md`（<8KB）。本文件放"什么时候需要什么时候翻"的东西。

---

## 一、为什么要做 LawRAG

### 起因（2026-09-11 对话）

用户进入第六阶段，准备做**简历项目一（RAG 知识库）**。提出四条硬要求：

1. **不能只是能跑的 demo**——"我要求的是符合生产级符合日常开发会遇到的问题经得住拷问的项目"
2. **先研究 GitHub 优秀项目，再讨论计划，最后才生成**
3. **核心必须自己会**——"保证我核心一定要会而且经得住问，从为什么这样设计开始"
4. **要贴合实际应用场景**——"比如医疗法律等等适合专业知识库的场景"

### 毕业设计的考量

用户面临毕业设计和论文。**同学大多做基于 Java/SpringBoot 的简单图书管理系统**，用户明确"不打算跟他们一样"。

选 LawRAG 作毕设主体的理由：
- RAG 领域有**清晰的量化指标**（Recall@5 / MRR / Citation F1）→ 论文实验章有东西可写
- 法律领域有**天然的 ground truth**（条文号）→ 评估集好标注、结果可复现
- 相比 Agent 项目，RAG 边界清晰、答辩可控、演示稳定

**决定**：项目一（RAG）作毕设主体，项目二（Agent）作为其中一个模块（M6 Agentic RAG）。两个项目放不同文件夹，独立仓库。

---

## 二、参考的 GitHub 项目（用户提供 + 调研补充）

用户最初给了 6 个：

| 项目 | Star | 借鉴什么 |
|------|------|---------|
| **RAGFlow** (infiniflow) | 50.1K | ★ 检索配置结构、`message_fit_in()` token 预算裁剪、加权融合参数 |
| **FastGPT** (labring) | 23.7K | ★ RRF 融合公式 `1/(60+rank)`、知识库配置随库走 |
| **Dify** | 93.7K | ★ 分层依赖强制（`import-linter` + `backend-layers` 契约）、模块目录切分 |
| **Haystack** (deepset-ai) | 20.4K | 组件抽象 / Pipeline 接口设计 |
| **txtai** (neuml) | 10.8K | 一站式多模态思路（本项目不做） |
| **QAnything** (netease) | 13.1K | Embedding + Reranker 分层的必要性佐证 |

**结论**：不抄代码，只抄**结构决策**。Star 数不是重点，能回答"为什么这样设计"才是。

---

## 三、本次对话的关键结论（已固化成 ADR）

见 `docs/adr/`。这里只记 ADR 之外的：

### 3.1 三条"这个项目值钱在哪"的判断

1. **面试官问"你怎么知道你的系统好？"→ 能掏出一个数字，而不是"我感觉还行"**
   → 这是判断"生产级"的唯一标准。所以 M5 评估体系**绝不砍**。

2. **法律领域的真正差异化不是"能查法条"**（那是 demo），而是：
   - **时效性**：法条会失效，且可能**部分失效**
   - **条款级引用校验**：引用必须能追溯到"《法规名》第 X 条第 X 款"，且要真的校验存在性

3. **"经得住拷问"是可设计的**——先把 17 个面试官会问的问题列出来，**接不住的功能就不做**。这是项目范围控制的依据。

### 3.2 语料调研的三个硬结论（已核实）

1. **不自己写爬虫**。现成资源已足够：`Duyu/Chinese_Law`（HF，结构化 Markdown，层级最完整）为主，`lawtext/law-flk-vol1` 补最新版本，`RanKKI/LawRefBook` 交叉校验。

2. **法律文本是公有领域**——《著作权法》第五条：法律、法规、国家机关的司法/行政性质文件不适用著作权法。可自由下载分发。（但"法条释义/案例评析"有版权，不碰。）

3. **⚠️ 时效性字段有来源冲突**：flk 的 `sxx` 编码存在两套矛盾说法（`3=有效` vs `3=尚未生效`）。**必须用《劳动合同法》（应为"已修改"）反推实测**，不许盲抄任何一方。

### 3.3 一个绝佳的测试用例（粒度试金石）

> 《最高法劳动争议司法解释（一）》**第 32 条第 1 款**自 2025-09-01 起被《解释（二）》（法释〔2025〕12号）废止——**整条仍有效，只有其中一款失效**。

只做到"条"粒度的系统**答不了**这个问题。所以 chunks 表必须存到**款**。

**另一个坑**：《解释（二）》2025-09-01 才施行，**2024 年前抓的镜像仓库基本都没有这部法**。校验语料时必须专门检查。

---

## 四、gowork 学习历程（Day43 - Day61，2026-08-12 ~ 09-01）

用户的加速学习阶段。**产出全是散装实验脚本**，LawRAG 要做的就是把这些散件组装成工程。

### Phase 3：LLM 基础（Day43-49）

| Day | 主题 | 关键产出 |
|-----|------|---------|
| 43 | LLM 基础概念 | token 认识、首次调 API（遇 401 Key 重复前缀 / 400 欠费，最终切 DeepSeek）、temperature 破坏性实验 |
| 44 | 多轮流式对话 | 带历史 vs 不带历史的对照（实证模型无记忆）、stream 逐 chunk、`delta.content is None` 过滤 |
| 45 | Function Calling | JSON Schema 四层结构、四段式闭环（user→assistant(tool_calls)→tool→assistant）、`tool_call_id` 配对 |
| 46 | Prompt 工程 | 四要素（角色/任务/约束/格式）、0-shot vs 2-shot 锁格式、JSON 输出三法 |
| 47 | Token 与上下文窗口 | 近似数 token、`finish_reason` 四值、`manage_history` 删最旧、成本估算 |
| 48 | **第一个 AI 项目** | FastAPI + Streamlit + MySQL，mock LLM 换真 DeepSeek；会话 LRU 淘汰；前端 session_id 修复 |
| 49 | 阶段复习 | 5 关自查，暴露卡点：**FC 三段式 / 预训练SFT-RLHF / KV Cache+QKV** |

### Phase 4：RAG（Day50-57）

| Day | 主题 | 关键产出 |
|-----|------|---------|
| 50 | RAG 原理与最小管线 | 手写 `char_overlap_score` 检索器、最小闭环、破坏性实验（打分恒 1 → 退化成取前几段） |
| 51 | 语义检索与 Embedding | Ollama `bge-m3`、手写余弦相似度、**实证"完全无关也永不为 0"**（问天气 0.493 > 问股票 0.427） |
| 52 | ChromaDB | PersistentClient / collection / add / query；metadata 过滤；分块粒度实验（分块 0.623 < 整段 0.721 命中更准） |
| 53 | 混合检索与重排序 | 手写 BM25（IDF+TF归一+k1/b）、RRF `1/(60+rank)`、LLM 当重排器（**7B 重排帮倒忙**，实证"重排器质量决定重排价值"） |
| 54 | 检索质量评估 | 12 题评估集、手写 evaluate、三路打分。**两个打脸**：编号题三路都对（bge-m3 对编号也有语义）；混合 Hit@1 反输向量 |
| 55 | 引用标注与防幻觉 | prompt 强制标 `[1][2]`、`re.findall` 提编号+边界过滤、**"幻觉的引用"实锤**（top_k=5 时引用飘到诱导段） |
| 56 | LangChain 映射 RAG | 五件套映射、`jieba` 挂 `preprocess_func` 是刚需、metadata src 引用链路 |
| 57 | **RAGService 封装** | 简历项目一的地基：类封装 + 幂等 Chroma + 三检索器 + LCEL chain；**增量索引**（delete+add 同 id 保幂等） |

### Phase 5：Agent（Day58-61）

| Day | 主题 | 关键产出 |
|-----|------|---------|
| 58 | Agent 概念 + 手写 ReAct | 纯文本协议（Thought/Action/Action Input/Final Answer）、`run_agent` 循环、**Observation 必须拼回 messages** |
| 59 | 真实工具 | `get_time` / `get_weather`（Open-Meteo 双 API + timeout）/ 文件系统工具（`_safe_path` 四层防御挡路径穿越）；**铁律：工具内部错误全消化，向外只输出字符串** |
| 60 | 工具契约复盘 + 多工具协同 | @tool 结构化 `tool_calls` vs raw 自由文本；**手写 ReAct 四道缝**：参数契约 / Observation 来源 / 出错包装 / 终止判断 |
| 61 | LangGraph 映射 | 手写 `run_agent` 逐行映射成 StateGraph（for 循环→边回环、call_llm→agent 节点、TOOLS→tools 节点、Final Answer 判断→条件路由）；`checkpointer` + `thread_id` 跨请求记忆；middleware 六钩子 |

### 加速阶段的结论（2026-08-31）

用户看完黑马课 P6-07~13 后判断 Day62 整合内容**过于简单**，决定**提前收官**，Day62 任务保留作参考，与 9 月企业级收尾合并。

---

## 五、用户能力画像（教学时的关键参考）

### 已掌握

- **LLM 应用层**：API 调用、多轮、流式、Function Calling、Prompt 工程、token 预算管理
- **RAG 全链路**：两遍——手写版（理解原理）+ LangChain 版（映射框架）
- **Agent**：手写 ReAct + LangGraph 图 + 工具契约 + checkpointer
- **Web 工程基础**：FastAPI、SQLAlchemy 异步、Alembic、JWT、Docker 基础、Streamlit

### 薄弱（必须在 LawRAG 里针对性补）

| 能力 | 自查结果 | 应对方式 |
|------|---------|---------|
| **能讲** | ★ **最弱**——"概念理解简单但就是讲不出来"，需反复复述 | 每个模块学完**必须用自己的话复述一遍**，助手不打断，听完再纠正 |
| **能写** | 手写慢、拼写笔误多（`Choram`/`Ebeddings`/`ciity`/漏 `await`） | 给骨架留空，用户填；review 时**专门盯拼写和缩进** |
| **能修** | 中等，能按"先查 X 再查 Y"的清单排查 | 每模块给一张排查清单 |
| **能答 why** | 中等，能复述但深度不够 | 每个决策写 ADR，强制问"为什么不用另一个" |
| **能扛边界** | ★ 弱——"想不全" | 主动追问"10 万文档会怎样""断网了会怎样"，列进规格表 |

### 已暴露的具体知识漏洞（Day49 自查）

- FC 三段式说不清
- QKV 只记得三个字母，说不出流程
- 预训练 / SFT / RLHF 只写到"预训练解决的是"
- KV Cache 空着
- 降成本只写出 1 条

**→ 这些是 Phase 6（计算机基础突击）要回补的，LawRAG 期间不必专门补，但 ADR 里涉及模型原理的地方要写清楚。**

### 用户的学习节奏偏好

- 每天 4-5 小时（开学后）
- 任务单格式已固定：目标 / 概念预习 / 动手实验 / 自测 5 关 / 产出 / 自评
- **三级代码引导**：【提示】（已见过的概念）/【骨架】（概念懂但第一次写）/【示例】（全新概念的最小可跑版本，且不含当天答案）
- 同一概念**只给一次【示例】**

---

## 六、环境备忘

| 项 | 值 | 备注 |
|----|-----|------|
| venv | `D:\LawRAG\venv\Scripts\python.exe` | 从 `D:\Go work\venv` 复制（936MB），已修复全部内嵌旧路径 |
| Python | 3.14.6 | ⚠️ 很新，个别包的 wheel 可能缺失，装不上时降级到 3.12 |
| Ollama | `OLLAMA_MODELS=D:\Ollama\models` | **服务必须带此环境变量启动**，否则找不到模型 |
| GPU | NVIDIA | 可本地跑模型 |
| 已知环境问题 | GBK 控制台打印中文/emoji 会 `UnicodeEncodeError` | 环境问题非代码错 |

### venv 复制踩过的坑（记录备查）

复制 venv **不是** `robocopy` 完就能用。Windows 的 venv 里有两处内嵌绝对路径：

1. **纯文本**：`Scripts/activate`、`activate.bat`、`activate.fish` → 直接字符串替换
2. **`.exe` 启动器**：格式是 `[PE 二进制] + [shebang 行] + [内嵌 zip]`，旧路径在 **zip 前面的 shebang** 里（不是 zip 里的 `__main__.py`）
   - 修法：定位 zip 起点，只替换起点之前的字节
   - 长度变化（14→13 字节）**不影响**——启动器靠扫 EOL 定位，不依赖固定偏移

**验证方法**：`venv/Scripts/pip.exe --version` 会打印 `pip X from <哪个 venv>\Lib\site-packages\pip`——这是判断 venv 身份最直接的证据。（走 `python.exe -m pip` 看不出问题，因为它绕过了启动器。）

> 注：本项目日常调用一律用 `D:\LawRAG\venv\Scripts\python.exe`，不走 `activate`，所以这个坑本来也不会踩到——但留着是隐患（将来 `pip install` 会装到旧 venv），已修。

---

## 七、当前状态与下一步

### 已完成（2026-09-11 立项日）

- ✅ 计划讨论与批准（11 条决策 → ADR-001~011）
- ✅ `D:\LawRAG` 目录结构 + 20 个 `__init__.py`
- ✅ venv 复制 + 45 个 `.exe` 启动器旧路径修复 + 补装 6 个包
- ✅ `.gitignore` / `.env.example` / `requirements.txt` / `docker/docker-compose.yml`
- ✅ `CLAUDE.md`（7.5KB）/ `docs/PROJECT-MEMORY.md` / `README.md`
- ✅ `docs/adr/` ADR-001~011 + 索引 / `docs/面试弹药库.md`
- ✅ `docs/任务单/M0-地基.md`
- ✅ 本地 git 提交（分支 `main`）

### 进行中：M0 地基（设计讨论阶段）

**规则**：Q1-Q5 五个设计讨论**全部讨论通了才写代码**，不许跳步。

| # | 讨论题 | 状态 | 结论 |
|---|--------|------|------|
| Q1 | 为什么后端要分层？ | ✅ 已过 | 用户答对：**评估脚本没有 HTTP 服务器，不分层则 core 没法复用**。补充第二层收益：想给检索逻辑写单测，不分层必须先起 HTTP 服务器 |
| Q2 | Provider 为什么抽象？ | ⬜ | 核心是"看起来过度设计，其实不是"——切换是既定需求（ADR-004/005），且评估实验要"一次只改一个变量"，`NoopReranker` 是实验设计的一部分 |
| Q3 | 统一异常的意义？ | ⬜ | 业务码用字符串不用数字 / 区分用户错误(4xx)与系统错误(5xx，不给用户看 traceback) / 全局兜底 |
| Q4 | 健康检查检查什么？ | ⬜ | 不是 `{"status":"ok"}` 而是**依赖探活**；快速/深度分两个接口；`degraded` 状态语义 |
| Q5 | 为什么 core/ 不许 import FastAPI？ | ⬜ | M5 评估脚本要复用同一内核；同一检索逻辑两个入口 |

**Q1 的讨论方式（可复用到后续）**：给两段做同一件事的代码（不分层 vs 分层），让用户判断"多绕这一圈赚到了什么"，并给一个**具体场景做锚点**（"M5 的评估脚本是命令行的，没有 HTTP 服务器，写法 A 能用吗？"）。
效果：用户直接答中要害——比抽象地问"为什么要分层"好答得多。**后续讨论继续用这招：给具体场景，不给抽象概念。**

### 环境决策（2026-09-11 确认）

- **MySQL = Docker 里新起一个**，宿主机端口 **3307**（3306 已被本机原有 MySQL 占用，PID 6636）。配置见 `docker/docker-compose.yml`
- **硅基流动 API Key 推迟到 M3 再注册**（rerank 接口到 M3 才用到）
- **GitHub 暂时推不上去**：`gh` CLI 未装，且 GitHub 连接被重置（连 gowork 的 remote 也连不上），用户自己也登不进去。本地 git 正常提交，等网络恢复再 push

### 下一步

1. 继续 M0 设计讨论 **Q2**（Provider 为什么抽象）
2. Q1-Q5 讨论完 → 按任务单动手写代码（Day 1 骨架 → Day 2 Provider 抽象）
3. GitHub 网络恢复后：建仓库 + `git push -u origin main`
4. 用户方便时启动 Docker Desktop 并 `docker compose up -d mysql`（M1 前需要）
