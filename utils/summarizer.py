"""
논문 요약 유틸리티
"""
import os
import logging
import requests

logger = logging.getLogger(__name__)


def summarize_with_gemini(abstract, model_name, api_key=None):
    """
    OpenRouter API를 통해 Gemini 모델을 사용하여 논문 초록을 요약합니다.
    
    Args:
        abstract: 논문 초록
        model_name: OpenRouter 모델 이름 (예: 'google/gemini-2.0-flash-exp')
        api_key: OpenRouter API 키 (없으면 환경변수에서 가져옴)
        
    Returns:
        HTML 형식의 요약
    """
    if not abstract:
        return "<p>요약할 초록 내용이 없습니다.</p>"
    
    api_key = api_key or os.environ.get('OPENROUTER_API_KEY')
    
    if not api_key:
        # Fallback: 간단 요약
        logger.warning("OpenRouter API key not available, using fallback summarization")
        snippet = (abstract or "").strip().replace("\n", " ")[:400]
        return f"<ul>\n  <li><strong>요약(로컬):</strong> {snippet}...</li>\n</ul>"

    logger.info(f"Summarizing with OpenRouter (Model: {model_name})...")
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/stagnes307/stagnes307.github.io",
            "X-Title": "Battery Paper Summarizer"
        }
        
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
        
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        summary = result['choices'][0]['message']['content'].strip()
        
        return summary
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error summarizing with OpenRouter (Request): {e}", exc_info=True)
        return f"<p>OpenRouter 요약에 실패했습니다: {e}</p>"
    except (KeyError, IndexError) as e:
        logger.error(f"Error parsing OpenRouter response: {e}", exc_info=True)
        logger.debug(f"Response: {response.text if 'response' in locals() else 'No response'}")
        return f"<p>OpenRouter 응답 파싱에 실패했습니다: {e}</p>"
    except Exception as e:
        logger.error(f"Error summarizing with OpenRouter: {e}", exc_info=True)
        return f"<p>OpenRouter 요약에 실패했습니다: {e}</p>"


def translate_title(title, model_name, api_key=None):
    """
    OpenRouter API를 통해 논문 제목을 한국어로 번역합니다.
    
    Args:
        title: 논문 제목 (영어)
        model_name: OpenRouter 모델 이름
        api_key: OpenRouter API 키
        
    Returns:
        한국어로 번역된 제목
    """
    if not title:
        return title
    
    api_key = api_key or os.environ.get('OPENROUTER_API_KEY')
    
    if not api_key:
        logger.warning("OpenRouter API key not available, skipping title translation")
        return title
    
    logger.info(f"Translating title with OpenRouter (Model: {model_name})...")
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/stagnes307/stagnes307.github.io",
            "X-Title": "Battery Paper Summarizer"
        }
        
        prompt = f"""다음 논문 제목을 자연스러운 한국어로 번역해주세요. 
학술 용어는 정확하게 번역하고, 전문 용어는 그대로 유지하세요.
번역만 출력하고 다른 설명은 하지 마세요.

제목: {title}"""
        
        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        translated_title = result['choices'][0]['message']['content'].strip()
        
        # 따옴표나 불필요한 문자 제거
        translated_title = translated_title.strip('"\'')
        
        return translated_title
        
    except Exception as e:
        logger.warning(f"Error translating title: {e}, using original title")
        return title


def extract_tags_from_title(title, summary):
    """
    제목과 요약에서 태그를 추출합니다 (간단한 키워드 매칭).
    
    Args:
        title: 논문 제목
        summary: 논문 요약
        
    Returns:
        태그 리스트
    """
    tags = []
    text = (title + " " + summary).lower()
    
    # 주요 재료 키워드
    material_keywords = {
        'ncm': 'NCM',
        'nca': 'NCA',
        'lco': 'LCO',
        'lmo': 'LMO',
        'lfo': 'LFO',
        'graphite': 'Graphite',
        'silicon': 'Silicon',
        'solid-state': 'Solid-State',
        'electrolyte': 'Electrolyte',
        'cathode': 'Cathode',
        'anode': 'Anode',
        'lithium metal': 'Lithium Metal',
        'sodium': 'Sodium',
    }
    
    for keyword, tag in material_keywords.items():
        if keyword in text:
            tags.append(tag)
    
    return list(set(tags))  # 중복 제거

