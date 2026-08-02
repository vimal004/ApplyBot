/* ApplyBot Background Service Worker (Manifest V3) */

// Setup context menu on installation
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "applybot-autofill-menu",
    title: "⚡ ApplyBot: 1-Tap Auto-Fill Form",
    contexts: ["page", "editable", "frame"]
  });
  console.log("[ApplyBot Extension] Background service worker initialized.");
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "applybot-autofill-menu" && tab && tab.id) {
    chrome.tabs.sendMessage(tab.id, { action: "FILL_FORM" }, (res) => {
      if (chrome.runtime.lastError) {
        console.warn("[ApplyBot Extension] Context menu message error:", chrome.runtime.lastError.message);
      }
    });
  }
});

// Listener for background API proxy requests from content/popup scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "FETCH_BACKEND_PROFILE") {
    fetch("http://localhost:5050/api/profile")
      .then(res => res.json())
      .then(data => sendResponse({ success: true, profile: data }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true; // Keep response channel open for async fetch
  }
  
  if (request.action === "ASK_AI_QUESTION") {
    fetch("http://localhost:5050/api/answer_question", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request.payload)
    })
      .then(res => res.json())
      .then(data => sendResponse({ success: true, answer: data.answer }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }
});
