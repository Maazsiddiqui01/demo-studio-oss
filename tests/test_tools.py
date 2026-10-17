import pytest

from demo_studio import tools


def test_ffmpeg_runs_and_reports_errors(tmp_path):
    tools.ffmpeg("-f", "lavfi", "-i", "testsrc=size=160x120:rate=10", "-t", "1", "ok.mp4", cwd=tmp_path)
    assert (tmp_path / "ok.mp4").stat().st_size > 0
    with pytest.raises(RuntimeError, match="ffmpeg failed"):
        tools.ffmpeg("-i", "missing.mp4", "x.mp4", cwd=tmp_path)


def test_stalled_ffmpeg_is_stopped(tmp_path, monkeypatch):
    # a filter that releases a frame almost never: no progress, so the watchdog stops it (twice)
    monkeypatch.setattr(tools, "STALL_SECONDS", 3)
    with pytest.raises(RuntimeError, match="no progress"):
        tools.ffmpeg("-f", "lavfi", "-i", "testsrc=size=160x120:rate=5", "-vf", "realtime=speed=0.00001",
                     "-t", "5", "stall.mp4", cwd=tmp_path)
