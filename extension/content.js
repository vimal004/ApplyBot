/* ApplyBot Content Script - Smart Form Auto-Filler Engine */

(function () {
  if (window.__ApplyBotLoaded) return;
  window.__ApplyBotLoaded = true;

  // Default candidate profile (can be overridden by chrome.storage or backend API)
  const defaultProfile = {
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

  // Helper to retrieve current stored profile or default
  function getProfile(callback) {
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      chrome.storage.local.get(['profile'], function (result) {
        if (result && result.profile) {
          callback(Object.assign({}, defaultProfile, result.profile));
        } else {
          callback(defaultProfile);
        }
      });
    } else {
      callback(defaultProfile);
    }
  }

  // Safely set input value and dispatch reactivity events (React/Vue/Angular compliant)
  function setNativeValue(element, value) {
    if (!element || value === undefined || value === null) return;

    try {
      const valueSetter = Object.getOwnPropertyDescriptor(element, 'value')?.set ||
        Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value')?.set;

      if (valueSetter) {
        valueSetter.call(element, value);
      } else {
        element.value = value;
      }
    } catch (e) {
      element.value = value;
    }

    element.dispatchEvent(new Event('input', { bubbles: true }));
    element.dispatchEvent(new Event('change', { bubbles: true }));
    element.dispatchEvent(new Event('blur', { bubbles: true }));
  }

  // Helper to extract text describing an element
  function getElementLabel(el) {
    let labels = [];

    // 1. Explicit <label for="..."> or wrapping <label>
    if (el.id) {
      const lbl = document.querySelector(`label[for="${el.id}"]`);
      if (lbl) labels.push(lbl.innerText);
    }
    const closestLbl = el.closest('label');
    if (closestLbl) labels.push(closestLbl.innerText);

    // 2. Attributes
    if (el.getAttribute('aria-label')) labels.push(el.getAttribute('aria-label'));
    if (el.placeholder) labels.push(el.placeholder);
    if (el.name) labels.push(el.name);
    if (el.id) labels.push(el.id);
    if (el.getAttribute('autocomplete')) labels.push(el.getAttribute('autocomplete'));

    // 3. Preceding sibling text or parent container text snippet
    const parent = el.parentElement;
    if (parent) {
      const parentText = parent.innerText || '';
      if (parentText.length < 150) labels.push(parentText);
    }

    return labels.join(' ').toLowerCase();
  }

  // Main Form Autofill function
  function autoFillForm(customProfile) {
    getProfile(function (profile) {
      const data = customProfile || profile;
      let filledCount = 0;

      const elements = document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]), textarea, select');

      elements.forEach(el => {
        // Skip disabled or hidden inputs
        if (el.disabled || el.type === 'file' || el.style.display === 'none' || el.style.visibility === 'hidden') {
          return;
        }

        const descriptor = getElementLabel(el);
        const type = (el.type || '').toLowerCase();

        let filled = false;

        // Email
        if (!filled && (type === 'email' || descriptor.includes('email') || descriptor.includes('e-mail'))) {
          setNativeValue(el, data.email);
          filled = true;
        }
        // Phone
        else if (!filled && (type === 'tel' || descriptor.includes('phone') || descriptor.includes('mobile') || descriptor.includes('contact') || descriptor.includes('cell'))) {
          setNativeValue(el, data.phone);
          filled = true;
        }
        // First Name
        else if (!filled && (descriptor.includes('first name') || descriptor.includes('given name') || descriptor.includes('fname'))) {
          setNativeValue(el, data.first_name);
          filled = true;
        }
        // Last Name
        else if (!filled && (descriptor.includes('last name') || descriptor.includes('surname') || descriptor.includes('family name') || descriptor.includes('lname'))) {
          setNativeValue(el, data.last_name);
          filled = true;
        }
        // Full Name
        else if (!filled && (descriptor.includes('full name') || (descriptor.includes('name') && !descriptor.includes('company') && !descriptor.includes('user') && !descriptor.includes('file')))) {
          setNativeValue(el, data.full_name);
          filled = true;
        }
        // LinkedIn
        else if (!filled && descriptor.includes('linkedin')) {
          setNativeValue(el, data.linkedin);
          filled = true;
        }
        // GitHub
        else if (!filled && descriptor.includes('github')) {
          setNativeValue(el, data.github);
          filled = true;
        }
        // Portfolio / Website / Link
        else if (!filled && (descriptor.includes('portfolio') || descriptor.includes('website') || descriptor.includes('personal site'))) {
          setNativeValue(el, data.portfolio || data.github);
          filled = true;
        }
        // College / University
        else if (!filled && (descriptor.includes('college') || descriptor.includes('university') || descriptor.includes('institute') || descriptor.includes('school'))) {
          setNativeValue(el, data.university);
          filled = true;
        }
        // Degree / Branch
        else if (!filled && (descriptor.includes('degree') || descriptor.includes('branch') || descriptor.includes('major') || descriptor.includes('field of study'))) {
          setNativeValue(el, data.degree);
          filled = true;
        }
        // GPA / CGPA / Marks
        else if (!filled && (descriptor.includes('cgpa') || descriptor.includes('gpa') || descriptor.includes('percentage') || descriptor.includes('marks'))) {
          setNativeValue(el, data.gpa);
          filled = true;
        }
        // Graduation Year / Passing Year / Batch
        else if (!filled && (descriptor.includes('graduat') || descriptor.includes('passing year') || descriptor.includes('grad year') || descriptor.includes('batch'))) {
          setNativeValue(el, data.graduation_year);
          filled = true;
        }
        // Resume Drive Link
        else if (!filled && (descriptor.includes('resume link') || descriptor.includes('cv link') || descriptor.includes('drive link') || descriptor.includes('gdrive'))) {
          setNativeValue(el, data.resume_gdrive_url);
          filled = true;
        }
        // Location / City / Address
        else if (!filled && (descriptor.includes('location') || descriptor.includes('city') || descriptor.includes('address'))) {
          setNativeValue(el, data.location);
          filled = true;
        }
        // Experience Years
        else if (!filled && (descriptor.includes('years of experience') || descriptor.includes('total experience') || descriptor.includes('work experience'))) {
          setNativeValue(el, data.experience_years);
          filled = true;
        }
        // Notice Period / Availability
        else if (!filled && (descriptor.includes('notice period') || descriptor.includes('availability') || descriptor.includes('how soon'))) {
          setNativeValue(el, data.notice_period);
          filled = true;
        }
        // Expected Salary
        else if (!filled && (descriptor.includes('salary') || descriptor.includes('ctc') || descriptor.includes('expected compensation'))) {
          setNativeValue(el, data.expected_salary);
          filled = true;
        }

        // Handle SELECT Dropdowns
        if (!filled && el.tagName === 'SELECT') {
          handleSelectDropdown(el, descriptor, data);
          filled = true;
        }

        if (filled) filledCount++;
      });

      showToast(`⚡ ApplyBot: Populated ${filledCount} field${filledCount === 1 ? '' : 's'} on this page!`);
    });
  }

  // Smart Select Dropdown Auto-Selector
  function handleSelectDropdown(selectEl, descriptor, data) {
    const options = Array.from(selectEl.options);
    if (!options || options.length === 0) return;

    let targetIdx = -1;

    if (descriptor.includes('gender')) {
      targetIdx = options.findIndex(o => o.text.toLowerCase().includes('male') && !o.text.toLowerCase().includes('female'));
    } else if (descriptor.includes('disability')) {
      targetIdx = options.findIndex(o => o.text.toLowerCase().includes('no') || o.text.toLowerCase().includes('don\'t have') || o.text.toLowerCase().includes('do not have'));
    } else if (descriptor.includes('veteran')) {
      targetIdx = options.findIndex(o => o.text.toLowerCase().includes('not a veteran') || o.text.toLowerCase().includes('no') || o.text.toLowerCase().includes('am not'));
    } else if (descriptor.includes('authorize') || descriptor.includes('sponsorship') || descriptor.includes('legally')) {
      targetIdx = options.findIndex(o => o.text.toLowerCase().includes('yes'));
    } else if (descriptor.includes('country')) {
      targetIdx = options.findIndex(o => o.text.toLowerCase().includes('india'));
    }

    if (targetIdx !== -1) {
      selectEl.selectedIndex = targetIdx;
      setNativeValue(selectEl, selectEl.options[targetIdx].value);
    }
  }

  // Toast Notification Overlay
  function showToast(msg) {
    const existing = document.querySelector('.applybot-toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'applybot-toast';
    toast.innerHTML = `<span>⚡</span><span>${msg}</span>`;
    document.body.appendChild(toast);

    setTimeout(() => {
      if (toast) toast.remove();
    }, 4000);
  }

  // Floating Action Button Injection
  function injectFloatingWidget() {
    if (document.getElementById('applybot-floating-widget')) return;

    // Only inject if inputs exist on page
    const inputs = document.querySelectorAll('input:not([type="hidden"]), textarea, select');
    if (inputs.length < 2) return;

    // Check setting for floating button
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      chrome.storage.local.get(['showFloatingButton'], function (res) {
        if (res.showFloatingButton === false) return;
        renderWidget();
      });
    } else {
      renderWidget();
    }
  }

  function renderWidget() {
    const btn = document.createElement('div');
    btn.id = 'applybot-floating-widget';
    btn.title = 'Click to 1-Tap Fill All Form Fields';
    btn.innerHTML = `
      <div class="ab-icon">⚡</div>
      <div class="ab-label">1-Tap Fill</div>
      <div class="ab-close-btn" id="ab-widget-close" title="Hide for this page">&times;</div>
    `;

    btn.addEventListener('click', function (e) {
      if (e.target.id === 'ab-widget-close') {
        btn.remove();
        e.stopPropagation();
        return;
      }
      autoFillForm();
    });

    document.body.appendChild(btn);
  }

  // Message listener from extension popup or background worker
  if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.onMessage) {
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
      if (request.action === 'FILL_FORM') {
        autoFillForm(request.profile);
        sendResponse({ status: 'SUCCESS' });
      } else if (request.action === 'PING') {
        sendResponse({ status: 'PONG', inputsFound: document.querySelectorAll('input:not([type="hidden"]), textarea, select').length });
      }
      return true;
    });
  }

  // Run floating widget check when page is loaded
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    injectFloatingWidget();
  } else {
    window.addEventListener('DOMContentLoaded', injectFloatingWidget);
  }
})();
