// 공통 JavaScript 기능

// 다크 모드 토글
function initDarkMode() {
    const darkMode = localStorage.getItem('darkMode') === 'true';
    if (darkMode) {
        document.body.classList.add('dark-mode');
    }
    
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            document.body.classList.toggle('dark-mode');
            const isDark = document.body.classList.contains('dark-mode');
            localStorage.setItem('darkMode', isDark);
            themeToggle.textContent = isDark ? '☀️' : '🌙';
        });
        
        if (darkMode) {
            themeToggle.textContent = '☀️';
        }
    }
}

// 스크롤 탑 버튼
function initScrollTop() {
    const scrollTopBtn = document.getElementById('scrollTopBtn');
    if (!scrollTopBtn) return;
    
    window.onscroll = function() {
        if (document.body.scrollTop > 100 || document.documentElement.scrollTop > 100) {
            scrollTopBtn.style.display = 'block';
        } else {
            scrollTopBtn.style.display = 'none';
        }
    };
    
    scrollTopBtn.onclick = function(e) {
        e.preventDefault();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };
}

// 북마크 기능
function initBookmarks() {
    const bookmarks = JSON.parse(localStorage.getItem('bookmarks') || '[]');
    
    // 북마크 버튼 이벤트 리스너
    document.querySelectorAll('.bookmark-btn').forEach(btn => {
        const paperId = btn.dataset.paperId;
        if (paperId && bookmarks.includes(paperId)) {
            btn.classList.add('bookmarked');
            btn.textContent = '★ 북마크됨';
            const paperItem = btn.closest('.paper-item');
            if (paperItem) {
                paperItem.classList.add('bookmarked');
            }
        }
        
        btn.addEventListener('click', function() {
            const paperId = this.dataset.paperId;
            if (!paperId) return;
            
            let bookmarks = JSON.parse(localStorage.getItem('bookmarks') || '[]');
            const index = bookmarks.indexOf(paperId);
            
            if (index > -1) {
                bookmarks.splice(index, 1);
                this.classList.remove('bookmarked');
                this.textContent = '☆ 북마크';
                const paperItem = this.closest('.paper-item');
                if (paperItem) {
                    paperItem.classList.remove('bookmarked');
                }
            } else {
                bookmarks.push(paperId);
                this.classList.add('bookmarked');
                this.textContent = '★ 북마크됨';
                const paperItem = this.closest('.paper-item');
                if (paperItem) {
                    paperItem.classList.add('bookmarked');
                }
            }
            
            localStorage.setItem('bookmarks', JSON.stringify(bookmarks));
        });
    });
}

// 검색 기능 (하이라이팅 포함)
function initSearch() {
    const searchBox = document.getElementById('searchBox');
    if (!searchBox) return;
    
    searchBox.addEventListener('input', function() {
        const query = this.value.toLowerCase().trim();
        
        paginationState.allItems.forEach(item => {
            const titleEl = item.querySelector('.paper-title');
            const metaEl = item.querySelector('.paper-meta');
            const summaryEl = item.querySelector('.paper-summary-content');
            
            const title = titleEl?.textContent.toLowerCase() || '';
            const authors = metaEl?.textContent.toLowerCase() || '';
            const summary = summaryEl?.textContent.toLowerCase() || '';
            
            if (!query || title.includes(query) || authors.includes(query) || summary.includes(query)) {
                // 검색 결과에 포함
                item.setAttribute('data-search-match', 'true');
                
                // 키워드 하이라이팅 적용
                if (query) {
                    highlightKeywords(item, query);
                } else {
                    removeHighlighting(item);
                }
            } else {
                item.setAttribute('data-search-match', 'false');
                removeHighlighting(item);
            }
        });
        
        // 페이지네이션 재렌더링 (검색 결과 반영)
        paginationState.currentPage = 1;
        renderPagination();
        updateResultCount();
    });
}

// 키워드 하이라이팅 함수
function highlightKeywords(item, query) {
    const titleEl = item.querySelector('.paper-title');
    const metaEl = item.querySelector('.paper-meta');
    const summaryEl = item.querySelector('.paper-summary-content');
    
    // 원본 텍스트 저장 (하이라이팅 제거 후 재적용용)
    if (!titleEl.dataset.originalText) titleEl.dataset.originalText = titleEl.innerHTML;
    if (!metaEl.dataset.originalText) metaEl.dataset.originalText = metaEl.innerHTML;
    if (!summaryEl.dataset.originalText) summaryEl.dataset.originalText = summaryEl.innerHTML;
    
    // 키워드 하이라이팅 적용
    if (titleEl) {
        titleEl.innerHTML = highlightText(titleEl.dataset.originalText, query);
    }
    if (metaEl) {
        metaEl.innerHTML = highlightText(metaEl.dataset.originalText, query);
    }
    if (summaryEl) {
        summaryEl.innerHTML = highlightText(summaryEl.dataset.originalText, query);
    }
}

