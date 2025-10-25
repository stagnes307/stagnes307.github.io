#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1일 1논문 자동화 스크립트
- Semantic Scholar API로 양극재 관련 최신 논문 검색
- Gemini API로 논문 요약
- Jekyll 사이트용 YAML 파일 업데이트
"""

import os
import yaml
import requests
from datetime import datetime
import time
import google.generativeai as genai


def load_yaml(filepath):
    """YAML 파일을 로드하는 함수"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            # 빈 파일이거나 None인 경우 빈 리스트 반환
            return data if data is not None else []
    except FileNotFoundError:
        print(f"파일을 찾을 수 없습니다: {filepath}")
        return [] if 'archive' in filepath else {}
    except Exception as e:
        print(f"파일 로드 중 오류 발생: {e}")
        return [] if 'archive' in filepath else {}


def save_yaml(filepath, data):
    """YAML 파일에 데이터를 저장하는 함수"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print(f"✅ 파일 저장 완료: {filepath}")
    except Exception as e:
        print(f"❌ 파일 저장 중 오류 발생: {e}")


def archive_today_paper(today_paper, archive_papers):
    """오늘의 논문을 아카이브에 추가하는 함수 (중복 방지)"""
    if not today_paper or not isinstance(today_paper, dict):
        print("⚠️ 오늘의 논문이 비어있거나 올바르지 않습니다.")
        return archive_papers
    
    # 오늘의 논문에 doi가 있는지 확인
    today_doi = today_paper.get('link', '')
    
    # 아카이브가 리스트가 아닌 경우 빈 리스트로 초기화
    if not isinstance(archive_papers, list):
        archive_papers = []
    
    # 아카이브에 이미 같은 doi가 있는지 확인
    for paper in archive_papers:
        if paper.get('link', '') == today_doi:
            print(f"⚠️ 이미 아카이브에 존재하는 논문입니다: {today_doi}")
            return archive_papers
    
    # 중복이 없으면 맨 앞에 추가
    archive_papers.insert(0, today_paper)
    print(f"✅ 논문이 아카이브에 추가되었습니다: {today_paper.get('title', 'Unknown')}")
    
    return archive_papers


def find_new_paper(archive_papers, keyword='cathode material', max_results=100):
    """Semantic Scholar API로 새로운 논문을 검색하는 함수"""
    print(f"🔍 '{keyword}' 키워드로 논문 검색 중...")
    
    # 아카이브된 논문들의 doi 목록 추출
    archived_dois = set()
    if isinstance(archive_papers, list):
        for paper in archive_papers:
            doi = paper.get('link', '')
            if doi:
                archived_dois.add(doi)
    
    # Semantic Scholar API 호출
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        'query': keyword,
        'limit': max_results,
        'fields': 'title,authors,year,abstract,externalIds,publicationDate,url',
        'sort': 'publicationDate:desc'  # 최신순 정렬
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        papers = data.get('data', [])
        print(f"📄 총 {len(papers)}개의 논문을 찾았습니다.")
        
        # 아카이브에 없는 새로운 논문 찾기
        for paper in papers:
            # DOI 링크 생성
            external_ids = paper.get('externalIds', {})
            doi = external_ids.get('DOI', '')
            
            paper_url = f"https://doi.org/{doi}" if doi else paper.get('url', '')
            
            # 이미 아카이브에 있는지 확인
            if paper_url and paper_url not in archived_dois:
                # 논문 정보 반환
                authors = paper.get('authors', [])
                author_names = ', '.join([author.get('name', 'Unknown') for author in authors[:3]])
                if len(authors) > 3:
                    author_names += ' et al.'
                
                new_paper = {
                    'title': paper.get('title', 'No Title'),
                    'authors': author_names if author_names else 'Unknown',
                    'date': paper.get('publicationDate', str(datetime.now().date())),
                    'link': paper_url,
                    'abstract': paper.get('abstract', 'No abstract available.')
                }
                
                print(f"✅ 새로운 논문을 찾았습니다: {new_paper['title']}")
                return new_paper
        
        print("⚠️ 아카이브에 없는 새로운 논문을 찾지 못했습니다.")
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API 요청 중 오류 발생: {e}")
        return None
    except Exception as e:
        print(f"❌ 논문 검색 중 오류 발생: {e}")
        return None


def summarize_with_gemini(abstract, api_key):
    """Gemini API를 사용해서 논문 초록을 요약하는 함수"""
    if not api_key:
        print("❌ Gemini API 키가 설정되지 않았습니다.")
        return "API 키가 없어 요약을 생성할 수 없습니다."
    
    if not abstract or abstract == 'No abstract available.':
        return "초록이 제공되지 않아 요약을 생성할 수 없습니다."
    
    try:
        # Gemini API 설정
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        # 프롬프트 작성
        prompt = f"""
