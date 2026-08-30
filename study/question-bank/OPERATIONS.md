# 기출·출제분석 운영 런북

이 문서는 기출·출제분석 제품의 안전한 갱신, 검증, 배포, 복구 절차를 정의한다. 데이터 구조와 권리 모델은 [README](README.md)를 함께 따른다. 저장소 관리자가 운영 책임자이며, canonical 데이터나 권리 상태를 바꾸는 변경에는 작성자 외 1명의 검토가 필요하다.

## 릴리스 불변조건

- 공개 JSON의 `privacy`는 반드시 `scope=public`, `contains_private_content=false`다.
- `private_only` 또는 `blocked` 출처와 원문은 공개 JSON·Pages artifact에 포함하지 않는다.
- 생성 파일은 canonical 입력과 같은 dataset hash를 가져야 한다.
- 데이터 검증, 전체 Python 회귀 테스트, JavaScript 문법 검사, Chromium E2E, axe 검사가 모두 성공한 revision만 배포한다.
- Pages artifact는 검증 job이 확인한 동일 revision에서 빌드한다.

## 로컬 갱신과 검증

저장소 루트에서 다음 명령을 실행한다.

```powershell
python study/factory/scripts/validate_questions.py big-data-analysis-engineer-written
python study/factory/scripts/build_question_bank.py big-data-analysis-engineer-written
python study/factory/scripts/build_question_bank.py big-data-analysis-engineer-written --check
python study/factory/scripts/validate_all.py big-data-analysis-engineer-written
python -m unittest discover -s study/factory/tests -p "test_*.py" -v
npm ci --prefix study/factory
npm --prefix study/factory test
```

최초 Chromium 설치 또는 Playwright 버전 변경 뒤에는 다음 명령을 한 번 실행한다.

```powershell
npx --prefix study/factory playwright install chromium
```

브라우저 실패의 HTML report, screenshot, video, trace는 저장소 루트의 `.cache/question-bank-playwright-*`에 생성된다. `.cache/`는 배포하거나 커밋하지 않는다.

## 비공개 overlay 취급

비공개 overlay와 SQLite는 웹 루트 밖에서만 보관한다. 로컬 미리보기도 모든 네트워크 인터페이스에 공개하지 않는다.

```powershell
python -m http.server 8000 --bind 127.0.0.1
```

브라우저에서는 `http://127.0.0.1:8000/...`만 사용한다. `0.0.0.0`, LAN 주소, 공유 호스트, GitHub Pages에 로컬 JSON이나 SQLite를 올리지 않는다. `?scope=local`은 비공개 파일을 웹에서 조회하는 기능이 아니며 공개 데이터로 안전하게 귀결되어야 한다.

커밋 전 확인:

```powershell
git status --short
git ls-files | Select-String -Pattern "questions[.]local[.]json|/private/|/build/|[.]sqlite$"
```

두 번째 명령은 결과가 없어야 한다.

## CI와 배포

- `Study question bank`: pull request의 데이터·생성물·전체 unit·브라우저·접근성 게이트다.
- `Deploy GitHub Pages`: `main` push를 같은 게이트로 재검증한 뒤 Jekyll artifact를 만들고, deploy job에만 Pages/OIDC 쓰기 권한을 부여한다.
- `Question bank production smoke`: 매주 배포된 shell, JS, CSS, 공개 JSON, privacy 불변조건을 재검증한다. 제3자 출처 본문은 요청하지 않는다.

GitHub 저장소 설정에서 Pages source를 **GitHub Actions**로 선택하고, `main`에는 pull request와 `Study question bank` 성공을 요구하는 ruleset을 적용해야 한다. 설정 확인:

```powershell
gh api repos/stagnes307/stagnes307.github.io/pages --jq .build_type
gh api repos/stagnes307/stagnes307.github.io/branches/main/protection
gh run list --workflow pages.yml --limit 5
```

첫 명령은 `workflow`를 반환해야 한다. 설정 변경 자체는 코드 배포와 분리해 관리한다.

## 배포 확인

배포가 끝난 뒤 다음 URL이 HTTP 200인지 확인한다.

- `https://stagnes307.github.io/study/courses/big-data-analysis-engineer-written/questions/`
- `https://stagnes307.github.io/study/courses/big-data-analysis-engineer-written/questions/data/questions.public.json`
- `https://stagnes307.github.io/study/assets/question-bank.js`
- `https://stagnes307.github.io/study/assets/question-bank.css`

Actions의 production smoke를 수동 실행하는 방법:

```powershell
$previousRunId = gh run list --workflow question-bank-smoke.yml --branch main --event workflow_dispatch --user "@me" --limit 1 --json databaseId --jq '.[0].databaseId'
gh workflow run question-bank-smoke.yml --ref main
if ($LASTEXITCODE -ne 0) { throw "production smoke 실행 요청에 실패했습니다." }

$runId = $null
for ($attempt = 0; $attempt -lt 30 -and -not $runId; $attempt++) {
    Start-Sleep -Seconds 2
    $candidate = gh run list --workflow question-bank-smoke.yml --branch main --event workflow_dispatch --user "@me" --limit 1 --json databaseId --jq '.[0].databaseId'
    if ($candidate -and $candidate -ne $previousRunId) { $runId = $candidate }
}

if (-not $runId) { throw "새 production smoke run ID를 찾지 못했습니다." }
gh run watch $runId --exit-status
```

## 롤백과 사고 대응

일반 기능 장애는 마지막 변경을 새 revert commit으로 되돌린다. 공유 이력을 강제로 재작성하거나 작업 디렉터리를 reset하지 않는다.

```powershell
git switch -c rollback/<incident-id>
git revert <problem-commit-sha>
git push -u origin HEAD
gh pr create --base main --fill
```

롤백 PR도 동일한 검증 gate를 통과시킨다. 권리 자료 노출처럼 대기 자체가 위험한 사고만 저장소의 승인된 긴급 변경 절차를 사용하고, 사후에 반드시 검토 기록을 남긴다.

권리 제한 원문이나 개인정보가 노출된 경우에는 다음 순서를 따른다.

1. 새 배포를 중지하고 노출 경로와 최초 revision을 기록한다.
2. 공개 artifact에서 자료를 제거한 긴급 commit을 검증·배포한다.
3. Pages URL, raw GitHub URL, Actions artifact와 Git history에 남은 사본을 확인한다.
4. Actions artifact를 삭제하고, Git history 제거가 필요하면 별도 백업·협업 공지 후 이력 재작성 절차를 수행한다.
5. 원인과 재발 방지 검증을 기록한 뒤 배포를 재개한다.

## 데이터 신선도와 경보

- 새 회차·일정 변경 뒤 공식 출처를 사람이 확인하고 `accessed_at`을 갱신한다.
- 공식 일정과 권리 정책은 최소 월 1회, 기타 링크는 분기 1회 수동 검토한다.
- production smoke 실패, privacy invariant 실패, Pages deploy 실패는 릴리스 차단 사고로 취급한다.
- 외부 출처 상태 확인은 저빈도·상태 코드 중심으로 수행하며, 자동 수집한 본문을 저장하지 않는다.
