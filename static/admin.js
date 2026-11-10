/* ==========================================================================
   SR University Helpdesk - Admin CRUD Logic
   ========================================================================== */

let activeTab = "faculty";
let tableData = [];
let editingRecordId = null;

const crudTable = document.getElementById("crudTable");
const tableHead = document.getElementById("tableHead");
const tableBody = document.getElementById("tableBody");
const adminSearchInput = document.getElementById("adminSearchInput");
const filterInfo = document.getElementById("filterInfo");
const crudModal = document.getElementById("crudModal");
const modalTitle = document.getElementById("modalTitle");
const modalFormFields = document.getElementById("modalFormFields");
const addNewBtn = document.getElementById("addNewBtn");
const themeToggleBtn = document.getElementById("themeToggleBtn");

// Tab counts
const countFaculty = document.getElementById("countFaculty");
const countAdmin = document.getElementById("countAdmin");
const countKnowledge = document.getElementById("countKnowledge");
const countClubs = document.getElementById("countClubs");
const countWebsites = document.getElementById("countWebsites");

// ==========================================================================
// Theme Management
// ==========================================================================
function initTheme() {
  const savedTheme = localStorage.getItem("sru_theme") || "light";
  document.documentElement.setAttribute("data-theme", savedTheme);
  updateThemeIcon(savedTheme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  const next = current === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("sru_theme", next);
  updateThemeIcon(next);
}

function updateThemeIcon(theme) {
  if (!themeToggleBtn) return;
  if (theme === "dark") {
    themeToggleBtn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>`;
  } else {
    themeToggleBtn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>`;
  }
}

themeToggleBtn.addEventListener("click", toggleTheme);
initTheme();

// ==========================================================================
// Tab Switching
// ==========================================================================
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    activeTab = btn.getAttribute("data-tab");
    adminSearchInput.value = "";
    loadTabRecords();
  });
});

addNewBtn.addEventListener("click", () => {
  openAddModal();
});

// ==========================================================================
// Fetch & Load Data
// ==========================================================================
async function refreshAllCounts() {
  try {
    const [fac, adm, knw, clb, web] = await Promise.all([
      fetch("/api/faculty").then((r) => r.json()),
      fetch("/api/administrative").then((r) => r.json()),
      fetch("/api/knowledge").then((r) => r.json()),
      fetch("/api/clubs").then((r) => r.json()),
      fetch("/api/websites").then((r) => r.json()),
    ]);
    if (countFaculty) countFaculty.textContent = fac.length || 0;
    if (countAdmin) countAdmin.textContent = adm.length || 0;
    if (countKnowledge) countKnowledge.textContent = knw.length || 0;
    if (countClubs) countClubs.textContent = clb.length || 0;
    if (countWebsites) countWebsites.textContent = web.length || 0;
  } catch (err) {
    console.error("Count refresh error:", err);
  }
}

async function loadTabRecords() {
  tableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-secondary); padding: 2rem;">Loading records...</td></tr>`;

  let endpoint = "/api/faculty";
  if (activeTab === "administrative") endpoint = "/api/administrative";
  else if (activeTab === "knowledge") endpoint = "/api/knowledge";
  else if (activeTab === "clubs") endpoint = "/api/clubs";
  else if (activeTab === "websites") endpoint = "/api/websites";

  try {
    const res = await fetch(endpoint);
    tableData = await res.json();
    renderTable(tableData);
    refreshAllCounts();
  } catch (err) {
    console.error("Fetch error:", err);
    tableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--destructive); padding: 2rem;">Failed to load records.</td></tr>`;
  }
}