당신은 양극재(cathode material) 분야의 전문가입니다.
아래 논문 초록을 읽고, 한국어로 정확히 3문장으로 요약해주세요.
각 문장은 논문의 핵심 내용을 담아야 하며, 전문적이면서도 이해하기 쉽게 작성해주세요.

논문 초록:
{abstract}

요약 (3문장):
"""
        
        print("🤖 Gemini API로 요약 생성 중...")
        response = model.generate_content(prompt)
        summary = response.text.strip()
        
        print("✅ 요약 생성 완료")
        return summary
        
    except Exception as e:
        print(f"❌ Gemini API 호출 중 오류 발생: {e}")
        return f"요약 생성 중 오류가 발생했습니다: {str(e)}"


def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("📚 1일 1논문 자동화 스크립트 시작")
    print("=" * 60)
    
    # 파일 경로 설정
    today_paper_path = '_data/today_paper.yml'
    archive_papers_path = '_data/archive_papers.yml'
    
    # 1. 파일 로드
    print("\n[1단계] YAML 파일 로드 중...")
    today_paper = load_yaml(today_paper_path)
    archive_papers = load_yaml(archive_papers_path)
    print(f"✅ 현재 아카이브 논문 수: {len(archive_papers) if isinstance(archive_papers, list) else 0}")
    
    # 2. 오늘의 논문을 아카이브에 추가
    print("\n[2단계] 오늘의 논문을 아카이브에 추가 중...")
    archive_papers = archive_today_paper(today_paper, archive_papers)
    save_yaml(archive_papers_path, archive_papers)
    
    # 3. 새로운 논문 검색
    print("\n[3단계] Semantic Scholar에서 새로운 논문 검색 중...")
    new_paper = find_new_paper(archive_papers, keyword='cathode material')
    
    if not new_paper:
        print("⚠️ 새로운 논문을 찾지 못했습니다. 스크립트를 종료합니다.")
        return
    
    # 4. Gemini로 요약 생성
    print("\n[4단계] Gemini API로 논문 요약 생성 중...")
    api_key = os.environ.get('GEMINI_API_KEY')
    
    if api_key:
        summary = summarize_with_gemini(new_paper['abstract'], api_key)
        new_paper['summary'] = summary
    else:
        print("⚠️ GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
        new_paper['summary'] = new_paper['abstract'][:300] + "..."  # 초록의 앞부분만 사용
    
    # abstract는 저장하지 않음 (요약만 저장)
    del new_paper['abstract']
    
    # 5. 새로운 논문을 today_paper.yml에 저장
    print("\n[5단계] 새로운 논문을 today_paper.yml에 저장 중...")
    save_yaml(today_paper_path, new_paper)
    
    print("\n" + "=" * 60)
    print("✅ 모든 작업이 완료되었습니다!")
    print("=" * 60)
    print(f"\n새로운 논문: {new_paper['title']}")
    print(f"저자: {new_paper['authors']}")
    print(f"날짜: {new_paper['date']}")
    print(f"링크: {new_paper['link']}")


if __name__ == "__main__":
    main()

