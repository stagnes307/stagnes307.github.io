import os
import yaml
try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except Exception:
    genai = None
    _GENAI_AVAILABLE = False
import arxiv
from datetime import datetime
import requests
import time

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

# --- 2. 논문 품질 필터링 함수 [신규] ---

def get_author_hindex_from_semantic_scholar(author_name):
    """
    Semantic Scholar API를 사용하여 저자의 h-index를 조회
    """
    try:
        # 저자 검색
        search_url = "https://api.semanticscholar.org/graph/v1/author/search"
        params = {"query": author_name, "limit": 1}
        
        response = requests.get(search_url, params=params, timeout=5)
        time.sleep(0.1)  # API rate limit 고려
        
        if response.status_code != 200:
            return None
            
        data = response.json()
        if not data.get('data') or len(data['data']) == 0:
            return None
        
        author_id = data['data'][0].get('authorId')
        if not author_id:
            return None
        
        # 저자 상세 정보 조회
        author_url = f"https://api.semanticscholar.org/graph/v1/author/{author_id}"
        params = {"fields": "hIndex,name"}
        
        response = requests.get(author_url, params=params, timeout=5)
        time.sleep(0.1)
        
        if response.status_code != 200:
            return None
            
        author_data = response.json()
        return author_data.get('hIndex', 0)
        
    except Exception as e:
        print(f"Error fetching h-index for {author_name}: {e}")
        return None

def check_author_in_list(author_name, author_list):
    """
    저자 이름이 리스트에 있는지 확인 (부분 매칭 지원)
    """
    author_name_lower = author_name.lower()
    for renowned_author in author_list:
        # 성(last name)이 일치하는지 확인
        if renowned_author.split()[-1].lower() in author_name_lower:
            return True
    return False

def check_institution_in_list(affiliation, institution_list):
    """
    소속 기관이 리스트에 있는지 확인 (부분 매칭 지원)
    """
    if not affiliation:
        return False
    affiliation_lower = affiliation.lower()
    for institution in institution_list:
        if institution.lower() in affiliation_lower:
            return True
    return False

def check_journal_published(paper, journal_list):
    """
    논문이 저명한 저널에 출판되었는지 확인
    arXiv API의 journal_ref 필드 사용
    """
    journal_ref = getattr(paper, 'journal_ref', None)
    if not journal_ref:
        return False
    
    journal_ref_lower = journal_ref.lower()
    for journal in journal_list:
        if journal.lower() in journal_ref_lower:
            return True
    return False

def should_exclude_paper(paper, exclude_keywords):
    """
    논문을 제외해야 하는지 확인
    - 제외 키워드가 있으면 제외
    """
    title = paper.title.lower()
    abstract = paper.summary.lower()
    full_text = title + " " + abstract
    
    # 제외 키워드 확인
    for keyword in exclude_keywords:
        if keyword.lower() in full_text:
            print(f"  [제외] '{keyword}' 키워드 발견")
            return True  # 제외
    
    return False  # 제외하지 않음

