"""请求与响应的数据结构（Pydantic 模型）。"""

from pydantic import BaseModel


class HealthData(BaseModel):
    status: str


class HealthResponse(BaseModel):
    request_id: str
    data: HealthData


class UploadData(BaseModel):
    audio_id: str


class UploadResponse(BaseModel):
    request_id: str
    data: UploadData
