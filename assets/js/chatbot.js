// /assets/js/chatbot.js

document.addEventListener('DOMContentLoaded', () => {
    const sendButton = document.getElementById('send-button');
    const userInput = document.getElementById('user-input');
    const chatWindow = document.getElementById('chat-window');

    // --- Configuration ---
    // This placeholder will be replaced by the GitHub Actions workflow.
    let OPENROUTER_API_KEY = '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';
    const OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions';
    const OPENROUTER_MODEL = 'google/gemini-1.5-flash'; // Or any other OpenRouter model you prefer

    let paperDataCache = null;

    // --- Functions ---

    /**
     * Fetches and caches paper data from YAML files.
     */
    async function loadPaperData() {
        if (paperDataCache) {
            return paperDataCache;
        }
        try {
            const anodeResponse = await fetch('/_data/anode/archive.yml');
            const cathodeResponse = await fetch('/_data/cathode/archive.yml');

            if (!anodeResponse.ok || !cathodeResponse.ok) {
                throw new Error('Failed to fetch paper data.');
            }

            const anodeText = await anodeResponse.text();
            const cathodeText = await cathodeResponse.text();

            const anodeData = jsyaml.load(anodeText);
            const cathodeData = jsyaml.load(cathodeText);

            paperDataCache = [...(anodeData || []), ...(cathodeData || [])];
            return paperDataCache;
        } catch (error) {
            console.error('Error loading paper data:', error);
            addMessageToChat('봇', '논문 데이터를 불러오는 데 실패했습니다.');
            return null;
        }
    }

    /**
     * Adds a message to the chat window.
     * @param {string} sender - '사용자' or '봇'.
     * @param {string} message - The message content.
     * @param {boolean} isLoading - If the message is a loading indicator.
     * @returns {HTMLElement} The created message element.
     */
    function addMessageToChat(sender, message, isLoading = false) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', sender === '사용자' ? 'user-message' : 'bot-message');
        if (isLoading) {
            messageElement.classList.add('loading');
        }
        
        const p = document.createElement('p');
        p.innerHTML = window.marked.parse(message); // Use marked to parse markdown
        messageElement.appendChild(p);
        chatWindow.appendChild(messageElement);
        chatWindow.scrollTop = chatWindow.scrollHeight;
        return messageElement;
    }

    /**
     * Handles the user's query.
     */
    async function handleQuery() {
        const query = userInput.value.trim();
        if (!query) return;

        addMessageToChat('사용자', query);
        userInput.value = '';
        const loadingMessage = addMessageToChat('봇', '답변을 생성 중입니다', true);

        if (OPENROUTER_API_KEY === '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') {
            loadingMessage.innerHTML = '<p>오류: 사이트 관리자에 의해 API 키가 설정되지 않았습니다. 챗봇을 사용할 수 없습니다.</p>';
            loadingMessage.classList.remove('loading');
            return;
        }

        const papers = await loadPaperData();
        if (!papers) {
            loadingMessage.innerHTML = '<p>오류: 논문 데이터가 없어 답변을 생성할 수 없습니다.</p>';
            loadingMessage.classList.remove('loading');
            return;
        }

        // Create a simplified text representation of papers for the prompt
        const paperContext = papers.slice(0, 100).map(p => 
            `- 제목: ${p.title_en}\n  저자: ${p.authors}\n  요약: ${p.summary.replace(/<[^>]+>/g, ' ')}\n`
        ).join('\n');

        const prompt = `
            당신은 2차전지 논문 전문 AI 챗봇입니다.
            아래에 제공된 논문 목록을 참고하여 사용자의 질문에 답변해주세요.
            답변은 반드시 제공된 논문 내용에 근거해야 합니다.
            관련된 논문을 찾으면, 해당 논문의 제목과 링크(예: [제목](링크))를 꼭 포함하여 자연스러운 문장으로 설명해주세요.
            
            [사용자 질문]
            ${query}

            [논문 데이터]
            ${paperContext}
        `;

        try {
            const response = await fetch(OPENROUTER_API_URL, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${OPENROUTER_API_KEY}`,
                    'Content-Type': 'application/json',
                    'HTTP-Referer': 'https://stagnes307.github.io', // Replace with your actual domain
                    'X-Title': 'Battery Paper Chatbot'
                },
                body: JSON.stringify({
                    model: OPENROUTER_MODEL,
                    messages: [
                        { role: 'user', content: prompt }
                    ]
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error.message || 'API 요청에 실패했습니다.');
            }

            const data = await response.json();
            const botResponse = data.choices[0].message.content;
            
            loadingMessage.innerHTML = marked.parse(botResponse); // Update message with final response
            loadingMessage.classList.remove('loading');

        } catch (error) {
            console.error('Error with OpenRouter API:', error);
            loadingMessage.innerHTML = `<p>AI 답변 생성 중 오류가 발생했습니다: ${error.message}</p>`;
            loadingMessage.classList.remove('loading');
        }
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }

    // --- Event Listeners ---
    sendButton.addEventListener('click', handleQuery);
    userInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            handleQuery();
        }
    });

    // --- Initial Load ---
    loadPaperData(); // Pre-load data on page load
});