// ==========================================================================
// Table Rendering
// ==========================================================================
function renderTable(data) {
  tableHead.innerHTML = "";
  tableBody.innerHTML = "";

  if (activeTab === "faculty") {
    tableHead.innerHTML = `
      <tr>
        <th style="width: 150px;">Employee ID</th>
        <th>Faculty Name</th>
        <th>Email</th>
        <th>Cabin ID</th>
        <th style="width: 140px; text-align: right;">Actions</th>
      </tr>
    `;
    if (data.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-secondary); padding: 2rem;">No faculty records found.</td></tr>`;
      return;
    }
    data.forEach((row) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><span class="badge badge-blue font-mono">${escapeHtml(row.emp_id)}</span></td>
        <td><strong>${escapeHtml(row.name)}</strong></td>
        <td>${row.email ? `<a href="mailto:${escapeHtml(row.email)}" style="color: #2563eb;">${escapeHtml(row.email)}</a>` : '<span style="color: var(--text-muted);">&mdash;</span>'}</td>
        <td>${row.cabin_id ? `<code>${escapeHtml(row.cabin_id)}</code>` : '<span style="color: var(--text-muted);">&mdash;</span>'}</td>
        <td style="text-align: right;">
          <div class="table-actions" style="justify-content: flex-end;">
            <button class="btn btn-outline btn-sm" onclick="openEditModal('${escapeHtml(row.emp_id)}')">Edit</button>
            <button class="btn btn-outline btn-sm" style="color: var(--destructive);" onclick="deleteRecord('${escapeHtml(row.emp_id)}')">Delete</button>
          </div>
        </td>
      `;
      tableBody.appendChild(tr);
    });

  } else if (activeTab === "administrative") {
    tableHead.innerHTML = `
      <tr>
        <th>Role / Responsibility</th>
        <th>Officer Name</th>
        <th>Email</th>
        <th>Cabin / Room Number</th>
        <th style="width: 140px; text-align: right;">Actions</th>
      </tr>
    `;
    if (data.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-secondary); padding: 2rem;">No administrative records found.</td></tr>`;
      return;
    }
    data.forEach((row) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><span class="badge badge-amber">${escapeHtml(row.role)}</span></td>
        <td><strong>${escapeHtml(row.name)}</strong></td>
        <td>${row.email ? `<a href="mailto:${escapeHtml(row.email)}" style="color: #2563eb;">${escapeHtml(row.email)}</a>` : '<span style="color: var(--text-muted);">&mdash;</span>'}</td>
        <td><code>${escapeHtml(row.cabin_room_number)}</code></td>
        <td style="text-align: right;">
          <div class="table-actions" style="justify-content: flex-end;">
            <button class="btn btn-outline btn-sm" onclick="openEditModal(${row.id})">Edit</button>
            <button class="btn btn-outline btn-sm" style="color: var(--destructive);" onclick="deleteRecord(${row.id})">Delete</button>
          </div>
        </td>
      `;
      tableBody.appendChild(tr);
    });

  } else if (activeTab === "knowledge") {
    tableHead.innerHTML = `
      <tr>
        <th style="width: 140px;">Category</th>
        <th style="width: 220px;">Title</th>
        <th>Content Preview</th>
        <th style="width: 180px;">Tags</th>
        <th style="width: 140px; text-align: right;">Actions</th>
      </tr>
    `;
    if (data.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-secondary); padding: 2rem;">No knowledge records found.</td></tr>`;
      return;
    }
    data.forEach((row) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><span class="badge badge-blue" style="text-transform: capitalize;">${escapeHtml(row.category)}</span></td>
        <td><strong>${escapeHtml(row.title)}</strong></td>
        <td style="max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(row.content)}">${escapeHtml(row.content)}</td>
        <td><span class="badge badge-green" style="font-size: 0.72rem;">${escapeHtml(row.tags)}</span></td>
        <td style="text-align: right;">
          <div class="table-actions" style="justify-content: flex-end;">
            <button class="btn btn-outline btn-sm" onclick="openEditModal(${row.id})">Edit</button>
            <button class="btn btn-outline btn-sm" style="color: var(--destructive);" onclick="deleteRecord(${row.id})">Delete</button>
          </div>
        </td>
      `;
      tableBody.appendChild(tr);
    });

  } else if (activeTab === "clubs") {
    tableHead.innerHTML = `
      <tr>
        <th>Club Name</th>
        <th>Social Media Link</th>
        <th style="width: 140px; text-align: right;">Actions</th>
      </tr>
    `;
    if (data.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-secondary); padding: 2rem;">No student clubs found.</td></tr>`;
      return;
    }
    data.forEach((row) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><span class="badge badge-purple" style="font-size: 0.85rem;">${escapeHtml(row.club_name)}</span></td>
        <td><a href="${escapeHtml(row.social_media_link)}" target="_blank" rel="noopener noreferrer" style="color: #2563eb; text-decoration: none;">${escapeHtml(row.social_media_link)}</a></td>
        <td style="text-align: right;">
          <div class="table-actions" style="justify-content: flex-end;">
            <button class="btn btn-outline btn-sm" onclick="openEditModal(${row.id})">Edit</button>
            <button class="btn btn-outline btn-sm" style="color: var(--destructive);" onclick="deleteRecord(${row.id})">Delete</button>
          </div>
        </td>
      `;
      tableBody.appendChild(tr);
    });

  } else if (activeTab === "websites") {
    tableHead.innerHTML = `
      <tr>
        <th style="width: 260px;">Website URL</th>
        <th>Purpose & Usage Tags</th>
        <th style="width: 140px; text-align: right;">Actions</th>
      </tr>
    `;
    if (data.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-secondary); padding: 2rem;">No website records found.</td></tr>`;
      return;
    }
    data.forEach((row) => {
      const tr = document.createElement("tr");
      const tagsList = row.tags_list || (row.purpose_tags ? row.purpose_tags.split(",") : []);
      const tagsHtml = tagsList
        .map((t) => `<span class="badge badge-green" style="margin-right: 0.3rem; margin-bottom: 0.2rem;">${escapeHtml(t.trim())}</span>`)
        .join(" ");

      tr.innerHTML = `
        <td><a href="${escapeHtml(row.url)}" target="_blank" rel="noopener noreferrer" style="color: #2563eb; font-weight: 500; text-decoration: none;">${escapeHtml(row.url)}</a></td>
        <td><div style="display: flex; flex-wrap: wrap;">${tagsHtml}</div></td>
        <td style="text-align: right;">
          <div class="table-actions" style="justify-content: flex-end;">
            <button class="btn btn-outline btn-sm" onclick="openEditModal(${row.id})">Edit</button>
            <button class="btn btn-outline btn-sm" style="color: var(--destructive);" onclick="deleteRecord(${row.id})">Delete</button>
          </div>
        </td>
      `;
      tableBody.appendChild(tr);
    });
  }

  filterInfo.textContent = `Showing ${data.length} records`;
}

