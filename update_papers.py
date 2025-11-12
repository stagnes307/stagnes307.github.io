"""
논문 업데이트 메인 스크립트
arXiv에서 논문을 검색하고 Gemini로 요약하여 저장합니다.
"""
import os
import sys
import logging
from datetime import datetime, timezone, timedelta

# 한국 시간대 설정
KST = timezone(timedelta(hours=9))

# 로깅 설정 (KST 시간대 사용)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('update_papers.log', encoding='utf-8')
    ],
    datefmt='%Y-%m-%d %H:%M:%S KST'
)
logger = logging.getLogger(__name__)

# 로그 시간을 한국 시간으로 변환하는 함수
def get_kst_time():
    """한국 시간(KST)을 반환합니다."""
    return datetime.now(KST)

# 설정 파일 경로
CONFIG_FILE = 'config.yml'
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')

# 유틸리티 임포트
from utils.yaml_helper import load_yaml, save_yaml
from utils.config_validator import validate_config
from utils.paper_fetcher import find_new_papers
from utils.summarizer import summarize_with_gemini, extract_tags_from_title, translate_title
from utils.quality_filter import calculate_paper_quality_score


def archive_today_paper(today_path, archive_path):
    """
    오늘의 논문을 아카이브로 이동합니다.
    
    Args:
        today_path: today.yml 파일 경로
        archive_path: archive.yml 파일 경로
    """
    logger.info(f"Archiving papers from {today_path} to {archive_path}...")
    
    today_papers = load_yaml(today_path) 
    
    if not today_papers or not isinstance(today_papers, list):
        logger.info(f"'{today_path}' is empty or not a list. Skipping archive.")
        return

    archive_papers = load_yaml(archive_path)
    if archive_papers is None:
        archive_papers = []

    existing_ids = {paper.get('paper_id') for paper in archive_papers if paper.get('paper_id')}
    
    archived_count = 0
    for paper in today_papers:
        if paper.get('paper_id') and paper.get('paper_id') not in existing_ids:
            archive_papers.insert(0, paper)  # 최신 논문을 맨 앞에 추가
            archived_count += 1
        else:
            logger.debug(f"Paper already in archive or has no ID: {paper.get('title', 'Unknown')}")
            
    if archived_count > 0:
        save_yaml(archive_papers, archive_path)
        logger.info(f"Archived {archived_count} new papers.")
    else:
        logger.info("No new papers to archive.")


def process_papers(category_name, settings, filter_config, today_path, archive_path, model_name):
    """
    특정 카테고리(양극재/음극재)의 논문을 처리합니다.
    
    Args:
        category_name: 카테고리 이름 ('CATHODE' or 'ANODE')
        settings: 검색 설정
        filter_config: 필터 설정
        today_path: today.yml 파일 경로
        archive_path: archive.yml 파일 경로
        model_name: Gemini 모델 이름
        
    Returns:
        처리된 논문 개수
    """
    logger.info(f"\n=== [{category_name}] 업데이트 ===")
    
    # 아카이브
    archive_today_paper(today_path, archive_path)
    
    # 새 논문 검색
    query = settings.get('search_query', '')
    max_fetch = settings.get('max_results_to_fetch', 30)
    num_target = settings.get('num_papers_to_summarize', 3)
    
    yaml_helper = {
        'load_yaml': load_yaml,
        'save_yaml': save_yaml
    }
    
    new_papers = find_new_papers(
        archive_path=archive_path,
        query=query,
        max_fetch=max_fetch,
        num_target=num_target,
        filter_config=filter_config,
        settings=settings,
        yaml_helper=yaml_helper
    )

    today_list = []
    if not new_papers:
        logger.info(f"No new {category_name.lower()} papers to update. Clearing today's list.")
    else:
        for new_paper in new_papers:
            try:
                summary = summarize_with_gemini(new_paper.summary, model_name, OPENROUTER_API_KEY)
                title_kr = translate_title(new_paper.title.strip(), model_name, OPENROUTER_API_KEY)
                tags = extract_tags_from_title(new_paper.title, new_paper.summary)
                
                paper_data = {
                    'title': title_kr,  # 한국어 제목
                    'title_en': new_paper.title.strip(),  # 영어 제목 (원본)
                    'authors': ", ".join([author.name for author in new_paper.authors]),
                    'date': new_paper.published.strftime('%Y-%m-%d'),
                    'paper_id': new_paper.get_short_id(),
                    'link': new_paper.entry_id,
                    'summary': summary,
                    'summary_date': get_kst_time().strftime('%Y-%m-%d %H:%M KST')
                }
                
                # 태그 추가
                if tags:
                    paper_data['tags'] = tags
                
                today_list.append(paper_data)
                logger.info(f"Processed ({category_name.lower()}): {paper_data['title'][:60]}...")
            except Exception as e:
                logger.error(f"Error processing paper {new_paper.get_short_id()}: {e}", exc_info=True)
                continue

    save_yaml(today_list, today_path)
    logger.info(f"Successfully updated '{today_path}' with {len(today_list)} papers.")
    
    return len(today_list)


