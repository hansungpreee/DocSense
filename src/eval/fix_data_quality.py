import os
import glob

html_dir = "data/html"
json_files = glob.glob(os.path.join(html_dir, "*.json"))
if not json_files:
    json_files = glob.glob("*.json")

for file_path in json_files:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    original = content
    
    # 1. 가맹점주 이름 '이철수' -> '이대호'로 통일
    content = content.replace("이철수", "이대호")
    
    # 2. 실존 인물 '정용진' -> '정태민'으로 교체
    content = content.replace("정용진", "정태민")
    
    # 3. 표준임대차계약서에서 '2024. 5. 8 개정' 문구 제거
    if "02_standard_lease.json" in file_path:
        content = content.replace("(2024. 5. 8 개정)", "").replace("2024. 5. 8 개정", "").replace("2024.5.8 개정", "")
        
    if content != original:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"🛠️ 품질 보완 완료: {os.path.basename(file_path)}")

print("✅ PRD 6절 데이터 품질 보완 사항 일괄 수정이 완료되었습니다!")