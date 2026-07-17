from pathlib import Path


def test_streamlit_app_file_exists() -> None:
    app_path = Path("src/app.py")
    assert app_path.exists()
    assert app_path.stat().st_size > 0


def test_streamlit_entrypoint_contains_title() -> None:
    content = Path("src/app.py").read_text(encoding="utf-8")
    assert "QuantVision" in content
