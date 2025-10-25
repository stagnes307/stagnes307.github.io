import os
import yaml
import google.generativeai as genai
import arxiv # arXiv 라이브러리 사용
from datetime import datetime

# --- 설정 ---
TODAY_FILE = '_data/today_paper.yml' # 이제 이 파일은 3개의 논문 '리스트'를 담게 됩니다.
ARCHIVE_FILE = '_data/archive_papers.yml'
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# [수정됨] 키워드: 초록(abstract)에 셋 중 하나가 포함된 논문
SEARCH_KEYWORDS = 'abs:("cathode material" OR "NCM" OR "NCA")'

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
# [수정됨] 1개가 아닌 3개(리스트)를 아카이빙하도록 변경

def archive_today_paper():
    print("Archiving 'today_papers'...")
    today_papers = load_yaml(TODAY_FILE) # 이제 'list'를 불러옵니다.
    
    # 리스트가 아니거나 비어있으면 스킵
    if not today_papers or not isinstance(today_papers, list):
        print("'today_paper.yml' is empty or not a list. Skipping archive.")
        return

    archive_papers = load_yaml(ARCHIVE_FILE)
    if archive_papers is None:
        archive_papers = []

    # 'paper_id' (arXiv 고유 ID)를 기준으로 중복 체크
    existing_ids = {paper.get('paper_id') for paper in archive_papers if paper.get('paper_id')}
    
    archived_count = 0
    # 3개의 논문을 하나씩 아카이브에 추가
    for paper in today_papers:
        if paper.get('paper_id') and paper.get('paper_id') not in existing_ids:
            archive_papers.insert(0, paper) # 리스트 맨 앞에 추가
            archived_count += 1
        else:
            print(f"Paper already in archive or has no ID: {paper.get('title')}")
            
    if archived_count > 0:
        save_yaml(archive_papers, ARCHIVE_FILE)
        print(f"Archived {archived_count} new papers.")

# --- 3. 새 논문 검색 (arXiv API 사용) ---
# [수정됨] 1개가 아닌 3개를 찾아 '리스트'로 반환

def find_new_papers(): # 'papers' (복수형)로 함수 이름 변경
    print("Finding 3 new papers from arXiv.org...")
    archive_papers = load_yaml(ARCHIVE_FILE) or []
    existing_ids = {paper.get('paper_id') for paper in archive_papers if paper.get('paper_id')}

    new_papers_list = [] # 3개를 담을 빈 리스트

    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query = SEARCH_KEYWORDS,
            max_results = 30, # 30개 정도 넉넉히 가져와서 중복되지 않는 3개를 찾음
            sort_by = arxiv.SortCriterion.SubmittedDate,
            sort_order = arxiv.SortOrder.Descending
        )
        results = list(client.results(search))

        for paper in results:
            paper_id = paper.get_short_id() 
            
            if paper_id not in existing_ids:
                print(f"Found new paper: {paper.title}")
                new_papers_list.append(paper)
                if len(new_papers_list) == 3: # 3개를 모두 찾았으면 중단
                    break
        
        if len(new_papers_list) == 0:
            print("No new papers found.")
            return []
            
        print(f"Found {len(new_papers_list)} new papers total.")
        return new_papers_list # 3개가 담긴 리스트 반환

    except Exception as e:
        print(f"Error fetching new paper from arXiv: {e}")
        return []

# --- 4. 논문 요약 (Gemini API) (동일) ---

def summarize_with_gemini(abstract):
    if not abstract:
        return "요약할 초록 내용이 없습니다."
    print("Summarizing with Gemini...")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"""
        당신은 2차전지 및 재료공학 분야의 전문가입니다.
        다음 양극재(cathode material) 관련 논문의 초록(abstract)을 받아서,
        이 논문의 핵심 내용(연구 배경, 방법, 주요 결과)을
        한국어로 요약해 주세요.

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
# [수정됨] 3개의 논문을 처리하도록 변경

def main():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY is not set in GitHub Secrets.")
        return

    # 1. '오늘의 논문' -> '이전 논문'으로 이동
    archive_today_paper()
    
    # 2. 새 논문 3개 검색
    new_papers = find_new_papers() # 3개가 담긴 리스트
    
    if not new_papers:
        print("No new papers to update.")
        return

    today_papers_data_list = [] # 3개의 데이터를 담을 빈 리스트
    
    # 3. 3개의 논문을 하나씩 요약하고 리스트에 추가
    for new_paper in new_papers:
        summary = summarize_with_gemini(new_paper.summary) # .abstract 대신 .summary
        
        paper_data = {
            'title': new_paper.title.strip(),
            'authors': ", ".join([author.name for author in new_paper.authors]),
            'date': new_paper.published.strftime('%Y-%m-%d'),
            'paper_id': new_paper.get_short_id(),
            'link': new_paper.entry_id,
            'summary': summary
        }
        today_papers_data_list.append(paper_data)
        print(f"Processed: {paper_data['title']}")

    # 4. 'today_paper.yml' 파일에 3개 논문 리스트 덮어쓰기
    save_yaml(today_papers_data_list, TODAY_FILE)
    print(f"Successfully updated 'today_paper.yml' with {len(today_papers_data_list)} papers.")

if __name__ == "__main__":
    main()
