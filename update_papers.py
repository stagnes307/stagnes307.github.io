"""
논문 업데이트 메인 스크립트
arXiv에서 논문을 검색하고 Gemini로 요약하여 저장합니다.
"""
import os
import sys
import logging
import re
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

# 설정 파일 경로
CONFIG_FILE = 'config.yml'
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')

# 유틸리티 임포트
from utils.yaml_helper import load_yaml, save_yaml
from utils.config_validator import validate_config
from utils.paper_fetcher import find_new_papers
from utils.summarizer import summarize_with_gemini, extract_tags_from_title, translate_title

def clean_latex_title(title):
    """Converts LaTeX-style sub/super-scripts in titles to HTML tags."""
    title = re.sub(r'\$_{\s*([^}]+)\s*}\$', r'<sub>\1</sub>', title)
    title = re.sub(r'\$^{\s*([^}]+)\s*}\$', r'<sup>\1</sup>', title)
    title = re.sub(r'_(\d+)', r'<sub>\1</sub>', title)
    title = re.sub(r'\^(\d+)', r'<sup>\1</sup>', title)
    return title

def archive_today_paper(today_path, archive_path):
    """오늘의 논문을 아카이브로 이동합니다."""
    logger.info(f"Archiving papers from {today_path} to {archive_path}...")
    today_papers = load_yaml(today_path)
    
    if not today_papers or not isinstance(today_papers, list):
        logger.info(f"'{today_path}' is empty or not a list. Skipping archive.")
        return

    archive_papers = load_yaml(archive_path) or []
    existing_ids = {paper.get('paper_id') for paper in archive_papers if paper.get('paper_id')}
    
    archived_count = 0
    for paper in today_papers:
        if paper.get('paper_id') and paper.get('paper_id') not in existing_ids:
            archive_papers.insert(0, paper)
            archived_count += 1
    
    if archived_count > 0:
        save_yaml(archive_papers, archive_path)
        logger.info(f"Archived {archived_count} new papers.")
    else:
        logger.info("No new papers to archive.")

def process_papers(category, model_name):
    """특정 카테고리의 논문을 처리합니다."""
    category_name = category.get('name', 'Unknown')
    paths = category.get('paths', {})
    today_path = paths.get('today')
    archive_path = paths.get('archive')
    filter_config = category.get('filter_config', {})

    if not today_path or not archive_path:
        logger.error(f"[{category_name}] 'paths' configuration is missing or incomplete. Skipping.")
        return 0

    logger.info(f"\n=== [{category_name}] 업데이트 시작 ===")
    
    # 품질 필터 설정 출력
    if filter_config.get('enabled', False):
        logger.info(f"  [품질 필터링 활성화]")
        logger.info(f"    - 최소 점수: {filter_config.get('min_score', 0)}점")
        logger.info(f"    - 저명 기관: {len(filter_config.get('prestigious_institutions', []))}개")
        logger.info(f"    - 저명 연구자: {len(filter_config.get('renowned_authors', []))}명")

    # 아카이브
    archive_today_paper(today_path, archive_path)
    
    # 새 논문 검색
    new_papers = find_new_papers(
        archive_path=archive_path,
        num_target=category.get('num_papers_to_summarize', 3),
        filter_config=filter_config,
        settings=category  # 카테고리 전체를 settings로 전달
    )

    today_list = []
    if not new_papers:
        logger.info(f"No new {category_name.lower()} papers to update. Clearing today's list.")
    else:
        for new_paper in new_papers:
            try:
                cleaned_title_en = clean_latex_title(new_paper.title.strip())

                summary = summarize_with_gemini(new_paper.summary, model_name, OPENROUTER_API_KEY)
                title_kr = translate_title(cleaned_title_en, model_name, OPENROUTER_API_KEY)
                tags = extract_tags_from_title(cleaned_title_en, new_paper.summary)
                
                paper_data = {
                    'title': title_kr,
                    'title_en': cleaned_title_en,
                    'authors': ", ".join([author.name for author in new_paper.authors]),
                    'date': new_paper.published.strftime('%Y-%m-%d'),
                    'paper_id': new_paper.get_short_id(),
                    'link': new_paper.entry_id,
                    'summary': summary,
                    'summary_date': datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')
                }
                
                if tags:
                    paper_data['tags'] = tags
                
                today_list.append(paper_data)
                logger.info(f"  Processed: {paper_data['title'][:60]}...")
            except Exception as e:
                logger.error(f"Error processing paper {new_paper.get_short_id()}: {e}", exc_info=True)
                continue

    save_yaml(today_list, today_path)
    logger.info(f"Successfully updated '{today_path}' with {len(today_list)} papers.")
    
    return len(today_list)

def main():
    """메인 실행 함수"""
    if not OPENROUTER_API_KEY:
        logger.warning("OPENROUTER_API_KEY not set. Using local fallback summarizer.")

    config = load_yaml(CONFIG_FILE)
    if not config:
        logger.error(f"Error: {CONFIG_FILE} not found or could not be loaded.")
        return 1

    is_valid, errors = validate_config(config)
    if not is_valid:
        logger.error("Config validation failed.")
        return 1

    try:
        gemini_model = config.get('gemini_model', 'gemini-1.5-flash')
        categories = config.get('categories', [])
        
        if not categories:
            logger.error("No 'categories' found in config.yml. Nothing to process.")
            return 1
            
        total_counts = {}
        for category in categories:
            count = process_papers(category, gemini_model)
            total_counts[category.get('name', 'Unknown')] = count

        logger.info("\n=== 모든 카테고리 업데이트 완료 ===")
        for name, count in total_counts.items():
            logger.info(f"  - {name}: {count}개 논문 처리")
        
        return 0
        
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())