def calculate_paper_quality_score(paper, filter_config):
    """
    논문의 품질 점수를 계산 (0-10점 척도)
    
    옵션 1: 저명한 기관 (2점)
    옵션 1: 저명한 연구자 (3점)
    옵션 2: 저자 h-index (3점)
    옵션 3: 저널 출판 (3점)
    """
    score = 0
    details = []
    
    # 옵션 3: 저널 출판 체크 (가장 먼저 - 빠름)
    prestigious_journals = filter_config.get('prestigious_journals', [])
    if check_journal_published(paper, prestigious_journals):
        journal_score = filter_config.get('journal_published_score', 3)
        score += journal_score
        details.append(f"저널 출판 (+{journal_score}점)")
        print(f"  [O] 저널 출판: {paper.journal_ref}")
    
    # 옵션 1: 저명한 기관 및 연구자 체크
    prestigious_institutions = filter_config.get('prestigious_institutions', [])
    renowned_authors = filter_config.get('renowned_authors', [])
    
    renowned_author_found = False
    prestigious_institution_found = False
    
    for author in paper.authors[:3]:  # 처음 3명의 저자만 체크 (주저자 중심)
        author_name = author.name
        
        # 저명한 연구자 체크
        if not renowned_author_found and check_author_in_list(author_name, renowned_authors):
            score += 3
            details.append(f"저명한 연구자: {author_name} (+3점)")
            print(f"  [O] 저명한 연구자: {author_name}")
            renowned_author_found = True
        
        # 저명한 기관 체크 (arXiv에서는 소속 정보가 제한적)
        # 논문의 comment나 다른 메타데이터에서 찾을 수 있으면 체크
    
    # comment 필드에서 기관 정보 확인 (일부 논문에 포함)
    if not prestigious_institution_found:
        comment = getattr(paper, 'comment', '')
        if comment and check_institution_in_list(comment, prestigious_institutions):
            score += 2
            details.append("저명한 기관 (+2점)")
            print(f"  [O] 저명한 기관 발견")
            prestigious_institution_found = True
    
    # 옵션 2: h-index 체크 (API 호출이 필요하므로 마지막에)
    min_hindex = filter_config.get('min_author_hindex', 0)
    if min_hindex > 0 and not renowned_author_found:  # 이미 저명 연구자로 인정받지 않은 경우만
        # 첫 번째 저자의 h-index만 체크 (API 호출 최소화)
        if len(paper.authors) > 0:
            first_author = paper.authors[0].name
            hindex = get_author_hindex_from_semantic_scholar(first_author)
            
            if hindex and hindex >= min_hindex:
                hindex_score = filter_config.get('hindex_score', 3)
                score += hindex_score
                details.append(f"저자 h-index: {hindex} (+{hindex_score}점)")
                print(f"  [O] 저자 h-index: {hindex} (기준: {min_hindex})")
    
    return score, details

# --- 3. 아카이빙 함수 [수정됨] ---
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

# --- 4. 새 논문 검색 함수 [수정됨 + 배치 검색] ---
# [수정] 10개씩 나눠서 검색하고, 목표 개수 달성까지 반복
def find_new_papers(archive_path, query, max_fetch, num_target, filter_config=None, settings=None):
    print(f"Finding {num_target} new papers from arXiv.org...")
    
    # [수정] archive_path 사용
    archive_papers = load_yaml(archive_path) or []
    existing_ids = {paper.get('paper_id') for paper in archive_papers if paper.get('paper_id')}

    new_papers_list = []
    filter_enabled = filter_config and filter_config.get('enabled', False)
    min_score = filter_config.get('min_score', 0) if filter_enabled else 0
    
    # 제외/포함 키워드 설정
    exclude_keywords = settings.get('exclude_keywords', []) if settings else []
    include_keywords_any = settings.get('include_keywords_any', []) if settings else []
    
    # 검색 설정
    total_searched = 0

    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query = query,
            max_results = max_fetch,
            sort_by = arxiv.SortCriterion.Relevance,
            sort_order = arxiv.SortOrder.Descending
        )
        
        print(f"\n논문 검색 중 (최대 {max_fetch}개)...")
        
        # 한 번에 모든 결과 가져오기 (페이징 에러 처리)
        results = []
        try:
            for paper in client.results(search):
                results.append(paper)
                
                # 10개 단위로 진행상황 출력
                if len(results) % 10 == 0:
                    print(f"  검색 진행: {len(results)}개...")
                
                if len(results) >= max_fetch:
                    break
        except Exception as page_error:
            if results:
                print(f"Warning: Pagination error, but got {len(results)} papers")
            else:
                print(f"Error: Could not fetch papers")
                return []
        
        if not results:
            print("No papers found")
            return []
        
        total_searched = len(results)
        print(f"\n총 {total_searched}개 논문 검색 완료. 필터링 시작...")
        
        # 논문 필터링 (목표 개수 찾을 때까지)
        for i, paper in enumerate(results, 1):
            paper_id = paper.get_short_id() 
            
            if paper_id not in existing_ids:
                # 제외 키워드 체크 (소듐, 폴리머 등)
                if exclude_keywords and should_exclude_paper(paper, exclude_keywords):
                    continue  # 이 논문은 건너뜀

                # 포함 키워드(ANY) 체크: 지정된 키워드가 하나도 없으면 제외
                if include_keywords_any:
                    title_lower = (paper.title or "").lower()
                    abstract_lower = (paper.summary or "").lower()
                    full_text = title_lower + " " + abstract_lower
                    if not any(kw.lower() in full_text for kw in include_keywords_any):
                        # 지정된 포함 키워드와 무관 → 스킵
                        continue
                
                # 품질 필터링이 활성화된 경우
                if filter_enabled:
                    print(f"\n[{i}/{total_searched}] 검토: {paper.title[:70]}...")
                    score, details = calculate_paper_quality_score(paper, filter_config)
                    
                    if score >= min_score:
                        print(f"[O] 합격! 점수: {score}점 (총 {len(new_papers_list)+1}/{num_target}개)")
                        print(f"   세부사항: {', '.join(details)}")
                        new_papers_list.append(paper)
                    else:
                        print(f"[X] 불합격: {score}점")
                        if details:
                            print(f"   세부사항: {', '.join(details)}")
                else:
                    # 필터링 비활성화 - 모든 논문 수용
                    print(f"Found new paper: {paper.title}")
                    new_papers_list.append(paper)
                
                # 목표 개수 달성하면 중단
                if len(new_papers_list) >= num_target: 
                    print(f"\n[OK] 목표 달성! {num_target}개 논문 확보 (검색: {i}/{total_searched})")
                    break
        
        if len(new_papers_list) == 0:
            print(f"\nNo new papers found that meet the quality criteria (searched {total_searched} papers).")
            return []
            
        print(f"\n[OK] Found {len(new_papers_list)} qualified new papers (searched {total_searched} papers total).")
        return new_papers_list

    except Exception as e:
        print(f"Error fetching new paper from arXiv: {e}")
        return []