// ==========================================================================
// Filtering & Search
// ==========================================================================
function handleSearch(e) {
  const query = e.target.value.toLowerCase().trim();
  if (!query) {
    renderTable(tableData);
    return;
  }
  const filtered = tableData.filter((row) => {
    return Object.values(row).some((val) => {
      if (typeof val === "string") return val.toLowerCase().includes(query);
      if (Array.isArray(val)) return val.join(" ").toLowerCase().includes(query);
      return false;
    });
  });
  renderTable(filtered);
  filterInfo.textContent = `Filtered ${filtered.length} of ${tableData.length} records`;
}

// ==========================================================================
// Modal & Form Handlers
// ==========================================================================
function openAddModal() {
  editingRecordId = null;
  modalTitle.textContent = `Add ${getTabDisplayName()}`;
  buildFormFields();
  crudModal.classList.add("active");
}

function openEditModal(recordId) {
  editingRecordId = recordId;
  modalTitle.textContent = `Edit ${getTabDisplayName()}`;

  const item = tableData.find((r) => (r.emp_id === recordId || r.id === recordId));
  if (!item) return;

  buildFormFields(item);
  crudModal.classList.add("active");
}

function closeModal() {
  crudModal.classList.remove("active");
  editingRecordId = null;
}

function getTabDisplayName() {
  if (activeTab === "faculty") return "Faculty Member";
  if (activeTab === "administrative") return "Administrative Personnel";
  if (activeTab === "knowledge") return "Knowledge Item";
  if (activeTab === "clubs") return "Student Club";
  return "College Website";
}

