"""
arXiv 논문 검색 및 필터링
"""
import arxiv
import logging

from utils.quality_filter import (
    should_exclude_paper,
    check_include_keywords,
    calculate_paper_quality_score
)
from utils.cache import load_cache, save_cache

logger = logging.getLogger(__name__)


def find_new_papers(archive_path, query, max_fetch, num_target, filter_config=None, settings=None, yaml_helper=None):
    """
    새로운 논문을 검색하고 필터링합니다.
    
    Args:
        archive_path: 아카이브 파일 경로
        query: arXiv 검색 쿼리
        max_fetch: 최대 검색 개수
        num_target: 목표 논문 개수
        filter_config: 품질 필터 설정
        settings: 검색 설정 (exclude_keywords, include_keywords_any 등)
        yaml_helper: YAML 헬퍼 함수들
        
    Returns:
        새 논문 리스트
    """
    logger.info(f"Finding {num_target} new papers from arXiv.org...")
    
    # 아카이브 로드
    if yaml_helper:
        load_yaml = yaml_helper.get('load_yaml')
    else:
        from utils.yaml_helper import load_yaml
    
    archive_papers = load_yaml(archive_path) or []
    existing_ids = {paper.get('paper_id') for paper in archive_papers if paper.get('paper_id')}

    new_papers_list = []
    filter_enabled = filter_config and filter_config.get('enabled', False)
    min_score = filter_config.get('min_score', 0) if filter_enabled else 0
    
    # 제외/포함 키워드 설정
    exclude_keywords = settings.get('exclude_keywords', []) if settings else []
    include_keywords_any = settings.get('include_keywords_any', []) if settings else []
    
    # h-index 캐시 (성능 최적화)
    hindex_cache = load_cache()
    from utils.cache import get_cached_hindex, set_cached_hindex
    
    # CacheManager 클래스 정의
    class CacheManager:
        def get_cached_hindex(self, name, cache):
            return get_cached_hindex(name, cache)
        
        def set_cached_hindex(self, name, value, cache):
            return set_cached_hindex(name, value, cache)
    
    cache_manager = CacheManager()
    
    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_fetch,
            sort_by=arxiv.SortCriterion.Relevance,
            sort_order=arxiv.SortOrder.Descending
        )
        
        logger.info(f"Searching for papers (max {max_fetch} results)...")
        
        # 한 번에 모든 결과 가져오기
        results = []
        try:
            for paper in client.results(search):
                results.append(paper)
                
                # 진행상황 출력
                if len(results) % 10 == 0:
                    logger.info(f"  Searched: {len(results)} papers...")
                
                if len(results) >= max_fetch:
                    break
        except Exception as page_error:
            if results:
                logger.warning(f"Pagination error, but got {len(results)} papers: {page_error}")
            else:
                logger.error(f"Could not fetch papers: {page_error}")
                return []
        
        if not results:
            logger.warning("No papers found")
            return []
        
        total_searched = len(results)
        logger.info(f"Total {total_searched} papers found. Starting filtering...")
        
        # 논문 필터링
        for i, paper in enumerate(results, 1):
            paper_id = paper.get_short_id() 
            
            if paper_id not in existing_ids:
                # 제외 키워드 체크
                if exclude_keywords and should_exclude_paper(paper, exclude_keywords):
                    continue

                # 포함 키워드(ANY) 체크
                if include_keywords_any and not check_include_keywords(paper, include_keywords_any):
                    continue
                
                # 품질 필터링
                if filter_enabled:
                    logger.debug(f"[{i}/{total_searched}] Reviewing: {paper.title[:70]}...")
                    score, details = calculate_paper_quality_score(paper, filter_config, hindex_cache, cache_manager)
                    
                    if score >= min_score:
                        logger.info(f"[✓] Accepted! Score: {score} ({len(new_papers_list)+1}/{num_target})")
                        logger.debug(f"  Details: {', '.join(details)}")
                        new_papers_list.append(paper)
                    else:
                        logger.debug(f"[✗] Rejected: Score {score} (min: {min_score})")
                else:
                    # 필터링 비활성화 - 모든 논문 수용
                    logger.info(f"Found new paper: {paper.title}")
                    new_papers_list.append(paper)
                
                # 목표 개수 달성하면 중단
                if len(new_papers_list) >= num_target: 
                    logger.info(f"Target reached! Found {num_target} papers (searched {i}/{total_searched})")
                    break
        
        if len(new_papers_list) == 0:
            logger.warning(f"No new papers found that meet criteria (searched {total_searched} papers)")
            return []
            
        # 캐시 저장
        save_cache(hindex_cache)
        
        logger.info(f"Found {len(new_papers_list)} qualified new papers (searched {total_searched} total)")
        return new_papers_list

    except Exception as e:
        logger.error(f"Error fetching papers from arXiv: {e}", exc_info=True)
        return []

