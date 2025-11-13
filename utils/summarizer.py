"""
논문 요약, 번역, 분석 유틸리티
"""
import os
import logging
import requests
import re

logger = logging.getLogger(__name__)


def _call_openrouter_api(prompt, model_name, api_key, timeout=60):
    """OpenRouter API 호출을 위한 내부 헬퍼 함수"""
    if not api_key:
        raise ValueError("OpenRouter API key is not provided.")

    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/stagnes307/stagnes307.github.io",
            "X-Title": "Battery Paper Analyzer"
        }
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        
        if response.status_code != 200:
            error_detail = response.text
            logger.error(f"OpenRouter API error ({response.status_code}): {error_detail}")
            response.raise_for_status()
        
        result = response.json()
        return result['choices'][0]['message']['content'].strip()

    except requests.exceptions.RequestException as e:
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.text
                logger.error(f"API Request Error: {e}\nResponse: {error_detail}")
            except:
                logger.error(f"API Request Error: {e}", exc_info=True)
        else:
            logger.error(f"API Request Error: {e}", exc_info=True)
        raise  # Re-raise the exception to be handled by the caller
    except (KeyError, IndexError) as e:
        logger.error(f"Error parsing API response: {e}", exc_info=True)
        raise


def summarize_with_gemini(abstract, model_name, api_key=None):
    """Gemini를 사용하여 논문 초록을 HTML 형식으로 요약합니다."""
    if not abstract:
        return "<p>요약할 초록 내용이 없습니다.</p>"
    
    api_key = api_key or os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        logger.warning("API key not available, using fallback summarization")
        snippet = (abstract or "").strip().replace("\n", " ")[:400]
        return f"<ul>\n  <li><strong>요약(로컬):</strong> {snippet}...</li>\n</ul>"

    logger.info(f"Summarizing with OpenRouter (Model: {model_name})...")
    prompt = f"""당신은 2차전지 및 재료공학 분야의 전문가입니다.
다음 논문의 초록(abstract)을 받아서,
핵심 내용을 [연구 배경], [연구 방법], [주요 결과]로 구분하여
**HTML 불릿 리스트(<ul>) 형식**으로 요약해 주세요.

[지시 사항]
1. 각 항목은 <li> 태그로 감싸고, <strong> 태그로 제목을 강조해 주세요.
2. 마크다운(###, **)이나 LaTeX($...$) 문법을 **절대 사용하지 마세요.**
3. 모든 LaTeX 문법, 특수 기호, 위첨자/아래첨자는 
   'LiCoO2', 'alpha-V2O5' 처럼 **일반 텍스트로만 풀어쓰세요.**
   (예: LiCoO$_2$ -> LiCoO2, $\\alpha$ -> alpha, $10^{{10}}$ -> 10^10)

[초록 내용]
{abstract}

[HTML 요약]
<ul>
  <li><strong>연구 배경:</strong> ...</li>
  <li><strong>연구 방법:</strong> ...</li>
  <li><strong>주요 결과:</strong> ...</li>
</ul>"""
    
    try:
        return _call_openrouter_api(prompt, model_name, api_key)
    except Exception as e:
        return f"<p>Gemini 요약에 실패했습니다: {e}</p>"


def translate_title(title, model_name, api_key=None):
    """Gemini를 사용하여 논문 제목을 한국어로 번역합니다."""
    if not title:
        return title
    
    api_key = api_key or os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        logger.warning("API key not available, skipping title translation")
        return title
    
    logger.info(f"Translating title with OpenRouter (Model: {model_name})...")
    prompt = f"""다음 논문 제목을 자연스러운 한국어로 번역해주세요. 
학술 용어는 정확하게 번역하고, 전문 용어는 그대로 유지하세요.
번역된 제목만 출력하고 다른 설명은 절대 하지 마세요.

제목: {title}"""
    
    try:
        translated_title = _call_openrouter_api(prompt, model_name, api_key, timeout=30)
        return translated_title.strip('"\'')
    except Exception as e:
        logger.warning(f"Error translating title: {e}, using original title")
        return title


def extract_keywords_with_gemini(abstract, model_name, api_key=None):
    """Gemini를 사용하여 논문 초록에서 핵심 키워드를 추출합니다."""
    if not abstract:
        return []
    
    api_key = api_key or os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        logger.warning("API key not available, skipping keyword extraction")
        return []

    logger.info(f"Extracting keywords with OpenRouter (Model: {model_name})...")
    prompt = f"""다음 논문 초록을 읽고, 가장 중요한 핵심 키워드 5개를 쉼표(,)로 구분하여 나열해주세요.
다른 설명 없이 키워드만 나열해야 합니다.

[초록 내용]
{abstract}

[키워드]
예시: High-nickel cathode, Solid electrolyte, Interfacial stability, Dendrite suppression, All-solid-state batteries"""

    try:
        keywords_str = _call_openrouter_api(prompt, model_name, api_key, timeout=30)
        # AI가 반환할 수 있는 다양한 형식(예: "키워드: a, b, c")에 대응하기 위해 정규식 사용
        keywords_str = re.sub(r".*:\s*", "", keywords_str) # "키워드: " 같은 접두어 제거
        keywords = [kw.strip() for kw in keywords_str.split(',') if kw.strip()]
        return keywords[:5] # 최대 5개만 반환
    except Exception as e:
        logger.warning(f"Error extracting keywords: {e}")
        return []


def classify_category_with_gemini(abstract, model_name, api_key=None):
    """Gemini를 사용하여 논문을 미리 정의된 카테고리로 분류합니다."""
    if not abstract:
        return "분류 안됨"

    api_key = api_key or os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        logger.warning("API key not available, skipping category classification")
        return "분류 안됨"

    logger.info(f"Classifying category with OpenRouter (Model: {model_name})...")
    categories = ["소재 기술", "공정 기술", "성능 평가", "이론/모델링"]
    
    prompt = f"""다음 논문 초록은 2차전지 기술에 관한 것입니다.
아래 네 가지 카테고리 중 이 논문이 **가장** 핵심적으로 다루는 주제 하나를 선택해주세요.
다른 설명 없이 카테고리 이름만 정확히 출력해야 합니다.

[카테고리 목록]
- 소재 기술: 새로운 양극, 음극, 전해질 등의 소재 개발 및 특성 분석
- 공정 기술: 전극 제조, 셀 조립, 합성 방법 등 생산 관련 기술
- 성능 평가: 배터리의 수명, 안정성, 효율 등을 측정하고 분석하는 기술
- 이론/모델링: DFT 계산, 시뮬레이션, 모델링을 통한 현상 분석 및 예측

[초록 내용]
{abstract}

[카테고리]"""

    try:
        category = _call_openrouter_api(prompt, model_name, api_key, timeout=30)
        # AI가 "카테고리: 소재 기술" 처럼 응답할 경우를 대비
        for cat in categories:
            if cat in category:
                return cat
        logger.warning(f"Could not match returned category '{category}' to predefined list. Defaulting.")
        return "기타" # 매칭 실패 시
    except Exception as e:
        logger.warning(f"Error classifying category: {e}")
        return "분류 안됨"

