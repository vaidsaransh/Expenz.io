/**
 * Expenz.io - Interactive Modern Expense & Budget Tracker Client
 * Includes Gemini AI Statement Analyzer for Bank & Amex Statements
 */

// Application State
const state = {
    categories: [],
    budgets: {},
    summary: null,
    expenses: [],
    selectedMonth: 'auto',
    pagination: {
        page: 1,
        limit: 8,
        total_items: 0,
        total_pages: 1
    },
    filters: {
        category: 'all',
        payment_method: 'all',
        search: '',
        month: 'auto'
    },
    charts: {
        timeline: null,
        categoryDonut: null,
        budgetBar: null,
        payment: null
    },
    isEditing: false,
    theme: localStorage.getItem('theme') || 'dark',
    aiParsedTransactions: []
};

/* ==========================================================================
   Multi-Tenant Workspace & Device ID Resolver
   ========================================================================== */
function getUserId() {
    let uid = localStorage.getItem('expenz_user_id');
    if (!uid) {
        uid = 'default';
        localStorage.setItem('expenz_user_id', uid);
    }
    return uid;
}

function setUserId(newUid) {
    if (newUid) {
        localStorage.setItem('expenz_user_id', newUid.trim());
    }
}

async function apiFetch(url, options = {}) {
    options.headers = options.headers || {};
    const userId = getUserId();
    const apiKey = localStorage.getItem('ai_api_key') || localStorage.getItem('gemini_api_key') || '';
    const provider = localStorage.getItem('ai_provider') || 'gemini';
    
    if (options.headers instanceof Headers) {
        if (!options.headers.has('X-User-Id')) options.headers.set('X-User-Id', userId);
        if (apiKey && !options.headers.has('X-AI-API-Key')) options.headers.set('X-AI-API-Key', apiKey);
        if (apiKey && !options.headers.has('X-Gemini-API-Key')) options.headers.set('X-Gemini-API-Key', apiKey);
        if (provider && !options.headers.has('X-AI-Provider')) options.headers.set('X-AI-Provider', provider);
    } else {
        options.headers['X-User-Id'] = userId;
        if (apiKey && !options.headers['X-AI-API-Key']) options.headers['X-AI-API-Key'] = apiKey;
        if (apiKey && !options.headers['X-Gemini-API-Key']) options.headers['X-Gemini-API-Key'] = apiKey;
        if (provider && !options.headers['X-AI-Provider']) options.headers['X-AI-Provider'] = provider;
    }
    return fetch(url, options);
}

// DOM Ready
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initDateInputs();
    initEventListeners();
    initWorkspaceSync();
    initCopilot();
    loadInitialData();
});

/* ==========================================================================
   Theme Management
   ========================================================================== */
function initTheme() {
    document.documentElement.setAttribute('data-theme', state.theme);
    updateThemeIcon();
}

function toggleTheme() {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', state.theme);
    localStorage.setItem('theme', state.theme);
    updateThemeIcon();
    
    if (state.summary) {
        renderCharts(state.summary);
    }
}

function updateThemeIcon() {
    const btn = document.getElementById('themeToggleBtn');
    if (btn) {
        btn.innerHTML = state.theme === 'dark' 
            ? '<i class="fa-solid fa-sun"></i>' 
            : '<i class="fa-solid fa-moon"></i>';
    }
}

/* ==========================================================================
   Date Defaults
   ========================================================================== */
function initDateInputs() {
    const today = new Date().toISOString().split('T')[0];
    const quickDate = document.getElementById('quickDate');
    const modalDate = document.getElementById('modalDate');
    if (quickDate) quickDate.value = today;
    if (modalDate) modalDate.value = today;
}

/* ==========================================================================
   Event Listeners
   ========================================================================== */
function initEventListeners() {
    // Theme Toggle
    document.getElementById('themeToggleBtn')?.addEventListener('click', toggleTheme);

    // Modal Triggers
    document.getElementById('openAddModalBtn')?.addEventListener('click', () => openExpenseModal());
    document.getElementById('closeExpenseModalBtn')?.addEventListener('click', closeExpenseModal);
    document.getElementById('cancelExpenseModalBtn')?.addEventListener('click', closeExpenseModal);

    document.getElementById('openBudgetsModalBtn')?.addEventListener('click', openBudgetsModal);
    document.getElementById('closeBudgetsModalBtn')?.addEventListener('click', closeBudgetsModal);
    document.getElementById('cancelBudgetsModalBtn')?.addEventListener('click', closeBudgetsModal);

    // AI Statement Modal Triggers
    document.getElementById('openStatementModalBtn')?.addEventListener('click', openStatementModal);
    document.getElementById('closeStatementModalBtn')?.addEventListener('click', closeStatementModal);
    document.getElementById('cancelStatementReviewBtn')?.addEventListener('click', closeStatementModal);
    document.getElementById('reUploadStatementBtn')?.addEventListener('click', showUploadStep);
    document.getElementById('confirmBulkImportBtn')?.addEventListener('click', handleBulkImportConfirm);
    document.getElementById('topConfirmBulkImportBtn')?.addEventListener('click', handleBulkImportConfirm);

    // API Key Settings Modal
    document.getElementById('openApiKeyModalBtn')?.addEventListener('click', openApiKeyModal);
    document.getElementById('closeApiKeyModalBtn')?.addEventListener('click', closeApiKeyModal);
    document.getElementById('cancelApiKeyModalBtn')?.addEventListener('click', closeApiKeyModal);
    document.getElementById('apiKeyForm')?.addEventListener('submit', handleApiKeySubmit);
    document.getElementById('aiProviderSelect')?.addEventListener('change', (e) => {
        updateProviderHelpUI(e.target.value);
    });

    // Initialize Mobile Experience & Navigation
    initMobileExperience();

    initDropzoneEvents();

    // Dashboard Month Selector
    document.getElementById('dashboardMonthSelector')?.addEventListener('change', (e) => {
        state.selectedMonth = e.target.value;
        state.filters.month = e.target.value;
        state.pagination.page = 1;
        fetchSummary();
        fetchExpenses();
    });

    // Dashboard Category Filter
    document.getElementById('dashboardCategoryFilter')?.addEventListener('change', (e) => {
        state.filters.category = e.target.value;
        const tblFilter = document.getElementById('tableCategoryFilter');
        if (tblFilter) tblFilter.value = e.target.value;
        state.pagination.page = 1;
        fetchExpenses();
    });

    // Table Category Filter sync with Dashboard Category Filter
    document.getElementById('tableCategoryFilter')?.addEventListener('change', (e) => {
        state.filters.category = e.target.value;
        const dashFilter = document.getElementById('dashboardCategoryFilter');
        if (dashFilter) dashFilter.value = e.target.value;
        state.pagination.page = 1;
        fetchExpenses();
    });

    // AI Financial Insights Triggers
    document.getElementById('openInsightsModalBtn')?.addEventListener('click', openInsightsModal);
    document.getElementById('triggerInsightsBottomBtn')?.addEventListener('click', openInsightsModal);
    document.getElementById('closeInsightsModalBtn')?.addEventListener('click', closeInsightsModal);
    document.getElementById('closeInsightsModalBtn2')?.addEventListener('click', closeInsightsModal);
    document.getElementById('regenerateInsightsBtn')?.addEventListener('click', loadFinancialInsights);

    // Reset / Clear All Expenses Action
    document.getElementById('clearAllExpensesBtn')?.addEventListener('click', handleClearAllExpenses);

    // Forms
    document.getElementById('quickLogForm')?.addEventListener('submit', handleQuickLogSubmit);
    document.getElementById('expenseForm')?.addEventListener('submit', handleExpenseModalSubmit);
    document.getElementById('budgetsForm')?.addEventListener('submit', handleBudgetsSubmit);

    // Bulk Import Action
    document.getElementById('confirmBulkImportBtn')?.addEventListener('click', handleBulkImportConfirm);
    document.getElementById('toggleSelectAllBtn')?.addEventListener('click', toggleSelectAllReviewRows);
    document.getElementById('selectAllCheckbox')?.addEventListener('change', (e) => {
        document.querySelectorAll('.review-row-check').forEach(cb => cb.checked = e.target.checked);
        recalcReviewSummary();
    });

    // Quick Preset Chips in Modal
    document.querySelectorAll('.chip-preset').forEach(chip => {
        chip.addEventListener('click', (e) => {
            const addVal = parseFloat(e.target.dataset.val);
            const amountInput = document.getElementById('modalAmount');
            const currentVal = parseFloat(amountInput.value) || 0;
            amountInput.value = (currentVal + addVal).toFixed(2);
        });
    });

    // Table Filtering & Search
    const searchInput = document.getElementById('tableSearchInput');
    let searchDebounce = null;
    searchInput?.addEventListener('input', (e) => {
        clearTimeout(searchDebounce);
        const clearBtn = document.getElementById('clearSearchBtn');
        if (clearBtn) clearBtn.style.display = e.target.value ? 'block' : 'none';
        searchDebounce = setTimeout(() => {
            state.filters.search = e.target.value.trim();
            state.pagination.page = 1;
            fetchExpenses();
        }, 300);
    });

    document.getElementById('clearSearchBtn')?.addEventListener('click', () => {
        if (searchInput) searchInput.value = '';
        document.getElementById('clearSearchBtn').style.display = 'none';
        state.filters.search = '';
        state.pagination.page = 1;
        fetchExpenses();
    });

    document.getElementById('tableCategoryFilter')?.addEventListener('change', (e) => {
        state.filters.category = e.target.value;
        state.pagination.page = 1;
        fetchExpenses();
    });

    document.getElementById('tablePaymentFilter')?.addEventListener('change', (e) => {
        state.filters.payment_method = e.target.value;
        state.pagination.page = 1;
        fetchExpenses();
    });

    // Pagination
    document.getElementById('prevPageBtn')?.addEventListener('click', () => {
        if (state.pagination.page > 1) {
            state.pagination.page--;
            fetchExpenses();
        }
    });

    document.getElementById('nextPageBtn')?.addEventListener('click', () => {
        if (state.pagination.page < state.pagination.total_pages) {
            state.pagination.page++;
            fetchExpenses();
        }
    });

    // Keyboard Shortcuts
    document.addEventListener('keydown', (e) => {
        if ((e.key === 'n' || e.key === 'N') && !['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
            e.preventDefault();
            openExpenseModal();
        }
        if (e.key === 'Escape') {
            closeExpenseModal();
            closeBudgetsModal();
            closeStatementModal();
        }
    });
}

/* ==========================================================================
   AI Statement Analyzer & Upload Dropzone
   ========================================================================== */
function openStatementModal() {
    showUploadStep();
    document.getElementById('statementModal')?.classList.add('active');
}

function closeStatementModal() {
    document.getElementById('statementModal')?.classList.remove('active');
}

function showUploadStep() {
    document.getElementById('statementUploadStep').style.display = 'block';
    document.getElementById('statementProcessingStep').style.display = 'none';
    document.getElementById('statementReviewStep').style.display = 'none';
    const fileInput = document.getElementById('statementFileInput');
    if (fileInput) fileInput.value = '';
}

function showProcessingStep(fileName) {
    document.getElementById('statementUploadStep').style.display = 'none';
    document.getElementById('statementProcessingStep').style.display = 'block';
    document.getElementById('statementReviewStep').style.display = 'none';
    const nameEl = document.getElementById('processingFileName');
    if (nameEl) nameEl.textContent = `Analyzing "${fileName}" with Gemini AI...`;
}

function showReviewStep(transactions) {
    document.getElementById('statementUploadStep').style.display = 'none';
    document.getElementById('statementProcessingStep').style.display = 'none';
    document.getElementById('statementReviewStep').style.display = 'block';
    renderReviewTable(transactions);
}

function initDropzoneEvents() {
    const dropzone = document.getElementById('statementDropzone');
    const fileInput = document.getElementById('statementFileInput');

    if (!dropzone || !fileInput) return;

    dropzone.addEventListener('click', () => fileInput.click());

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleStatementUpload(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleStatementUpload(e.target.files[0]);
        }
    });
}

