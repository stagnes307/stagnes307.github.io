"""
arXiv 논문 검색 및 필터링 (계층적 검색 로직 포함)
"""
import arxiv
import logging
from utils.yaml_helper import load_yaml
from utils.quality_filter import (
    should_exclude_paper,
    check_include_keywords,
    calculate_paper_quality_score
)
from utils.cache import load_cache, save_cache

logger = logging.getLogger(__name__)

def _search_and_filter_papers(client, existing_ids, num_target, filter_config, settings, sort_by_date=False):
    """Helper function to perform a single search and filtering pass."""
    query = settings.get('query')
    max_fetch = settings.get('max_results_to_fetch', 150)
    
    sort_criterion = arxiv.SortCriterion.SubmittedDate if sort_by_date else arxiv.SortCriterion.Relevance
    
    search = arxiv.Search(
        query=query,
        max_results=max_fetch,
        sort_by=sort_criterion,
        sort_order=arxiv.SortOrder.Descending
    )
    
    logger.info(f"Searching arXiv with query: '{query}' (Sort: {sort_criterion.value}, Max: {max_fetch})")
    
    results = list(client.results(search))
    if not results:
        logger.warning("  -> No papers found for this query.")
        return []

    total_searched = len(results)
    logger.info(f"  -> Found {total_searched} papers. Starting filtering...")

    # 필터링 로직
    new_papers_list = []
    filter_enabled = filter_config and filter_config.get('enabled', False)
    min_score = filter_config.get('min_score', 0) if filter_enabled else 0
    
    exclude_keywords = settings.get('exclude_keywords', [])
    include_keywords_any = settings.get('include_keywords_any', [])
    
    hindex_cache = load_cache()
    from utils.cache import get_cached_hindex, set_cached_hindex
    
    class CacheManager:
        def get_cached_hindex(self, name, cache): return get_cached_hindex(name, cache)
        def set_cached_hindex(self, name, value, cache): return set_cached_hindex(name, value, cache)
    
    cache_manager = CacheManager()

    for paper in results:
        if paper.get_short_id() in existing_ids:
            continue
        
        if exclude_keywords and should_exclude_paper(paper, exclude_keywords):
            continue
        if include_keywords_any and not check_include_keywords(paper, include_keywords_any):
            continue
            
        if filter_enabled:
            score, _ = calculate_paper_quality_score(paper, filter_config, hindex_cache, cache_manager)
            if score >= min_score:
                new_papers_list.append(paper)
        else:
            new_papers_list.append(paper)
        
        if len(new_papers_list) >= num_target:
            break
            
    save_cache(hindex_cache)
    logger.info(f"  -> Found {len(new_papers_list)} qualified papers from this tier.")
    return new_papers_list


def find_new_papers(archive_path, num_target, filter_config=None, settings=None):
    """
    새로운 논문을 계층적 검색 방식으로 찾습니다.
    """
    archive_papers = load_yaml(archive_path) or []
    existing_ids = {paper.get('paper_id') for paper in archive_papers if paper.get('paper_id')}
    
    client = arxiv.Client()
    search_queries = settings.get('search_queries', [])
    
    final_papers = []

    # 1. 계층적 검색 (관련도순)
    for i, query in enumerate(search_queries):
        logger.info(f"--- Tier {i+1}/{len(search_queries)} Search ---")
        tier_settings = settings.copy()
        tier_settings['query'] = query
        
        found_papers = _search_and_filter_papers(
            client=client,
            existing_ids=existing_ids,
            num_target=num_target,
            filter_config=filter_config,
            settings=tier_settings,
            sort_by_date=False
        )
        
        if len(found_papers) >= num_target:
            logger.info(f"Sufficient papers found at Tier {i+1}. Finalizing selection.")
            final_papers = found_papers
            break
        else:
            logger.warning(f"Not enough papers at Tier {i+1}. Trying next tier...")

    # 2. 최종 단계: 최신순 강제 검색
    if not final_papers:
        logger.info("--- Final Fallback Search (Sort by Date) ---")
        latest_sort_query_index = settings.get('latest_sort_query_index', -1)
        
        if 0 <= latest_sort_query_index < len(search_queries):
            fallback_query = search_queries[latest_sort_query_index]
            fallback_settings = settings.copy()
            fallback_settings['query'] = fallback_query
            
            final_papers = _search_and_filter_papers(
                client=client,
                existing_ids=existing_ids,
                num_target=num_target,
                filter_config=filter_config,
                settings=fallback_settings,
                sort_by_date=True
            )
        else:
            logger.error("`latest_sort_query_index` is invalid. Skipping fallback search.")

    if not final_papers:
        logger.warning("No new papers found after all search tiers and fallbacks.")
        return []

    logger.info(f"Final selection: {len(final_papers)} papers.")
    return final_papers[:num_target]