import os
import tempfile
import pathlib
from pathlib import Path

from src.config_store import ConfigStore
from src.scan_engine import ScanEngine, ScanResult


def test_core_patterns():
    cs = ConfigStore()
    cs.config = {
        "scan_folders": [],
        "file_age_days": 0,
        "scan_interval_minutes": 1440,
        "file_types": [".txt", ".csv", ".docx", ".xlsx", ".pdf", ".log"],
    }
    engine = ScanEngine(cs)

    assert engine._matches_cpr("1203861234") == "1203861234"
    assert engine._matches_cpr("2812991234") == "2812991234"
    assert engine._matches_cpr("9913991234") is None

    assert engine._matches_email("foo@bar.dk") == "foo@bar.dk"
    assert engine._matches_email("test@example.com") is None

    assert engine._matches_phone("+45 12 34 56 78") == "+45 12 34 56 78"
    assert engine._matches_phone("00 45 12 34 56 78") == "00 45 12 34 56 78" or engine._matches_phone("00 45 12 34 56 78") is not None

    assert engine._filename_match(Path("kunde_list.txt")) == "Filename contains keyword 'kunde'"
    assert engine._filename_match(Path("notes.txt")) is None


def test_csv_header_detects_pii():
    cs = ConfigStore()
    cs.config = {
        "scan_folders": [],
        "file_age_days": 0,
        "scan_interval_minutes": 1440,
        "file_types": [".txt", ".csv", ".docx", ".xlsx", ".pdf", ".log"],
    }
    engine = ScanEngine(cs)

    with tempfile.TemporaryDirectory() as tempdir:
        path = Path(tempdir) / "data.csv"
        path.write_text("CPR,Name\n120386-1234,Test\n", encoding="utf-8")

        cs.config["scan_folders"] = [tempdir]
        result: ScanResult = engine.scan()

        assert result.files_scanned == 1
        assert any("Spreadsheet header indicates PII" in f.reason for f in result.findings)


def test_txt_content_detects_email_and_phone_and_cpr():
    cs = ConfigStore()
    cs.config = {
        "scan_folders": [],
        "file_age_days": 0,
        "scan_interval_minutes": 1440,
        "file_types": [".txt", ".csv", ".docx", ".xlsx", ".pdf", ".log"],
    }
    engine = ScanEngine(cs)

    with tempfile.TemporaryDirectory() as tempdir:
        path = Path(tempdir) / "record.txt"
        path.write_text("Person data 120386-1234 email foo@bar.dk phone +45 12 34 56 78", encoding="utf-8")

        cs.config["scan_folders"] = [tempdir]
        result: ScanResult = engine.scan()

        assert result.files_scanned == 1
        reasons = {f.reason for f in result.findings}
        assert "CPR match" in reasons
        assert "Email match" in reasons
        assert "Phone match" in reasons


def test_config_store_ignore_list():
    cs = ConfigStore()
    # use temporary app dir to avoid modifying real path
    tempdir = tempfile.TemporaryDirectory()
    cs.APP_DIR = pathlib.Path(tempdir.name)
    cs.CONFIG_FILE = cs.APP_DIR / "config.json"
    cs._ensure_dir()
    cs.config = cs.load()

    testfile = str(pathlib.Path(tempdir.name) / "ignore.txt")
    testfile_norm = os.path.normcase(os.path.abspath(testfile))
    cs.add_ignore_path(testfile)
    assert testfile_norm in cs.get_config()["ignore_paths"]
    cs.remove_ignore_path(testfile)
    assert testfile_norm not in cs.get_config()["ignore_paths"]
    tempdir.cleanup()
