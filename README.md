# 🤖 AI 기반 2차전지 논문 자동 분석 플랫폼

매일 arXiv.org에 새로 등록되는 2차전지(양극재/음극재) 관련 논문을 자동으로 수집하고, Google Gemini AI를 통해 다각도로 분석하여 연구 동향을 한눈에 파악할 수 있도록 제공하는 웹 플랫폼입니다.

![메인 페이지 스크린샷](https-placeholder-for-main-screenshot.png)
*(여기에 메인 페이지 스크린샷을 추가하세요)*

## ✨ 주요 기능 (Key Features)

### 🧠 AI 기반 다차원 분석
본 프로젝트의 핵심은 Gemini AI를 활용하여 단순 요약을 넘어선 깊이 있는 데이터 분석을 자동화하는 데 있습니다.

- **AI 3줄 요약**: 논문 초록의 핵심 내용을 **[연구 배경], [연구 방법], [주요 결과]**로 구조화하여 빠르게 핵심을 파악할 수 있도록 요약합니다.
- **AI 핵심 키워드 추출**: 각 논문에서 가장 중요한 기술적, 학술적 **키워드 5개를 AI가 자동으로 추출**하여 최신 연구의 핵심 트렌드를 파악할 수 있도록 돕습니다.
- **AI 연구 분야 분류**: 모든 논문을 **'소재 기술', '공정 기술', '성능 평가', '이론/모델링'**의 4가지 주요 카테고리 중 하나로 AI가 직접 분류하여 연구 분야의 분포를 쉽게 이해할 수 있도록 합니다.

### 📊 AI 기반 통계 대시보드
AI가 분석하고 축적한 데이터를 기반으로, 복잡한 연구 동향을 한눈에 파악할 수 있는 동적인 시각화 대시보드를 제공합니다.

- **연구 동향 시각화**: 월별 논문 발행 수, AI가 분류한 연구 분야의 분포(원형 차트) 등을 통해 최신 트렌드를 직관적으로 보여줍니다.
- **Top 10 핫 키워드 & 연구 기관**: 가장 많이 언급된 기술 키워드와 가장 활발하게 연구를 수행하는 기관을 막대 차트로 시각화하여 제공합니다.

![대시보드 스크린샷](https-placeholder-for-dashboard-screenshot.png)
*(여기에 통계 대시보드 스크린샷을 추가하세요)*

### 🔗 AI 추천 관련 논문
- 사용자가 현재 보고 있는 논문과 **AI가 추출한 핵심 키워드를 기반으로** 유사한 주제의 다른 논문을 최대 3개까지 자동으로 추천하여 깊이 있는 정보 탐색을 돕습니다.

### 👤 사용자 편의 기능
- **고품질 논문 필터링**: 저명 기관, 저명 저자, 저널 등을 기반으로 한 정교한 필터링 기능
- **강력한 검색 및 정렬**: 제목, 저자, 내용 기반의 실시간 검색, 키워드 하이라이팅, 다양한 정렬 옵션
- **개인화 기능**: 다크 모드, 북마크 기능 제공

## ⚙️ 시스템 아키텍처 (System Architecture)

본 플랫폼은 GitHub Actions를 중심으로 한 완전 자동화 파이프라인으로 구성되어 있습니다.

```
[arXiv.org API]
       |
       v
[GitHub Actions (매일 자동 실행)]
       |
       +--> [Python Script (update_papers.py)]
       |      |
       |      +--> 1. 논문 수집 및 필터링
       |      |
       |      +--> 2. [Gemini AI API] 호출 (요약, 키워드, 카테고리 분석)
       |      |
       |      +--> 3. 분석 데이터를 YAML 파일로 저장 (_data/*.yml)
       |
       +--> [Jekyll 사이트 빌드]
       |      |
       |      +--> YAML 데이터를 기반으로 HTML 페이지 생성
       |
       v
[GitHub Pages (웹사이트 배포)]
       |
       v
[사용자 (웹 브라우저)]
```

## 🛠️ 기술 스택 (Tech Stack)

- **Automation**: GitHub Actions
- **Backend**: Python 3.x
- **AI Model**: Google Gemini (via OpenRouter API)
- **Frontend**: HTML, CSS, JavaScript, Chart.js
- **Static Site Generator**: Jekyll
- **Data Source**: arXiv API, Semantic Scholar API (인용 정보)

## 🚀 시작하기

### 1. 저장소 복제
```bash
git clone https://github.com/stagnes307/stagnes307.github.io.git
cd stagnes307.github.io
```

### 2. Python 의존성 설치
```bash
pip install -r requirements.txt
```

### 3. API 키 설정
OpenRouter API 키를 GitHub 리포지토리의 `Settings > Secrets and variables > Actions`에 `OPENROUTER_API_KEY`라는 이름으로 등록해야 합니다.

### 4. 로컬에서 스크립트 실행
```bash
python update_papers.py
```
*로컬 실행 시에는 `OPENROUTER_API_KEY`를 환경 변수로 설정해야 합니다.*

## 📄 라이선스
MIT License