// 텍스트에서 키워드 하이라이팅
function highlightText(text, query) {
    if (!query) return text;
    
    // HTML 태그를 보존하면서 텍스트만 하이라이팅
    const regex = new RegExp(`(${escapeRegExp(query)})`, 'gi');
    
    // HTML 태그를 임시로 치환
    const placeholders = [];
    let placeholderIndex = 0;
    const textWithoutTags = text.replace(/<[^>]+>/g, (match) => {
        placeholders.push(match);
        return `__HTML_PLACEHOLDER_${placeholderIndex++}__`;
    });
    
    // 키워드 하이라이팅 적용
    const highlighted = textWithoutTags.replace(regex, '<mark class="search-highlight">$1</mark>');
    
    // HTML 태그 복원
    return highlighted.replace(/__HTML_PLACEHOLDER_(\d+)__/g, (match, index) => {
        return placeholders[parseInt(index)] || '';
    });
}

// 하이라이팅 제거
function removeHighlighting(item) {
    const titleEl = item.querySelector('.paper-title');
    const metaEl = item.querySelector('.paper-meta');
    const summaryEl = item.querySelector('.paper-summary-content');
    
    if (titleEl && titleEl.dataset.originalText) {
        titleEl.innerHTML = titleEl.dataset.originalText;
    }
    if (metaEl && metaEl.dataset.originalText) {
        metaEl.innerHTML = metaEl.dataset.originalText;
    }
    if (summaryEl && summaryEl.dataset.originalText) {
        summaryEl.innerHTML = summaryEl.dataset.originalText;
    }
}

// 정규식 특수문자 이스케이프
function escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// 정렬 기능
function initSort() {
    const sortSelect = document.getElementById('sortSelect');
    if (!sortSelect) return;
    
    sortSelect.addEventListener('change', function() {
        // 정렬 후 페이지네이션 재렌더링
        paginationState.currentPage = 1;
        renderPagination();
        updateResultCount();
    });
}

// 결과 카운트 업데이트
function updateResultCount() {
    const visibleItems = Array.from(document.querySelectorAll('.paper-item')).filter(
        item => item.style.display !== 'none'
    ).length;
    const totalItems = document.querySelectorAll('.paper-item').length;
    
    const countElement = document.getElementById('resultCount');
    if (countElement) {
        countElement.textContent = `검색 결과: ${visibleItems} / ${totalItems}`;
    }
}

// 페이지네이션 (전역 변수로 관리)
let paginationState = {
    itemsPerPage: 10,
    currentPage: 1,
    allItems: [],
    visibleItems: [],
    container: null
};
window.paginationState = paginationState; // 전역 접근 가능하도록

function initPagination(itemsPerPage = 10) {
    paginationState.itemsPerPage = itemsPerPage;
    paginationState.allItems = Array.from(document.querySelectorAll('.paper-item'));
    updateVisibleItems();
    renderPagination();
}

function updateVisibleItems() {
    // 검색 및 필터 적용된 항목만 가져오기
    paginationState.visibleItems = paginationState.allItems.filter(item => {
        // 검색 필터 확인
        const searchMatch = item.getAttribute('data-search-match');
        if (searchMatch === 'false') return false;
        
        // 태그 필터 확인
        const tagMatch = item.getAttribute('data-tag-match');
        if (tagMatch === 'false') return false;
        
        // 북마크 필터 확인
        const filterSelect = document.getElementById('filterSelect');
        if (filterSelect && filterSelect.value === 'bookmarked') {
            const bookmarks = JSON.parse(localStorage.getItem('bookmarks') || '[]');
            const paperId = item.dataset.paperId;
            if (!bookmarks.includes(paperId)) return false;
        }
        
        return true;
    });
}