async function handleStatementUpload(file) {
    if (!file) return;
    
    showProcessingStep(file.name);

    const formData = new FormData();
    formData.append('file', file);

    const clientApiKey = localStorage.getItem('gemini_api_key') || '';
    const headers = {};
    if (clientApiKey) headers['X-Gemini-API-Key'] = clientApiKey;

    try {
        const res = await apiFetch('/api/upload-statement', {
            method: 'POST',
            body: formData
        });

        const data = await res.json();
        if (data.success && data.transactions && data.transactions.length > 0) {
            state.aiParsedTransactions = data.transactions;
            showReviewStep(data.transactions);
            showToast(`Gemini extracted ${data.count} transactions! Review before saving.`, 'success');
        } else if (data.success && (!data.transactions || data.transactions.length === 0)) {
            showToast('No expense transactions detected in this statement.', 'error');
            showUploadStep();
        } else {
            showToast(data.error || 'Failed to parse statement', 'error');
            showUploadStep();
            if (data.error && data.error.includes('API key')) {
                openApiKeyModal();
            }
        }
    } catch (err) {
        showToast('Error uploading statement: ' + err.message, 'error');
        showUploadStep();
    }
}

function formatDateForInput(dateStr) {
    if (!dateStr) return new Date().toISOString().split('T')[0];
    const s = String(dateStr).trim().split('T')[0].split(' ')[0];
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
    const parsed = new Date(dateStr);
    if (!isNaN(parsed.getTime())) {
        return parsed.toISOString().split('T')[0];
    }
    return new Date().toISOString().split('T')[0];
}

function renderReviewTable(transactions) {
    const tbody = document.getElementById('statementReviewTableBody');
    if (!tbody) return;

    tbody.innerHTML = transactions.map((t, idx) => {
        const catOptions = state.categories.map(c => 
            `<option value="${c.name}" ${c.name === t.category ? 'selected' : ''}>${c.name}</option>`
        ).join('');
        const formattedDate = formatDateForInput(t.date);

        return `
            <tr data-index="${idx}" class="review-row">
                <td>
                    <input type="checkbox" class="review-row-check" checked onchange="recalcReviewSummary()">
                </td>
                <td>
                    <input type="date" class="review-row-date" value="${formattedDate}">
                </td>
                <td>
                    <input type="text" class="review-row-desc" value="${escapeHtml(t.description || 'Expense')}">
                </td>
                <td>
                    <select class="review-row-cat">
                        ${catOptions}
                    </select>
                </td>
                <td>
                    <input type="text" class="review-row-pay" value="${escapeHtml(t.payment_method || 'Credit Card')}">
                </td>
                <td>
                    <input type="number" step="0.01" min="0.01" class="review-row-amt" value="${(parseFloat(t.amount) || 0).toFixed(2)}" oninput="recalcReviewSummary()">
                </td>
                <td class="text-center">
                    <button type="button" class="review-row-del-btn" onclick="removeReviewRow(${idx})" title="Remove">
                        <i class="fa-solid fa-trash-can"></i>
                    </button>
                </td>
            </tr>
        `;
    }).join('');

    recalcReviewSummary();
}

function removeReviewRow(idx) {
    const row = document.querySelector(`.review-row[data-index="${idx}"]`);
    if (row) {
        row.remove();
        recalcReviewSummary();
    }
}

function toggleSelectAllReviewRows() {
    const checkboxes = document.querySelectorAll('.review-row-check');
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    checkboxes.forEach(cb => cb.checked = !allChecked);
    const selectAllCb = document.getElementById('selectAllCheckbox');
    if (selectAllCb) selectAllCb.checked = !allChecked;
    recalcReviewSummary();
}

function recalcReviewSummary() {
    let total = 0;
    let count = 0;

    document.querySelectorAll('.review-row').forEach(row => {
        const isChecked = row.querySelector('.review-row-check')?.checked;
        const amt = parseFloat(row.querySelector('.review-row-amt')?.value) || 0;
        if (isChecked) {
            total += amt;
            count++;
        }
    });

    const badge = document.getElementById('reviewCountBadge');
    const totalEl = document.getElementById('reviewTotalAmount');
    const btnText = document.getElementById('confirmImportBtnText');
    const topBtnText = document.getElementById('topConfirmImportBtnText');

    if (badge) badge.textContent = `${count} selected (${document.querySelectorAll('.review-row').length} total)`;
    if (totalEl) totalEl.textContent = formatCurrency(total);
    if (btnText) btnText.textContent = `Import ${count} to Excel`;
    if (topBtnText) topBtnText.textContent = `Import (${count})`;
}

async function handleBulkImportConfirm() {
    const btn = document.getElementById('confirmBulkImportBtn');
    const topBtn = document.getElementById('topConfirmBulkImportBtn');
    const btnText = document.getElementById('confirmImportBtnText');
    const topBtnText = document.getElementById('topConfirmImportBtnText');
    const itemsToImport = [];

    document.querySelectorAll('.review-row').forEach(row => {
        const isChecked = row.querySelector('.review-row-check')?.checked;
        if (isChecked) {
            let date = row.querySelector('.review-row-date')?.value;
            if (!date) {
                date = new Date().toISOString().split('T')[0];
            }
            const description = (row.querySelector('.review-row-desc')?.value || 'Expense').trim();
            const category = row.querySelector('.review-row-cat')?.value || 'Miscellaneous';
            const payment_method = (row.querySelector('.review-row-pay')?.value || 'Credit Card').trim();
            const amount = parseFloat(row.querySelector('.review-row-amt')?.value) || 0;

            if (amount > 0) {
                itemsToImport.push({ date, description, category, payment_method, amount });
            }
        }
    });

    if (itemsToImport.length === 0) {
        showToast('Please select at least one valid transaction to import.', 'error');
        return;
    }

    if (btn) btn.disabled = true;
    if (topBtn) topBtn.disabled = true;
    if (btnText) btnText.textContent = 'Importing...';
    if (topBtnText) topBtnText.textContent = 'Importing...';

    try {
        const res = await apiFetch('/api/expenses/bulk', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items: itemsToImport })
        });

        const data = await res.json();
        if (data.success) {
            showToast(`🎉 Successfully imported ${data.count} expenses into Excel!`, 'success');
            closeStatementModal();
            
            // Auto-switch to imported month if available
            if (data.imported_month) {
                state.selectedMonth = data.imported_month;
                state.filters.month = data.imported_month;
            } else {
                state.selectedMonth = 'auto';
                state.filters.month = 'auto';
            }

            // Reset filters to show new records immediately
            state.filters.category = 'all';
            state.filters.payment_method = 'all';
            state.filters.search = '';
            state.pagination.page = 1;
            
            const catFilter = document.getElementById('tableCategoryFilter');
            const payFilter = document.getElementById('tablePaymentFilter');
            const searchInput = document.getElementById('tableSearchInput');
            if (catFilter) catFilter.value = 'all';
            if (payFilter) payFilter.value = 'all';
            if (searchInput) searchInput.value = '';
            
            await Promise.all([fetchSummary(), fetchExpenses()]);
        } else {
            showToast(data.error || 'Failed to import expenses', 'error');
        }
    } catch (err) {
        showToast('Error importing expenses: ' + err.message, 'error');
    } finally {
        if (btn) btn.disabled = false;
        if (topBtn) topBtn.disabled = false;
        if (btnText) btnText.textContent = 'Import to Excel';
        if (topBtnText) topBtnText.textContent = 'Import to Excel';
    }
}

