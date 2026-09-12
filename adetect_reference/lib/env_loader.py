"""09_tracking/.env 공통 로더 — python-dotenv 우회, 의존성 최소화."""
from __future__ import annotations

import os
from pathlib import Path

REPORT_ROOT = Path(__file__).resolve().parents[2]  # _shared/
ENV_PATH = REPORT_ROOT.parent / "09_tracking" / ".env"


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    # 시스템 env 우선 (CI/CD 의 GitHub Secrets 가 .env 를 덮어쓸 수 있게)
    for k in list(env.keys()) + [
        "META_APP_ID", "META_APP_SECRET", "META_ACCESS_TOKEN", "META_AD_ACCOUNT_ID",
        "SLACK_WEBHOOK_URL",
        "GOOGLE_SHEETS_ID", "GOOGLE_SERVICE_ACCOUNT_PATH", "GOOGLE_SERVICE_ACCOUNT_JSON",
        "GA4_PROPERTY_ID", "GA4_SERVICE_ACCOUNT_PATH", "GA4_SERVICE_ACCOUNT_JSON",
        "CLARITY_API_TOKEN", "CLARITY_PROJECT_ID",
    ]:
        v = os.environ.get(k)
        if v:
            env[k] = v
    return env


def require(env: dict[str, str], keys: list[str]) -> None:
    missing = [k for k in keys if not env.get(k)]
    if missing:
        raise RuntimeError(f"필수 env 누락: {missing} (확인: {ENV_PATH} 또는 GitHub Secrets)")
