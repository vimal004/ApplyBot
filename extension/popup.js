/* ApplyBot Popup Script */

document.addEventListener("DOMContentLoaded", () => {
  // Tab switching
  const tabs = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");

  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      tabContents.forEach(c => c.classList.remove("active"));

      tab.classList.add("active");
      const target = document.getElementById(tab.dataset.tab);
      if (target) target.classList.add("active");
    });
  });

  // Check Backend Connection & Load Stored Profile
  checkBackendConnection();
  loadStoredProfile();

  // Floating widget toggle checkbox listener
  const chkFloating = document.getElementById("chk-floating-widget");
  chrome.storage.local.get(["showFloatingButton"], (res) => {
    chkFloating.checked = res.showFloatingButton !== false;
  });
  chkFloating.addEventListener("change", () => {
    chrome.storage.local.set({ showFloatingButton: chkFloating.checked });
  });

  // 1-Tap Auto-Fill Button Click
  document.getElementById("btn-fill-now").addEventListener("click", () => {
    getProfile((profile) => {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs[0] && tabs[0].id) {
          chrome.tabs.sendMessage(tabs[0].id, { action: "FILL_FORM", profile: profile }, (response) => {
            if (chrome.runtime.lastError) {
              // Content script might not be injected yet, try injecting script manually
              chrome.scripting.executeScript({
                target: { tabId: tabs[0].id },
                files: ["content.js"]
              }, () => {
                setTimeout(() => {
                  chrome.tabs.sendMessage(tabs[0].id, { action: "FILL_FORM", profile: profile });
                }, 200);
              });
            } else {
              setQuickStatus("⚡ Form populated!");
            }
          });
        }
      });
    });
  });

  // Sync Profile from Backend Button
  document.getElementById("btn-sync-backend").addEventListener("click", () => {
    syncProfileFromBackend();
  });

  // Save Profile Button
  document.getElementById("btn-save-profile").addEventListener("click", () => {
    const updatedProfile = {
      first_name: document.getElementById("prof-first-name").value,
      last_name: document.getElementById("prof-last-name").value,
      full_name: document.getElementById("prof-full-name").value,
      email: document.getElementById("prof-email").value,
      phone: document.getElementById("prof-phone").value,
      university: document.getElementById("prof-university").value,
      degree: document.getElementById("prof-degree").value,
      gpa: document.getElementById("prof-gpa").value,
      graduation_year: document.getElementById("prof-grad-year").value,
      linkedin: document.getElementById("prof-linkedin").value,
      github: document.getElementById("prof-github").value,
      resume_gdrive_url: document.getElementById("prof-resume-url").value
    };

    chrome.storage.local.set({ profile: updatedProfile }, () => {
      setQuickStatus("Profile saved to storage!");
      alert("✅ Candidate profile saved successfully!");
    });
  });

  // Ask AI Button
  document.getElementById("btn-ask-ai").addEventListener("click", () => {
    const question = document.getElementById("ai-question-input").value.trim();
    if (!question) {
      alert("Please enter a question prompt.");
      return;
    }

    const aiResBox = document.getElementById("ai-result");
    const aiText = document.getElementById("ai-answer-text");
    aiResBox.style.display = "block";
    aiText.innerHTML = "<em>Asking Groq AI...</em>";

    fetch("http://localhost:5050/api/answer_question", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: question, company: "Company", role: "Applicant" })
    })
      .then(res => res.json())
      .then(data => {
        if (data.answer) {
          aiText.innerText = data.answer;
        } else {
          aiText.innerText = "Error: " + (data.error || "Could not generate answer.");
        }
      })
      .catch(err => {
        aiText.innerText = "Backend Offline. Please start 'python3 app.py' to use AI features.";
      });
  });
});

function checkBackendConnection() {
  const badge = document.getElementById("backend-status");
  const badgeText = document.getElementById("backend-status-text");

  fetch("http://localhost:5050/api/profile", { method: "GET" })
    .then(res => res.json())
    .then(data => {
      badge.className = "badge badge-online";
      badgeText.innerText = "Backend Connected";
    })
    .catch(err => {
      badge.className = "badge badge-offline";
      badgeText.innerText = "Local Mode";
    });
}

function syncProfileFromBackend() {
  setQuickStatus("Syncing from backend...");
  fetch("http://localhost:5050/api/profile")
    .then(res => res.json())
    .then(data => {
      chrome.storage.local.set({ profile: data }, () => {
        populateProfileFields(data);
        setQuickStatus("Synced from ApplyBot backend!");
      });
    })
    .catch(err => {
      setQuickStatus("Backend offline at localhost:5050");
    });
}

function loadStoredProfile() {
  getProfile((profile) => {
    populateProfileFields(profile);
  });
}

function populateProfileFields(p) {
  if (!p) return;
  document.getElementById("prof-first-name").value = p.first_name || "";
  document.getElementById("prof-last-name").value = p.last_name || "";
  document.getElementById("prof-full-name").value = p.full_name || "";
  document.getElementById("prof-email").value = p.email || "";
  document.getElementById("prof-phone").value = p.phone || "";
  document.getElementById("prof-university").value = p.university || "";
  document.getElementById("prof-degree").value = p.degree || "";
  document.getElementById("prof-gpa").value = p.gpa || "";
  document.getElementById("prof-grad-year").value = p.graduation_year || "";
  document.getElementById("prof-linkedin").value = p.linkedin || "";
  document.getElementById("prof-github").value = p.github || "";
  document.getElementById("prof-resume-url").value = p.resume_gdrive_url || "";
}

function getProfile(callback) {
  chrome.storage.local.get(["profile"], (res) => {
    if (res && res.profile) {
      callback(res.profile);
    } else {
      // Default fallback
      callback({
        full_name: "Vimal Manoharan",
        first_name: "Vimal",
        last_name: "Manoharan",
        email: "2004.vimal@gmail.com",
        phone: "+91 76038 32537",
        university: "SRM Institute of Science and Technology",
        degree: "Bachelor of Technology in Computer Science Engineering",
        gpa: "8.91 / 10.0",
        graduation_year: "2026",
        linkedin: "https://linkedin.com/in/vimalmanoharan04",
        github: "https://github.com/vimal004",
        resume_gdrive_url: "https://drive.google.com/file/d/1ozzluGbJEgqQkFpfPu97VnXoLoDkE0Rw/view?usp=share_link"
      });
    }
  });
}

function setQuickStatus(msg) {
  const box = document.getElementById("quick-status");
  if (box) box.innerText = msg;
}
