import os
import yaml
import google.generativeai as genai
import arxiv
from datetime import datetime

# --- 설정 ---
CONFIG_FILE = 'config.yml' # 설정 파일 경로
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# --- 1. YAML 헬퍼 함수 (동일) ---

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

# --- 2. 아카이빙 함수 [수정됨] ---
# [수정] main 함수에서 파일 경로를 인자로 받도록 변경
def archive_today_paper(today_path, archive_path):
    print("Archiving 'today_papers'...")
    # [수정] 하드코딩된 TODAY_FILE 대신 인자로 받은 today_path 사용
    today_papers = load_yaml(today_path) 
    
    if not today_papers or not isinstance(today_papers, list):
        print(f"'{today_path}' is empty or not a list. Skipping archive.")
        return

    # [수정] 하드코딩된 ARCHIVE_FILE 대신 인자로 받은 archive_path 사용
    archive_papers = load_yaml(archive_path)
    if archive_papers is None:
        archive_papers = []

    existing_ids = {paper.get('paper_id') for paper in archive_papers if paper.get('paper_id')}
    
    archived_count = 0
    for paper in today_papers:
        if paper.get('paper_id') and paper.get('paper_id') not in existing_ids:
            archive_papers.insert(0, paper)
            archived_count += 1
        else:
            print(f"Paper already in archive or has no ID: {paper.get('title')}")
            
    if archived_count > 0:
        # [수정] archive_path 사용
        save_yaml(archive_papers, archive_path)
        print(f"Archived {archived_count} new papers.")

# --- 3. 새 논문 검색 함수 [수정됨] ---
# [수정] main 함수에서 필요한 설정값들을 인자로 받도록 변경
def find_new_papers(archive_path, query, max_fetch, num_target):
    print(f"Finding {num_target} new papers from arXiv.org...")
    
    # [수정] archive_path 사용
    archive_papers = load_yaml(archive_path) or []
    existing_ids = {paper.get('paper_id') for paper in archive_papers if paper.get('paper_id')}

    new_papers_list = []

    try:
        client = arxiv.Client()
        search = arxiv.Search(
            # [수정] 인자로 받은 query, max_fetch 사용
            query = query,
            max_results = max_fetch, 
            sort_by = arxiv.SortCriterion.SubmittedDate,
            sort_order = arxiv.SortOrder.Descending
        )
        results = list(client.results(search))

        for paper in results:
            paper_id = paper.get_short_id() 
            
            if paper_id not in existing_ids:
                print(f"Found new paper: {paper.title}")
                new_papers_list.append(paper)
                # [수정] 인자로 받은 num_target 사용
                if len(new_papers_list) == num_target: 
                    break
        
        if len(new_papers_list) == 0:
            print("No new papers found.")
            return []
            
        print(f"Found {len(new_papers_list)} new papers total.")
        return new_papers_list

    except Exception as e:
        print(f"Error fetching new paper from arXiv: {e}")
        return []