/* ==========================================================================
   Data Fetching & Init
   ========================================================================== */
async function loadInitialData() {
    try {
        checkApiKeyStatus();
        await fetchCategories();
        await fetchSummary();
        await fetchExpenses();
    } catch (err) {
        showToast('Error loading data: ' + err.message, 'error');
    }
}

async function fetchCategories() {
    const res = await apiFetch('/api/categories');
    const data = await res.json();
    if (data.success) {
        state.categories = data.data;
        populateCategoryDropdowns(data.data);
    }
}

function populateCategoryDropdowns(categories) {
    const quickSelect = document.getElementById('quickCategory');
    const modalSelect = document.getElementById('modalCategory');
    const tableFilter = document.getElementById('tableCategoryFilter');
    const dashCategoryFilter = document.getElementById('dashboardCategoryFilter');

    if (quickSelect) {
        quickSelect.innerHTML = '<option value="" disabled selected>Category</option>';
        categories.forEach(c => {
            quickSelect.innerHTML += `<option value="${c.name}">${c.name}</option>`;
        });
    }

    if (modalSelect) {
        modalSelect.innerHTML = '<option value="" disabled selected>Select Category</option>';
        categories.forEach(c => {
            modalSelect.innerHTML += `<option value="${c.name}">${c.name}</option>`;
        });
    }

    if (tableFilter) {
        tableFilter.innerHTML = '<option value="all">All Categories</option>';
        categories.forEach(c => {
            tableFilter.innerHTML += `<option value="${c.name}">${c.name}</option>`;
        });
    }

    if (dashCategoryFilter) {
        dashCategoryFilter.innerHTML = '<option value="all">All Categories</option>';
        categories.forEach(c => {
            dashCategoryFilter.innerHTML += `<option value="${c.name}">${c.name}</option>`;
        });
    }
}

async function fetchSummary() {
    try {
        const monthParam = state.selectedMonth || 'auto';
        const res = await apiFetch(`/api/summary?month=${encodeURIComponent(monthParam)}`);
        const data = await res.json();
        if (data.success) {
            state.summary = data.data;
            if (data.data.active_month && (!state.selectedMonth || state.selectedMonth === 'auto')) {
                state.selectedMonth = data.data.active_month;
            }
            state.selectedMonthLabel = data.data.active_month_label || 'Current Month';
            updateDashboardMetrics(data.data);
            renderCharts(data.data);
            updateResetButtonUI();

            // Populate / sync month dropdown
            const monthSelect = document.getElementById('dashboardMonthSelector');
            if (monthSelect && data.data.available_months) {
                const currentVal = state.selectedMonth || data.data.active_month;
                monthSelect.innerHTML = data.data.available_months.map(m => 
                    `<option value="${m.value}" ${m.value === currentVal ? 'selected' : ''}>${m.label}</option>`
                ).join('');
                monthSelect.innerHTML += `<option value="all" ${currentVal === 'all' ? 'selected' : ''}>All Time Overview</option>`;
            }

            const activeLabelEl = document.getElementById('activePeriodLabel');
            if (activeLabelEl) {
                activeLabelEl.textContent = `${data.data.active_month_label} Overview`;
            }

            const insightsPeriodLabel = document.getElementById('insightsPeriodLabel');
            if (insightsPeriodLabel) {
                insightsPeriodLabel.textContent = data.data.active_month_label;
            }
        }
    } catch (err) {
        console.error('Failed to fetch summary:', err);
    }
}

async function fetchExpenses() {
    try {
        const currentMonth = state.selectedMonth || (state.summary?.active_month) || 'auto';
        const params = new URLSearchParams({
            page: state.pagination.page,
            limit: state.pagination.limit,
            category: state.filters.category,
            payment_method: state.filters.payment_method,
            search: state.filters.search,
            month: currentMonth
        });

        const res = await apiFetch(`/api/expenses?${params.toString()}`);
        const data = await res.json();
        if (data.success) {
            state.expenses = data.data;
            state.pagination = data.pagination;
            renderExpensesTable(data.data);
            updatePaginationUI();
        }
    } catch (err) {
        console.error('Failed to fetch expenses:', err);
    }
}

/* ==========================================================================
   Dashboard Metrics Render
   ========================================================================== */
