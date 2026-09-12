"""统一错误体系 —— 所有错误的形状都从这一个文件出（M0 Day1 任务 1.2）。

【骨架是助手给的，带 TODO(你) 的行你写。不准删掉 TODO 直接抄答案，我会 review。】

------------------------------------------------------------
要实现的契约（前端只认这一个形状）
------------------------------------------------------------
成功： { "success": true,  "data": {...}, "code": null, "message": null, "detail": null }
失败： { "success": false, "data": null,  "code": "KB_NOT_FOUND",
         "message": "知识库不存在", "detail": null }

前端只判断 success / code 两个字段，不用写一堆 if 去猜结构（任务单 Q3）。

------------------------------------------------------------
三条要能讲的设计点（写完自己复述一遍，面试会问）
------------------------------------------------------------
1. 业务错误码用**字符串**不用数字：日志里 KB_NOT_FOUND 一眼看懂，不用查表。
2. 区分用户错误(4xx) 和系统错误(5xx)：
   - 4xx：告诉用户"你哪里错了"，detail 可带字段名，日志用 warning
   - 5xx：**只给通用话术**，真实堆栈进日志。
     为什么？—— 泄露表名/路径/依赖版本是安全问题，而且对用户毫无意义。
     只有 config.debug 为 True 时才允许外露细节。
3. 全局兜底：任何没被捕获的异常都变成 500 的统一结构，
   绝不把 Python traceback 吐进 HTTP 响应体。
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


# ============================================================
# 一、错误码
# ============================================================
class ErrorCode(StrEnum):
    """业务错误码。命名规则：**业务对象 + 出了什么事**，不要写"怎么错的"。

    反例：PATH_IS_WRONG（这是描述错误本身，不是业务语义）
    正例：KB_NOT_FOUND（谁 + 怎么了）
    """

    # ---- 4xx 用户错误 ----
    INVALID_PARAMETER = "INVALID_PARAMETER"     # 参数校验不过（422/400）
    NOT_FOUND = "NOT_FOUND"                     # 路由不存在
    KB_NOT_FOUND = "KB_NOT_FOUND"               # 知识库不存在
    DOC_NOT_FOUND = "DOC_NOT_FOUND"             # 文档不存在

    # ---- 5xx 系统错误 ----
    INTERNAL_ERROR = "INTERNAL_ERROR"           # 兜底
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"   # Ollama / rerank 挂了（对应 /health/deep 的 error）

    # TODO(你): 再补两个，命名按上面规则。
    #   ① M2 里用户上传一个 .exe，解析器不支持 → 叫什么？
    #   ② 想删一个还有文档在引用的知识库 → 叫什么？
    #   （提示：两个都是"用户错误"，具体是 400 还是 409，自己定并写下理由）


# ============================================================
# 二、异常层次
# ============================================================
class AppError(Exception):
    """所有业务异常的基类。

    为什么要有基类？—— 全局处理器只需要 except AppError 一处，
    以后加 20 个业务异常都不用改处理器。这就是"统一"的收益。
    """

    code: ErrorCode = ErrorCode.INTERNAL_ERROR
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    message: str = "服务内部错误"

    def __init__(self, message: str | None = None, detail: Any = None) -> None:
        # TODO(你): 三行
        #   1. self.message = 传进来的 message，没传就用类默认值（怎么写最简？）
        #   2. self.detail = detail
        #   3. super().__init__(...)
        #      问自己：super 这一行要传什么？不传会怎样？
        #      （提示：str(exc) 取的是谁给的字符串？日志里会不会看到一个空异常？）
        raise NotImplementedError("TODO(你): AppError.__init__")


# TODO(你): 派生三个具体异常，每个只覆盖 code / status_code / message 三个类属性，
#           **不要写 __init__**（想想为什么不用写？继承链是怎么起作用的？）。
#
#   NotFoundError              → 404, NOT_FOUND      , "资源不存在"
#   InvalidParameterError      → 400, INVALID_PARAMETER, "参数不合法"
#   DependencyUnavailableError → 503, DEPENDENCY_UNAVAILABLE, "依赖服务不可用"
#   （503 不是 500：语义是"我这个服务是好的，是下游挂了"，监控告警要能分开看）


# ============================================================
# 三、统一响应出口
# ============================================================
def _error_response(
    code: ErrorCode,
    message: str,
    status_code: int,
    detail: Any = None,
) -> JSONResponse:
    """所有失败响应的**唯一出口**。

    为什么要收成一个函数？—— 将来想加 trace_id / request_id，
    只改这里一处，不会漏掉某个分支。
    """
    # TODO(你): 返回 JSONResponse，content 是 5 个字段：
    #   success=False, data=None, code=code, message=message, detail=detail
    # 想一想：code 是 StrEnum 成员，JSONResponse 序列化它会得到 "NOT_FOUND"
    #         还是 "<ErrorCode.NOT_FOUND: 'NOT_FOUND'>"？先猜，再实测。
    raise NotImplementedError("TODO(你): _error_response")


# ============================================================
# 四、异常处理器（在 main.py 里注册）
# ============================================================
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """处理我们自己 raise 的业务异常。"""
    # TODO(你):
    #   1. 判断 exc.status_code < 500 还是 >= 500
    #   2. 4xx → logger.warning(...)，message 和 detail **原样**返回
    #      （用户错在哪儿，就该告诉他）
    #   3. 5xx → logger.exception(...)（为什么是 exception 不是 error？——
    #      它会自动带上当前堆栈），返回给用户的 message 换成**通用话术**，
    #      detail 只有 get_settings().debug 为 True 时才给
    #   4. 两个分支都调 _error_response(...)
    #   5. 日志里记得带上 request.url.path —— 不然线上报警你不知道是哪个接口
    raise NotImplementedError("TODO(你): app_error_handler")


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """治 FastAPI 默认的 {"detail": "Not Found"}（验收标准 #5）。

    这条必须注册，否则访问不存在的路由拿到的是 FastAPI 默认形状，
    和你自己的错误结构不一致——前端就又多了一种要猜的结构。
    """
    # TODO(你): 把 exc.status_code 翻译成我们的 ErrorCode + 统一结构。
    #   提示：404 → NOT_FOUND，其余 4xx → INVALID_PARAMETER，5xx → INTERNAL_ERROR
    #   提示：exc.detail 是现成的，可以塞进 detail 字段
    raise NotImplementedError("TODO(你): http_exception_handler")


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """FastAPI 的参数校验失败（默认 422 + 一个很长的 list）。"""
    # TODO(你): 转成 INVALID_PARAMETER + 统一结构，exc.errors() 放进 detail。
    #   问自己：422 属于"用户错误"还是"系统错误"？→ 决定日志级别和 detail 能不能外露。
    #   再问：为什么这里 detail 可以原样返回给用户，而 5xx 不行？
    raise NotImplementedError("TODO(你): validation_error_handler")


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底：任何没被上面接住的异常。"""
    # TODO(你):
    #   1. logger.exception(...) —— 必须带堆栈，否则线上出事你什么都看不到
    #   2. 返回 500 的统一结构，message 用通用话术。
    #      **绝不能**把 str(exc) 给用户（想想 SQLAlchemy 的异常里都有什么）
    #   3. 回答我一个问题（写在下面这行注释里，我会来问）：
    #      这个函数执行完之后，Python 进程会不会死？请求会不会拿到 500？
    #      这两个答案为什么可以不一样？
    raise NotImplementedError("TODO(你): unhandled_exception_handler")


def register_exception_handlers(app: FastAPI) -> None:
    """在 main.py 里调用一次。"""
    # TODO(你): 用 app.add_exception_handler(异常类, 处理函数) 注册上面 4 个。
    #   注意：RequestValidationError 和 StarletteHTTPException 都要注册，
    #        漏掉哪个，哪条路径就会漏出 FastAPI 的默认形状。
    #   顺便回答：为什么集中注册，而不是每个路由自己 try/except？
    #             （提示：想一下 20 个路由要写多少遍，漏一个会怎样）
    raise NotImplementedError("TODO(你): register_exception_handlers")


# ============================================================
# 自检清单（做完自己打勾）
# ============================================================
# [ ] ① ErrorCode 补了 2 个码，并写下了 400/409 的选择理由
# [ ] ② AppError.__init__ 3 行，且 super().__init__ 传了东西
# [ ] ③ 3 个派生异常，只有类属性、没有 __init__
# [ ] ④ _error_response 返回 5 字段，并**实测**了 StrEnum 的序列化结果
# [ ] ⑤ 4 个处理器 + register 函数
# [ ] ⑥ 回答"进程会不会死 / 请求会不会拿到 500"那两问
