/**
 * PlacidWay Medical Tourism Knowledge Assistant - Web Client
 * Connects to FastAPI backend, supports multi-pattern switching,
 * citation rendering, clinical disclaimers, lead capture, and diagnostics.
 */

document.addEventListener("DOMContentLoaded", () => {
    // Multi-Chat Session Management with LocalStorage
    const STORAGE_KEY = "placidway_chats_v1";
    let chats = [];
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) chats = JSON.parse(stored);
    } catch (e) {
        chats = [];
    }

    let activeChatId = null;

    function saveChats() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(chats));
        } catch (e) {
            console.error("Failed to save chats", e);
        }
    }

    // DOM Elements
    const chatForm = document.getElementById("chatForm");
    const userInput = document.getElementById("userInput");
    const chatMessages = document.getElementById("chatMessages");
    const heroSuggestions = document.getElementById("heroSuggestions");
    const sendBtn = document.getElementById("sendBtn");
    const refreshKbBtn = document.getElementById("refreshKbBtn");
    const newChatBtn = document.getElementById("newChatBtn");
    const chatHistoryList = document.getElementById("chatHistoryList");

    // Modal elements
    const leadModal = document.getElementById("leadModal");
    const closeLeadModal = document.getElementById("closeLeadModal");
    const cancelLeadBtn = document.getElementById("cancelLeadBtn");
    const leadForm = document.getElementById("leadForm");
    const manualLeadBtn = document.getElementById("manualLeadBtn");

    const diagnosticsModal = document.getElementById("diagnosticsModal");
    const closeDiagnosticsModal = document.getElementById("closeDiagnosticsModal");
    const diagnosticsTitle = document.getElementById("diagnosticsTitle");
    const diagnosticsSubtitle = document.getElementById("diagnosticsSubtitle");
    const diagnosticsContent = document.getElementById("diagnosticsContent");
    const openLeadsBtn = document.getElementById("openLeadsBtn");
    const openGapsBtn = document.getElementById("openGapsBtn");
    const leadsCountBadge = document.getElementById("leadsCountBadge");
    const gapsCountBadge = document.getElementById("gapsCountBadge");
    const toastContainer = document.getElementById("toastContainer");

    // Auto-expand textarea
    userInput.addEventListener("input", function () {
        this.style.height = "auto";
        this.style.height = (this.scrollHeight) + "px";
        if (this.value.trim().length > 0) {
            sendBtn.removeAttribute("disabled");
        }
    });

    // Enter to submit (Shift+Enter for newline)
    userInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event("submit"));
        }
    });

    // Create New Chat Session
    function createNewChat() {
        const newId = "pw_chat_" + Math.random().toString(36).substring(2, 10);
        const newChat = {
            id: newId,
            title: "New Conversation",
            messages: [],
            createdAt: Date.now(),
        };
        chats.unshift(newChat);
        saveChats();
        switchToChat(newId);
    }

    // Switch Active Chat Session
    function switchToChat(chatId) {
        activeChatId = chatId;
        const chat = chats.find(c => c.id === chatId);
        if (!chat) return;

        chatMessages.innerHTML = "";

        if (!chat.messages || chat.messages.length === 0) {
            // Unstarted chat: show centered hero suggestions in middle of screen
            if (heroSuggestions) heroSuggestions.classList.remove("hidden");
            if (chatMessages) chatMessages.classList.add("hidden");
        } else {
            // Active chat: hide hero suggestions and render message bubbles
            if (heroSuggestions) heroSuggestions.classList.add("hidden");
            if (chatMessages) chatMessages.classList.remove("hidden");
            chat.messages.forEach(msg => {
                appendMessage(msg.role, msg.content, msg.meta);
            });
        }

        renderChatHistoryList();
        userInput.value = "";
        userInput.style.height = "auto";
        userInput.focus();
    }

    // Delete Chat Session
    function deleteChat(chatId, e) {
        if (e) e.stopPropagation();
        chats = chats.filter(c => c.id !== chatId);
        saveChats();
        if (activeChatId === chatId) {
            if (chats.length > 0) {
                switchToChat(chats[0].id);
            } else {
                createNewChat();
            }
        } else {
            renderChatHistoryList();
        }
    }

    // Render Conversation List in Sidebar
    function renderChatHistoryList() {
        if (!chatHistoryList) return;
        chatHistoryList.innerHTML = "";

        if (chats.length === 0) {
            chatHistoryList.innerHTML = `<div class="chat-history-empty">No conversations yet.<br>Click "New Chat" to begin.</div>`;
            return;
        }

        chats.forEach(c => {
            const item = document.createElement("div");
            item.className = `chat-history-item ${c.id === activeChatId ? "active" : ""}`;
            item.innerHTML = `
                <span class="chat-item-title" title="${c.title}">${c.title}</span>
                <button class="chat-item-delete" title="Delete conversation">✕</button>
            `;
            item.addEventListener("click", () => switchToChat(c.id));
            item.querySelector(".chat-item-delete").addEventListener("click", (e) => deleteChat(c.id, e));
            chatHistoryList.appendChild(item);
        });
    }

    if (newChatBtn) {
        newChatBtn.addEventListener("click", () => {
            createNewChat();
        });
    }

    // Hero Prompts (Centered in Middle of Screen)
    document.querySelectorAll(".hero-prompt-card").forEach(card => {
        card.addEventListener("click", () => {
            const prompt = card.getAttribute("data-prompt");
            if (prompt) {
                userInput.value = prompt;
                chatForm.dispatchEvent(new Event("submit"));
            }
        });
    });

    // Markdown Formatter (Simple, robust lightweight renderer)
    function formatMarkdown(text) {
        if (!text) return "";
        let formatted = text
            // Escape HTML entities
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

        // Code blocks
        formatted = formatted.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');

        // Bold
        formatted = formatted.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

        // Italic
        formatted = formatted.replace(/\*(.*?)\*/g, "<em>$1</em>");

        // Headers
        formatted = formatted.replace(/^### (.*$)/gim, '<h4 style="margin: 12px 0 6px; font-weight:700;">$1</h4>');
        formatted = formatted.replace(/^## (.*$)/gim, '<h3 style="margin: 14px 0 8px; font-weight:700;">$1</h3>');

        // Lists
        formatted = formatted.replace(/^\* (.*$)/gim, '<li>$1</li>');
        formatted = formatted.replace(/^- (.*$)/gim, '<li>$1</li>');
        formatted = formatted.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

        // Markdown tables (detect table lines)
        const lines = formatted.split("\n");
        let inTable = false;
        let tableHtml = "";
        let finalLines = [];

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();
            if (line.startsWith("|") && line.endsWith("|")) {
                if (!inTable) {
                    inTable = true;
                    tableHtml = "<div class='table-responsive'><table>";
                }
                const cells = line.split("|").slice(1, -1).map(c => c.trim());
                if (line.includes("---")) {
                    // separator line, skip
                    continue;
                }
                tableHtml += "<tr>";
                cells.forEach(c => {
                    tableHtml += `<td>${c}</td>`;
                });
                tableHtml += "</tr>";
            } else {
                if (inTable) {
                    inTable = false;
                    tableHtml += "</table></div>";
                    finalLines.push(tableHtml);
                    tableHtml = "";
                }
                finalLines.push(line);
            }
        }
        if (inTable) {
            tableHtml += "</table></div>";
            finalLines.push(tableHtml);
        }

        // Paragraphs
        return finalLines
            .map(l => (l.startsWith("<") || l.length === 0) ? l : `<p>${l}</p>`)
            .join("\n");
    }

    // Render Bottom-Left Source Box with Hover Dropdown (Matches Wireframe)
    function renderSourceDropdown(citations) {
        if (!citations || citations.length === 0) return null;

        const wrapper = document.createElement("div");
        wrapper.className = "source-tag-wrapper";

        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "source-tag-btn";
        btn.setAttribute("aria-label", "View canonical PlacidWay source citations");
        btn.innerHTML = `
            <span >Source</span></ br>
            <span class="source-tag-count">${citations.length}</span>
        `;

        const dropdown = document.createElement("div");
        dropdown.className = "source-dropdown";

        const header = document.createElement("div");
        header.className = "source-dropdown-header";
        header.textContent = `Verified Sources (${citations.length})`;
        dropdown.appendChild(header);

        const list = document.createElement("div");
        list.className = "source-dropdown-list";

        citations.forEach(c => {
            const item = document.createElement("a");
            item.href = c.url;
            item.target = "_blank";
            item.rel = "noopener noreferrer";
            item.className = "source-dropdown-item";

            const title = document.createElement("span");
            title.className = "source-item-title";
            title.textContent = c.title || "Authorized PlacidWay Page";

            const url = document.createElement("span");
            url.className = "source-item-url";
            url.textContent = c.url;

            item.appendChild(title);
            item.appendChild(url);
            list.appendChild(item);
        });

        dropdown.appendChild(list);
        wrapper.appendChild(btn);
        wrapper.appendChild(dropdown);

        return wrapper;
    }

    // Render Claude & ChatGPT Style AI Reasoning Accordion
    function renderThinkingBlock(thoughtText, duration = null, collapsed = true) {
        if (!thoughtText) return null;

        const container = document.createElement("div");
        container.className = `thinking-container ${collapsed ? "collapsed" : ""}`;

        const toggleBtn = document.createElement("button");
        toggleBtn.type = "button";
        toggleBtn.className = "thinking-toggle";
        toggleBtn.setAttribute("aria-label", "Toggle AI reasoning process");

        const statusLabel = duration ? `Thought for ${duration}s` : "Thought process";

        toggleBtn.innerHTML = `
            <div class="thinking-toggle-left">
                <span class="thinking-icon">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z"></path>
                        <path d="M9 21h6"></path>
                    </svg>
                </span>
                <span class="thinking-status">${statusLabel}</span>
            </div>
            <svg class="thinking-chevron" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
        `;

        const content = document.createElement("div");
        content.className = "thinking-content";

        const body = document.createElement("div");
        body.className = "thinking-body";
        body.innerHTML = formatMarkdown(thoughtText);
        content.appendChild(body);

        toggleBtn.addEventListener("click", () => {
            container.classList.toggle("collapsed");
        });

        container.appendChild(toggleBtn);
        container.appendChild(content);

        return container;
    }

    // Append Message to Thread
    function appendMessage(role, content, meta = null) {
        const messageDiv = document.createElement("div");
        messageDiv.className = `message ${role === "user" ? "user-message" : "assistant-message"}`;

        const avatar = document.createElement("div");
        avatar.className = "message-avatar";
        avatar.textContent = role === "user" ? "You" : "PW";

        const body = document.createElement("div");
        body.className = "message-body";

        const header = document.createElement("div");
        header.className = "message-header";

        const nameSpan = document.createElement("span");
        nameSpan.className = "sender-name";
        nameSpan.textContent = role === "user" ? "You" : "PlacidWay Assistant";

        const timeSpan = document.createElement("span");
        timeSpan.className = "time-stamp";
        const now = new Date();
        timeSpan.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        header.appendChild(nameSpan);
        header.appendChild(timeSpan);
        body.appendChild(header);

        const textDiv = document.createElement("div");
        textDiv.className = "message-text";

        // Render Claude/ChatGPT-style reasoning accordion if thought was recorded
        if (role === "assistant" && meta && meta.thought) {
            const thoughtBlock = renderThinkingBlock(meta.thought, meta.thought_duration, true);
            if (thoughtBlock) {
                textDiv.appendChild(thoughtBlock);
            }
        }

        const answerDiv = document.createElement("div");
        answerDiv.className = "bubble-content";
        answerDiv.innerHTML = formatMarkdown(content);
        textDiv.appendChild(answerDiv);

        // Render clean bottom-left Source button if citations exist
        if (role === "assistant" && meta && meta.citations && meta.citations.length > 0) {
            const sourceTag = renderSourceDropdown(meta.citations);
            if (sourceTag) {
                textDiv.appendChild(sourceTag);
            }
        }

        body.appendChild(textDiv);
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(body);
        chatMessages.appendChild(messageDiv);

        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Append Streaming Assistant Bubble with Real-Time Reasoning Traces & Claude/GPT Style Thinking
    function appendAssistantStreamingMessage() {
        const messageDiv = document.createElement("div");
        messageDiv.className = "message assistant-message";

        const avatar = document.createElement("div");
        avatar.className = "message-avatar";
        avatar.textContent = "PW";

        const body = document.createElement("div");
        body.className = "message-body";

        const header = document.createElement("div");
        header.className = "message-header";

        const nameSpan = document.createElement("span");
        nameSpan.className = "sender-name";
        nameSpan.textContent = "PlacidWay Assistant";

        const timeSpan = document.createElement("span");
        timeSpan.className = "time-stamp";
        const now = new Date();
        timeSpan.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        header.appendChild(nameSpan);
        header.appendChild(timeSpan);
        body.appendChild(header);

        // SINGLE UNIFIED BUBBLE
        const bubble = document.createElement("div");
        bubble.className = "message-text unified-bubble";

        // 1. Tool trace section inside the bubble (RAG search, CRM)
        const traceContainer = document.createElement("div");
        traceContainer.className = "trace-container hidden";

        const traceHeader = document.createElement("div");
        traceHeader.className = "trace-header";
        traceHeader.innerHTML = `
            <div class="trace-header-left">
                <span class="trace-header-check">✓</span>
                <span class="trace-status-text">Checking knowledge base...</span>
            </div>
            <svg class="trace-chevron" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><polyline points="6 9 12 15 18 9"></polyline></svg>
        `;

        const traceList = document.createElement("div");
        traceList.className = "trace-steps-list";

        traceHeader.addEventListener("click", () => {
            traceContainer.classList.toggle("collapsed");
        });

        traceContainer.appendChild(traceHeader);
        traceContainer.appendChild(traceList);
        bubble.appendChild(traceContainer);

        // 2. Claude & ChatGPT Style AI Reasoning / Thinking Container
        const thinkingContainer = document.createElement("div");
        thinkingContainer.className = "thinking-container hidden";

        const thinkingToggle = document.createElement("button");
        thinkingToggle.type = "button";
        thinkingToggle.className = "thinking-toggle";
        thinkingToggle.setAttribute("aria-label", "Toggle AI reasoning thought process");
        thinkingToggle.innerHTML = `
            <div class="thinking-toggle-left">
                <span class="thinking-icon thinking-pulsing">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 2a7 7 0 0 1 7 7c0 2.38-1.19 4.47-3 5.74V17a2 2 0 0 1-2 2h-4a2 2 0 0 1-2-2v-2.26C6.19 13.47 5 11.38 5 9a7 7 0 0 1 7-7z"></path>
                        <path d="M9 21h6"></path>
                    </svg>
                </span>
                <span class="thinking-status">Thinking...</span>
            </div>
            <svg class="thinking-chevron" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><polyline points="6 9 12 15 18 9"></polyline></svg>
        `;

        const thinkingContent = document.createElement("div");
        thinkingContent.className = "thinking-content";

        const thinkingBody = document.createElement("div");
        thinkingBody.className = "thinking-body";
        thinkingContent.appendChild(thinkingBody);

        thinkingToggle.addEventListener("click", () => {
            thinkingContainer.classList.toggle("collapsed");
        });

        thinkingContainer.appendChild(thinkingToggle);
        thinkingContainer.appendChild(thinkingContent);
        bubble.appendChild(thinkingContainer);

        // 3. Response content div INSIDE the same bubble
        const contentDiv = document.createElement("div");
        contentDiv.className = "bubble-content";
        contentDiv.innerHTML = '<span class="streaming-cursor"></span>';
        bubble.appendChild(contentDiv);

        body.appendChild(bubble);
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(body);
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        let traceCount = 0;
        let activeRunningStep = null;
        let liveThoughtText = "";
        let thoughtFinished = false;

        return {
            addTrace: (step, message, status) => {
                traceContainer.classList.remove("hidden");
                traceCount++;

                const statusEl = traceHeader.querySelector(".trace-status-text");
                if (statusEl) statusEl.textContent = message;

                if (status === "done" && activeRunningStep) {
                    const prevIcon = activeRunningStep.querySelector(".trace-step-icon");
                    if (prevIcon) {
                        prevIcon.className = "trace-step-icon step-checked";
                        prevIcon.textContent = "✓";
                    }
                    const prevText = activeRunningStep.querySelector(".trace-step-text");
                    if (prevText && message) {
                        prevText.textContent = message;
                    }
                    activeRunningStep = null;
                    return;
                }

                const stepItem = document.createElement("div");
                stepItem.className = `trace-step ${step}`;

                const isRunning = (status === "running" || step === "rag_search" || step === "crm");
                const iconClass = isRunning ? "trace-step-icon step-running" : "trace-step-icon step-checked";
                const iconContent = isRunning ? "" : "✓";

                stepItem.innerHTML = `
                    <span class="${iconClass}">${iconContent}</span>
                    <span class="trace-step-text">${message}</span>
                `;
                traceList.appendChild(stepItem);

                if (isRunning) {
                    activeRunningStep = stepItem;
                } else {
                    activeRunningStep = null;
                }

                chatMessages.scrollTop = chatMessages.scrollHeight;
            },
            addThought: (chunk) => {
                thinkingContainer.classList.remove("hidden");
                liveThoughtText += chunk;
                thinkingBody.innerHTML = formatMarkdown(liveThoughtText);
                chatMessages.scrollTop = chatMessages.scrollHeight;
            },
            finishThought: (duration) => {
                if (thoughtFinished) return;
                thoughtFinished = true;
                const icon = thinkingToggle.querySelector(".thinking-icon");
                if (icon) icon.classList.remove("thinking-pulsing");
                const statusEl = thinkingToggle.querySelector(".thinking-status");
                if (statusEl) {
                    statusEl.textContent = duration ? `Thought for ${duration}s` : "Thought process";
                }
                // Smoothly collapse thinking block like Claude/ChatGPT so user focus moves to answer
                setTimeout(() => {
                    thinkingContainer.classList.add("collapsed");
                }, 350);
            },
            update: (text) => {
                contentDiv.innerHTML = formatMarkdown(text) + '<span class="streaming-cursor"></span>';
                chatMessages.scrollTop = chatMessages.scrollHeight;
            },
            finalize: (finalText, meta = null) => {
                contentDiv.innerHTML = formatMarkdown(finalText);

                // If thoughts arrived via sync fallback or metadata
                if (meta && meta.thought && !liveThoughtText) {
                    thinkingContainer.classList.remove("hidden");
                    thinkingContainer.classList.add("collapsed");
                    const icon = thinkingToggle.querySelector(".thinking-icon");
                    if (icon) icon.classList.remove("thinking-pulsing");
                    const statusEl = thinkingToggle.querySelector(".thinking-status");
                    if (statusEl) {
                        statusEl.textContent = meta.thought_duration ? `Thought for ${meta.thought_duration}s` : "Thought process";
                    }
                    thinkingBody.innerHTML = formatMarkdown(meta.thought);
                }

                if (traceCount > 0) {
                    if (activeRunningStep) {
                        const icon = activeRunningStep.querySelector(".trace-step-icon");
                        if (icon) {
                            icon.className = "trace-step-icon step-checked";
                            icon.textContent = "✓";
                        }
                    }

                    const statusEl = traceHeader.querySelector(".trace-status-text");
                    if (statusEl) {
                        statusEl.textContent = `Completed knowledge check (${traceCount} step${traceCount > 1 ? "s" : ""})`;
                    }

                    setTimeout(() => {
                        traceContainer.classList.add("collapsed");
                    }, 1400);
                }

                if (meta && meta.citations && meta.citations.length > 0) {
                    const sourceTag = renderSourceDropdown(meta.citations);
                    if (sourceTag) {
                        bubble.appendChild(sourceTag);
                    }
                }
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }
        };
    }

    // Handle Chat Form Submit with Real-time SSE Streaming
    chatForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const message = userInput.value.trim();
        if (!message) return;

        // Ensure active chat exists
        if (!activeChatId) {
            createNewChat();
        }
        const currentChat = chats.find(c => c.id === activeChatId);

        // Hide centered hero suggestions and show chat messages thread
        if (heroSuggestions) heroSuggestions.classList.add("hidden");
        if (chatMessages) chatMessages.classList.remove("hidden");

        // If title is default, rename using query
        if (currentChat && (currentChat.title === "New Conversation" || !currentChat.title)) {
            currentChat.title = message.length > 26 ? message.substring(0, 26) + "..." : message;
            saveChats();
            renderChatHistoryList();
        }

        // Append user turn
        appendMessage("user", message);
        if (currentChat) {
            currentChat.messages.push({ role: "user", content: message, meta: null });
            saveChats();
        }

        userInput.value = "";
        userInput.style.height = "auto";
        sendBtn.setAttribute("disabled", "true");

        const streamMessage = appendAssistantStreamingMessage();

        try {
            const response = await fetch("/api/chat/stream", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: message,
                    session_id: activeChatId,
                }),
            });

            if (!response.ok) {
                // Fallback to sync chat endpoint if stream route fails
                const syncResp = await fetch("/api/chat", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ message: message, session_id: activeChatId }),
                });
                if (syncResp.ok) {
                    const syncData = await syncResp.json();
                    streamMessage.finalize(syncData.answer, syncData);
                    if (currentChat) {
                        currentChat.messages.push({ role: "assistant", content: syncData.answer, meta: syncData });
                        saveChats();
                    }
                } else {
                    const errData = await syncResp.json().catch(() => ({ detail: "Server error" }));
                    const errMsg = `⚠️ Error: ${errData.detail || "Could not process request."}`;
                    streamMessage.finalize(errMsg);
                    if (currentChat) {
                        currentChat.messages.push({ role: "assistant", content: errMsg, meta: null });
                        saveChats();
                    }
                }
                return;
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let buffer = "";
            let accumulatedText = "";
            let accumulatedThought = "";
            let thoughtDuration = null;
            let currentEvent = null;
            let completionMeta = null;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop(); // Keep partial line in buffer

                for (const line of lines) {
                    const trimmed = line.trim();
                    if (!trimmed) {
                        currentEvent = null;
                        continue;
                    }
                    if (trimmed.startsWith("event:")) {
                        currentEvent = trimmed.replace("event:", "").trim();
                    } else if (trimmed.startsWith("data:")) {
                        const jsonStr = trimmed.replace("data:", "").trim();
                        try {
                            const data = JSON.parse(jsonStr);
                            if (currentEvent === "trace" && data.message) {
                                streamMessage.addTrace(data.step || "tool", data.message, data.status || "done");
                            } else if (currentEvent === "thought" && data.text) {
                                accumulatedThought += data.text;
                                streamMessage.addThought(data.text);
                            } else if (currentEvent === "thought_done") {
                                thoughtDuration = data.duration;
                                streamMessage.finishThought(data.duration || 1);
                            } else if (currentEvent === "delta" && data.text) {
                                accumulatedText += data.text;
                                streamMessage.update(accumulatedText);
                            } else if (currentEvent === "done") {
                                completionMeta = data;
                                if (data.answer) {
                                    accumulatedText = data.answer;
                                }
                                if (data.thought && !accumulatedThought) {
                                    accumulatedThought = data.thought;
                                }
                                if (data.thought_duration && !thoughtDuration) {
                                    thoughtDuration = data.thought_duration;
                                }
                            }
                        } catch (parseErr) {
                            console.warn("SSE parse error", parseErr, jsonStr);
                        }
                    }
                }
            }

            streamMessage.finalize(accumulatedText, {
                ...completionMeta,
                thought: accumulatedThought || (completionMeta ? completionMeta.thought : null),
                thought_duration: thoughtDuration || (completionMeta ? completionMeta.thought_duration : null),
            });

            if (currentChat) {
                currentChat.messages.push({
                    role: "assistant",
                    content: accumulatedText,
                    meta: {
                        ...completionMeta,
                        thought: accumulatedThought || (completionMeta ? completionMeta.thought : null),
                        thought_duration: thoughtDuration || (completionMeta ? completionMeta.thought_duration : null),
                    },
                });
                saveChats();
            }

        } catch (error) {
            console.error("Chat streaming error:", error);
            const errText = `⚠️ Connection error: Failed to reach knowledge assistant backend. ${error.message}`;
            streamMessage.finalize(errText);
            if (currentChat) {
                currentChat.messages.push({ role: "assistant", content: errText, meta: null });
                saveChats();
            }
        } finally {
            sendBtn.removeAttribute("disabled");
        }
    });