function getSortedItems() {
    // 정렬 적용
    const sortSelect = document.getElementById('sortSelect');
    if (!sortSelect) return paginationState.visibleItems;
    
    const sorted = [...paginationState.visibleItems];
    const sortBy = sortSelect.value;
    
    sorted.sort((a, b) => {
        switch(sortBy) {
            case 'date-desc':
                const dateA = new Date(a.querySelector('.paper-meta span:nth-child(2)')?.textContent.split(':')[1]?.trim() || '');
                const dateB = new Date(b.querySelector('.paper-meta span:nth-child(2)')?.textContent.split(':')[1]?.trim() || '');
                return dateB - dateA;
            case 'date-asc':
                const dateA2 = new Date(a.querySelector('.paper-meta span:nth-child(2)')?.textContent.split(':')[1]?.trim() || '');
                const dateB2 = new Date(b.querySelector('.paper-meta span:nth-child(2)')?.textContent.split(':')[1]?.trim() || '');
                return dateA2 - dateB2;
            case 'author':
                const authorA = a.querySelector('.paper-meta span:first-child')?.textContent.split(':')[1]?.trim() || '';
                const authorB = b.querySelector('.paper-meta span:first-child')?.textContent.split(':')[1]?.trim() || '';
                return authorA.localeCompare(authorB, 'ko');
            case 'title':
                const titleA = a.querySelector('.paper-title')?.textContent || '';
                const titleB = b.querySelector('.paper-title')?.textContent || '';
                return titleA.localeCompare(titleB, 'ko');
            default:
                return 0;
        }
    });
    
    return sorted;
}

function renderPagination() {
    updateVisibleItems();
    const sortedItems = getSortedItems();
    const totalItems = sortedItems.length;
    const totalPages = Math.ceil(totalItems / paginationState.itemsPerPage);
    
    // 기존 페이지네이션 제거
    const existingPagination = document.getElementById('pagination');
    if (existingPagination) {
        existingPagination.remove();
    }
    
    if (totalPages <= 1) {
        // 페이지네이션이 필요 없으면 모든 항목 표시
        sortedItems.forEach(item => item.style.display = '');
        return;
    }
    
    // 현재 페이지 범위 계산
    const start = (paginationState.currentPage - 1) * paginationState.itemsPerPage;
    const end = start + paginationState.itemsPerPage;
    
    // 모든 항목 숨기기
    sortedItems.forEach(item => item.style.display = 'none');
    
    // 현재 페이지 항목만 표시
    for (let i = start; i < end && i < sortedItems.length; i++) {
        sortedItems[i].style.display = '';
        // DOM에서 재배치 (정렬된 순서로)
        sortedItems[i].parentElement.appendChild(sortedItems[i]);
    }
    
    // 페이지네이션 버튼 생성
    const paginationContainer = document.createElement('div');
    paginationContainer.className = 'pagination';
    paginationContainer.id = 'pagination';
    
    // 이전 버튼
    const prevBtn = document.createElement('button');
    prevBtn.textContent = '이전';
    prevBtn.disabled = paginationState.currentPage === 1;
    prevBtn.addEventListener('click', () => {
        if (paginationState.currentPage > 1) {
            paginationState.currentPage--;
            renderPagination();
        }
    });
    paginationContainer.appendChild(prevBtn);
    
    // 페이지 번호 버튼
    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= paginationState.currentPage - 2 && i <= paginationState.currentPage + 2)) {
            const pageBtn = document.createElement('button');
            pageBtn.textContent = i;
            pageBtn.className = i === paginationState.currentPage ? 'active' : '';
            pageBtn.addEventListener('click', () => {
                paginationState.currentPage = i;
                renderPagination();
            });
            paginationContainer.appendChild(pageBtn);
        } else if (i === paginationState.currentPage - 3 || i === paginationState.currentPage + 3) {
            const ellipsis = document.createElement('span');
            ellipsis.textContent = '...';
            ellipsis.style.padding = '8px';
            paginationContainer.appendChild(ellipsis);
        }
    }
    
    // 다음 버튼
    const nextBtn = document.createElement('button');
    nextBtn.textContent = '다음';
    nextBtn.disabled = paginationState.currentPage === totalPages;
    nextBtn.addEventListener('click', () => {
        if (paginationState.currentPage < totalPages) {
            paginationState.currentPage++;
            renderPagination();
        }
    });
    paginationContainer.appendChild(nextBtn);
    
    // 페이지네이션 컨테이너 추가
    const container = document.querySelector('.container');
    if (container) {
        container.appendChild(paginationContainer);
    }
}

// 인용 정보 로드
async function loadCitationInfo(paperId) {
    try {
        const response = await fetch(`https://api.semanticscholar.org/graph/v1/paper/arXiv:${paperId}?fields=citationCount`);
        if (response.ok) {
            const data = await response.json();
            return data.citationCount || 0;
        }
    } catch (error) {
        console.log('Citation info not available');
    }
    return null;
}

