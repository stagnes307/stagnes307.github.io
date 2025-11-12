"""
설정 파일 검증 유틸리티
"""
import logging

logger = logging.getLogger(__name__)

def _validate_category(category, index):
    """Helper function to validate a single category."""
    errors = []
    prefix = f"categories[{index}]"

    if not isinstance(category, dict):
        errors.append(f"{prefix} must be a dictionary.")
        return errors

    # 필수 키 확인
    required_keys = ['name', 'search_query', 'paths']
    for key in required_keys:
        if key not in category:
            errors.append(f"Missing required key '{key}' in {prefix}")

    # 타입 확인
    if 'name' in category and not isinstance(category['name'], str):
        errors.append(f"{prefix}.name must be a string.")
    if 'search_query' in category and not isinstance(category['search_query'], str):
        errors.append(f"{prefix}.search_query must be a string.")

    # paths 내부 검증
    if 'paths' in category:
        paths = category['paths']
        if not isinstance(paths, dict):
            errors.append(f"{prefix}.paths must be a dictionary.")
        else:
            if 'today' not in paths or not paths['today']:
                errors.append(f"Missing or empty 'today' path in {prefix}.paths")
            if 'archive' not in paths or not paths['archive']:
                errors.append(f"Missing or empty 'archive' path in {prefix}.paths")

    # filter_config 내부 검증 (선택적)
    if 'filter_config' in category:
        filter_config = category['filter_config']
        if not isinstance(filter_config, dict):
            errors.append(f"{prefix}.filter_config must be a dictionary.")
        elif filter_config.get('enabled'):
            if 'min_score' not in filter_config:
                errors.append(f"Missing 'min_score' in enabled {prefix}.filter_config")
            elif not isinstance(filter_config['min_score'], (int, float)):
                errors.append(f"{prefix}.filter_config.min_score must be a number.")

    return errors

def validate_config(config):
    """
    설정 파일의 유효성을 검증합니다.
    
    Args:
        config: 설정 딕셔너리
        
    Returns:
        (is_valid, errors) 튜플
    """
    errors = []
    
    if 'gemini_model' not in config or not config['gemini_model']:
        errors.append("Missing required top-level key: 'gemini_model'")

    if 'categories' not in config:
        errors.append("Missing required top-level key: 'categories'")
    elif not isinstance(config['categories'], list) or not config['categories']:
        errors.append("'categories' must be a non-empty list.")
    else:
        for i, category in enumerate(config['categories']):
            errors.extend(_validate_category(category, i))
    
    is_valid = len(errors) == 0
    
    if not is_valid:
        logger.error("Config validation failed:")
        for error in errors:
            logger.error(f"  - {error}")
    else:
        logger.info("Config validation passed.")
    
    return is_valid, errors