function formatCurrency(num) {
    return '$' + (num || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function updateDashboardMetrics(summary) {
    const kpiMonthSpend = document.getElementById('kpiMonthSpend');
    if (kpiMonthSpend) kpiMonthSpend.textContent = formatCurrency(summary.current_month_spend);

    const kpiMonthTitle = document.getElementById('kpiMonthSpendTitle');
    if (kpiMonthTitle) kpiMonthTitle.textContent = `Spent (${summary.active_month_label})`;

    const kpiGrowthBadge = document.getElementById('kpiGrowthBadge');
    const kpiGrowthText = document.getElementById('kpiGrowthText');
    if (kpiGrowthBadge && kpiGrowthText) {
        const growth = summary.mom_growth_pct;
        kpiGrowthText.textContent = `${growth >= 0 ? '+' : ''}${growth}% vs prev mo`;
        kpiGrowthBadge.className = `badge ${growth > 10 ? 'badge-warning' : 'badge-success'}`;
    }

    const kpiTxnCount = document.getElementById('kpiTxnCount');
    if (kpiTxnCount) kpiTxnCount.textContent = `${summary.current_month_count} entries in ${summary.active_month_label}`;

    const kpiTotalBudget = document.getElementById('kpiTotalBudget');
    if (kpiTotalBudget) kpiTotalBudget.textContent = formatCurrency(summary.total_monthly_budget);

    const progressBar = document.getElementById('kpiBudgetProgressBar');
    const budgetPctLabel = document.getElementById('kpiBudgetUsagePct');
    if (progressBar && budgetPctLabel) {
        const usage = Math.min(summary.budget_usage_pct, 100);
        progressBar.style.width = `${usage}%`;
        budgetPctLabel.textContent = `${summary.budget_usage_pct}% spent`;
        
        if (summary.budget_usage_pct > 90) {
            progressBar.style.background = 'linear-gradient(90deg, #f59e0b, #f43f5e)';
        } else {
            progressBar.style.background = 'linear-gradient(90deg, #6366f1, #06b6d4)';
        }
    }

    const kpiRemaining = document.getElementById('kpiRemainingBudget');
    const statusBadge = document.getElementById('kpiBudgetStatusBadge');
    if (kpiRemaining) kpiRemaining.textContent = formatCurrency(summary.remaining_budget);
    if (statusBadge) {
        if (summary.budget_usage_pct > 100) {
            statusBadge.className = 'badge badge-danger';
            statusBadge.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Over Budget';
        } else if (summary.budget_usage_pct > 80) {
            statusBadge.className = 'badge badge-warning';
            statusBadge.innerHTML = '<i class="fa-solid fa-circle-exclamation"></i> Close to Limit';
        } else {
            statusBadge.className = 'badge badge-success';
            statusBadge.innerHTML = '<i class="fa-solid fa-shield-check"></i> On Track';
        }
    }

    const kpiDailyAvg = document.getElementById('kpiDailyAvg');
    const kpiProjected = document.getElementById('kpiProjectedTotal');
    if (kpiDailyAvg) kpiDailyAvg.textContent = formatCurrency(summary.daily_avg_spend);
    if (kpiProjected) {
        const now = new Date();
        const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
        const projected = summary.daily_avg_spend * daysInMonth;
        kpiProjected.textContent = `Projected: ${formatCurrency(projected)} by month-end`;
    }

    const kpiTopCategory = document.getElementById('kpiTopCategory');
    const kpiTopAmt = document.getElementById('kpiTopCategoryAmount');
    if (kpiTopCategory) kpiTopCategory.textContent = summary.top_category;
    if (kpiTopAmt) kpiTopAmt.textContent = formatCurrency(summary.top_category_amount);
}

/* ==========================================================================
   Chart.js Visualizations
   ========================================================================== */
function getChartTextColor() {
    return state.theme === 'dark' ? '#94a3b8' : '#475569';
}

function getChartGridColor() {
    return state.theme === 'dark' ? 'rgba(255, 255, 255, 0.06)' : 'rgba(0, 0, 0, 0.06)';
}

function renderCharts(summary) {
    const isDark = state.theme === 'dark';
    const textColor = getChartTextColor();
    const gridColor = getChartGridColor();

    // 1. Timeline Area Chart
    const ctxTimeline = document.getElementById('timelineChart')?.getContext('2d');
    if (ctxTimeline) {
        if (state.charts.timeline) state.charts.timeline.destroy();

        const gradient = ctxTimeline.createLinearGradient(0, 0, 0, 240);
        gradient.addColorStop(0, 'rgba(99, 102, 241, 0.45)');
        gradient.addColorStop(1, 'rgba(99, 102, 241, 0.0)');

        state.charts.timeline = new Chart(ctxTimeline, {
            type: 'line',
            data: {
                labels: summary.timeline.labels,
                datasets: [{
                    label: 'Daily Spending ($)',
                    data: summary.timeline.values,
                    borderColor: '#6366f1',
                    borderWidth: 2.5,
                    fill: true,
                    backgroundColor: gradient,
                    tension: 0.35,
                    pointBackgroundColor: '#8b5cf6',
                    pointBorderColor: '#fff',
                    pointHoverRadius: 6,
                    pointRadius: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: isDark ? 'rgba(15, 23, 42, 0.95)' : 'rgba(255, 255, 255, 0.95)',
                        titleColor: isDark ? '#fff' : '#0f172a',
                        bodyColor: isDark ? '#cbd5e1' : '#334155',
                        borderColor: 'rgba(99, 102, 241, 0.3)',
                        borderWidth: 1,
                        padding: 10,
                        callbacks: {
                            label: (context) => `Spent: $${context.raw.toFixed(2)}`
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: textColor, font: { size: 11 } }
                    },
                    y: {
                        grid: { color: gridColor },
                        ticks: {
                            color: textColor,
                            font: { size: 11 },
                            callback: (value) => `$${value}`
                        }
                    }
                }
            }
        });
    }

    // 2. Category Donut Chart
    const ctxDonut = document.getElementById('categoryDonutChart')?.getContext('2d');
    if (ctxDonut) {
        if (state.charts.categoryDonut) state.charts.categoryDonut.destroy();

        const catLabels = summary.category_breakdown.map(c => c.category);
        const catValues = summary.category_breakdown.map(c => c.amount);
        const catColors = summary.category_breakdown.map(c => c.color);

        state.charts.categoryDonut = new Chart(ctxDonut, {
            type: 'doughnut',
            data: {
                labels: catLabels.length ? catLabels : ['No Expenses'],
                datasets: [{
                    data: catValues.length ? catValues : [1],
                    backgroundColor: catColors.length ? catColors : ['#334155'],
                    borderWidth: 0,
                    hoverOffset: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '72%',
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const val = context.raw || 0;
                                const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
                                return ` $${val.toFixed(2)} (${pct}%)`;
                            }
                        }
                    }
                }
            }
        });

        const legendContainer = document.getElementById('categoryLegendContainer');
        if (legendContainer) {
            legendContainer.innerHTML = summary.category_breakdown.map(c => `
                <div class="legend-item" title="${c.category}: $${c.amount.toFixed(2)} (${c.percentage}%)">
                    <span class="legend-color-dot" style="background-color: ${c.color}"></span>
                    <span>${c.category} (${c.percentage}%)</span>
                </div>
            `).join('') || '<span class="metric-subtext">No expenses recorded yet.</span>';
        }
    }

    // 3. Budget vs Actual Bar Chart
    const ctxBudget = document.getElementById('budgetBarChart')?.getContext('2d');
    if (ctxBudget) {
        if (state.charts.budgetBar) state.charts.budgetBar.destroy();

        const budgetCats = summary.budget_comparison.slice(0, 8);
        const labels = budgetCats.map(b => b.category);
        const actuals = budgetCats.map(b => b.actual);
        const limits = budgetCats.map(b => b.budget);

        state.charts.budgetBar = new Chart(ctxBudget, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Actual Spend ($)',
                        data: actuals,
                        backgroundColor: '#6366f1',
                        borderRadius: 6
                    },
                    {
                        label: 'Budget Limit ($)',
                        data: limits,
                        backgroundColor: isDark ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.12)',
                        borderRadius: 6
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: { color: textColor, font: { size: 12, weight: 600 } }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => ` ${context.dataset.label}: $${context.raw.toFixed(2)}`
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { color: textColor, font: { size: 11 } }
                    },
                    y: {
                        grid: { color: gridColor },
                        ticks: {
                            color: textColor,
                            font: { size: 11 },
                            callback: (value) => `$${value}`
                        }
                    }
                }
            }
        });
    }

    // 4. Payment Methods Donut Chart
    const ctxPayment = document.getElementById('paymentChart')?.getContext('2d');
    if (ctxPayment) {
        if (state.charts.payment) state.charts.payment.destroy();

        const payLabels = Object.keys(summary.payment_methods);
        const payValues = Object.values(summary.payment_methods);
        const payColors = ['#10b981', '#3b82f6', '#f59e0b', '#8b5cf6', '#ec4899', '#64748b'];

        state.charts.payment = new Chart(ctxPayment, {
            type: 'doughnut',
            data: {
                labels: payLabels.length ? payLabels : ['None'],
                datasets: [{
                    data: payValues.length ? payValues : [1],
                    backgroundColor: payColors.slice(0, payLabels.length || 1),
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: textColor, font: { size: 11 }, boxWidth: 10 }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => ` $${context.raw.toFixed(2)}`
                        }
                    }
                }
            }
        });
    }
}

/* ==========================================================================
   Transactions Table Render
   ========================================================================== */
