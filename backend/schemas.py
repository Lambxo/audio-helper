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


class AsrRequest(BaseModel):
    audio_id: str


class AsrData(BaseModel):
    text: str


class AsrResponse(BaseModel):
    request_id: str
    data: AsrData


class ExtractRequest(BaseModel):
    text: str
    city: str


class ExtractData(BaseModel):
    city_a: str
    address_a: str
    city_b: str
    address_b: str
    category: str


class ExtractResponse(BaseModel):
    request_id: str
    data: ExtractData