// 태그 필터 기능
function initTagFilter() {
    // 태그 클릭 이벤트 리스너
    document.querySelectorAll('.tag').forEach(tag => {
        tag.addEventListener('click', function(e) {
            e.stopPropagation();
            
            const tagText = this.textContent.trim();
            
            // 토글: 이미 활성화되어 있으면 비활성화, 아니면 활성화
            const isActive = this.classList.contains('active');
            
            if (isActive) {
                // 모든 태그 비활성화
                document.querySelectorAll('.tag').forEach(t => t.classList.remove('active'));
                
                // 모든 논문 표시
                paginationState.allItems.forEach(item => {
                    item.setAttribute('data-tag-match', 'true');
                });
            } else {
                // 모든 태그에서 active 클래스 제거
                document.querySelectorAll('.tag').forEach(t => t.classList.remove('active'));
                
                // 클릭된 태그에 active 추가
                this.classList.add('active');
                
                // 현재 활성화된 태그 필터 확인
                const activeTags = Array.from(document.querySelectorAll('.tag.active')).map(t => t.textContent.trim());
                
                // 논문 필터링
                paginationState.allItems.forEach(item => {
                    const tags = Array.from(item.querySelectorAll('.tag')).map(t => t.textContent.trim());
                    const hasActiveTag = activeTags.length === 0 || activeTags.some(activeTag => tags.includes(activeTag));
                    
                    if (hasActiveTag) {
                        item.setAttribute('data-tag-match', 'true');
                    } else {
                        item.setAttribute('data-tag-match', 'false');
                    }
                });
            }
            
            // 페이지네이션 재렌더링
            if (window.location.pathname.includes('archive')) {
                paginationState.currentPage = 1;
                renderPagination();
            } else {
                // 메인 페이지에서는 단순 필터링
                paginationState.allItems.forEach(item => {
                    const tagMatch = item.getAttribute('data-tag-match');
                    if (tagMatch === 'false') {
                        item.style.display = 'none';
                    } else {
                        item.style.display = '';
                    }
                });
            }
            
            updateResultCount();
        });
    });
    
    // 태그 필터 초기화
    document.querySelectorAll('.paper-item').forEach(item => {
        item.setAttribute('data-tag-match', 'true');
    });
}

// 탭 스위칭
function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const targetPanel = this.getAttribute('aria-controls');
            const panel = document.getElementById(targetPanel);
            
            if (!panel) return;
            
            // 모든 탭 비활성화
            document.querySelectorAll('.tab-button').forEach(btn => {
                btn.classList.remove('active');
                btn.setAttribute('aria-selected', 'false');
            });
            
            // 모든 패널 숨기기
            document.querySelectorAll('[role="tabpanel"]').forEach(p => {
                p.style.display = 'none';
            });
            
            // 선택된 탭 활성화
            this.classList.add('active');
            this.setAttribute('aria-selected', 'true');
            panel.style.display = '';
            
            // 검색/정렬 재초기화
            setTimeout(() => {
                initSearch();
                initSort();
                initTagFilter();
                if (window.location.pathname.includes('archive')) {
                    initPagination();
                }
            }, 100);
        });
    });
}

// 초기화
document.addEventListener('DOMContentLoaded', function() {
    initDarkMode();
    initScrollTop();
    initBookmarks();
    initTabs();
    
    // 페이지네이션은 아카이브 페이지에서만
    if (window.location.pathname.includes('archive')) {
        // 모든 항목을 검색 매치로 초기화
        document.querySelectorAll('.paper-item').forEach(item => {
            item.setAttribute('data-search-match', 'true');
            item.setAttribute('data-tag-match', 'true');
        });
        initPagination(10);
    } else {
        // 메인 페이지에서도 태그 매치 초기화
        document.querySelectorAll('.paper-item').forEach(item => {
            item.setAttribute('data-tag-match', 'true');
        });
    }
    
    // 검색과 정렬은 페이지네이션 이후에 초기화
    setTimeout(() => {
        initSearch();
        initSort();
        initTagFilter();
    }, 100);
    
    // 인용 정보 로드 (지연 로드)
    setTimeout(() => {
        document.querySelectorAll('[data-paper-id]').forEach(el => {
            const paperId = el.dataset.paperId;
            if (paperId) {
                loadCitationInfo(paperId).then(count => {
                    if (count !== null && count > 0) {
                        const citationEl = el.querySelector('.citation-count');
                        if (citationEl) {
                            citationEl.textContent = `인용 ${count}회`;
                        }
                    }
                });
            }
        });
    }, 1000);
});