function buildFormFields(data = {}) {
  modalFormFields.innerHTML = "";

  if (activeTab === "faculty") {
    modalFormFields.innerHTML = `
      <div class="form-group">
        <label class="form-label">Employee ID (e.g. SRU-CSE-101) *</label>
        <input type="text" id="f_emp_id" class="form-input" required value="${escapeHtml(data.emp_id || "")}" ${editingRecordId ? "readonly" : ""}>
      </div>
      <div class="form-group">
        <label class="form-label">Faculty Name *</label>
        <input type="text" id="f_name" class="form-input" required value="${escapeHtml(data.name || "")}" placeholder="e.g. Dr. A. Ramesh Babu">
      </div>
      <div class="form-group">
        <label class="form-label">Email Address (Optional)</label>
        <input type="email" id="f_email" class="form-input" value="${escapeHtml(data.email || "")}" placeholder="e.g. faculty.name@sru.edu.in">
      </div>
      <div class="form-group">
        <label class="form-label">Cabin ID / Room (Optional, defaults to null)</label>
        <input type="text" id="f_cabin_id" class="form-input" value="${escapeHtml(data.cabin_id || "")}" placeholder="e.g. Block-I, Room 102">
      </div>
    `;
  } else if (activeTab === "administrative") {
    modalFormFields.innerHTML = `
      <div class="form-group">
        <label class="form-label">Role / Responsibility *</label>
        <input type="text" id="a_role" class="form-input" required value="${escapeHtml(data.role || "")}" placeholder="e.g. Buses In-Charge, Fees Officer, Warden">
      </div>
      <div class="form-group">
        <label class="form-label">Officer Name *</label>
        <input type="text" id="a_name" class="form-input" required value="${escapeHtml(data.name || "")}" placeholder="e.g. Mr. Ch. Venkat Narayana">
      </div>
      <div class="form-group">
        <label class="form-label">Email Address</label>
        <input type="email" id="a_email" class="form-input" value="${escapeHtml(data.email || "")}" placeholder="e.g. officer@sru.edu.in">
      </div>
      <div class="form-group">
        <label class="form-label">Cabin / Room Number *</label>
        <input type="text" id="a_cabin" class="form-input" required value="${escapeHtml(data.cabin_room_number || "")}" placeholder="e.g. Cabin T-102, Admin Block">
      </div>
    `;
  } else if (activeTab === "knowledge") {
    modalFormFields.innerHTML = `
      <div class="form-group">
        <label class="form-label">Category *</label>
        <select id="k_category" class="form-input" required>
          <option value="fees" ${data.category === "fees" ? "selected" : ""}>Fees</option>
          <option value="scholarships" ${data.category === "scholarships" ? "selected" : ""}>Scholarships</option>
          <option value="gamification_ssm" ${data.category === "gamification_ssm" ? "selected" : ""}>Gamification (SSM Coins & Badges)</option>
          <option value="academics" ${data.category === "academics" ? "selected" : ""}>Academics</option>
          <option value="permissions" ${data.category === "permissions" ? "selected" : ""}>Permissions & Gate Pass</option>
          <option value="campus_life" ${data.category === "campus_life" ? "selected" : ""}>Campus Life & Fests</option>
          <option value="placements" ${data.category === "placements" ? "selected" : ""}>Placements</option>
          <option value="facilities" ${data.category === "facilities" ? "selected" : ""}>Facilities</option>
          <option value="rules" ${data.category === "rules" ? "selected" : ""}>Rules & Discipline</option>
        </select>
      </div>
      <div class="form-group">
        <label class="form-label">Title *</label>
        <input type="text" id="k_title" class="form-input" required value="${escapeHtml(data.title || "")}" placeholder="e.g. B.Tech Tuition Fee Structure">
      </div>
      <div class="form-group">
        <label class="form-label">Content *</label>
        <textarea id="k_content" class="form-input" rows="5" required placeholder="Detailed rules, fee amounts, policies...">${escapeHtml(data.content || "")}</textarea>
      </div>
      <div class="form-group">
        <label class="form-label">Search Tags *</label>
        <input type="text" id="k_tags" class="form-input" required value="${escapeHtml(data.tags || "")}" placeholder="e.g. tuition, btech fees, semester">
      </div>
    `;
  } else if (activeTab === "clubs") {
    modalFormFields.innerHTML = `
      <div class="form-group">
        <label class="form-label">Club Name *</label>
        <input type="text" id="c_name" class="form-input" required value="${escapeHtml(data.club_name || "")}" placeholder="e.g. RoboSRU - Robotics & IoT Club">
      </div>
      <div class="form-group">
        <label class="form-label">Social Media Link *</label>
        <input type="url" id="c_link" class="form-input" required value="${escapeHtml(data.social_media_link || "")}" placeholder="e.g. https://instagram.com/sru_robotics">
      </div>
    `;
  } else if (activeTab === "websites") {
    modalFormFields.innerHTML = `
      <div class="form-group">
        <label class="form-label">Website / Portal URL *</label>
        <input type="url" id="w_url" class="form-input" required value="${escapeHtml(data.url || "")}" placeholder="e.g. https://feepay.sru.edu.in">
      </div>
      <div class="form-group">
        <label class="form-label">Purpose & Usage Tags *</label>
        <input type="text" id="w_tags" class="form-input" required value="${escapeHtml(data.purpose_tags || "")}" placeholder="e.g. tuition fees, exam timetable, hall ticket">
      </div>
    `;
  }
}