function renderExpensesTable(expenses) {
    const tbody = document.getElementById('expensesTableBody');
    const mobileCardsContainer = document.getElementById('mobileTxnsCardsContainer');

    if (!expenses || expenses.length === 0) {
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="table-empty-state">
                        <i class="fa-solid fa-inbox" style="font-size: 24px; margin-bottom: 8px; display: block; opacity: 0.5;"></i>
                        No expense records found. Try logging a new expense, uploading a statement, or clearing filters!
                    </td>
                </tr>
            `;
        }
        if (mobileCardsContainer) {
            mobileCardsContainer.innerHTML = `
                <div class="mobile-empty-state">
                    <div class="empty-icon-circle">
                        <i class="fa-solid fa-receipt"></i>
                    </div>
                    <h4>No expenses found</h4>
                    <p>Log an expense or upload a statement to start tracking your finances.</p>
                </div>
            `;
        }
        return;
    }

    const catMetaMap = {};
    state.categories.forEach(c => {
        catMetaMap[c.name] = c;
    });

    if (tbody) {
        tbody.innerHTML = expenses.map(item => {
            const meta = catMetaMap[item.category] || { color: '#64748B', icon: 'tags' };
            const paymentIcon = getPaymentIcon(item.payment_method);

            return `
                <tr data-id="${item.id}">
                    <td class="td-id">#${item.id}</td>
                    <td class="td-date">${item.date}</td>
                    <td class="td-desc">${escapeHtml(item.description || 'No description')}</td>
                    <td>
                        <span class="category-pill" style="background-color: ${meta.color}20; color: ${meta.color}; border: 1px solid ${meta.color}40;">
                            <i class="fa-solid fa-${meta.icon}"></i>
                            ${escapeHtml(item.category)}
                        </span>
                    </td>
                    <td>
                        <span class="payment-badge">
                            <i class="${paymentIcon}"></i>
                            ${escapeHtml(item.payment_method)}
                        </span>
                    </td>
                    <td class="td-amount text-right">${formatCurrency(item.amount)}</td>
                    <td class="text-center">
                        <div class="table-row-actions">
                            <button class="btn-action-icon" title="Edit Expense" onclick="openExpenseModal(${item.id})">
                                <i class="fa-solid fa-pencil"></i>
                            </button>
                            <button class="btn-action-icon btn-delete" title="Delete Expense" onclick="handleDeleteExpense(${item.id})">
                                <i class="fa-solid fa-trash-can"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    }

    if (mobileCardsContainer) {
        mobileCardsContainer.innerHTML = expenses.map(item => {
            const meta = catMetaMap[item.category] || { color: '#64748B', icon: 'tags' };
            const paymentIcon = getPaymentIcon(item.payment_method);

            return `
                <div class="mobile-txn-card" data-id="${item.id}">
                    <div class="txn-card-header">
                        <div class="txn-card-cat-wrap">
                            <div class="txn-cat-badge" style="background-color: ${meta.color}20; color: ${meta.color};">
                                <i class="fa-solid fa-${meta.icon}"></i>
                            </div>
                            <div class="txn-cat-title-group">
                                <span class="txn-cat-name" style="color: ${meta.color};">${escapeHtml(item.category)}</span>
                                <span class="txn-date-tag">${item.date}</span>
                            </div>
                        </div>
                        <div class="txn-amount-badge">
                            -${formatCurrency(item.amount)}
                        </div>
                    </div>
                    <div class="txn-card-body">
                        <h4 class="txn-card-desc">${escapeHtml(item.description || 'No description')}</h4>
                    </div>
                    <div class="txn-card-footer">
                        <span class="txn-payment-pill">
                            <i class="${paymentIcon}"></i>
                            ${escapeHtml(item.payment_method)}
                        </span>
                        <div class="txn-actions-pill-group">
                            <button class="btn-mob-action" title="Edit" onclick="openExpenseModal(${item.id})">
                                <i class="fa-solid fa-pencil"></i>
                            </button>
                            <button class="btn-mob-action btn-mob-del" title="Delete" onclick="handleDeleteExpense(${item.id})">
                                <i class="fa-solid fa-trash-can"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }
}

function getPaymentIcon(method) {
    if (!method) return 'fa-solid fa-wallet';
    const m = method.toLowerCase();
    if (m.includes('amex') || m.includes('american express')) return 'fa-brands fa-cc-amex';
    if (m.includes('credit')) return 'fa-solid fa-credit-card';
    if (m.includes('debit')) return 'fa-solid fa-id-card';
    if (m.includes('cash')) return 'fa-solid fa-money-bill-1-wave';
    if (m.includes('bank') || m.includes('transfer')) return 'fa-solid fa-building-columns';
    if (m.includes('upi') || m.includes('online')) return 'fa-solid fa-mobile-screen-button';
    return 'fa-solid fa-wallet';
}

function updatePaginationUI() {
    const { page, limit, total_items, total_pages } = state.pagination;
    
    const start = total_items === 0 ? 0 : (page - 1) * limit + 1;
    const end = Math.min(page * limit, total_items);

    document.getElementById('pagStart').textContent = start;
    document.getElementById('pagEnd').textContent = end;
    document.getElementById('pagTotal').textContent = total_items;

    const mobBadge = document.getElementById('mobTxnCountBadge');
    if (mobBadge) mobBadge.textContent = total_items;

    const prevBtn = document.getElementById('prevPageBtn');
    const nextBtn = document.getElementById('nextPageBtn');

    if (prevBtn) prevBtn.disabled = page <= 1;
    if (nextBtn) nextBtn.disabled = page >= total_pages;

    const numbersContainer = document.getElementById('pageNumbersContainer');
    if (numbersContainer) {
        let pagesHtml = '';
        for (let i = 1; i <= total_pages; i++) {
            if (i === 1 || i === total_pages || (i >= page - 1 && i <= page + 1)) {
                pagesHtml += `
                    <button class="btn-page-num ${i === page ? 'active' : ''}" onclick="goToPage(${i})">
                        ${i}
                    </button>
                `;
            }
        }
        numbersContainer.innerHTML = pagesHtml;
    }
}

function goToPage(page) {
    state.pagination.page = page;
    fetchExpenses();
}

/* ==========================================================================
   Expense Logging & Mutations
   ========================================================================== */
async function handleQuickLogSubmit(e) {
    e.preventDefault();
    const amount = document.getElementById('quickAmount').value;
    const description = document.getElementById('quickDescription').value;
    const category = document.getElementById('quickCategory').value;
    const payment_method = document.getElementById('quickPaymentMethod').value;
    const date = document.getElementById('quickDate').value;

    if (!category) {
        showToast('Please select a category', 'error');
        return;
    }

    try {
        const res = await apiFetch('/api/expenses', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ amount, description, category, payment_method, date })
        });
        const data = await res.json();
        if (data.success) {
            showToast('Expense logged and saved to Excel!', 'success');
            document.getElementById('quickAmount').value = '';
            document.getElementById('quickDescription').value = '';
            
            await Promise.all([fetchSummary(), fetchExpenses()]);
        } else {
            showToast(data.error || 'Failed to save expense', 'error');
        }
    } catch (err) {
        showToast('Network error: ' + err.message, 'error');
    }
}

function openExpenseModal(expenseId = null) {
    const modal = document.getElementById('expenseModal');
    const title = document.getElementById('expenseModalTitle');
    const submitText = document.getElementById('saveExpenseBtnText');
    const idInput = document.getElementById('modalExpenseId');
    const amountInput = document.getElementById('modalAmount');
    const descInput = document.getElementById('modalDescription');
    const catSelect = document.getElementById('modalCategory');
    const paySelect = document.getElementById('modalPaymentMethod');
    const dateInput = document.getElementById('modalDate');

    if (expenseId) {
        const item = state.expenses.find(e => e.id === expenseId);
        if (!item) return;

        state.isEditing = true;
        title.textContent = 'Edit Expense Record';
        submitText.textContent = 'Update Excel Record';
        idInput.value = item.id;
        amountInput.value = item.amount;
        descInput.value = item.description;
        catSelect.value = item.category;
        paySelect.value = item.payment_method;
        dateInput.value = item.date;
    } else {
        state.isEditing = false;
        title.textContent = 'Log New Expense';
        submitText.textContent = 'Save to Excel';
        idInput.value = '';
        amountInput.value = '';
        descInput.value = '';
        catSelect.selectedIndex = 0;
        paySelect.value = 'Credit Card';
        dateInput.value = new Date().toISOString().split('T')[0];
    }

    modal?.classList.add('active');
    setTimeout(() => amountInput?.focus(), 100);
}

function closeExpenseModal() {
    document.getElementById('expenseModal')?.classList.remove('active');
}

async function handleExpenseModalSubmit(e) {
    e.preventDefault();
    const id = document.getElementById('modalExpenseId').value;
    const amount = document.getElementById('modalAmount').value;
    const description = document.getElementById('modalDescription').value;
    const category = document.getElementById('modalCategory').value;
    const payment_method = document.getElementById('modalPaymentMethod').value;
    const date = document.getElementById('modalDate').value;

    const payload = { amount, description, category, payment_method, date };
    const url = state.isEditing ? `/api/expenses/${id}` : '/api/expenses';
    const method = state.isEditing ? 'PUT' : 'POST';

    try {
        const res = await apiFetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
            showToast(state.isEditing ? 'Expense updated in Excel!' : 'Expense saved to Excel!', 'success');
            closeExpenseModal();
            await Promise.all([fetchSummary(), fetchExpenses()]);
        } else {
            showToast(data.error || 'Failed to save', 'error');
        }
    } catch (err) {
        showToast('Error: ' + err.message, 'error');
    }
}

async function handleDeleteExpense(id) {
    if (!confirm(`Are you sure you want to delete expense record #${id}? This will remove it from expenses_data.xlsx.`)) {
        return;
    }

    try {
        const res = await apiFetch(`/api/expenses/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            showToast('Expense removed from Excel!', 'success');
            await Promise.all([fetchSummary(), fetchExpenses()]);
        } else {
            showToast(data.error || 'Failed to delete', 'error');
        }
    } catch (err) {
        showToast('Error: ' + err.message, 'error');
    }
}

async function handleClearAllExpenses() {
    const activeMonth = state.selectedMonth;
    const monthLabel = state.selectedMonthLabel || (activeMonth === 'all' ? 'All Months' : activeMonth);
    const isSpecific = activeMonth && activeMonth !== 'all' && activeMonth !== 'auto';
    
    const promptText = isSpecific
        ? `⚠️ Are you sure you want to delete ALL expenses for ${monthLabel} from expenses_data.xlsx?\n\nExpenses in other months will NOT be deleted.`
        : `⚠️ Are you sure you want to delete ALL expenses across ALL months from expenses_data.xlsx?\n\nThis will wipe all records. This action cannot be undone.`;

    if (!confirm(promptText)) return;

    try {
        const res = await apiFetch('/api/expenses/clear-all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ month: activeMonth })
        });
        const data = await res.json();
        if (data.success) {
            showToast(data.message || 'Expenses cleared successfully!', 'success');
            state.pagination.page = 1;
            await Promise.all([fetchSummary(), fetchExpenses()]);
        } else {
            showToast(data.error || 'Failed to reset expenses', 'error');
        }
    } catch (err) {
        showToast('Error: ' + err.message, 'error');
    }
}

function updateResetButtonUI() {
    const btn = document.getElementById('clearAllExpensesBtn');
    const mobResetItem = document.getElementById('mobActionResetAll');
    const activeMonth = state.selectedMonth;
    const monthLabel = state.selectedMonthLabel || 'Selected Month';
    const isSpecific = activeMonth && activeMonth !== 'all' && activeMonth !== 'auto';

    if (btn) {
        if (isSpecific) {
            btn.innerHTML = `<i class="fa-solid fa-trash-can"></i> <span>Reset ${monthLabel}</span>`;
            btn.title = `Clear all expense transactions for ${monthLabel} from Excel spreadsheet`;
        } else {
            btn.innerHTML = '<i class="fa-solid fa-trash-can"></i> <span>Reset All</span>';
            btn.title = 'Clear all expense transactions across all months from Excel spreadsheet';
        }
    }

    if (mobResetItem) {
        const strong = mobResetItem.querySelector('strong');
        if (strong) {
            strong.textContent = isSpecific ? `Reset ${monthLabel} Expenses` : 'Reset All Expenses';
        }
    }
}

/* ==========================================================================
   Budget Manager Modal
   ========================================================================== */
async function openBudgetsModal() {
    try {
        const res = await apiFetch('/api/budgets');
        const data = await res.json();
        if (data.success) {
            state.budgets = data.data;
            renderBudgetsInputs(data.data);
            document.getElementById('budgetsModal')?.classList.add('active');
        }
    } catch (err) {
        showToast('Failed to load budgets: ' + err.message, 'error');
    }
}

function closeBudgetsModal() {
    document.getElementById('budgetsModal')?.classList.remove('active');
}

function renderBudgetsInputs(budgets) {
    const grid = document.getElementById('budgetsInputsGrid');
    if (!grid) return;

    let total = 0;
    grid.innerHTML = state.categories.map(c => {
        const val = budgets[c.name] !== undefined ? budgets[c.name] : 0;
        total += parseFloat(val) || 0;
        return `
            <div class="budget-input-item">
                <div class="budget-item-header">
                    <span class="category-pill" style="background-color: ${c.color}20; color: ${c.color}; border: 1px solid ${c.color}40;">
                        <i class="fa-solid fa-${c.icon}"></i>
                    </span>
                    <span>${c.name}</span>
                </div>
                <div class="budget-input-wrap">
                    <span>$</span>
                    <input type="number" step="10" min="0" class="budget-cat-val" data-category="${c.name}" value="${val}" oninput="recalcTotalBudget()">
                </div>
            </div>
        `;
    }).join('');

    const totalEl = document.getElementById('modalTotalBudgetValue');
    if (totalEl) totalEl.textContent = formatCurrency(total);
}

function recalcTotalBudget() {
    let sum = 0;
    document.querySelectorAll('.budget-cat-val').forEach(input => {
        sum += parseFloat(input.value) || 0;
    });
    const totalEl = document.getElementById('modalTotalBudgetValue');
    if (totalEl) totalEl.textContent = formatCurrency(sum);
}

async function handleBudgetsSubmit(e) {
    e.preventDefault();
    const newBudgets = {};
    document.querySelectorAll('.budget-cat-val').forEach(input => {
        const cat = input.dataset.category;
        newBudgets[cat] = parseFloat(input.value) || 0;
    });

    try {
        const res = await apiFetch('/api/budgets', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ budgets: newBudgets })
        });
        const data = await res.json();
        if (data.success) {
            showToast('Monthly budgets updated in Excel!', 'success');
            closeBudgetsModal();
            await fetchSummary();
        } else {
            showToast(data.error || 'Failed to save budgets', 'error');
        }
    } catch (err) {
        showToast('Error: ' + err.message, 'error');
    }
}

/* ==========================================================================
   Toast Notifications
   ========================================================================== */
function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icon = type === 'success' ? 'fa-solid fa-circle-check' : 'fa-solid fa-circle-exclamation';
    
    toast.innerHTML = `
        <i class="${icon}"></i>
        <span>${escapeHtml(message)}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

/* ==========================================================================
   AI Provider & API Key Modal & Settings
   ========================================================================== */
function openApiKeyModal() {
    const modal = document.getElementById('apiKeyModal');
    if (!modal) return;
    modal.classList.add('active');

    const providerSelect = document.getElementById('aiProviderSelect');
    const input = document.getElementById('apiKeyInput');
    const savedKey = localStorage.getItem('ai_api_key') || localStorage.getItem('gemini_api_key') || '';
    const savedProvider = localStorage.getItem('ai_provider') || 'gemini';

    if (providerSelect) {
        providerSelect.value = savedProvider;
        updateProviderHelpUI(savedProvider);
    }
    if (input) {
        input.value = savedKey;
        input.focus();
    }
}

function closeApiKeyModal() {
    const modal = document.getElementById('apiKeyModal');
    if (modal) modal.classList.remove('active');
}

function updateProviderHelpUI(provider) {
    const input = document.getElementById('apiKeyInput');
    const link = document.getElementById('getApiKeyLink');
    const label = document.getElementById('apiKeyLabelText');

    if (provider === 'openai') {
        if (input) input.placeholder = 'sk-proj-... or sk-...';
        if (link) {
            link.href = 'https://platform.openai.com/api-keys';
            link.textContent = 'Get an OpenAI API key →';
        }
        if (label) label.textContent = 'OpenAI API Key';
    } else if (provider === 'anthropic') {
        if (input) input.placeholder = 'sk-ant-api03-...';
        if (link) {
            link.href = 'https://console.anthropic.com/';
            link.textContent = 'Get an Anthropic Claude key →';
        }
        if (label) label.textContent = 'Anthropic API Key';
    } else if (provider === 'openrouter') {
        if (input) input.placeholder = 'sk-or-v1-...';
        if (link) {
            link.href = 'https://openrouter.ai/keys';
            link.textContent = 'Get an OpenRouter key →';
        }
        if (label) label.textContent = 'OpenRouter API Key';
    } else {
        // Gemini
        if (input) input.placeholder = 'AIzaSy... or AQ.Ab8...';
        if (link) {
            link.href = 'https://aistudio.google.com/';
            link.textContent = 'Get a free Gemini key →';
        }
        if (label) label.textContent = 'Google Gemini API Key';
    }
}

async function handleApiKeySubmit(e) {
    e.preventDefault();
    const providerSelect = document.getElementById('aiProviderSelect');
    const input = document.getElementById('apiKeyInput');
    const newKey = input ? input.value.trim() : '';
    const newProvider = providerSelect ? providerSelect.value : 'gemini';

    if (!newKey) {
        showToast('Please enter a valid API key', 'error');
        return;
    }

    try {
        localStorage.setItem('ai_api_key', newKey);
        localStorage.setItem('gemini_api_key', newKey);
        localStorage.setItem('ai_provider', newProvider);
        
        // Also save to server backend config
        const res = await apiFetch('/api/config/api-key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: newKey, provider: newProvider })
        });
        const data = await res.json();
        
        if (data.success) {
            showToast(`${getProviderDisplayName(newProvider)} key saved & verified!`, 'success');
            updateApiKeyBadge(true, newProvider);
            closeApiKeyModal();
        } else {
            showToast(data.error || 'Failed to save key on server', 'error');
        }
    } catch (err) {
        showToast('Key saved locally in browser!', 'success');
        updateApiKeyBadge(true, newProvider);
        closeApiKeyModal();
    }
}

function getProviderDisplayName(provider) {
    switch (provider) {
        case 'openai': return 'OpenAI';
        case 'anthropic': return 'Claude';
        case 'openrouter': return 'OpenRouter';
        default: return 'Gemini';
    }
}

async function checkApiKeyStatus() {
    try {
        const clientKey = localStorage.getItem('ai_api_key') || localStorage.getItem('gemini_api_key');
        const clientProvider = localStorage.getItem('ai_provider') || 'gemini';

        if (clientKey) {
            updateApiKeyBadge(true, clientProvider);
            // Sync with backend if needed
            fetch('/api/config/api-key', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_key: clientKey, provider: clientProvider })
            }).catch(() => {});
            return;
        }

        const res = await apiFetch('/api/config/api-key');
        const data = await res.json();
        if (data.success && data.configured) {
            updateApiKeyBadge(true, data.provider || 'gemini');
        } else {
            updateApiKeyBadge(false, 'gemini');
        }
    } catch (err) {
        console.warn('API key status check failed:', err);
    }
}

function updateApiKeyBadge(isConfigured, provider = 'gemini') {
    const btnText = document.getElementById('apiKeyBtnText');
    const btn = document.getElementById('openApiKeyModalBtn');
    const providerName = getProviderDisplayName(provider);

    if (btn) {
        if (isConfigured) {
            if (btnText) btnText.textContent = `${providerName} ✓`;
            btn.style.borderColor = 'rgba(16, 185, 129, 0.4)';
            btn.style.color = 'var(--accent-emerald)';
            btn.title = `${providerName} API Key Configured ✓`;
        } else {
            if (btnText) btnText.textContent = 'Set AI Key';
            btn.style.borderColor = 'rgba(244, 63, 94, 0.4)';
            btn.style.color = 'var(--accent-rose)';
            btn.title = 'Configure AI Model & API Key';
        }
    }
}

/* ==========================================================================
   AI Financial Insights Modal
   ========================================================================== */
function openInsightsModal() {
    const modal = document.getElementById('insightsModal');
    if (!modal) return;
    modal.classList.add('active');
    loadFinancialInsights();
}

function closeInsightsModal() {
    const modal = document.getElementById('insightsModal');
    if (modal) modal.classList.remove('active');
}

async function loadFinancialInsights() {
    const loadingState = document.getElementById('insightsLoadingState');
    const contentState = document.getElementById('insightsContentState');
    const subtitle = document.getElementById('insightsModalSubtitle');
    const regenBtn = document.getElementById('regenerateInsightsBtn');

    if (loadingState) loadingState.style.display = 'flex';
    if (contentState) contentState.style.display = 'none';
    if (regenBtn) regenBtn.disabled = true;

    const clientApiKey = localStorage.getItem('gemini_api_key') || '';
    const headers = { 'Content-Type': 'application/json' };
    if (clientApiKey) headers['X-Gemini-API-Key'] = clientApiKey;

    try {
        const monthParam = state.selectedMonth || 'auto';
        const res = await apiFetch(`/api/insights?month=${encodeURIComponent(monthParam)}`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({ month: monthParam, gemini_api_key: clientApiKey })
        });
        const data = await res.json();

        if (data.success && data.data) {
            if (subtitle) subtitle.textContent = `Intelligent spending analysis for ${data.period || 'selected month'}`;
            renderInsightsContent(data.data);
            if (loadingState) loadingState.style.display = 'none';
            if (contentState) contentState.style.display = 'block';
        } else {
            showToast(data.error || 'Failed to generate insights', 'error');
            closeInsightsModal();
            if (data.error && data.error.includes('API key')) {
                openApiKeyModal();
            }
        }
    } catch (err) {
        showToast('Error generating insights: ' + err.message, 'error');
        closeInsightsModal();
    } finally {
        if (regenBtn) regenBtn.disabled = false;
    }
}

