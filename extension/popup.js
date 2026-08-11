/* ═══════════════════════════════════════════
   ApplyBot Popup Script v1.1
   Vimal Manoharan — personalised extension
   ═══════════════════════════════════════════ */

const BACKEND = "http://localhost:5050";

// ─── Default Profile (Vimal) ───
const DEFAULT_PROFILE = {
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
  portfolio: "https://github.com/vimal004",
  resume_gdrive_url: "https://drive.google.com/file/d/1ozzluGbJEgqQkFpfPu97VnXoLoDkE0Rw/view?usp=share_link",
  location: "Chennai, Tamil Nadu, India",
  experience_years: "1+ years (Internships & Freelance)",
  notice_period: "Immediate / Student (Graduating 2026)",
  expected_salary: "As per industry standards"
};

let currentPageContext = null; // Will hold scraped page info

document.addEventListener("DOMContentLoaded", () => {

  // ─── Tab Switching ───
  document.querySelectorAll(".tab-btn").forEach(tab => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
      tab.classList.add("active");
      const target = document.getElementById(tab.dataset.tab);
      if (target) target.classList.add("active");
    });
  });

  // ─── JD Source Sub-Tabs ───
  document.querySelectorAll(".jd-source-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".jd-source-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".jd-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      const panel = document.getElementById(btn.dataset.jdtab);
      if (panel) panel.classList.add("active");
    });
  });

  // ─── Init ───
  checkBackendConnection();
  loadStoredProfile();
  loadStoredJD();
  refreshPageContext();

  // ─── Floating Widget Toggle ───
  const chkFloating = document.getElementById("chk-floating-widget");
  chrome.storage.local.get(["showFloatingButton"], res => {
    chkFloating.checked = res.showFloatingButton !== false;
  });
  chkFloating.addEventListener("change", () => {
    chrome.storage.local.set({ showFloatingButton: chkFloating.checked });
  });

  // ─── 1-Tap Fill Button ───
  document.getElementById("btn-fill-now").addEventListener("click", () => {
    getProfile(profile => {
      chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
        if (!tabs[0] || !tabs[0].id) return;
        chrome.tabs.sendMessage(tabs[0].id, { action: "FILL_FORM", profile }, response => {
          if (chrome.runtime.lastError) {
            // Inject then retry
            chrome.scripting.executeScript({ target: { tabId: tabs[0].id }, files: ["content.js"] }, () => {
              setTimeout(() => {
                chrome.tabs.sendMessage(tabs[0].id, { action: "FILL_FORM", profile });
              }, 250);
            });
          }
          setQuickStatus("⚡ Form fields populated!", "success");
          // Re-scan after fill
          setTimeout(refreshPageContext, 500);
        });
      });
    });
  });

  // ─── Sync from Backend ───
  document.getElementById("btn-sync-backend").addEventListener("click", () => {
    syncProfileFromBackend();
  });

  // ─── Re-scan Page ───
  document.getElementById("btn-refresh-context").addEventListener("click", () => {
    refreshPageContext();
    setQuickStatus("🔍 Re-scanning page...", "loading");
  });

  // ─── Save Profile ───
  document.getElementById("btn-save-profile").addEventListener("click", () => {
    const p = {
      first_name: document.getElementById("prof-first-name").value,
      last_name: document.getElementById("prof-last-name").value,
      full_name: document.getElementById("prof-full-name").value,
      email: document.getElementById("prof-email").value,
      phone: document.getElementById("prof-phone").value,
      location: document.getElementById("prof-location").value,
      university: document.getElementById("prof-university").value,
      degree: document.getElementById("prof-degree").value,
      gpa: document.getElementById("prof-gpa").value,
      graduation_year: document.getElementById("prof-grad-year").value,
      linkedin: document.getElementById("prof-linkedin").value,
      github: document.getElementById("prof-github").value,
      resume_gdrive_url: document.getElementById("prof-resume-url").value,
      experience_years: document.getElementById("prof-experience").value,
      expected_salary: document.getElementById("prof-salary").value,
    };

    chrome.storage.local.set({ profile: p }, () => {
      showInlineStatus("profile-status", "✅ Profile saved successfully!", "success");
      updateProfileDisplay(p);
    });
  });

  // ─── AI Answer ───
  document.getElementById("btn-ask-ai").addEventListener("click", () => {
    generateAIAnswer();
  });

  document.getElementById("btn-copy-answer").addEventListener("click", () => {
    const text = document.getElementById("ai-answer-text").innerText;
    navigator.clipboard.writeText(text).then(() => {
      document.getElementById("btn-copy-answer").textContent = "✅ Copied!";
      setTimeout(() => { document.getElementById("btn-copy-answer").textContent = "📋 Copy"; }, 2000);
    });
  });

  document.getElementById("btn-regen-answer").addEventListener("click", () => {
    generateAIAnswer();
  });

  // ─── JD Save ───
  document.getElementById("btn-save-jd").addEventListener("click", () => {
    saveCurrentJD();
  });

  // ─── JD Clear ───
  document.getElementById("btn-clear-jd").addEventListener("click", () => {
    chrome.storage.local.remove("jd_text", () => {
      document.getElementById("jd-text-input").value = "";
      document.getElementById("jd-active-pill").style.display = "none";
      showInlineStatus("jd-status", "🗑️ JD cleared.", "");
    });
  });

  // ─── JD File Upload ───
  const uploadZone = document.getElementById("upload-zone");
  const fileInput = document.getElementById("jd-file-input");

  uploadZone.addEventListener("click", () => fileInput.click());

  uploadZone.addEventListener("dragover", e => {
    e.preventDefault();
    uploadZone.style.borderColor = "rgba(139,92,246,0.7)";
  });

  uploadZone.addEventListener("dragleave", () => {
    uploadZone.style.borderColor = "";
  });

  uploadZone.addEventListener("drop", e => {
    e.preventDefault();
    uploadZone.style.borderColor = "";
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
  });

  fileInput.addEventListener("change", () => {
    const file = fileInput.files[0];
    if (file) handleFileUpload(file);
  });

  // ─── JD From Page ───
  document.getElementById("btn-use-page-jd").addEventListener("click", () => {
    if (currentPageContext && currentPageContext.bodyText) {
      document.getElementById("jd-page-preview").textContent = currentPageContext.bodyText;
      showInlineStatus("jd-status", "✅ Page text scraped. Click Save JD to confirm.", "success");
    } else {
      refreshPageContext(() => {
        if (currentPageContext && currentPageContext.bodyText) {
          document.getElementById("jd-page-preview").textContent = currentPageContext.bodyText;
        } else {
          document.getElementById("jd-page-preview").textContent = "Could not scrape page text.";
        }
      });
    }
  });

  // ─── Email Note Counter ───
  document.getElementById("email-note").addEventListener("input", () => {
    const len = document.getElementById("email-note").value.length;
    document.getElementById("email-note-counter").textContent = Math.min(len, 300);
  });

  // ─── Email Preview ───
  document.getElementById("btn-preview-email").addEventListener("click", () => {
    generateEmailPreview();
  });

  // ─── Email Send ───
  document.getElementById("btn-send-email").addEventListener("click", () => {
    sendEmail();
  });

});