async function ensureAdminToken() {
  let token = localStorage.getItem("sru_admin_token");
  if (token) return token;
  const pw = prompt("Enter Master Administrator Password to perform this action:");
  if (!pw) return null;
  try {
    const res = await fetch("/api/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: pw })
    });
    const data = await res.json();
    if (res.ok && data.token) {
      localStorage.setItem("sru_admin_token", data.token);
      return data.token;
    } else {
      showToast(data.detail || "Authentication failed: invalid password.", "error", "Access Denied");
      return null;
    }
  } catch (e) {
    showToast("Unable to reach admin auth service.", "error", "Network Error");
    return null;
  }
}

async function handleFormSubmit(e) {
  e.preventDefault();
  const token = await ensureAdminToken();
  if (!token) return;

  let payload = {};
  let url = "";
  let method = editingRecordId ? "PUT" : "POST";

  if (activeTab === "faculty") {
    const emp_id = document.getElementById("f_emp_id").value.trim();
    const name = document.getElementById("f_name").value.trim();
    const email = document.getElementById("f_email").value.trim() || null;
    const cabin_id = document.getElementById("f_cabin_id").value.trim() || null;
    payload = { emp_id, name, email, cabin_id };
    url = editingRecordId ? `/api/faculty/${encodeURIComponent(editingRecordId)}` : "/api/faculty";
  } else if (activeTab === "administrative") {
    const role = document.getElementById("a_role").value.trim();
    const name = document.getElementById("a_name").value.trim();
    const email = document.getElementById("a_email").value.trim() || null;
    const cabin_room_number = document.getElementById("a_cabin").value.trim();
    payload = { role, name, email, cabin_room_number };
    url = editingRecordId ? `/api/administrative/${editingRecordId}` : "/api/administrative";
  } else if (activeTab === "knowledge") {
    const category = document.getElementById("k_category").value;
    const title = document.getElementById("k_title").value.trim();
    const content = document.getElementById("k_content").value.trim();
    const tags = document.getElementById("k_tags").value.trim();
    payload = { category, title, content, tags };
    url = editingRecordId ? `/api/knowledge/${editingRecordId}` : "/api/knowledge";
  } else if (activeTab === "clubs") {
    const club_name = document.getElementById("c_name").value.trim();
    const social_media_link = document.getElementById("c_link").value.trim();
    payload = { club_name, social_media_link };
    url = editingRecordId ? `/api/clubs/${editingRecordId}` : "/api/clubs";
  } else if (activeTab === "websites") {
    const webUrl = document.getElementById("w_url").value.trim();
    const purpose_tags = document.getElementById("w_tags").value.trim();
    payload = { url: webUrl, purpose_tags };
    url = editingRecordId ? `/api/websites/${editingRecordId}` : "/api/websites";
  }

  try {
    const res = await fetch(url, {
      method,
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: JSON.stringify(payload)
    });
    if (res.status === 401) {
      localStorage.removeItem("sru_admin_token");
      showToast("Admin session expired. Please enter password again.", "error", "Unauthorized");
      return;
    }
    const result = await res.json();
    if (res.ok) {
      showToast(editingRecordId ? "Record updated successfully." : "Record created successfully.", "success", editingRecordId ? "Record Updated" : "Record Created");
      closeModal();
      loadTabRecords();
    } else {
      showToast(result.detail || "Error saving record", "error", "Save Error");
    }
  } catch (err) {
    console.error("Save error:", err);
    showToast("Network error saving record", "error", "Network Error");
  }
}

