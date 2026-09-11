"""应用配置 —— 所有可调参数的唯一入口。

【这份代码是助手给的（ADR-007 分工线），但你要能讲清每个配置项为什么存在】

------------------------------------------------------------
设计要点（面试会被问，先看这三条）
------------------------------------------------------------

1. 为什么用 pydantic-settings，而不是满世界 `os.getenv()`？
   - `os.getenv()` 返回的是 **str 或 None**，你得自己 int()/float()/split()，
     而且转换失败要等到**用的时候**才炸。pydantic-settings 在**启动时**就把
     类型校验完，配错了立刻报错，不会带病上线。
   - 配置项**集中声明**在一处，看这一个文件就知道系统有哪些旋钮。

2. 为什么用 `.env` 文件 + `get_settings()` 单例？
   - 换环境（开发/演示/测试）只改 `.env`，**代码零改动**。
     这就是 M0 的 Provider 能"改一行 `.env` 切换实现"的物理基础。
   - 配置解析要读文件，属于 IO。用 `lru_cache` 保证**只解析一次**，
     避免每次请求都去读一遍 `.env`。

3. 为什么 `.env` 路径要用绝对路径算出来？
   - `env_file=".env"` 是**相对当前工作目录**的。你在 `D:\\LawRAG` 下启动
     uvicorn 能找到，但从别的目录启动（比如 IDE 直接跑某个脚本）就找不到，
     配置全部变成默认值或直接报错——**这种 bug 极难排查**。
     所以用 `__file__` 反推出项目根目录，路径永远正确。

------------------------------------------------------------
铁律提醒
------------------------------------------------------------
`.env` 里含 API Key，**绝不提交**（已在 .gitignore 第 24-25 行盖住）。
提交前 `git status` 扫一眼，确认没有 `.env` 出现。
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# ------------------------------------------------------------
# 项目根目录：backend/app/config.py → parents[0]=app, [1]=backend, [2]=LawRAG
# ------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    """全部配置项。字段名小写，对应 `.env` 里的大写变量（大小写不敏感）。"""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        # 遇到没声明过的环境变量就忽略，别让无关变量把启动搞崩
        extra="ignore",
    )

    # ---------- 应用 ----------
    app_name: str = "LawRAG"
    env: Literal["dev", "prod"] = "dev"
    # DEBUG=true 时：日志更啰嗦、`/docs` 打开、错误详情可以外露
    # ⚠️ 生产环境必须是 false，否则 traceback 会泄露内部结构
    debug: bool = True

    # ---------- 数据库 ----------
    # 为什么两份 URL？—— 异步/同步是两套驱动，用途不同：
    #   async_database_url：应用运行时用（aiomysql，不阻塞事件循环）
    #   sync_database_url ：Alembic 迁移用（迁移是命令行脚本，没有事件循环）
    # 少写一份的代价是迁移时得手拼 URL，迟早写错。
    async_database_url: str
    sync_database_url: str

    # ---------- 跨域 ----------
    # 前端 Streamlit 跑在 8501，后端跑在 8000，属于跨域。
    # 这里存**逗号分隔的字符串**而不是 list：
    # 环境变量本身只能是字符串，声明成 list 反而要在 .env 里写 JSON，
    # 手写起来更容易错。用下面的 cors_origin_list 属性做拆分。
    cors_origins: str = "http://localhost:8501"

    # ---------- LLM Provider ----------
    # 这个字段就是"Provider 抽象"的开关：
    # 换模型只改这一行，services / core 的代码一行不动（见 ADR-013）。
    llm_provider: Literal["ollama", "deepseek"] = "ollama"

    # 本地 Ollama
    ollama_base_url: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen2.5:7b"
    # 法律问答要求稳定复现，temperature 设 0
    llm_temperature: float = 0.0

    # 云端 DeepSeek（作为备选 / 降级目标）
    # 默认空字符串：没配 Key 时不该在**启动**就失败，
    # 而是等到真的要用它的时候（factory 里）才报"未配置"——这本身就是降级策略的一部分。
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-v4-flash"

    # ---------- Embedding ----------
    # 维度必须和模型真实输出一致：bge-m3 = 1024。
    # 这个数字写错的后果是**向量库写入时才发现维度不匹配**，所以宁可显式声明。
    embed_model: str = "bge-m3"
    embed_dim: int = 1024

    # ---------- Reranker ----------
    # 三个实现（见 ADR-005）：
    #   siliconflow → 云端 bge-reranker-v2-m3（默认）
    #   local       → 本地 cross-encoder（断网/答辩备用）
    #   none        → NoopReranker，**评估的对照组**，不是"以防万一"
    rerank_provider: Literal["siliconflow", "local", "none"] = "siliconflow"
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"

    # ---------- 向量库 ----------
    # Chroma 是"当前最优选择"而非"最佳选择"（见 ADR-004）：
    # 它靠抽象层隔离，换 Qdrant 只改实现类 + 这一行配置。
    chroma_dir: str = "./chroma_data"
    vectorstore: Literal["chroma", "qdrant"] = "chroma"

    # ---------- 检索默认参数 ----------
    # 注意：这些是**默认值**，将来可以被 knowledge_bases.config（每个知识库自己的配置）覆盖。
    # 放两份的理由：全局默认让新库开箱可用，库级配置让不同库能各自调参。
    retrieval_mode: Literal["bm25", "vector", "hybrid"] = "hybrid"
    retrieval_top_k: int = 20      # 粗排召回量
    rerank_top_n: int = 5          # 精排后真正进 prompt 的条数
    rrf_k: int = 60                # RRF 融合公式里的常数（出处：FastGPT）
    score_threshold: float = 0.3   # rerank 分数低于此值直接丢弃（防噪音进 prompt）

    # ---------- 法律领域 ----------
    default_region: str = "全国"    # 地方性法规预留字段，第一版不做本地化

    # ---------- 可观测 ----------
    # /health/deep 探测**每一个依赖**的超时（秒）。
    # 为什么单独给一个这么小的值？—— 健康检查自己不能变成慢接口。
    # 如果探 reranker 卡 30 秒，监控系统会以为你的**健康检查**挂了。
    # 探活超时必须独立于业务超时，且要短。
    health_check_timeout: float = 3.0

    @property
    def cors_origin_list(self) -> list[str]:
        """把逗号分隔的字符串拆成列表，顺手去掉空白项。

        `CORS_ORIGINS=a,b,` 这种手滑写了多余逗号的情况，也不会产生一个空字符串源
        （空字符串在 CORS 里是无效源，会让中间件行为变得难以理解）。
        """
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"


@lru_cache
def get_settings() -> Settings:
    """获取配置单例。

    `@lru_cache` 让整个进程只解析一次 `.env`。
    测试里想换配置时用 `get_settings.cache_clear()` 清掉缓存。
    """
    return Settings()  # type: ignore[call-arg]  # 字段由 .env 填充
