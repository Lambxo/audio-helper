"""GET /health 的接口测试。

不涉及任何外部服务，因此不需要 mock，也不消耗任何真实密钥/额度。
"""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_returns_200_with_ok_status():
    response = client.get("/health")

    assert response.status_code == 200

    body = response.json()
    assert isinstance(body.get("request_id"), str) and body["request_id"]
    assert body.get("data") == {"status": "ok"}


def test_health_request_id_changes_between_calls():
    first = client.get("/health").json()
    second = client.get("/health").json()

    assert first["request_id"] != second["request_id"]
