from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]


def test_realtime_redis_keys_are_namespaced():
    """Realtime PubChat не должен создавать общие ключи Redis без префикса проекта."""
    service = (BACKEND / "components" / "realtime" / "service.py").read_text(
        encoding="utf-8"
    )
    active_context = (
        BACKEND / "components" / "realtime" / "active_context.py"
    ).read_text(encoding="utf-8")

    expected = (
        'CHANNEL = "pubchat:realtime:v2"',
        'return f"pubchat:rt:ticket:{digest}"',
        'return f"pubchat:rt:presence:user:{user_uid}"',
        'return f"pubchat:rt:presence:room:{room_uid}"',
        'return f"pubchat:rt:presence:connection:{connection_id}"',
        'key = f"pubchat:rt:rate:{bucket}:{user_uid}"',
    )
    for marker in expected:
        assert marker in service

    assert (
        'return f"pubchat:rt:active:messenger:{account_uid}:{dialog_uid}"'
        in active_context
    )


def test_chat_has_no_shared_celery_worker_configuration():
    """PubChat использует собственные DB/timer workers, а не общую очередь Celery."""
    celery_files = [
        path
        for path in BACKEND.rglob("*.py")
        if "celery" in path.name.lower()
    ]
    assert celery_files == []
