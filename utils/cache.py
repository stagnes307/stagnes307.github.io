"""
캐싱 유틸리티
"""
import json
import os
import time
import logging

logger = logging.getLogger(__name__)

CACHE_DIR = '.cache'
CACHE_FILE = os.path.join(CACHE_DIR, 'hindex_cache.json')
CACHE_TTL = 7 * 24 * 60 * 60  # 7일 (초 단위)


def ensure_cache_dir():
    """캐시 디렉토리가 없으면 생성"""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)


def load_cache():
    """
    캐시 파일을 로드합니다.
    
    Returns:
        캐시 딕셔너리
    """
    ensure_cache_dir()
    
    if not os.path.exists(CACHE_FILE):
        return {}
    
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # 만료된 항목 제거
        current_time = time.time()
        expired_keys = []
        for key, value in data.items():
            if isinstance(value, dict) and 'timestamp' in value:
                if current_time - value['timestamp'] > CACHE_TTL:
                    expired_keys.append(key)
        
        for key in expired_keys:
            del data[key]
        
        # 타임스탬프 제거하고 값만 반환
        cleaned_data = {}
        for key, value in data.items():
            if isinstance(value, dict) and 'value' in value:
                cleaned_data[key] = value['value']
            else:
                cleaned_data[key] = value
        
        return cleaned_data
    except Exception as e:
        logger.warning(f"Error loading cache: {e}")
        return {}


def save_cache(cache):
    """
    캐시를 파일에 저장합니다.
    
    Args:
        cache: 캐시 딕셔너리
    """
    ensure_cache_dir()
    
    try:
        # 타임스탬프와 함께 저장
        data_with_timestamp = {}
        current_time = time.time()
        for key, value in cache.items():
            data_with_timestamp[key] = {
                'value': value,
                'timestamp': current_time
            }
        
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_with_timestamp, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Error saving cache: {e}")


def get_cached_hindex(author_name, cache):
    """
    캐시에서 h-index를 가져옵니다.
    
    Args:
        author_name: 저자 이름
        cache: 캐시 딕셔너리
        
    Returns:
        h-index 또는 None
    """
    return cache.get(author_name)


def set_cached_hindex(author_name, hindex, cache):
    """
    캐시에 h-index를 저장합니다.
    
    Args:
        author_name: 저자 이름
        hindex: h-index 값
        cache: 캐시 딕셔너리
    """
    if hindex is not None:
        cache[author_name] = hindex