def main():
    """메인 실행 함수"""
    # OpenRouter API 키 확인
    use_openrouter = bool(OPENROUTER_API_KEY)
    if not use_openrouter:
        logger.warning("OPENROUTER_API_KEY not set. Using local fallback summarizer.")

    # 설정 파일 로드
    config = load_yaml(CONFIG_FILE)
    if not config:
        logger.error(f"Error: {CONFIG_FILE} not found or could not be loaded.")
        return 1

    # 설정 파일 검증
    is_valid, errors = validate_config(config)
    if not is_valid:
        logger.error("Config validation failed. Please fix the errors above.")
        return 1

    try:
        # 설정값 추출
        settings = config.get('arxiv_settings', {})
        settings_anode = config.get('arxiv_settings_anode', {})
        paths = config.get('file_paths', {})
        filter_config = config.get('quality_filter', {})
        filter_config_anode = config.get('quality_filter_anode', filter_config)
        
        # 파일 경로
        today_cathode = paths.get('today_cathode')
        archive_cathode = paths.get('archive_cathode')
        today_anode = paths.get('today_anode')
        archive_anode = paths.get('archive_anode')
        
        # Gemini 모델명
        gemini_model = config.get('gemini_model', 'gemini-2.5-pro')

        # 필수 경로 확인
        if not today_cathode or not archive_cathode:
            logger.error("Error: Missing critical paths in config.yml (today_cathode, archive_cathode)")
            return 1
        
        # 품질 필터 설정 출력
        if filter_config.get('enabled', False):
            logger.info("\n[품질 필터링 활성화]")
            logger.info(f"   최소 점수: {filter_config.get('min_score', 5)}점")
            logger.info(f"   저명 기관: {len(filter_config.get('prestigious_institutions', []))}개")
            logger.info(f"   저명 연구자: {len(filter_config.get('renowned_authors', []))}명")
            logger.info(f"   최소 h-index: {filter_config.get('min_author_hindex', 0)}")
            logger.info(f"   저널 목록: {len(filter_config.get('prestigious_journals', []))}개\n")

        # 양극재 처리
        count_cathode = process_papers(
            'CATHODE',
            settings,
            filter_config,
            today_cathode,
            archive_cathode,
            gemini_model
        )

        # 음극재 처리
        count_anode = 0
        if today_anode and archive_anode:
            count_anode = process_papers(
                'ANODE',
                settings_anode if settings_anode else settings,
                filter_config_anode,
                today_anode,
                archive_anode,
                gemini_model
            )
        else:
            logger.info("[ANODE] Skipped (paths not configured)")

        logger.info(f"\n=== 완료 ===")
        logger.info(f"양극재: {count_cathode}개, 음극재: {count_anode}개")
        
        return 0
        
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

