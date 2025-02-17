// ✅ 전역 변수 선언
let currentContract = ""; // 계약서 내용을 저장할 변수
let selectedContractType = "";  // 선택된 계약서 유형
let mediaRecorder;
let audioChunks = [];
let isRecording = false;

document.addEventListener('DOMContentLoaded', function () {
    console.log("✅ Document Loaded!");

    const sendMessageBtn = document.getElementById('send-message');
    const messageInput = document.getElementById('message-input');

    if (messageInput && sendMessageBtn) {
        // ✅ 메시지 입력창 이벤트 리스너
        messageInput.addEventListener('keydown', function (event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                extractContractFields(); //
            } else if (event.key === 'Enter' && event.shiftKey) {
                event.preventDefault();
                messageInput.value += "\n"; // 새 줄 추가
            }
        });

        // ✅ 전송 버튼 클릭 이벤트 리스너
        sendMessageBtn.addEventListener('click', function () {
            extractContractFields();
        });
    }
});

document.addEventListener('DOMContentLoaded', function () {
    console.log("✅ Document Loaded!");

    const recordBtn = document.getElementById('record-btn');
    if (recordBtn) {
        console.log("🎤 Record button detected!");
        recordBtn.addEventListener('click', function () {
            if (!isRecording) {
                startRecording();
            } else {
                stopRecording();
            }
        });
    } else {
        console.error("❌ can't find the record button.");
    }
});

// 🎤 음성 녹음 시작
function startRecording() {
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = event => audioChunks.push(event.data);
            mediaRecorder.onstop = sendAudioToServer;
            mediaRecorder.start();

            isRecording = true;
            document.getElementById('record-btn').textContent = "⏹️ 녹음 중지";
            console.log("🎙️ Start recording...");
        })
        .catch(error => {
            console.error("❌ microphone error:", error);
            alert("Microphone use not permitted. Check your web browser settings.");
        });
}

// ⏹️ 음성 녹음 중지
function stopRecording() {
    if (mediaRecorder) {
        mediaRecorder.stop();
    }
    isRecording = false;
    document.getElementById('record-btn').textContent = "🎤 voice input";
    console.log("⏹️ Recording has stopped. Converting to text...");
}

