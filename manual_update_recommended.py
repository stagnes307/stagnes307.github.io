import yaml
import os
import sys
import logging
from datetime import datetime, timezone, timedelta

# 한국 시간대 설정
KST = timezone(timedelta(hours=9))

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S KST')
logger = logging.getLogger(__name__)

def load_yaml(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or []

def save_yaml(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)

def update_today_with_recommended(category_name, recommended_path, today_path):
    logger.info(f"[{category_name}] Updating today list with recommended papers...")
    
    recommended_papers = load_yaml(recommended_path)
    if not recommended_papers:
        logger.error(f"  -> No papers found in {recommended_path}")
        return

    today_list = []
    current_time = datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')
    today_date = datetime.now(KST).strftime('%Y-%m-%d')

    for paper in recommended_papers:
        # recommended.yml 형식을 today.yml 형식으로 변환
        paper_data = {
            'title': paper.get('title'),
            'title_en': paper.get('title'), # 추천 논문은 보통 영어 제목이므로
            'authors': "Editor's Pick", # 저자 정보가 없으면 대체
            'date': today_date,
            'paper_id': paper.get('doi', 'N/A').replace('/', '_'), # DOI를 ID로 사용
            'link': paper.get('link'),
            'summary': paper.get('desc'),
            'summary_date': current_time,
            'keywords': ["Editor's Pick", "Recommended"],
            'category': "Review / Key Paper"
        }
        today_list.append(paper_data)

    save_yaml(today_list, today_path)
    logger.info(f"  -> Successfully updated {today_path} with {len(today_list)} papers.")

def main():
    # CATHODE
    update_today_with_recommended(
        "CATHODE",
        "_data/cathode/recommended.yml",
        "_data/cathode/today.yml"
    )

    # ANODE
    update_today_with_recommended(
        "ANODE",
        "_data/anode/recommended.yml",
        "_data/anode/today.yml"
    )
    
    logger.info("All done. Please push changes to GitHub.")

if __name__ == "__main__":
    main()
