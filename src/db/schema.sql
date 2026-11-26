-- DocSense SQLite 스키마 초안 (app/services.py의 메모리 Store를 옮길 대상)
-- 연결마다 PRAGMA foreign_keys = ON; 을 실행해야 외래 키가 검사된다.
-- 시각은 Store와 같은 형식의 문자열: datetime.now().isoformat(timespec="seconds") (예: 2026-10-08T16:05:00)

-- 신규 분류: NEW 코드 1개 = 제안 1건. 같은 제안명이면 같은 NEW 코드가 발급되어 문서 여러 개가 묶인다.
-- 발급 시점(분류 결과 저장 시)에 행을 만들고, 담당자가 결정하면 결정 열을 채운다.
CREATE TABLE IF NOT EXISTS class_proposals (
    new_code       TEXT PRIMARY KEY,              -- NEW-01
    proposed_name  TEXT,                          -- 모델 제안명 (없으면 NULL)
    proposed_major TEXT,                          -- 모델이 제안한 대분류 (없으면 NULL)
    decision       TEXT CHECK (decision IN ('approved', 'edited', 'rejected')),  -- NULL = 승인 대기
    final_code     TEXT,                          -- 승인·수정: NEW 코드 그대로, 반려: 재지정한 기존 코드
    final_name     TEXT,
    final_major    TEXT,
    created_at     TEXT NOT NULL,                 -- NEW 코드 발급 시각
    decided_at     TEXT,
    CHECK ((decision IS NULL) = (decided_at IS NULL)),
    CHECK ((decision IS NULL) = (final_code IS NULL))
);

-- 분류 결과: 문서 1건 분류 1회 = 1행
CREATE TABLE IF NOT EXISTS classifications (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash      TEXT NOT NULL CHECK (length(file_hash) = 64),  -- 업로드 파일 sha256
    result_json    TEXT NOT NULL,                 -- 엔진 결과 JSON 통째 (모델이 낸 그대로, 결정 후에도 고치지 않음)
    prompt_version TEXT NOT NULL,
    model          TEXT NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('confirmed', 'pending_review', 'error')),
    new_code       TEXT REFERENCES class_proposals (new_code),  -- 「기타」로 빠진 문서만. 결정 후에도 남겨 결정과 연결
    created_at     TEXT NOT NULL,
    CHECK (status <> 'pending_review' OR new_code IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_classifications_cache ON classifications (file_hash, prompt_version, model);
CREATE INDEX IF NOT EXISTS idx_classifications_new_code ON classifications (new_code);