// ═══════════════════════════════════════════
// PAGE CONTEXT
// ═══════════════════════════════════════════
function refreshPageContext(callback) {
  chrome.tabs.query({ active: true, currentWindow: true }, tabs => {
    if (!tabs[0] || !tabs[0].id) {
      updateContextUI(null);
      if (callback) callback();
      return;
    }

    chrome.tabs.sendMessage(tabs[0].id, { action: "PING" }, response => {
      if (chrome.runtime.lastError || !response) {
        // Inject content.js and retry once
        chrome.scripting.executeScript({ target: { tabId: tabs[0].id }, files: ["content.js"] }, () => {
          setTimeout(() => {
            chrome.tabs.sendMessage(tabs[0].id, { action: "PING" }, res2 => {
              currentPageContext = res2 || null;
              updateContextUI(res2);
              if (callback) callback();
            });
          }, 300);
        });
        return;
      }
      currentPageContext = response;
      updateContextUI(response);
      if (callback) callback();
    });
  });
}

function updateContextUI(ctx) {
  const titleEl = document.getElementById("ctx-job-title");
  const urlEl = document.getElementById("ctx-page-url");
  const fieldsEl = document.getElementById("ctx-fields-pill");
  const paCompany = document.getElementById("pa-company");
  const paTitle = document.getElementById("pa-jobtitle");
  const paFields = document.getElementById("pa-fields");
  const paUrl = document.getElementById("pa-url");
  const btnCountLabel = document.getElementById("btn-fill-count-label");

  if (!ctx) {
    titleEl.textContent = "No active page detected";
    urlEl.textContent = "—";
    fieldsEl.textContent = "— fields";
    return;
  }

  const displayTitle = ctx.jobTitle || ctx.pageTitle || "Unknown Page";
  const displayUrl = ctx.pageUrl || "—";
  const fieldCount = ctx.inputsFound || 0;
  const company = ctx.company || "—";

  titleEl.textContent = displayTitle.length > 50 ? displayTitle.substring(0, 47) + "…" : displayTitle;
  urlEl.textContent = displayUrl.length > 55 ? displayUrl.substring(0, 52) + "…" : displayUrl;
  fieldsEl.textContent = `${fieldCount} fields`;
  btnCountLabel.textContent = fieldCount > 0 ? `(${fieldCount} detected)` : "";

  paCompany.textContent = company;
  paTitle.textContent = displayTitle;
  paFields.textContent = fieldCount;
  paUrl.textContent = displayUrl.length > 60 ? displayUrl.substring(0, 57) + "…" : displayUrl;

  // Pre-fill AI tab company/role from page
  const aiCompanyEl = document.getElementById("ai-company");
  const aiRoleEl = document.getElementById("ai-role");
  if (!aiCompanyEl.value && company !== "—") aiCompanyEl.value = company;
  if (!aiRoleEl.value && ctx.jobTitle) aiRoleEl.value = ctx.jobTitle;

  // Pre-fill email tab
  const emailCompanyEl = document.getElementById("email-company");
  const emailRoleEl = document.getElementById("email-role");
  if (!emailCompanyEl.value && company !== "—") emailCompanyEl.value = company;
  if (!emailRoleEl.value && ctx.jobTitle) emailRoleEl.value = ctx.jobTitle;

  setQuickStatus(`✅ Found ${fieldCount} field${fieldCount !== 1 ? 's' : ''} on ${company}`, fieldCount > 0 ? "success" : "");
}