// Lead Modal Control
function openLeadModalWindow() {
    leadModal.classList.remove("hidden");
}

function closeLeadModalWindow() {
    leadModal.classList.add("hidden");
    leadForm.reset();
}

if (manualLeadBtn) manualLeadBtn.addEventListener("click", openLeadModalWindow);
if (closeLeadModal) closeLeadModal.addEventListener("click", closeLeadModalWindow);
if (cancelLeadBtn) cancelLeadBtn.addEventListener("click", closeLeadModalWindow);

leadModal.addEventListener("click", (e) => {
    if (e.target === leadModal) closeLeadModalWindow();
});

// Submit Lead Inquiry
leadForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const submitBtn = document.getElementById("submitLeadBtn");
    submitBtn.setAttribute("disabled", "true");
    submitBtn.textContent = "Submitting...";

    const leadData = {
        name: document.getElementById("leadName").value.trim(),
        email: document.getElementById("leadEmail").value.trim(),
        phone: document.getElementById("leadPhone").value.trim() || null,
        country: document.getElementById("leadCountry").value.trim() || null,
        treatment_interest: document.getElementById("leadTreatment").value.trim(),
        notes: document.getElementById("leadNotes").value.trim() || null,
        session_id: activeChatId || "default-session",
    };

    try {
        const resp = await fetch("/api/leads", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(leadData),
        });

        if (resp.ok) {
            closeLeadModalWindow();
            showToast("Consultation request submitted! A clinical coordinator will contact you.", "success");
            updateCounts();
        } else {
            const err = await resp.json().catch(() => ({}));
            showToast(`Failed to submit: ${err.detail || "Please check inputs"}`, "error");
        }
    } catch (err) {
        showToast(`Submission error: ${err.message}`, "error");
    } finally {
        submitBtn.removeAttribute("disabled");
        submitBtn.textContent = "Submit Consultation Request";
    }
});