# --- 4. 논문 요약 함수 [수정됨] ---
# [수정] main 함수에서 모델 이름을 인자로 받도록 변경
def summarize_with_gemini(abstract, model_name):
    if not abstract:
        return "<p>요약할 초록 내용이 없습니다.</p>"
        
    if not _GENAI_AVAILABLE or not GEMINI_API_KEY:
        # Fallback: 간단 요약
        snippet = (abstract or "").strip().replace("\n", " ")[:400]
        return f"<ul>\n  <li><strong>요약(로컬):</strong> {snippet}...</li>\n</ul>"

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
    # Gemini API 키가 없어도 로컬 요약으로 진행 가능하도록 처리
    use_gemini = bool(GEMINI_API_KEY)
    if not use_gemini:
        print("[WARN] GEMINI_API_KEY not set. Using local fallback summarizer.")

    def summarize(abstract, model_name):
        if use_gemini:
            return summarize_with_gemini(abstract, model_name)
        if not abstract:
            return "<p>요약할 초록 내용이 없습니다.</p>"
        snippet = (abstract or "").strip().replace("\n", " ")[:400]
        return f"<ul>\n  <li><strong>요약(로컬):</strong> {snippet}...</li>\n</ul>"

    # --- [수정] 설정 파일 로드 ---
    config = load_yaml(CONFIG_FILE)
    if not config:
        print(f"Error: {CONFIG_FILE} not found or empty.")
        return

    # 설정값 변수로 사용
    settings = config.get('arxiv_settings', {})
    settings_anode = config.get('arxiv_settings_anode', {})
    paths = config.get('file_paths', {})
    filter_config = config.get('quality_filter', {})
    filter_config_anode = config.get('quality_filter_anode', filter_config)
    
    # [아이디어 2 적용] 강화된 검색 쿼리 사용
    SEARCH_KEYWORDS = settings.get('search_query', 'abs:cathode') # 기본값 설정
    MAX_RESULTS = settings.get('max_results_to_fetch', 30)
    NUM_PAPERS = settings.get('num_papers_to_summarize', 3)

    # anode 설정 (없으면 cathode와 동일 기본값 일부 상속)
    SEARCH_KEYWORDS_ANODE = settings_anode.get('search_query', 'abs:anode')
    MAX_RESULTS_ANODE = settings_anode.get('max_results_to_fetch', MAX_RESULTS)
    NUM_PAPERS_ANODE = settings_anode.get('num_papers_to_summarize', NUM_PAPERS)
    
    TODAY_FILE = paths.get('today')
    ARCHIVE_FILE = paths.get('archive')
    TODAY_FILE_CATHODE = paths.get('today_cathode', TODAY_FILE)
    ARCHIVE_FILE_CATHODE = paths.get('archive_cathode', ARCHIVE_FILE)
    TODAY_FILE_ANODE = paths.get('today_anode')
    ARCHIVE_FILE_ANODE = paths.get('archive_anode')
    
    GEMINI_MODEL = config.get('gemini_model', 'gemini-2.5-pro') # 모델명 로드

    # 설정값 로드 확인
    if not TODAY_FILE or not ARCHIVE_FILE or not SEARCH_KEYWORDS:
        print("Error: Missing critical paths or search_query in config.yml")
        return
    
    # 품질 필터 설정 출력
    if filter_config.get('enabled', False):
        print("\n[품질 필터링 활성화]")
        print(f"   최소 점수: {filter_config.get('min_score', 5)}점")
        print(f"   저명 기관: {len(filter_config.get('prestigious_institutions', []))}개")
        print(f"   저명 연구자: {len(filter_config.get('renowned_authors', []))}명")
        print(f"   최소 h-index: {filter_config.get('min_author_hindex', 0)}")
        print(f"   저널 목록: {len(filter_config.get('prestigious_journals', []))}개\n")
    # --- 설정 로드 완료 ---

    # --- CATHODE ---
    print("\n=== [CATHODE] 업데이트 ===")
    archive_today_paper(TODAY_FILE_CATHODE, ARCHIVE_FILE_CATHODE)

    new_papers_cathode = find_new_papers(
        archive_path=ARCHIVE_FILE_CATHODE,
        query=SEARCH_KEYWORDS,
        max_fetch=MAX_RESULTS,
        num_target=NUM_PAPERS,
        filter_config=filter_config,
        settings=settings
    )

    today_cathode_list = []
    if not new_papers_cathode:
        print("No new cathode papers to update. Clearing today's cathode list.")
    else:
        for new_paper in new_papers_cathode:
            summary = summarize(new_paper.summary, GEMINI_MODEL)
            paper_data = {
                'title': new_paper.title.strip(),
                'authors': ", ".join([author.name for author in new_paper.authors]),
                'date': new_paper.published.strftime('%Y-%m-%d'),
                'paper_id': new_paper.get_short_id(),
                'link': new_paper.entry_id,
                'summary': summary,
                'summary_date': datetime.now().strftime('%Y-%m-%d %H:%M KST')
            }
            today_cathode_list.append(paper_data)
            print(f"Processed (cathode): {paper_data['title']}")

    save_yaml(today_cathode_list, TODAY_FILE_CATHODE)
    print(f"Successfully updated '{TODAY_FILE_CATHODE}' with {len(today_cathode_list)} papers.")

    # --- ANODE ---
    if TODAY_FILE_ANODE and ARCHIVE_FILE_ANODE:
        print("\n=== [ANODE] 업데이트 ===")
        # anode는 동일한 품질 필터 사용, settings_anode로 제외 키워드 등 전달
        archive_today_paper(TODAY_FILE_ANODE, ARCHIVE_FILE_ANODE)

        new_papers_anode = find_new_papers(
            archive_path=ARCHIVE_FILE_ANODE,
            query=SEARCH_KEYWORDS_ANODE,
            max_fetch=MAX_RESULTS_ANODE,
            num_target=NUM_PAPERS_ANODE,
            filter_config=filter_config_anode,
            settings=settings_anode if settings_anode else settings
        )

        today_anode_list = []
        if not new_papers_anode:
            print("No new anode papers to update. Clearing today's anode list.")
        else:
            for new_paper in new_papers_anode:
                summary = summarize(new_paper.summary, GEMINI_MODEL)
                paper_data = {
                    'title': new_paper.title.strip(),
                    'authors': ", ".join([author.name for author in new_paper.authors]),
                    'date': new_paper.published.strftime('%Y-%m-%d'),
                    'paper_id': new_paper.get_short_id(),
                    'link': new_paper.entry_id,
                    'summary': summary,
                    'summary_date': datetime.now().strftime('%Y-%m-%d %H:%M KST')
                }
                today_anode_list.append(paper_data)
                print(f"Processed (anode): {paper_data['title']}")

        save_yaml(today_anode_list, TODAY_FILE_ANODE)
        print(f"Successfully updated '{TODAY_FILE_ANODE}' with {len(today_anode_list)} papers.")
    else:
        print("[ANODE] Skipped (paths not configured)")
    
if __name__ == "__main__":
    main()