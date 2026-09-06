"""请求与响应的数据结构（Pydantic 模型）。

本轮仅包含 /health 所需的模型，其余接口的 schema 会在实现对应
接口的轮次中补充，不在此提前定义。
"""

from pydantic import BaseModel


class HealthData(BaseModel):
    """/health 的 data 字段结构。"""

    status: str


class HealthResponse(BaseModel):
    """/health 的完整响应结构：{"request_id": ..., "data": {...}}"""

    request_id: str
    data: HealthData
