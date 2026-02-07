from fastapi.testclient import TestClient

from VoiceServer import main


class FakeStorage:
    def __init__(self) -> None:
        self.uploaded = None

    def upload(self, path, data, file_options=None):
        self.uploaded = {"path": path, "data": data, "options": file_options}
        return {"path": path}

    def get_public_url(self, path):
        return {"publicUrl": f"https://example.com/{path}"}


def test_upload_requires_file():
    client = TestClient(main.app)
    response = client.post("/audio/upload")
    assert response.status_code == 400


def test_upload_returns_public_url(monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr(main, "get_storage", lambda: fake)

    client = TestClient(main.app)
    response = client.post(
        "/audio/upload",
        files={"file": ("test.m4a", b"abc", "audio/mp4")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["url"] == f"https://example.com/{fake.uploaded['path']}"
    assert body["path"] == fake.uploaded["path"]
    assert body["size"] == 3