# --- 4. 논문 요약 함수 [수정됨] ---
# [수정] main 함수에서 모델 이름을 인자로 받도록 변경
def summarize_with_gemini(abstract, model_name):
    if not abstract:
        return "<p>요약할 초록 내용이 없습니다.</p>"
        
    print(f"Summarizing with Gemini (Model: {model_name})...")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # [수정] 하드코딩된 모델명 대신 인자로 받은 model_name 사용
        model = genai.GenerativeModel(model_name) 
        
        # [아이디어 3 적용] 프롬프트 강화
        prompt = f"""
        당신은 2차전지 및 재료공학 분야의 전문가입니다.
        다음 논문의 초록(abstract)을 받아서,
        핵심 내용을 [연구 배경], [연구 방법], [주요 결과]로 구분하여
        **HTML 불릿 리스트(<ul>) 형식**으로 요약해 주세요.

        [지시 사항]
        1. 각 항목은 <li> 태그로 감싸고, <strong> 태그로 제목을 강조해 주세요.
        2. 마크다운(###, **)이나 LaTeX($...$) 문법을 **절대 사용하지 마세요.**
        3. 모든 LaTeX 문법, 특수 기호, 위첨자/아래첨자는 
           'LiCoO2', 'alpha-V2O5' 처럼 **일반 텍스트로만 풀어쓰세요.**
           (예: LiCoO$_2$ -> LiCoO2, $\\alpha$ -> alpha, $10^{{10}}$ -> 10^10)

        [초록 내용]
        {abstract}
        
        [HTML 요약]
        <ul>
          <li><strong>연구 배경:</strong> ...</li>
          <li><strong>연구 방법:</strong> ...</li>
          <li><strong>주요 결과:</strong> ...</li>
        </ul>
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        print(f"Error summarizing with Gemini: {e}")
        return f"<p>Gemini 요약에 실패했습니다: {e}</p>"
        
# --- 5. 메인 실행 로직 [수정됨] ---
def main():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY is not set in GitHub Secrets.")
        return

    # --- [수정] 설정 파일 로드 ---
    config = load_yaml(CONFIG_FILE)
    if not config:
        print(f"Error: {CONFIG_FILE} not found or empty.")
        return

    # 설정값 변수로 사용
    settings = config.get('arxiv_settings', {})
    paths = config.get('file_paths', {})
    
    # [아이디어 2 적용] 강화된 검색 쿼리 사용
    SEARCH_KEYWORDS = settings.get('search_query', 'abs:cathode') # 기본값 설정
    MAX_RESULTS = settings.get('max_results_to_fetch', 30)
    NUM_PAPERS = settings.get('num_papers_to_summarize', 3)
    
    TODAY_FILE = paths.get('today')
    ARCHIVE_FILE = paths.get('archive')
    
    GEMINI_MODEL = config.get('gemini_model', 'gemini-2.5-flash') # 모델명 로드

    # 설정값 로드 확인
    if not TODAY_FILE or not ARCHIVE_FILE or not SEARCH_KEYWORDS:
        print("Error: Missing critical paths or search_query in config.yml")
        return
    # --- 설정 로드 완료 ---

    # 1. '오늘의 논문' -> '이전 논문'으로 이동
    # [수정] 설정 변수를 인자로 전달
    archive_today_paper(TODAY_FILE, ARCHIVE_FILE)
    
    # 2. 새 논문 검색
    # [수정] 설정 변수를 인자로 전달
    new_papers = find_new_papers(
        archive_path=ARCHIVE_FILE,
        query=SEARCH_KEYWORDS,
        max_fetch=MAX_RESULTS,
        num_target=NUM_PAPERS
    )
    
    today_papers_data_list = []
    
    if not new_papers:
        print("No new papers to update. Clearing today's list.")
    else:
        # 3. 3개의 논문을 하나씩 요약하고 리스트에 추가
        for new_paper in new_papers:
            # [수정] 설정 변수(모델명)를 인자로 전달
            summary = summarize_with_gemini(new_paper.summary, GEMINI_MODEL)
            
            paper_data = {
                'title': new_paper.title.strip(),
                'authors': ", ".join([author.name for author in new_paper.authors]),
                'date': new_paper.published.strftime('%Y-%m-%d'),
                'paper_id': new_paper.get_short_id(),
                'link': new_paper.entry_id,
                'summary': summary,
                'summary_date': datetime.now().strftime('%Y-%m-%d %H:%M KST')
            }
            today_papers_data_list.append(paper_data)
            print(f"Processed: {paper_data['title']}")

    # 4. 'today_paper.yml' 파일 덮어쓰기
    # [수정] 설정 변수(파일 경로) 사용
    save_yaml(today_papers_data_list, TODAY_FILE)
    print(f"Successfully updated '{TODAY_FILE}' with {len(today_papers_data_list)} papers.")
    
if __name__ == "__main__":
    main()