async function deleteRecord(recordId) {
  if (!confirm(`Are you sure you want to delete this record (${recordId})?`)) {
    return;
  }
  const token = await ensureAdminToken();
  if (!token) return;

  let endpoint = `/api/faculty/${encodeURIComponent(recordId)}`;
  if (activeTab === "administrative") endpoint = `/api/administrative/${recordId}`;
  else if (activeTab === "knowledge") endpoint = `/api/knowledge/${recordId}`;
  else if (activeTab === "clubs") endpoint = `/api/clubs/${recordId}`;
  else if (activeTab === "websites") endpoint = `/api/websites/${recordId}`;

  try {
    const res = await fetch(endpoint, {
      method: "DELETE",
      headers: {
        "Authorization": `Bearer ${token}`
      }
    });
    if (res.status === 401) {
      localStorage.removeItem("sru_admin_token");
      showToast("Admin session expired. Please enter password again.", "error", "Unauthorized");
      return;
    }
    if (res.ok) {
      showToast(`Permanently deleted record "${recordId}" from database.`, "delete", "Record Deleted");
      loadTabRecords();
    } else {
      const data = await res.json();
      showToast(data.detail || "Error deleting record", "error", "Delete Error");
    }
  } catch (err) {
    console.error("Delete error:", err);
    showToast("Network error deleting record", "error", "Network Error");
  }
}

async function reseedDatabase() {
  if (!confirm("This will restore default SR University seed records. Continue?")) {
    return;
  }
  try {
    const res = await fetch("/api/seed", { method: "POST" });
    if (res.ok) {
      showToast("Database successfully re-seeded with demo records.", "success", "Database Reset");
      loadTabRecords();
    } else {
      const data = await res.json().catch(() => ({}));
      showToast(data.detail || "Error re-seeding database.", "warning", "Action Restricted");
    }
  } catch (err) {
    console.error(err);
    showToast("Failed to re-seed database.", "error", "Network Error");
  }
}

// ==========================================================================
// Utilities
// ==========================================================================
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function showToast() {
  // Toast notifications disabled per user preference
}

// Initial load
loadTabRecords();
