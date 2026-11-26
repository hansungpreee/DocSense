"""모든 테스트가 개발자 .env의 TAXONOMY_PATH(데모용 복사본)와 상관없이 실제 config/taxonomy.yaml을 읽게 한다.
빈 값으로 정해 두면 load_dotenv()가 .env 값을 덮어쓰지 않는다.
엔진 로그도 저장소의 logs/ 대신 임시 폴더에 쓴다 (로그 파일은 프로세스당 한 번 열리므로 테스트 시작 전에 정한다)."""
import os
import tempfile

import pytest

os.environ["ENGINE_LOG_PATH"] = os.path.join(tempfile.mkdtemp(), "engine.log")


@pytest.fixture(autouse=True)
def _real_taxonomy(monkeypatch):
    monkeypatch.setenv("TAXONOMY_PATH", "")
