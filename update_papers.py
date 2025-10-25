import os
import yaml
import google.generativeai as genai
import arxiv # Semantic Scholar 대신 arxiv 라이브러리 사용
from datetime import datetime

# --- 설정 ---
TODAY_FILE = '_data/today_paper.yml'
ARCHIVE_FILE = '_data/archive_papers.yml'
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
SEARCH_KEYWORDS = "all:\"cathode material\"" # arXiv 검색용 쿼리 (정확한 구문 검색)

# --- 1. YAML 파일 로드/저장 헬퍼 함수 (동일) ---

def load_yaml(filename):
    if not os.path.exists(filename):
        return None
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return None

def save_yaml(data, filename):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    except Exception as e:
        print(f"Error saving {filename}: {e}")

# --- 2. '오늘의 논문'을 '이전 논문'으로 아카이빙 ---
# (doi 대신 paper_id를 기준으로 중복 체크하도록 수정)

def archive_today_paper():
    print("Archiving 'today_paper'...")
    today_paper = load_yaml(TODAY_FILE)
    
    if not today_paper or not today_paper.get('title'):
        print("'today_paper.yml' is empty or invalid. Skipping archive.")
        return

    archive_papers = load_yaml(ARCHIVE_FILE)
    if archive_papers is None:
        archive_papers = []

    # 'paper_id' (arXiv 고유 ID)를 기준으로 중복 체크
    existing_ids = {paper.get('paper_id') for paper in archive_papers if paper.get('paper_id')}
    
    if today_paper.get('paper_id') and today_paper.get('paper_id') not in existing_ids:
        archive_papers.insert(0, today_paper)
        save_yaml(archive_papers, ARCHIVE_FILE)
        print(f"Archived paper: {today_paper.get('title')}")
    else:
        print(f"Paper already in archive or has no ID: {today_paper.get('title')}")

# --- 3. 새 논문 검색 (arXiv API 사용) ---

def find_new_paper():
    print("Finding new paper from arXiv.org...")
    archive_papers = load_yaml(ARCHIVE_FILE) or []
    # 'paper_id' (arXiv 고유 ID)를 기준으로 중복 체크
    existing_ids = {paper.get('paper_id') for paper in archive_papers if paper.get('paper_id')}

    try:
        # arXiv API 클라이언트 생성 (API 키 필요 없음)
        client = arxiv.Client()
        
        # 최신순으로 'cathode material'이 포함된 논문 검색
        search = arxiv.Search(
            query = SEARCH_KEYWORDS,
            max_results = 20, # 20개 정도 가져와서 중복되지 않는 것을 찾음
            sort_by = arxiv.SortCriterion.SubmittedDate, # 제출일 기준
            sort_order = arxiv.SortOrder.Descending
        )
        
        results = list(client.results(search))

        for paper in results:
            # paper.get_short_id()는 '2410.12345' 같은 고유 ID를 반환
            paper_id = paper.get_short_id() 
            
            if paper_id not in existing_ids:
                print(f"Found new paper: {paper.title}")
                return paper # 찾았다!
        
        print("No new papers found.")
        return None

    except Exception as e:
        print(f"Error fetching new paper from arXiv: {e}")
        return None

# --- 4. 논문 요약 (Gemini API) (동일) ---

def summarize_with_gemini(abstract):
    if not abstract:
        return "요약할 초록 내용이 없습니다."
    print("Summarizing with Gemini...")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        당신은 2차전지 및 재료공학 분야의 전문가입니다.
        다음 양극재(cathode material) 관련 논문의 내용을 받아서,
        이 논문의 핵심 내용(연구 배경, 방법, 주요 결과)을
        한국어로 최대한 자세하게 요약해 주세요.

        [초록 내용]
        {abstract}
        
        [요약]
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error summarizing with Gemini: {e}")
        return f"Gemini 요약에 실패했습니다: {e}"

# --- 5. 메인 실행 로직 ---

def main():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY is not set in GitHub Secrets.")
        return

    # 1. '오늘의 논문' -> '이전 논문'으로 이동
    archive_today_paper()
    
    # 2. 새 논문 검색
    new_paper = find_new_paper()
    
    if not new_paper:
        print("No new paper to update.")
        return

    # 3. 새 논문 초록 요약
    summary = summarize_with_gemini(new_paper.summary) # .abstract 대신 .summary
    
    # 4. '오늘의 논문' 데이터 생성 (arXiv 형식에 맞게)
    today_paper_data = {
        'title': new_paper.title.strip(),
        'authors': ", ".join([author.name for author in new_paper.authors]),
        'date': new_paper.published.strftime('%Y-%m-%d'), # 발행일
        'paper_id': new_paper.get_short_id(), # arXiv 고유 ID
        'link': new_paper.entry_id, # 'http://arxiv.org/abs/...' 링크
        'summary': summary
    }
    
    # 5. 'today_paper.yml' 파일 덮어쓰기
    save_yaml(today_paper_data, TODAY_FILE)
    print(f"Successfully updated 'today_paper.yml' with: {today_paper_data['title']}")

if __name__ == "__main__":
    main()
