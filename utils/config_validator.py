"""
설정 파일 검증 유틸리티
"""
import logging

logger = logging.getLogger(__name__)


def validate_config(config):
    """
    설정 파일의 유효성을 검증합니다.
    
    Args:
        config: 설정 딕셔너리
        
    Returns:
        (is_valid, errors) 튜플
    """
    errors = []
    
    # 필수 섹션 확인
    required_sections = ['arxiv_settings', 'file_paths']
    for section in required_sections:
        if section not in config:
            errors.append(f"Missing required section: {section}")
    
    # arxiv_settings 검증
    if 'arxiv_settings' in config:
        settings = config['arxiv_settings']
        if 'search_query' not in settings or not settings['search_query']:
            errors.append("arxiv_settings.search_query is required")
        if 'max_results_to_fetch' in settings:
            if not isinstance(settings['max_results_to_fetch'], int) or settings['max_results_to_fetch'] < 1:
                errors.append("arxiv_settings.max_results_to_fetch must be a positive integer")
    
    # file_paths 검증
    if 'file_paths' in config:
        paths = config['file_paths']
        required_paths = ['today_cathode', 'archive_cathode']
        for path_key in required_paths:
            if path_key not in paths or not paths[path_key]:
                errors.append(f"file_paths.{path_key} is required")
    
    # quality_filter 검증
    if 'quality_filter' in config:
        filter_config = config['quality_filter']
        if filter_config.get('enabled', False):
            if 'min_score' in filter_config:
                min_score = filter_config['min_score']
                if not isinstance(min_score, (int, float)) or min_score < 0:
                    errors.append("quality_filter.min_score must be a non-negative number")
    
    is_valid = len(errors) == 0
    
    if not is_valid:
        logger.error("Config validation failed:")
        for error in errors:
            logger.error(f"  - {error}")
    else:
        logger.info("Config validation passed")
    
    return is_valid, errors

