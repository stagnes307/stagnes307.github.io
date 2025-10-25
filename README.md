# 🔋 1일 1논문 자동화 프로젝트

매일 자동으로 양극재(cathode material) 관련 최신 논문을 찾아서 Gemini AI로 요약하고 Jekyll 웹사이트에 게시하는 시스템입니다.

## 📋 프로젝트 구조

```
poscofuturem.ai/
├── _data/
│   ├── today_paper.yml      # 오늘의 논문 데이터
│   └── archive_papers.yml   # 이전 논문 목록
├── papers/                  # 논문 프로젝트 서브디렉토리
│   ├── index.html          # 메인 페이지
│   └── archive.html        # 아카이브 페이지
├── .github/
│   └── workflows/
│       └── daily_paper_update.yml  # GitHub Actions 자동화
├── update_papers.py        # 핵심 Python 스크립트
└── requirements.txt        # Python 의존성
```

## 🚀 설치 및 설정

### 1. 필요한 라이브러리 설치

```bash
pip install -r requirements.txt
```

### 2. Gemini API 키 설정

Google AI Studio에서 API 키를 발급받으세요: https://makersuite.google.com/app/apikey

#### 로컬 실행시:
```bash
export GEMINI_API_KEY="your-api-key-here"
```

#### GitHub Actions 설정:
1. GitHub 리포지토리의 Settings → Secrets and variables → Actions로 이동
2. "New repository secret" 클릭
3. Name: `GEMINI_API_KEY`
4. Secret: 발급받은 API 키 입력
5. "Add secret" 클릭

### 3. GitHub Pages 설정

1. GitHub 리포지토리의 Settings → Pages로 이동
2. Source: "Deploy from a branch" 선택
3. Branch: `main` (또는 `master`) 선택, 폴더: `/ (root)` 선택
4. Save 클릭

## 🎯 사용 방법

### 자동 실행 (GitHub Actions)
- 매일 자정(UTC 0시, 한국 시간 오전 9시)에 자동으로 실행됩니다.
- Actions 탭에서 "Daily Paper Update" 워크플로우를 수동으로 실행할 수도 있습니다.

### 수동 실행
```bash
python update_papers.py
```

## 📚 작동 방식

1. **아카이빙**: 현재 `today_paper.yml`의 논문을 `archive_papers.yml`에 추가
2. **논문 검색**: Semantic Scholar API로 'cathode material' 키워드 최신 논문 검색
3. **중복 확인**: 아카이브에 없는 새로운 논문만 선택
4. **AI 요약**: Gemini API로 논문 초록을 한국어 3문장으로 요약
5. **업데이트**: 새 논문 정보를 `today_paper.yml`에 저장
6. **자동 커밋**: GitHub Actions가 변경사항을 자동으로 커밋 및 푸시

## 🌐 웹사이트

- **메인 페이지** (`/papers/`): 오늘의 양극재 논문 표시
- **아카이브 페이지** (`/papers/archive.html`): 이전에 소개된 모든 논문 목록

GitHub Pages로 배포되면 다음 주소로 접속할 수 있습니다:
- 논문 메인: `https://[username].github.io/[repository]/papers/`
- 논문 아카이브: `https://[username].github.io/[repository]/papers/archive.html`

> 💡 **참고**: 논문 프로젝트는 `/papers/` 서브디렉토리에 있어서 기존 프로젝트와 충돌하지 않습니다.

## 🔧 커스터마이징

### 검색 키워드 변경
`update_papers.py` 파일의 `find_new_paper()` 함수에서 키워드를 변경할 수 있습니다:

```python
new_paper = find_new_paper(archive_papers, keyword='your-keyword-here')
```

### 실행 시간 변경
`.github/workflows/daily_paper_update.yml` 파일의 cron 표현식을 수정하세요:

```yaml
schedule:
  - cron: '0 0 * * *'  # 분 시 일 월 요일 (UTC 기준)
```

### 요약 스타일 변경
`update_papers.py`의 `summarize_with_gemini()` 함수에서 프롬프트를 수정하세요.

## 🛠️ 문제 해결

### API 호출 실패시
- Gemini API 키가 올바르게 설정되었는지 확인
- API 할당량이 남아있는지 확인
- 네트워크 연결 확인

### 논문을 찾지 못할 때
- Semantic Scholar API가 정상 작동하는지 확인
- 검색 키워드를 더 일반적으로 변경
- `max_results` 파라미터를 늘려보기

### GitHub Actions 오류시
- Actions 탭에서 로그 확인
- `contents: write` 권한이 설정되어 있는지 확인
- Secret 키가 올바르게 설정되어 있는지 확인

## 📝 라이선스

이 프로젝트는 개인 학습 및 연구 목적으로 자유롭게 사용할 수 있습니다.

## 🙏 사용된 API

- [Semantic Scholar API](https://www.semanticscholar.org/product/api) - 논문 검색
- [Google Gemini API](https://ai.google.dev/) - AI 요약 생성
- [Jekyll](https://jekyllrb.com/) - 정적 사이트 생성
- [GitHub Actions](https://github.com/features/actions) - 자동화
- [GitHub Pages](https://pages.github.com/) - 웹 호스팅

---

Made with ❤️ for battery research enthusiasts

