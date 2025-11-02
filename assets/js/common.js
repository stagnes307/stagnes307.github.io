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

// 검색 기능
function initSearch() {
    const searchBox = document.getElementById('searchBox');
    if (!searchBox) return;
    
    const paperItems = document.querySelectorAll('.paper-item');
    
    searchBox.addEventListener('input', function() {
        const query = this.value.toLowerCase().trim();
        
        paperItems.forEach(item => {
            const title = item.querySelector('.paper-title')?.textContent.toLowerCase() || '';
            const authors = item.querySelector('.paper-meta')?.textContent.toLowerCase() || '';
            const summary = item.querySelector('.paper-summary-content')?.textContent.toLowerCase() || '';
            
            if (title.includes(query) || authors.includes(query) || summary.includes(query)) {
                item.style.display = '';
            } else {
                item.style.display = 'none';
            }
        });
        
        updateResultCount();
    });
}

// 정렬 기능
function initSort() {
    const sortSelect = document.getElementById('sortSelect');
    if (!sortSelect) return;
    
    sortSelect.addEventListener('change', function() {
        const container = document.querySelector('.container');
        const paperItems = Array.from(document.querySelectorAll('.paper-item'));
        
        const sortBy = this.value;
        
        paperItems.sort((a, b) => {
            switch(sortBy) {
                case 'date-desc':
                    const dateA = new Date(a.querySelector('.paper-meta span:last-child')?.textContent.split(':')[1]?.trim() || '');
                    const dateB = new Date(b.querySelector('.paper-meta span:last-child')?.textContent.split(':')[1]?.trim() || '');
                    return dateB - dateA;
                case 'date-asc':
                    const dateA2 = new Date(a.querySelector('.paper-meta span:last-child')?.textContent.split(':')[1]?.trim() || '');
                    const dateB2 = new Date(b.querySelector('.paper-meta span:last-child')?.textContent.split(':')[1]?.trim() || '');
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
        
        // 재배치
        const parent = paperItems[0]?.parentElement;
        if (parent) {
            paperItems.forEach(item => parent.appendChild(item));
        }
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

// 페이지네이션
function initPagination(itemsPerPage = 10) {
    const paperItems = Array.from(document.querySelectorAll('.paper-item'));
    const totalItems = paperItems.length;
    const totalPages = Math.ceil(totalItems / itemsPerPage);
    
    if (totalPages <= 1) return;
    
    let currentPage = 1;
    const paginationContainer = document.createElement('div');
    paginationContainer.className = 'pagination';
    paginationContainer.id = 'pagination';
    
    function renderPage(page) {
        const start = (page - 1) * itemsPerPage;
        const end = start + itemsPerPage;
        
        paperItems.forEach((item, index) => {
            if (index >= start && index < end) {
                item.style.display = '';
            } else {
                item.style.display = 'none';
            }
        });
        
        // 페이지네이션 버튼 생성
        paginationContainer.innerHTML = '';
        
        // 이전 버튼
        const prevBtn = document.createElement('button');
        prevBtn.textContent = '이전';
        prevBtn.disabled = page === 1;
        prevBtn.addEventListener('click', () => renderPage(page - 1));
        paginationContainer.appendChild(prevBtn);
        
        // 페이지 번호 버튼
        for (let i = 1; i <= totalPages; i++) {
            if (i === 1 || i === totalPages || (i >= page - 2 && i <= page + 2)) {
                const pageBtn = document.createElement('button');
                pageBtn.textContent = i;
                pageBtn.className = i === page ? 'active' : '';
                pageBtn.addEventListener('click', () => renderPage(i));
                paginationContainer.appendChild(pageBtn);
            } else if (i === page - 3 || i === page + 3) {
                const ellipsis = document.createElement('span');
                ellipsis.textContent = '...';
                ellipsis.style.padding = '8px';
                paginationContainer.appendChild(ellipsis);
            }
        }
        
        // 다음 버튼
        const nextBtn = document.createElement('button');
        nextBtn.textContent = '다음';
        nextBtn.disabled = page === totalPages;
        nextBtn.addEventListener('click', () => renderPage(page + 1));
        paginationContainer.appendChild(nextBtn);
    }
    
    // 페이지네이션 컨테이너 추가
    const container = document.querySelector('.container');
    if (container) {
        container.appendChild(paginationContainer);
        renderPage(1);
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
                initPagination();
            }, 100);
        });
    });
}

// 초기화
document.addEventListener('DOMContentLoaded', function() {
    initDarkMode();
    initScrollTop();
    initBookmarks();
    initSearch();
    initSort();
    initTabs();
    
    // 페이지네이션은 아카이브 페이지에서만
    if (window.location.pathname.includes('archive')) {
        initPagination(10);
    }
    
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

