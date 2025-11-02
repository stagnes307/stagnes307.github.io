# 오늘의 논문 📚

배터리 연구 논문을 자동으로 수집하고 요약하는 GitHub Pages 사이트입니다.

## 주요 기능 ✨

### 🎯 핵심 기능
- **자동 논문 수집**: arXiv에서 양극재/음극재 논문을 자동으로 검색
- **AI 요약**: Gemini API를 사용한 논문 요약
- **품질 필터링**: 저명한 기관, 연구자, 저널 기반 품질 필터링
- **카테고리 분류**: 양극재(Cathode)와 음극재(Anode) 분리 관리

### 🔍 검색 및 정렬
- **실시간 검색**: 제목, 저자, 내용으로 검색
- **정렬 기능**: 날짜순, 저자순, 제목순 정렬
- **페이지네이션**: 대량의 논문을 효율적으로 탐색

### 🎨 사용자 경험
- **다크 모드**: 눈의 피로를 줄이는 다크 테마
- **북마크**: 중요 논문을 북마크로 저장 (localStorage)
- **반응형 디자인**: 모바일/태블릿/데스크톱 지원

### 📊 통계 및 분석
- **통계 대시보드**: 논문 수, 카테고리별 분포, 월별 트렌드
- **인용 정보**: Semantic Scholar API 연동으로 인용 수 표시
- **태그 시스템**: 자동 태그 생성 (NCM, LCO, Graphite 등)

### 📡 피드 및 공유
- **RSS 피드**: 새 논문 알림을 RSS로 구독
- **북마크 필터**: 북마크한 논문만 보기

## 설치 및 설정

### 1. 저장소 클론
```bash
git clone https://github.com/stagnes307/stagnes307.github.io.git
cd stagnes307.github.io
```

### 2. Python 환경 설정
```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정
```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

### 4. 설정 파일 수정
`config.yml` 파일을 수정하여 검색 쿼리, 필터 설정 등을 구성합니다.

## 사용 방법

### 논문 업데이트
```bash
python update_papers.py
```

이 명령은:
1. 오늘의 논문을 아카이브로 이동
2. arXiv에서 새 논문 검색
3. 품질 필터링
4. Gemini로 요약 생성
5. YAML 파일에 저장

### 설정 파일 (`config.yml`)

#### 검색 설정
```yaml
arxiv_settings:
  search_query: 'cat:cond-mat.mtrl-sci AND cathode AND lithium'
  max_results_to_fetch: 150
  num_papers_to_summarize: 3
  exclude_keywords:
    - "sodium"
    - "polymer"
```

#### 품질 필터 설정
```yaml
quality_filter:
  enabled: true
  min_score: 2
  prestigious_institutions:
    - "MIT"
    - "KAIST"
  renowned_authors:
    - "Kisuk Kang"
  min_author_hindex: 5
```

## 프로젝트 구조

```
.
├── update_papers.py          # 메인 스크립트
├── config.yml                # 설정 파일
├── requirements.txt          # Python 의존성
├── utils/                    # 유틸리티 모듈
│   ├── yaml_helper.py       # YAML 파일 처리
│   ├── paper_fetcher.py     # 논문 검색
│   ├── summarizer.py        # 요약 생성
│   ├── quality_filter.py    # 품질 필터링
│   ├── config_validator.py  # 설정 검증
│   └── cache.py             # 캐싱
├── _data/                    # 논문 데이터
│   ├── cathode/
│   │   ├── today.yml
│   │   └── archive.yml
│   └── anode/
│       ├── today.yml
│       └── archive.yml
├── assets/                   # 정적 파일
│   ├── css/
│   │   └── common.css
│   └── js/
│       └── common.js
├── index.html               # 메인 페이지
├── stats.html               # 통계 대시보드
├── feed.xml                 # RSS 피드
└── archive.html             # 아카이브 페이지
```

## 주요 개선사항 🚀

### 코드 품질
- ✅ **모듈화**: 단일 파일을 여러 모듈로 분리
- ✅ **에러 처리**: 포괄적인 예외 처리 및 로깅
- ✅ **설정 검증**: 설정 파일 유효성 검증
- ✅ **코드 중복 제거**: 공통 CSS/JS 파일화

### 성능 최적화
- ✅ **API 캐싱**: Semantic Scholar h-index 캐싱 (7일 TTL)
- ✅ **배치 처리**: 논문 검색 최적화
- ✅ **지연 로드**: 인용 정보 지연 로드

### 사용자 기능
- ✅ **검색 기능**: 실시간 검색 및 필터링
- ✅ **정렬 기능**: 다양한 정렬 옵션
- ✅ **페이지네이션**: 대량 데이터 처리
- ✅ **다크 모드**: 테마 전환 기능
- ✅ **북마크**: 논문 저장 기능
- ✅ **통계 대시보드**: 데이터 시각화
- ✅ **RSS 피드**: 새 논문 알림
- ✅ **인용 정보**: 논문 인용 수 표시
- ✅ **태그 시스템**: 자동 태그 생성

## 기술 스택

- **Backend**: Python 3.x
- **Frontend**: HTML, CSS, JavaScript
- **Framework**: Jekyll (GitHub Pages)
- **API**: 
  - arXiv API (논문 검색)
  - Google Gemini API (요약 생성)
  - Semantic Scholar API (인용 정보)
- **라이브러리**:
  - `arxiv` - arXiv API 클라이언트
  - `google-generativeai` - Gemini API
  - `pyyaml` - YAML 처리
  - `requests` - HTTP 요청

## 라이선스

MIT License

## 기여

이슈나 풀 리퀘스트를 환영합니다!

## 문의

문제가 있거나 제안사항이 있으시면 이슈를 생성해주세요.