// ═══════════════════════════════════════════
// BACKEND CONNECTION
// ═══════════════════════════════════════════
function checkBackendConnection() {
  const badge = document.getElementById("backend-status");
  const badgeText = document.getElementById("backend-status-text");

  fetch(`${BACKEND}/api/profile`, { method: "GET" })
    .then(res => res.json())
    .then(() => {
      badge.className = "badge badge-online";
      badgeText.innerText = "Backend Live";
    })
    .catch(() => {
      badge.className = "badge badge-offline";
      badgeText.innerText = "Local Mode";
    });
}

function syncProfileFromBackend() {
  setQuickStatus("Syncing from backend...", "loading");
  fetch(`${BACKEND}/api/profile`)
    .then(res => res.json())
    .then(data => {
      chrome.storage.local.set({ profile: data }, () => {
        populateProfileFields(data);
        updateProfileDisplay(data);
        setQuickStatus("✅ Synced from ApplyBot backend!", "success");
      });
    })
    .catch(() => {
      setQuickStatus("❌ Backend offline. Run python3 app.py", "error");
    });
}

// ═══════════════════════════════════════════
// PROFILE
// ═══════════════════════════════════════════
function loadStoredProfile() {
  getProfile(profile => {
    populateProfileFields(profile);
    updateProfileDisplay(profile);
  });
}

function populateProfileFields(p) {
  if (!p) return;
  const set = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.value = val || "";
  };
  set("prof-first-name", p.first_name);
  set("prof-last-name", p.last_name);
  set("prof-full-name", p.full_name);
  set("prof-email", p.email);
  set("prof-phone", p.phone);
  set("prof-location", p.location);
  set("prof-university", p.university);
  set("prof-degree", p.degree);
  set("prof-gpa", p.gpa);
  set("prof-grad-year", p.graduation_year);
  set("prof-linkedin", p.linkedin);
  set("prof-github", p.github);
  set("prof-resume-url", p.resume_gdrive_url);
  set("prof-experience", p.experience_years);
  set("prof-salary", p.expected_salary);
}

function updateProfileDisplay(p) {
  if (!p) return;
  const nameEl = document.getElementById("profile-display-name");
  const emailEl = document.getElementById("profile-display-email");
  if (nameEl) nameEl.textContent = p.full_name || "—";
  if (emailEl) emailEl.textContent = p.email || "—";
}

function getProfile(callback) {
  chrome.storage.local.get(["profile"], res => {
    if (res && res.profile) {
      callback(Object.assign({}, DEFAULT_PROFILE, res.profile));
    } else {
      callback(DEFAULT_PROFILE);
    }
  });
}

// ═══════════════════════════════════════════
// JD
// ═══════════════════════════════════════════
function loadStoredJD() {
  chrome.storage.local.get(["jd_text"], res => {
    if (res && res.jd_text) {
      document.getElementById("jd-text-input").value = res.jd_text;
      document.getElementById("jd-active-pill").style.display = "inline-flex";
    }
  });
}

