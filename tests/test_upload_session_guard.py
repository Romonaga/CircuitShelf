import os
import time

from backend.services.upload_session_guard import (
    active_upload_sessions,
    complete_upload_session,
    mark_upload_session_active,
    normalize_upload_session_id,
    upload_session_lock_path,
)


def test_upload_session_lock_lifecycle(tmp_path):
    session_id = mark_upload_session_active(str(tmp_path), "upload/session 1")

    assert session_id == "upload-session-1"
    assert active_upload_sessions(str(tmp_path)) == ["upload-session-1"]
    assert os.path.exists(upload_session_lock_path(str(tmp_path), session_id))

    complete_upload_session(str(tmp_path), session_id)

    assert active_upload_sessions(str(tmp_path)) == []


def test_upload_session_guard_drops_stale_locks(tmp_path):
    session_id = mark_upload_session_active(str(tmp_path), "stale")
    lock_path = upload_session_lock_path(str(tmp_path), session_id)
    old_time = time.time() - 120
    os.utime(lock_path, (old_time, old_time))

    assert active_upload_sessions(str(tmp_path), stale_seconds=60) == []
    assert not os.path.exists(lock_path)


def test_upload_session_id_normalization():
    assert normalize_upload_session_id("../bad/session\\id") == "..-bad-session-id"
    assert normalize_upload_session_id("") == ""
