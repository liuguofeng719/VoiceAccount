from fastapi.testclient import TestClient

from VoiceServer import main


def test_parse_requires_audio_url():
    client = TestClient(main.app)
    response = client.post("/audio/parse", json={"categories": ["餐饮"]})
    assert response.status_code == 400


def test_parse_returns_items(monkeypatch):
    def fake_download(_):
        return b"audio"

    def fake_parse(_audio_bytes, categories, _audio_format, _audio_url=None):
        return [
            {"title": "午餐", "amount": 23.5, "category": categories[0]},
            {"title": "咖啡", "amount": 18.0, "category": categories[0]},
        ]

    monkeypatch.setattr(main, "download_audio", fake_download)
    monkeypatch.setattr(main, "parse_audio_with_ai", fake_parse)

    client = TestClient(main.app)
    response = client.post(
        "/audio/parse",
        json={"audio_url": "https://example.com/audio.m4a", "categories": ["餐饮"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body[0]["title"] == "午餐"