function renderInsightsContent(insights) {
    const container = document.getElementById('insightsContentState');
    if (!container) return;

    const score = insights.health_score || 80;
    const scoreColor = score >= 80 ? 'linear-gradient(135deg, #10b981, #06b6d4)' : score >= 60 ? 'linear-gradient(135deg, #f59e0b, #ec4899)' : 'linear-gradient(135deg, #f43f5e, #8b5cf6)';
    const status = escapeHtml(insights.status || 'Healthy');
    const headline = escapeHtml(insights.headline || 'Your spending is well balanced this month.');

    const observationsHtml = (insights.observations || []).map(obs => 
        `<li><i class="fa-solid fa-circle-info text-cyan"></i> <span>${escapeHtml(obs)}</span></li>`
    ).join('');

    const recommendationsHtml = (insights.recommendations || []).map(rec => 
        `<li><i class="fa-solid fa-lightbulb text-accent"></i> <span>${escapeHtml(rec)}</span></li>`
    ).join('');

    const alertsHtml = (insights.alerts && insights.alerts.length > 0) ? `
        <div class="insight-block" style="margin-bottom: 20px; border-color: rgba(244, 63, 94, 0.3); background: rgba(244, 63, 94, 0.05);">
            <div class="insight-block-title" style="color: var(--accent-rose);">
                <i class="fa-solid fa-triangle-exclamation text-rose"></i>
                <span>Budget Alerts & Overages</span>
            </div>
            <ul class="insight-list">
                ${insights.alerts.map(a => `<li><i class="fa-solid fa-circle-exclamation text-rose"></i> <span>${escapeHtml(a)}</span></li>`).join('')}
            </ul>
        </div>
    ` : '';

    const savingsVal = parseFloat(insights.projected_monthly_savings) || 0;

    container.innerHTML = `
        <div class="insights-header-card">
            <div class="score-dial-wrap">
                <div class="score-dial" style="background: ${scoreColor};">
                    ${score}
                </div>
                <div class="score-meta">
                    <strong>Financial Health: <span style="color: ${score >= 80 ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">${status}</span></strong>
                    <span>Calculated by budget discipline & spend pacing</span>
                </div>
            </div>
            <div class="badge-tech">
                <i class="fa-solid fa-wand-magic-sparkles text-accent"></i> Gemini 3.5 Flash
            </div>
        </div>

        <div class="insights-headline-box">
            <i class="fa-solid fa-quote-left" style="opacity: 0.5; margin-right: 6px;"></i>
            ${headline}
        </div>

        ${alertsHtml}

        <div class="insights-grid-2">
            <div class="insight-block">
                <div class="insight-block-title">
                    <i class="fa-solid fa-chart-line text-blue"></i>
                    <span>Key Spending Trends</span>
                </div>
                <ul class="insight-list">
                    ${observationsHtml || '<li>No notable anomalies detected.</li>'}
                </ul>
            </div>

            <div class="insight-block">
                <div class="insight-block-title">
                    <i class="fa-solid fa-piggy-bank text-emerald"></i>
                    <span>Actionable Recommendations</span>
                </div>
                <ul class="insight-list">
                    ${recommendationsHtml || '<li>Keep maintaining your daily budget tracking!</li>'}
                </ul>
            </div>
        </div>

        ${savingsVal > 0 ? `
        <div class="savings-highlight-card">
            <div class="savings-highlight-left">
                <div class="insights-icon-circle" style="width: 44px; height: 44px; font-size: 18px; background: var(--accent-emerald);">
                    <i class="fa-solid fa-hand-holding-dollar"></i>
                </div>
                <div>
                    <strong style="color: var(--text-primary); font-size: 14px;">Projected Monthly Savings</strong>
                    <p style="color: var(--text-muted); font-size: 12px; margin: 0;">Estimated savings by executing recommendations</p>
                </div>
            </div>
            <div class="savings-amount-val">+${formatCurrency(savingsVal)} / mo</div>
        </div>
        ` : ''}
    `;
}