function saveCurrentJD() {
  // Determine which panel is active
  const activePaste = document.getElementById("jd-paste").classList.contains("active");
  const activePage = document.getElementById("jd-page").classList.contains("active");

  let jdText = "";

  if (activePaste) {
    jdText = document.getElementById("jd-text-input").value.trim();
  } else if (activePage) {
    jdText = document.getElementById("jd-page-preview").textContent.trim();
  } else {
    // Upload panel — check if we already set jd-text-input
    jdText = document.getElementById("jd-text-input").value.trim();
  }

  if (!jdText) {
    showInlineStatus("jd-status", "⚠️ No JD text to save.", "error");
    return;
  }

  chrome.storage.local.set({ jd_text: jdText }, () => {
    document.getElementById("jd-active-pill").style.display = "inline-flex";
    showInlineStatus("jd-status", `✅ JD saved (${jdText.length} chars). AI will use this context.`, "success");
  });
}

function handleFileUpload(file) {
  if (!file.name.endsWith(".txt")) {
    showInlineStatus("jd-status", "⚠️ Only .txt files are supported. Paste PDF content manually.", "error");
    return;
  }
  const reader = new FileReader();
  reader.onload = e => {
    const text = e.target.result;
    document.getElementById("jd-text-input").value = text;
    document.getElementById("upload-file-name").textContent = file.name;
    document.getElementById("upload-filename").style.display = "block";
    showInlineStatus("jd-status", `✅ "${file.name}" loaded (${text.length} chars). Click Save JD.`, "success");
    // Switch to paste tab to show content
    document.querySelectorAll(".jd-source-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".jd-panel").forEach(p => p.classList.remove("active"));
    document.querySelector('[data-jdtab="jd-paste"]').classList.add("active");
    document.getElementById("jd-paste").classList.add("active");
  };
  reader.readAsText(file);
}

// ═══════════════════════════════════════════
// AI ANSWER
// ═══════════════════════════════════════════
function generateAIAnswer() {
  const question = document.getElementById("ai-question-input").value.trim();
  const company = document.getElementById("ai-company").value.trim() || "Company";
  const role = document.getElementById("ai-role").value.trim() || "Applicant";

  if (!question) {
    alert("Please enter a question or prompt.");
    return;
  }

  const aiResBox = document.getElementById("ai-result");
  const aiText = document.getElementById("ai-answer-text");
  const aiActions = document.getElementById("ai-actions");

  aiResBox.style.display = "block";
  aiActions.style.display = "none";
  aiText.innerHTML = "<em style='color:#60a5fa'>✨ Generating personalised answer...</em>";

  // Build payload with page context and JD
  chrome.storage.local.get(["jd_text"], res => {
    const jdText = (res && res.jd_text) ? res.jd_text : "";
    const pageContext = currentPageContext ? currentPageContext.bodyText || "" : "";

    const payload = {
      question,
      company,
      role,
      jd_text: jdText,
      page_context: pageContext
    };

    chrome.runtime.sendMessage({ action: "ASK_AI_QUESTION", payload }, response => {
      if (response && response.success && response.answer) {
        aiText.innerText = response.answer;
        aiActions.style.display = "flex";
      } else {
        aiText.innerHTML = `<span style='color:#fb7185'>❌ Backend offline. Start <code>python3 app.py</code> first.</span>`;
      }
    });
  });
}

// ═══════════════════════════════════════════
// EMAIL
// ═══════════════════════════════════════════
function buildEmailPayload() {
  return {
    hr_name: document.getElementById("email-hr-name").value.trim(),
    hr_email: document.getElementById("email-hr-email").value.trim(),
    company: document.getElementById("email-company").value.trim(),
    role: document.getElementById("email-role").value.trim(),
    template: document.getElementById("email-template").value,
    custom_note: document.getElementById("email-note").value.trim(),
    candidate_name: DEFAULT_PROFILE.full_name,
    candidate_email: DEFAULT_PROFILE.email,
    linkedin: DEFAULT_PROFILE.linkedin,
    github: DEFAULT_PROFILE.github,
    resume_url: DEFAULT_PROFILE.resume_gdrive_url,
  };
}

function generateEmailPreview() {
  const payload = buildEmailPayload();

  if (!payload.hr_email || !payload.company || !payload.role) {
    showInlineStatus("email-status", "⚠️ Please fill HR Email, Company, and Role.", "error");
    return;
  }

  const preview = document.getElementById("email-preview");

  // Build local preview from template
  const body = buildEmailBody(payload);
  preview.style.display = "block";
  preview.innerHTML = `<strong>To:</strong> ${payload.hr_email}<br><strong>Subject:</strong> ${buildEmailSubject(payload)}<br><br>${body.replace(/\n/g, "<br>")}`;
}

function buildEmailSubject(p) {
  const templates = {
    referral: `Referral Request — ${p.role} | Vimal Manoharan (B.Tech CSE, SRM, 2026)`,
    cold_outreach: `Application for ${p.role} Position — Vimal Manoharan`,
    follow_up: `Following Up on ${p.role} Application — Vimal Manoharan`
  };
  return templates[p.template] || templates.cold_outreach;
}

function buildEmailBody(p) {
  const bodies = {
    referral: `Hi ${p.hr_name || "there"},\n\nI hope this message finds you well. My name is Vimal Manoharan, a final-year B.Tech Computer Science student at SRM Institute of Science and Technology (CGPA: 8.91/10, graduating 2026).\n\nI came across the ${p.role} opportunity at ${p.company} and I'm genuinely excited about it. I'd be incredibly grateful if you could refer me or forward my application internally.\n\n${p.custom_note ? p.custom_note + "\n\n" : ""}🔗 LinkedIn: ${DEFAULT_PROFILE.linkedin}\n🐙 GitHub: ${DEFAULT_PROFILE.github}\n📄 Resume: ${DEFAULT_PROFILE.resume_gdrive_url}\n\nThank you so much for your time!\n\nBest regards,\nVimal Manoharan\n${DEFAULT_PROFILE.phone} | ${DEFAULT_PROFILE.email}`,

    cold_outreach: `Dear HR team,\n\nI am Vimal Manoharan, a final-year B.Tech CSE student at SRM Institute (CGPA 8.91/10, graduating 2026), and I'm writing to express my strong interest in the ${p.role} role at ${p.company}.\n\nI have hands-on experience in full-stack development and AI/ML through internships and freelance projects, and I'm confident my skills align closely with your team's needs.\n\n${p.custom_note ? p.custom_note + "\n\n" : ""}📄 Resume: ${DEFAULT_PROFILE.resume_gdrive_url}\n🔗 LinkedIn: ${DEFAULT_PROFILE.linkedin}\n🐙 GitHub: ${DEFAULT_PROFILE.github}\n\nI would love the opportunity to discuss how I can contribute to ${p.company}.\n\nWarm regards,\nVimal Manoharan\n${DEFAULT_PROFILE.phone} | ${DEFAULT_PROFILE.email}`,

    follow_up: `Hi ${p.hr_name || "there"},\n\nI wanted to kindly follow up on my application for the ${p.role} position at ${p.company} that I submitted recently.\n\nI remain very enthusiastic about this opportunity and would love to discuss how I can contribute to your team.\n\n${p.custom_note ? p.custom_note + "\n\n" : ""}📄 Resume: ${DEFAULT_PROFILE.resume_gdrive_url}\n\nThank you for your consideration.\n\nBest,\nVimal Manoharan\n${DEFAULT_PROFILE.phone} | ${DEFAULT_PROFILE.email}`
  };
  return bodies[p.template] || bodies.cold_outreach;
}

function sendEmail() {
  const payload = buildEmailPayload();

  if (!payload.hr_email || !payload.company || !payload.role) {
    showInlineStatus("email-status", "⚠️ Please fill HR Email, Company, and Role.", "error");
    return;
  }

  showInlineStatus("email-status", "📤 Sending email...", "loading");

  // Build the full email payload for backend
  const emailPayload = {
    to_email: payload.hr_email,
    to_name: payload.hr_name || "Hiring Manager",
    subject: buildEmailSubject(payload),
    body: buildEmailBody(payload),
    company: payload.company,
    role: payload.role,
    template: payload.template
  };

  chrome.runtime.sendMessage({ action: "SEND_EMAIL", payload: emailPayload }, response => {
    if (response && response.success) {
      showInlineStatus("email-status", `✅ Email sent to ${payload.hr_email}!`, "success");
    } else {
      const msg = response ? response.message : "Unknown error";
      showInlineStatus("email-status", `❌ Failed: ${msg}. Ensure backend is running.`, "error");
    }
  });
}

// ═══════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════
function setQuickStatus(msg, type) {
  const box = document.getElementById("quick-status");
  if (!box) return;
  box.innerText = msg;
  box.className = "status-box" + (type ? " " + type : "");
}

function showInlineStatus(id, msg, type) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = msg;
  el.className = "status-box" + (type ? " " + type : "");
  el.style.display = "block";
  setTimeout(() => { el.style.display = "none"; }, 5000);
}