// Diagnostics Modal Control
function openDiagnostics(title, subtitle, tableHtml) {
    diagnosticsTitle.textContent = title;
    diagnosticsSubtitle.textContent = subtitle;
    diagnosticsContent.innerHTML = tableHtml;
    diagnosticsModal.classList.remove("hidden");
}

if (closeDiagnosticsModal) {
    closeDiagnosticsModal.addEventListener("click", () => {
        diagnosticsModal.classList.add("hidden");
    });
}

diagnosticsModal.addEventListener("click", (e) => {
    if (e.target === diagnosticsModal) diagnosticsModal.classList.add("hidden");
});

// Open Leads Table
openLeadsBtn.addEventListener("click", async () => {
    try {
        const res = await fetch("/api/leads");
        const leads = await res.json();
        if (!leads || leads.length === 0) {
            openDiagnostics("Patient Inquiries", "Captured clinical leads", "<p style='color:#64748b;'>No patient inquiries recorded yet.</p>");
            return;
        }

        let html = `
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Email</th>
                            <th>Treatment</th>
                            <th>Country</th>
                            <th>Notes</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
        leads.forEach(l => {
            html += `
                    <tr>
                        <td><strong>${escapeHtml(l.name)}</strong></td>
                        <td>${escapeHtml(l.email)}</td>
                        <td>${escapeHtml(l.treatment_interest)}</td>
                        <td>${escapeHtml(l.country || "—")}</td>
                        <td style="max-width:250px; font-size:0.8rem;">${escapeHtml(l.notes || "—")}</td>
                    </tr>
                `;
        });
        html += "</tbody></table>";
        openDiagnostics("Patient Inquiries", `${leads.length} recorded patient lead(s)`, html);
    } catch (err) {
        showToast("Failed to fetch leads: " + err.message, "error");
    }
});

// Open Content Gaps Table
openGapsBtn.addEventListener("click", async () => {
    try {
        const res = await fetch("/api/content-gaps");
        const gaps = await res.json();
        if (!gaps || gaps.length === 0) {
            openDiagnostics("Content Gaps Log", "Logged queries without grounded answers", "<p style='color:#64748b;'>No content gaps logged yet.</p>");
            return;
        }

        let html = `
                <table class="data-table">
                    <thead>
                        <tr>
                            <th>Query</th>
                            <th>Standalone Query</th>
                            <th>Session</th>
                            <th>Timestamp</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
        gaps.forEach(g => {
            html += `
                    <tr>
                        <td><strong>${escapeHtml(g.query)}</strong></td>
                        <td>${escapeHtml(g.standalone_query || "—")}</td>
                        <td><code>${escapeHtml(g.session_id || "—")}</code></td>
                        <td style="font-size:0.75rem; color:#64748b;">${escapeHtml(g.timestamp || "—")}</td>
                    </tr>
                `;
        });
        html += "</tbody></table>";
        openDiagnostics("Content Gaps Log", `${gaps.length} unanswered query gap(s) logged`, html);
    } catch (err) {
        showToast("Failed to fetch content gaps: " + err.message, "error");
    }
});

