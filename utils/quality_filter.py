"""
논문 품질 필터링 유틸리티
"""
import requests
import time
import logging
from utils.yaml_helper import load_yaml

logger = logging.getLogger(__name__)


def get_author_hindex_from_semantic_scholar(author_name, cache=None, cache_manager=None):
    """
    Semantic Scholar API를 사용하여 저자의 h-index를 조회
    
    Args:
        author_name: 저자 이름
        cache: 캐시 딕셔너리 (선택사항)
        
    Returns:
        h-index (int) 또는 None
    """
    # 캐시 확인
    if cache_manager:
        cached_value = cache_manager.get_cached_hindex(author_name, cache)
        if cached_value is not None:
            return cached_value
    elif cache and author_name in cache:
        return cache[author_name]
    
    try:
        # 저자 검색
        search_url = "https://api.semanticscholar.org/graph/v1/author/search"
        params = {"query": author_name, "limit": 1}
        
        response = requests.get(search_url, params=params, timeout=10)
        time.sleep(0.1)  # API rate limit 고려
        
        if response.status_code != 200:
            logger.warning(f"Semantic Scholar API error for {author_name}: {response.status_code}")
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
        
        response = requests.get(author_url, params=params, timeout=10)
        time.sleep(0.1)
        
        if response.status_code != 200:
            return None
            
        author_data = response.json()
        hindex = author_data.get('hIndex', 0)
        
        # 캐시 저장
        if cache_manager:
            cache_manager.set_cached_hindex(author_name, hindex, cache)
        elif cache is not None:
            cache[author_name] = hindex
            
        return hindex
        
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout while fetching h-index for {author_name}")
        return None
    except Exception as e:
        logger.warning(f"Error fetching h-index for {author_name}: {e}")
        return None


def check_author_in_list(author_name, author_list):
    """
    저자 이름이 리스트에 있는지 확인 (부분 매칭 지원)
    
    Args:
        author_name: 확인할 저자 이름
        author_list: 저명한 저자 리스트
        
    Returns:
        일치하면 True, 아니면 False
    """
    if not author_list:
        return False
        
    author_name_lower = author_name.lower()
    for renowned_author in author_list:
        # 성(last name)이 일치하는지 확인
        if renowned_author.split()[-1].lower() in author_name_lower:
            return True
    return False


def check_institution_in_list(affiliation, institution_list):
    """
    소속 기관이 리스트에 있는지 확인 (부분 매칭 지원)
    
    Args:
        affiliation: 소속 정보 문자열
        institution_list: 저명한 기관 리스트
        
    Returns:
        일치하면 True, 아니면 False
    """
    if not affiliation or not institution_list:
        return False
        
    affiliation_lower = affiliation.lower()
    for institution in institution_list:
        if institution.lower() in affiliation_lower:
            return True
    return False


def check_journal_published(paper, journal_list):
    """
    논문이 저명한 저널에 출판되었는지 확인
    
    Args:
        paper: arxiv Paper 객체
        journal_list: 저명한 저널 리스트
        
    Returns:
        출판되었으면 True, 아니면 False
    """
    if not journal_list:
        return False
        
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
    
    Args:
        paper: arxiv Paper 객체
        exclude_keywords: 제외 키워드 리스트
        
    Returns:
        제외해야 하면 True, 아니면 False
    """
    if not exclude_keywords:
        return False
        
    title = (paper.title or "").lower()
    abstract = (paper.summary or "").lower()
    full_text = title + " " + abstract
    
    for keyword in exclude_keywords:
        if keyword.lower() in full_text:
            logger.debug(f"Excluding paper due to keyword '{keyword}': {paper.title[:50]}...")
            return True
    
    return False


def check_include_keywords(paper, include_keywords_any):
    """
    포함 키워드가 하나라도 있는지 확인
    
    Args:
        paper: arxiv Paper 객체
        include_keywords_any: 포함되어야 하는 키워드 리스트 (하나라도 포함되면 통과)
        
    Returns:
        포함 키워드가 하나라도 있으면 True, 없으면 False
    """
    if not include_keywords_any:
        return True  # 필터가 없으면 모든 논문 통과
        
    title_lower = (paper.title or "").lower()
    abstract_lower = (paper.summary or "").lower()
    full_text = title_lower + " " + abstract_lower
    
    for kw in include_keywords_any:
        if kw.lower() in full_text:
            return True
    
    return False


def calculate_paper_quality_score(paper, filter_config, hindex_cache=None, cache_manager=None, institutions_path=None, authors_path=None):
    """
    논문의 품질 점수를 계산 (0-10점 척도)
    
    Args:
        paper: arxiv Paper 객체
        filter_config: 필터 설정 딕셔너리
        hindex_cache: h-index 캐시 딕셔너리 (선택사항)
        
    Returns:
        (score, details) 튜플
    """
    score = 0
    details = []
    
    prestigious_journals = filter_config.get('prestigious_journals', [])
    if prestigious_journals and check_journal_published(paper, prestigious_journals):
        journal_score = filter_config.get('journal_published_score', 3)
        score += journal_score
        details.append(f"저널 출판 (+{journal_score}점)")
        logger.debug(f"Journal published: {paper.journal_ref}")
    
    # filter_config에서 직접 가져오는 대신, 파일에서 로드
    prestigious_institutions = load_yaml(institutions_path) if institutions_path else []
    renowned_authors = load_yaml(authors_path) if authors_path else []
    
    renowned_author_found = False
    prestigious_institution_found = False
    
    # 처음 3명의 저자만 체크 (주저자 중심)
    for author in paper.authors[:3]:
        author_name = author.name
        
        # 저명한 연구자 체크
        if not renowned_author_found and check_author_in_list(author_name, renowned_authors):
            score += 3
            details.append(f"저명한 연구자: {author_name} (+3점)")
            logger.debug(f"Renowned author found: {author_name}")
            renowned_author_found = True
    
    # comment 필드에서 기관 정보 확인
    if not prestigious_institution_found:
        comment = getattr(paper, 'comment', '')
        if comment and check_institution_in_list(comment, prestigious_institutions):
            score += 2
            details.append("저명한 기관 (+2점)")
            logger.debug("Prestigious institution found")
            prestigious_institution_found = True
    
    # h-index 체크 (API 호출이 필요하므로 마지막에)
    min_hindex = filter_config.get('min_author_hindex', 0)
    if min_hindex > 0 and not renowned_author_found and len(paper.authors) > 0:
        first_author = paper.authors[0].name
        hindex = get_author_hindex_from_semantic_scholar(first_author, cache=hindex_cache, cache_manager=cache_manager)
        
        if hindex and hindex >= min_hindex:
            hindex_score = filter_config.get('hindex_score', 3)
            score += hindex_score
            details.append(f"저자 h-index: {hindex} (+{hindex_score}점)")
            logger.debug(f"Author h-index: {hindex} (min: {min_hindex})")
    
    return score, details

