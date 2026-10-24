from core.session_manager import SessionManager

def test_session_lifecycle() -> None:
    manager = SessionManager()
    assert manager.current is None
    assert not manager.is_authenticated
    manager.start("user-123", "user@example.com")
    assert manager.is_authenticated
    assert manager.current is not None
    assert manager.current.user_id == "user-123"
    assert manager.current.email == "user@example.com"
    manager.clear()
    assert manager.current is None
    assert not manager.is_authenticated
