import json
from pathlib import Path

import mercantile


class _FakeResponse:
    def __init__(self, status_code: int, body: bytes, headers=None):
        self.status_code = status_code
        self._body = body
        self.headers = headers or {"Content-Type": "image/png"}

    def iter_content(self, chunk_size=8192):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i : i + chunk_size]


class _FakeSession:
    def __init__(self, responses):
        self.headers = {}
        self._responses = list(responses)
        self._idx = 0

    def get(self, url, stream=True, timeout=None):
        if self._idx >= len(self._responses):
            return self._responses[-1]
        resp = self._responses[self._idx]
        self._idx += 1
        return resp


def test_retry_on_invalid_image_bytes(tmp_path, monkeypatch):
    import core.tile_downloader as td

    # First response: 200 but not an image (common anti-bot page)
    invalid = b"<html>blocked</html>" * 10
    # Second response: a PNG-looking byte stream (only header check needed)
    valid_png = b"\x89PNG\r\n\x1a\n" + (b"\x00" * 2048)

    fake_session = _FakeSession(
        [
            _FakeResponse(200, invalid, headers={"Content-Type": "text/html"}),
            _FakeResponse(200, valid_png, headers={"Content-Type": "image/png"}),
        ]
    )

    monkeypatch.setattr(td, "_make_session", lambda user_agent=None, proxies=None: fake_session)
    monkeypatch.setattr(td.time, "sleep", lambda s: None)

    tile = mercantile.Tile(x=1, y=2, z=3)
    checkpoint = tmp_path / "ckpt.json"

    downloader = td.TileDownloader(
        url_template="http://example/{z}/{x}/{y}.png",
        output_base_dir=str(tmp_path),
        checkpoint_path=str(checkpoint),
        max_workers=1,
        batch_size=1,
        batch_pause_min=0.0,
        batch_pause_max=0.0,
        per_thread_min_sleep=0.0,
        per_thread_max_sleep=0.0,
        max_retries=2,
        request_timeout=1.0,
        enable_adaptive=False,
        min_file_size_bytes=64,
        verify_existing=True,
    )

    downloader._download_tiles_impl([tile])

    out_file = tmp_path / f"{mercantile.quadkey(tile)}.png"
    assert out_file.exists()
    assert out_file.stat().st_size >= 64

    manifest = tmp_path / "download_manifest.json"
    assert manifest.exists()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["stats"]["downloaded_ok"] == 1
    assert payload["stats"]["failures"] == 0


def test_invalid_existing_file_is_redownloaded(tmp_path, monkeypatch):
    import core.tile_downloader as td

    valid_png = b"\x89PNG\r\n\x1a\n" + (b"\x00" * 2048)
    fake_session = _FakeSession([_FakeResponse(200, valid_png)])

    monkeypatch.setattr(td, "_make_session", lambda user_agent=None, proxies=None: fake_session)
    monkeypatch.setattr(td.time, "sleep", lambda s: None)

    tile = mercantile.Tile(x=10, y=20, z=5)
    out_file = tmp_path / f"{mercantile.quadkey(tile)}.png"
    out_file.write_bytes(b"")

    downloader = td.TileDownloader(
        url_template="http://example/{z}/{x}/{y}.png",
        output_base_dir=str(tmp_path),
        checkpoint_path=str(tmp_path / "ckpt.json"),
        max_workers=1,
        batch_size=1,
        batch_pause_min=0.0,
        batch_pause_max=0.0,
        per_thread_min_sleep=0.0,
        per_thread_max_sleep=0.0,
        max_retries=1,
        request_timeout=1.0,
        enable_adaptive=False,
        min_file_size_bytes=64,
        verify_existing=True,
    )

    downloader._download_tiles_impl([tile])

    assert out_file.exists()
    assert out_file.stat().st_size >= 64

    payload = json.loads((tmp_path / "download_manifest.json").read_text(encoding="utf-8"))
    assert payload["stats"]["re_downloaded_existing"] == 1
