from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    # 메시지 뒷부분(예: 느낌표 개수, 버전 문구)을 바꿔도 통과하도록 앞부분만 확인합니다.
    assert response.json()["message"].startswith("my-app")


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
