"""로컬 SQLite 전체 백업. 삭제·정리 전에 사용자가 직접 만들 수 있게 한다.

원본(storage/evidence)과 다운로드 파일(storage/exports)은 DB에 들어있지 않다 — 원본까지 보존하려면
앱 종료 후 두 폴더를 함께 복사해야 한다 (README '저장·다운로드 이력' 참고).
"""
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from config import settings
from core import storage


def folder():
    return Path(os.getenv("ADETECT_BACKUP_DIR", str(Path(settings.DB_PATH).parent / "backups"))).resolve()


def backup_db():
    """온라인 백업 API로 일관된 사본을 만든다 (앱 실행 중에도 안전). 기존 백업은 덮어쓰지 않는다."""
    if storage.remote():
        raise ValueError("원격 DB는 이 화면에서 백업하지 않습니다. 호스팅 서비스의 백업 기능을 사용해주세요.")
    source = Path(settings.DB_PATH)
    if not source.is_file():
        raise ValueError("백업할 DB 파일이 없습니다.")
    target_dir = folder()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"adetect_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.db"
    src, dst = sqlite3.connect(str(source)), sqlite3.connect(str(target))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return target


def backups():
    target_dir = folder()
    return sorted(target_dir.glob("adetect_*.db"), reverse=True) if target_dir.exists() else []
