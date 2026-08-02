/* ApplyBot Background Service Worker v1.1 */

// Setup context menu on installation
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "applybot-autofill-menu",
    title: "⚡ ApplyBot: 1-Tap Auto-Fill Form",
    contexts: ["page", "editable", "frame"]
  });
  console.log("[ApplyBot] Background service worker v1.1 initialized.");
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "applybot-autofill-menu" && tab && tab.id) {
    chrome.tabs.sendMessage(tab.id, { action: "FILL_FORM" }, (res) => {
      if (chrome.runtime.lastError) {
        console.warn("[ApplyBot] Context menu error:", chrome.runtime.lastError.message);
      }
    });
  }
});

// Message listener for background API proxy
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {

  // Fetch candidate profile from backend
  if (request.action === "FETCH_BACKEND_PROFILE") {
    fetch("http://localhost:5050/api/profile")
      .then(res => res.json())
      .then(data => sendResponse({ success: true, profile: data }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }

  // AI question with optional JD + page context
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

  // Send cold-outreach email via backend
  if (request.action === "SEND_EMAIL") {
    fetch("http://localhost:5050/api/send_email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request.payload)
    })
      .then(res => res.json())
      .then(data => sendResponse({ success: data.success, message: data.message }))
      .catch(err => sendResponse({ success: false, message: err.message }));
    return true;
  }
});
