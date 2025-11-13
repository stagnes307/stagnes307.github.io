"""
YAML 파일 읽기/쓰기 유틸리티
"""
import os
import yaml
import logging

logger = logging.getLogger(__name__)


def load_yaml(filename):
    """
    YAML 파일을 로드합니다.
    
    Args:
        filename: YAML 파일 경로
        
    Returns:
        로드된 데이터 (dict/list), 파일이 없거나 에러 시 None
    """
    if not os.path.exists(filename):
        logger.warning(f"YAML file not found: {filename}")
        return None
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file {filename}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error loading YAML file {filename}: {e}")
        return None


def save_yaml(data, filename):
    """
    데이터를 YAML 파일로 저장합니다.
    
    Args:
        data: 저장할 데이터
        filename: YAML 파일 경로
        
    Returns:
        성공 시 True, 실패 시 False
    """
    try:
        # 디렉토리가 없으면 생성
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        logger.info(f"Successfully saved YAML file: {filename}")
        return True
    except Exception as e:
        logger.error(f"Error saving YAML file {filename}: {e}")
        return False