// Live Knowledge Base Refresh Action
refreshKbBtn.addEventListener("click", async () => {
    if (!confirm("Trigger a polite live re-crawl and re-indexing of all 7 authorized PlacidWay pages?")) {
        return;
    }

    const originalText = refreshKbBtn.innerHTML;
    refreshKbBtn.setAttribute("disabled", "true");
    refreshKbBtn.innerHTML = "<span class='pulse-dot' style='display:inline-block; margin-right:6px;'></span> Crawling & Re-indexing...";

    try {
        const res = await fetch("/api/refresh", { method: "POST" });
        const data = await res.json();
        if (res.ok) {
            showToast(`Knowledge Base Refreshed! Indexed ${data.chunks_indexed} chunks across ${data.urls_crawled} pages.`, "success");
        } else {
            showToast(`Refresh failed: ${data.detail || "Server error"}`, "error");
        }
    } catch (err) {
        showToast(`Refresh error: ${err.message}`, "error");
    } finally {
        refreshKbBtn.removeAttribute("disabled");
        refreshKbBtn.innerHTML = originalText;
    }
});

// Update Counts for Badges
async function updateCounts() {
    try {
        const [leadsRes, gapsRes] = await Promise.all([
            fetch("/api/leads"),
            fetch("/api/content-gaps"),
        ]);
        if (leadsRes.ok) {
            const leads = await leadsRes.json();
            leadsCountBadge.textContent = leads.length;
        }
        if (gapsRes.ok) {
            const gaps = await gapsRes.json();
            gapsCountBadge.textContent = gaps.length;
        }
    } catch (e) {
        // Silently fail badge updates
    }
}

// Initial Session Bootstrap
if (chats.length > 0) {
    switchToChat(chats[0].id);
} else {
    createNewChat();
}

updateCounts();

// Toast Notifications
function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast ${type === "success" ? "toast-success" : type === "error" ? "toast-error" : ""}`;
    toast.textContent = message;
    toastContainer.appendChild(toast);
    setTimeout(() => {
        toast.remove();
    }, 4000);
}

function escapeHtml(text) {
    if (!text) return "";
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
});