/* ==========================================================================
   Mobile Experience & Navigation Controllers
   ========================================================================== */
function initMobileExperience() {
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) || window.innerWidth <= 768;
    document.documentElement.dataset.device = isMobile ? 'mobile' : 'desktop';

    window.addEventListener('resize', () => {
        const mob = window.innerWidth <= 768;
        document.documentElement.dataset.device = mob ? 'mobile' : 'desktop';
    });

    // Mobile Segmented Switcher Tabs
    const tabOverview = document.getElementById('mobTabOverview');
    const tabTxns = document.getElementById('mobTabTransactions');
    const metricsSection = document.querySelector('.metrics-grid');
    const chartsSection = document.querySelector('.analytics-grid, .charts-grid');
    const quickLogSection = document.getElementById('quickLogSection');
    const txnsSection = document.querySelector('.transactions-section');
    const insightsBanner = document.querySelector('.insights-banner-card');

    function switchMobileTab(tab) {
        if (tab === 'overview') {
            tabOverview?.classList.add('active');
            tabTxns?.classList.remove('active');
            if (metricsSection) metricsSection.style.display = 'grid';
            if (chartsSection) chartsSection.style.display = 'flex';
            if (quickLogSection) quickLogSection.style.display = 'block';
            if (insightsBanner) insightsBanner.style.display = 'flex';
            if (txnsSection) txnsSection.style.display = 'none';
            window.scrollTo({ top: 0, behavior: 'smooth' });
        } else {
            tabOverview?.classList.remove('active');
            tabTxns?.classList.add('active');
            if (metricsSection) metricsSection.style.display = 'none';
            if (chartsSection) chartsSection.style.display = 'none';
            if (quickLogSection) quickLogSection.style.display = 'none';
            if (insightsBanner) insightsBanner.style.display = 'none';
            if (txnsSection) {
                txnsSection.style.display = 'block';
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        }
    }

    if (isMobile) {
        switchMobileTab('overview');
    }

    tabOverview?.addEventListener('click', () => switchMobileTab('overview'));
    tabTxns?.addEventListener('click', () => switchMobileTab('transactions'));

    // Mobile Bottom App Bar Navigation
    const navHome = document.getElementById('mobNavDashboard');
    const navTxns = document.getElementById('mobNavTransactions');
    const fabAdd = document.getElementById('mobFabAddBtn');
    const navAi = document.getElementById('mobNavAiTools');
    const navSettings = document.getElementById('mobNavSettings');

    function setBottomNavActive(btn) {
        document.querySelectorAll('.mob-nav-item').forEach(b => b.classList.remove('active'));
        btn?.classList.add('active');
    }

    navHome?.addEventListener('click', () => {
        setBottomNavActive(navHome);
        switchMobileTab('overview');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    navTxns?.addEventListener('click', () => {
        setBottomNavActive(navTxns);
        switchMobileTab('transactions');
    });

    fabAdd?.addEventListener('click', () => {
        openExpenseModal();
    });

    // Mobile AI Tools Sheet
    const aiSheet = document.getElementById('mobAiActionSheet');
    navAi?.addEventListener('click', () => {
        if (aiSheet) aiSheet.classList.add('active');
    });
    document.getElementById('closeMobAiSheetBtn')?.addEventListener('click', () => {
        if (aiSheet) aiSheet.classList.remove('active');
    });

    document.getElementById('mobActionImportStatement')?.addEventListener('click', () => {
        if (aiSheet) aiSheet.classList.remove('active');
        openStatementModal();
    });

    document.getElementById('mobActionGenerateInsights')?.addEventListener('click', () => {
        if (aiSheet) aiSheet.classList.remove('active');
        openInsightsModal();
    });

    document.getElementById('mobActionConfigureKey')?.addEventListener('click', () => {
        if (aiSheet) aiSheet.classList.remove('active');
        openApiKeyModal();
    });

    // Mobile Manage/Settings Sheet
    const manageSheet = document.getElementById('mobManageActionSheet');
    navSettings?.addEventListener('click', () => {
        if (manageSheet) manageSheet.classList.add('active');
    });
    document.getElementById('closeMobManageSheetBtn')?.addEventListener('click', () => {
        if (manageSheet) manageSheet.classList.remove('active');
    });

    document.getElementById('mobActionEditBudgets')?.addEventListener('click', () => {
        if (manageSheet) manageSheet.classList.remove('active');
        openBudgetsModal();
    });

    document.getElementById('mobActionResetAll')?.addEventListener('click', () => {
        if (manageSheet) manageSheet.classList.remove('active');
        handleClearAllExpenses();
    });
}

/* ==========================================================================
   Workspace Profile & Multi-Device Sync
   ========================================================================== */
function openWorkspaceModal() {
    const modal = document.getElementById('workspaceModal');
    const input = document.getElementById('currentSyncCodeInput');
    if (input) input.value = getUserId();
    if (modal) modal.classList.add('active');
}

function updateSyncCodeUI() {
    const uid = getUserId();
    const desktopLabel = document.getElementById('desktopActiveSyncCodeLabel');
    if (desktopLabel) {
        desktopLabel.textContent = uid === 'default' ? 'Live Excel' : (uid.length > 12 ? `${uid.substring(0, 10)}...` : uid);
    }
}

function initWorkspaceSync() {
    updateSyncCodeUI();

    // Update all export links
    document.querySelectorAll('a[href^="/download-excel"]').forEach(a => {
        a.href = `/download-excel?user_id=${encodeURIComponent(getUserId())}`;
    });

    // Desktop navbar sync triggers
    document.getElementById('excelStatusPill')?.addEventListener('click', openWorkspaceModal);
    document.getElementById('desktopSyncNavBtn')?.addEventListener('click', openWorkspaceModal);

    const copyBtn = document.getElementById('copySyncCodeBtn');
    copyBtn?.addEventListener('click', () => {
        const uid = getUserId();
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(uid).then(() => {
                showToast('Sync Code copied to clipboard!', 'success');
            }).catch(() => {
                showToast(`Your Sync Code: ${uid}`, 'info');
            });
        } else {
            showToast(`Your Sync Code: ${uid}`, 'info');
        }
    });

    const switchBtn = document.getElementById('switchWorkspaceBtn');
    switchBtn?.addEventListener('click', async () => {
        const connectInput = document.getElementById('connectSyncCodeInput');
        const code = connectInput?.value?.trim();
        if (!code) {
            showToast('Please enter a Sync Code or custom name', 'error');
            return;
        }
        setUserId(code);
        updateSyncCodeUI();
        showToast(`Connected to workspace '${code}'!`, 'success');
        document.getElementById('workspaceModal')?.classList.remove('active');
        if (connectInput) connectInput.value = '';
        
        // Update export links
        document.querySelectorAll('a[href^="/download-excel"]').forEach(a => {
            a.href = `/download-excel?user_id=${encodeURIComponent(getUserId())}`;
        });

        // Refresh all data
        await loadInitialData();
    });

    document.getElementById('closeWorkspaceModalBtn')?.addEventListener('click', () => {
        document.getElementById('workspaceModal')?.classList.remove('active');
    });
    document.getElementById('closeWorkspaceModalBtn2')?.addEventListener('click', () => {
        document.getElementById('workspaceModal')?.classList.remove('active');
    });
    document.getElementById('mobActionWorkspaceSync')?.addEventListener('click', () => {
        document.getElementById('mobManageActionSheet')?.classList.remove('active');
        openWorkspaceModal();
    });
}

/* ==========================================================================
   Expenz AI Financial Copilot Chatbot
   ========================================================================== */
let copilotChatHistory = [];

function openCopilotModal() {
    const modal = document.getElementById('copilotModal');
    if (modal) modal.classList.add('active');
    
    // Hide floating launcher and mobile bottom bar while drawer is open
    const launcher = document.getElementById('copilotFloatingLauncher');
    if (launcher) launcher.style.display = 'none';
    const bottomBar = document.getElementById('mobileBottomBar');
    if (bottomBar && window.innerWidth <= 768) bottomBar.style.display = 'none';

    setTimeout(() => {
        document.getElementById('copilotInput')?.focus();
    }, 150);
}

function closeCopilotModal() {
    const modal = document.getElementById('copilotModal');
    if (modal) modal.classList.remove('active');

    // Restore floating launcher and mobile bottom bar
    const launcher = document.getElementById('copilotFloatingLauncher');
    if (launcher) launcher.style.display = 'block';
    const bottomBar = document.getElementById('mobileBottomBar');
    if (bottomBar && window.innerWidth <= 768) bottomBar.style.display = 'flex';
}

function clearCopilotHistory() {
    copilotChatHistory = [];
    const list = document.getElementById('copilotMessagesList');
    if (list) {
        list.innerHTML = `
            <div class="copilot-msg copilot-msg-ai">
                <div class="msg-avatar"><i class="fa-solid fa-brain"></i></div>
                <div class="msg-bubble">
                    <p>👋 Hi! I'm your <strong>Expenz AI Copilot</strong>. I have real-time access to your spreadsheet, category budgets, and transactions.</p>
                    <p style="margin-top: 6px; font-size: 12px; color: var(--text-secondary);">Ask me anything about your finances, top spending, budget forecasts, or how to save money!</p>
                </div>
            </div>
        `;
    }
    const followups = document.getElementById('copilotFollowups');
    if (followups) {
        followups.innerHTML = '';
        followups.style.display = 'none';
    }
    showToast('Chat history cleared', 'info');
}

function appendCopilotMessage(role, text) {
    const list = document.getElementById('copilotMessagesList');
    if (!list) return;

    const msgDiv = document.createElement('div');
    msgDiv.className = `copilot-msg copilot-msg-${role}`;

    if (role === 'ai') {
        const formatted = formatCopilotMarkdown(text);
        msgDiv.innerHTML = `
            <div class="msg-avatar"><i class="fa-solid fa-brain"></i></div>
            <div class="msg-bubble">${formatted}</div>
        `;
    } else {
        msgDiv.innerHTML = `
            <div class="msg-bubble"><p>${escapeHtml(text)}</p></div>
        `;
    }

    list.appendChild(msgDiv);
    list.scrollTop = list.scrollHeight;
}

function formatCopilotMarkdown(text) {
    if (!text) return '';
    let html = escapeHtml(text);
    // Bold: **text**
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Italic: *text*
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    // Monospace / Currency code: `code`
    html = html.replace(/`(.*?)`/g, '<code style="font-family: var(--font-mono); background: rgba(0,0,0,0.1); padding: 1px 4px; border-radius: 4px;">$1</code>');

    // Parse lines for bullet lists & paragraphs
    const lines = html.split('\n');
    let inList = false;
    let result = [];

    for (let rawLine of lines) {
        const line = rawLine.trim();
        if (line.startsWith('- ') || line.startsWith('* ')) {
            if (!inList) {
                result.push('<ul>');
                inList = true;
            }
            result.push(`<li>${line.substring(2)}</li>`);
        } else if (/^\d+\.\s/.test(line)) {
            if (!inList) {
                result.push('<ol>');
                inList = true;
            }
            result.push(`<li>${line.replace(/^\d+\.\s/, '')}</li>`);
        } else {
            if (inList) {
                result.push('</ul>');
                inList = false;
            }
            if (line) {
                result.push(`<p>${line}</p>`);
            }
        }
    }
    if (inList) result.push('</ul>');
    return result.join('');
}

async function sendCopilotPrompt(messageText) {
    const input = document.getElementById('copilotInput');
    const typingIndicator = document.getElementById('copilotTyping');
    const followupsContainer = document.getElementById('copilotFollowups');
    const sendBtn = document.getElementById('copilotSendBtn');

    const prompt = messageText.trim();
    if (!prompt) return;

    if (input) input.value = '';
    if (followupsContainer) followupsContainer.style.display = 'none';

    // Append user message
    appendCopilotMessage('user', prompt);
    copilotChatHistory.push({ role: 'user', text: prompt });

    if (typingIndicator) typingIndicator.style.display = 'flex';
    if (sendBtn) sendBtn.disabled = true;

    try {
        const res = await apiFetch('/api/copilot/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: prompt,
                history: copilotChatHistory,
                month: state.selectedMonth || 'auto'
            })
        });

        const data = await res.json();
        if (data.success && data.data) {
            const reply = data.data.reply || "I couldn't analyze that right now. Please try again.";
            appendCopilotMessage('ai', reply);
            copilotChatHistory.push({ role: 'ai', text: reply });

            // Render suggested followups
            if (data.data.suggested_followups && Array.isArray(data.data.suggested_followups) && data.data.suggested_followups.length > 0) {
                if (followupsContainer) {
                    followupsContainer.innerHTML = data.data.suggested_followups.map(q => 
                        `<button type="button" class="followup-btn"><i class="fa-solid fa-arrow-right text-accent" style="font-size: 10px;"></i> ${escapeHtml(q)}</button>`
                    ).join('');
                    followupsContainer.style.display = 'flex';

                    // Attach click handlers
                    followupsContainer.querySelectorAll('.followup-btn').forEach(btn => {
                        btn.addEventListener('click', () => {
                            sendCopilotPrompt(btn.textContent.trim());
                        });
                    });
                }
            }
        } else {
            const errorMsg = data.error || 'Failed to get answer from Copilot';
            appendCopilotMessage('ai', `⚠️ **Error**: ${errorMsg}`);
            if (errorMsg.includes('API key')) {
                openApiKeyModal();
            }
        }
    } catch (err) {
        appendCopilotMessage('ai', `⚠️ **Network Error**: ${err.message}`);
    } finally {
        if (typingIndicator) typingIndicator.style.display = 'none';
        if (sendBtn) sendBtn.disabled = false;
    }
}

function initCopilot() {
    // Triggers
    document.getElementById('openCopilotNavBtn')?.addEventListener('click', openCopilotModal);
    document.getElementById('openCopilotFloatingBtn')?.addEventListener('click', openCopilotModal);
    document.getElementById('closeCopilotBtn')?.addEventListener('click', closeCopilotModal);
    document.getElementById('clearCopilotChatBtn')?.addEventListener('click', clearCopilotHistory);
    
    document.getElementById('mobActionOpenCopilot')?.addEventListener('click', () => {
        document.getElementById('mobAiActionSheet')?.classList.remove('active');
        openCopilotModal();
    });

    // Form submit
    document.getElementById('copilotChatForm')?.addEventListener('submit', (e) => {
        e.preventDefault();
        const input = document.getElementById('copilotInput');
        if (input && input.value.trim()) {
            sendCopilotPrompt(input.value.trim());
        }
    });

    // Quick Starter Chips
    document.querySelectorAll('.copilot-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const prompt = chip.dataset.prompt;
            if (prompt) {
                sendCopilotPrompt(prompt);
            }
        });
    });
}

/* ==========================================================================
   Helper Utilities
   ========================================================================== */
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