// 🎤 녹음된 오디오를 서버로 전송하여 텍스트 변환 요청
function sendAudioToServer() {
    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
    const formData = new FormData();
    formData.append("file", audioBlob);

    console.log("📤 Start transfer to voice file server...");

    fetch('/stt', {
        method: 'POST',
        body: formData
    })
    .then(response => {
        console.log(`📥 Server response status code: ${response.status}`);
        if (!response.ok) {
            throw new Error(`❌ Server response error: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log("📥 server response data:", data);

        if (data.error) {
            console.error(`❌ An error occurred: ${data.error}`);
            alert("Voice conversion failed. server error: " + data.error);
        } else if (!data.text) {
            console.error("❌ No text converted.");
            alert("The speech conversion result is empty.");
        } else {
            console.log(`📜 transcribed text: ${data.text}`);
            window.location.href = `/chat.html?query=${encodeURIComponent(data.text)}&source=voice`;
        }
    })
    .catch(error => {
        console.error("❌ server error:", error);
        alert("❌ A server error occurred. Check the console log.");
    });
}

// ✅ 페이지 로드 후 이벤트 리스너 등록
document.addEventListener('DOMContentLoaded', function () {
    console.log("✅ Document Loaded!");

    // 🔍 검색 버튼 클릭 이벤트 추가
    const searchIcon = document.querySelector(".search-icons span:last-child"); // 🔍 아이콘 선택
    if (searchIcon) {
        console.log("🔍 Search button detected!");
        searchIcon.addEventListener("click", function () {
            console.log("🔍 Search button clicked");
            startChatFromSearch();
        });
    } else {
        console.warn("⚠️ The search button (🔍) has not been clicked or does not exist.");
    }

    // ⌨️ 검색창에서 엔터(Enter) 키 입력 시 검색 실행
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                console.log("🔍 엔터키 입력됨");
                startChatFromSearch();
            }
        });
    } else {
        console.warn("⚠️ The search input box (🔍) has not been clicked or does not exist.");
    }

    // 📌 바로가기 버튼 클릭 이벤트 등록
    document.querySelectorAll('.contract-btn').forEach(button => {
        button.addEventListener('click', function () {
            const contractType = this.dataset.value;
            console.log("📌 Shortcut button clicked: ${contractType}");
            navigateToChat(contractType, 'button');
        });
    });

    // 🌐 URL에서 검색어 확인 후 챗봇 응답 실행
    const params = new URLSearchParams(window.location.search);
    const query = params.get('query');
    const source = params.get('source');

    console.log("📥 Check URL parameters:", query, source);

    if (source === 'button') {
        requestChatbotResponseFromButton(query);
    }

    if (source === 'search') {
        requestChatbotResponseFromSearch(query);
    }

    // 🔹 음성 입력으로 넘어온 경우 자동 실행
    if (query && source === "voice") {
        console.log("🎤 음성 입력 감지됨. 자동으로 챗봇 요청 시작...");
        requestChatbotResponseFromSearch(query);
    }
});

// ✅ 검색 실행 함수 (검색창에서 입력 후)
function startChatFromSearch() {
    const query = document.getElementById('search-input')?.value.trim();

    if (!query || query.length < 3) {
        appendMessage("❌ Please enter a search term of at least 3 characters.", 'bot');
        return;
    }

    const targetUrl = `/chat.html?query=${encodeURIComponent(query)}&source=search`;
    console.log(`🔗 Go to page: ${targetUrl}`);
    navigateToChat(query, 'search');
}

// ✅ 챗봇 페이지로 이동하는 함수 (검색 & 버튼 클릭)
function navigateToChat(query, source) {
    const targetUrl = `/chat.html?query=${encodeURIComponent(query)}&source=${source}`;
    console.log(`🔗 Go to page: ${targetUrl}`);
    window.location.href = targetUrl;
}

let isFetching = false; // 요청 중인지 여부

// ✅ 챗봇 응답 요청 - 바로가기 버튼 클릭 시
function requestChatbotResponseFromButton(contractType) {
    if (isFetching) {
        appendMessage("⚠️ Your request is being processed. please wait for a moment.", 'bot');
        return;
    }
    isFetching = true;

    appendMessage(`📑 You have selected ${contractType}.`, 'bot');
    appendMessage("📌 I am analyzing the information required for the contract...", 'bot');

    fetch('/chatbot-response', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: contractType, source: 'button' })
    })
    .then(response => response.json())
    .then(data => {
        handleChatbotResponse(data);
    })
    .catch(error => {
        console.error("❌ Server error occurred:", error);
        appendMessage("❌ A server error occurred. Please try again.", 'bot');
    })
    .finally(() => isFetching = false); // 요청 완료 후 상태 해제
}

// ✅ 챗봇 응답 요청 - 검색창 입력 후
function requestChatbotResponseFromSearch(userMessage) {
    if (isFetching) {
        appendMessage("⚠️ Your request is being processed. please wait for a moment.", 'bot');
        return;
    }
    isFetching = true;

    appendMessage(`🔍 ${userMessage}`, 'user');
    appendMessage("📌 Looking for relevant contracts...", 'bot');

    fetch('/chatbot-response', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage, source: 'search' })
    })
    .then(response => response.json())
    .then(data => {
        handleChatbotResponse(data);
    })
    .catch(error => {
        console.error("❌ Server error occurred:", error);
        appendMessage("❌ A server error occurred. Please try again.", 'bot');
    })
    .finally(() => isFetching = false); // 요청 완료 후 상태 해제
}

// ✅ 챗봇 응답 핸들링 함수
function handleChatbotResponse(data) {
    if (data.error) {
        appendMessage("❌ " + data.error, 'bot');
        return;
    }

    if (data.suggested_contract) {
        appendMessage(`📌 ${data.suggested_contract}`, 'bot');
    }

    if (data.required_fields) {
        appendMessage("📌 Information needed to prepare a contract:", 'bot');
        appendMessage(`${data.required_fields}`, 'bot');  // 한 개의 메시지로 출력
    }

    if (data.contract) {
        currentContract = data.contract; // ✅ 계약서 내용 저장
        selectedContractType = data.contract_type; // ✅ 계약서 유형 저장

        // ✅ <pre> 태그가 중복으로 들어가지 않도록 정리
        let cleanedContract = data.contract.replace(/<pre>/g, "").replace(/<\/pre>/g, "");

        appendMessage("📜 Sample contract example:", 'bot');
        appendMessage(`${cleanedContract}`, 'bot', true);
        addDownloadButton();
        // 사용자 입력
    }
}

// ✅ 채팅창에 메시지 추가
function appendMessage(message, sender) {
    const chatBox = document.getElementById('chat-box');
    if (!chatBox) {
        console.error("❌ The chat-box element was not found.");
        return;
    }

    const messageDiv = document.createElement('div');
    messageDiv.className = sender === 'bot' ? 'bot-message' : 'user-message';
    messageDiv.textContent = message;

    chatBox.appendChild(messageDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// ✅ 엔터키 입력 시 계약서 정보 업데이트
document.getElementById('text-input').addEventListener('keydown', function (event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        extractContractFields();
    }
});

// ✅ 전송 버튼 클릭 시 계약서 정보 업데이트
document.getElementById('send-btn').addEventListener('click', function () {
    extractContractFields();
});

// ✅ 사용자 입력에서 계약서 필드 추출 요청
function extractContractFields() {
    const userInput = document.getElementById('text-input').value.trim();
    if (!userInput) return;

    appendMessage(userInput, 'user'); // 사용자가 입력한 메시지를 채팅창에 추가
    document.getElementById('text-input').value = ''; // 입력창 초기화

    appendMessage("📌 Analyzing your input...", 'bot');

    fetch('/extract-fields', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_input: userInput })
    })
    .then(response => response.json())
    .then(data => {
        if (data.extracted_fields && Object.keys(data.extracted_fields).length > 0) {
            const extracted = data.extracted_fields;
            localStorage.setItem(`contract_fields_${Date.now()}`, JSON.stringify(extracted));
            updateContract(extracted);
        } else {
            appendMessage("❌ Item extraction failed. Please try again.", 'bot');
        }
    })
    .catch(error => {
        console.error("JSON parsing error:", error);
        appendMessage("❌ Server response is incorrect. Please try again.", 'bot');
    });
}

// ✅ 계약서 업데이트 요청
function updateContract(extractedFields) {
    if (!currentContract) {
        console.error("There are currently no contract details.");
        appendMessage("❌ Contract update failed.", 'bot');
        return;
    }

    appendMessage("📌 Updating your contract...", 'bot');

    // ✅ 전송 데이터 로그 출력
    console.log("data to transfer:", JSON.stringify({
        current_contract: currentContract,
        contract_type: selectedContractType,
        extracted_fields: extractedFields
    }));

    fetch('/update-contract', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            current_contract: currentContract,
            contract_type: selectedContractType,
            extracted_fields: extractedFields
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.contract) {
            currentContract = data.contract;
            appendMessage("📜 updated contract:", 'bot');
            appendMessage(`${data.contract}`, 'bot', true);
            addDownloadButton();
        } else {
            appendMessage("❌ Contract update failed.", 'bot');
        }
    })
    .catch(error => {
        console.error("sever error:", error);
        appendMessage("❌ A server error occurred.", 'bot');
    });
}

// ✅ 계약서 다운로드 기능 추가
function downloadContract() {
    fetch('/download', { method: 'GET' })
    .then(response => response.ok ? response.blob() : Promise.reject())
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'completed_contract.docx';
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
    })
    .catch(() => appendMessage("❌ The contract file cannot be downloaded.", 'bot'));
}

// ✅ 다운로드 버튼 추가
function addDownloadButton() {
    const chatBox = document.getElementById('chat-box');

    // 기존 버튼 제거 (중복 생성 방지)
    const existingButton = document.getElementById('download-btn');
    if (existingButton) existingButton.remove();

    const downloadButton = document.createElement('button');
    downloadButton.id = 'download-btn';
    downloadButton.textContent = "📥 Download contract";

    downloadButton.addEventListener('click', () => {
        downloadButton.disabled = true;
        downloadButton.textContent = "⏳ Downloading...";

        fetch('/download', { method: 'GET' })
        .then(response => response.ok ? response.blob() : Promise.reject())
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'completed_contract.docx';
            document.body.appendChild(a);
            a.click();
            a.remove();
            window.URL.revokeObjectURL(url);

            downloadButton.textContent = "📥 Download complete!";
            setTimeout(() => downloadButton.textContent = "📥 Download contract", 3000);
        })
        .catch(() => {
            appendMessage("❌ The contract file cannot be downloaded.", 'bot');
            downloadButton.textContent = "📥 Download contract";
        })
        .finally(() => downloadButton.disabled = false);
    });

    chatBox.appendChild(document.createElement('br'));
    chatBox.appendChild(downloadButton);
}
