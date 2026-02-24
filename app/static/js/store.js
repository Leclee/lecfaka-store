/**
 * LecFaka Store - 插件商店前端逻辑
 *
 * 功能：
 *  - 用户认证（注册/登录/JWT存储）
 *  - 插件列表（搜索/分类筛选）
 *  - 插件购买（登录后一键购买）
 *  - 用户控制台（我的插件/域名管理/订单记录）
 */

const API_BASE = '/api/v1';

// ==================== 状态 ====================
let currentUser = null;
let accessToken = localStorage.getItem('store_token') || null;
let pluginsData = [];
let currentFilter = 'all';

// ==================== 初始化 ====================
document.addEventListener('DOMContentLoaded', async () => {
    initScrollEffect();
    if (accessToken) {
        await loadCurrentUser();
    }
    await loadPlugins();
});

/** 导航栏滚动效果 */
function initScrollEffect() {
    window.addEventListener('scroll', () => {
        const navbar = document.getElementById('navbar');
        if (window.scrollY > 20) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });
}

// ==================== API 调用 ====================
async function apiFetch(path, options = {}) {
    const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
    if (accessToken) {
        headers['Authorization'] = `Bearer ${accessToken}`;
    }
    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
    const data = await res.json();
    if (!res.ok) {
        throw new Error(data.detail || data.message || '请求失败');
    }
    return data;
}

// ==================== 认证 ====================
async function loadCurrentUser() {
    try {
        currentUser = await apiFetch('/auth/me');
        updateAuthUI();
    } catch {
        logout();
    }
}

function updateAuthUI() {
    const guest = document.getElementById('auth-guest');
    const user = document.getElementById('auth-user');
    const navDash = document.getElementById('nav-dashboard');

    if (currentUser) {
        guest.style.display = 'none';
        user.style.display = 'block';
        navDash.style.display = 'block';
        document.getElementById('userName').textContent = currentUser.username;
        document.getElementById('userAvatar').textContent = currentUser.username[0].toUpperCase();
        // 管理员与作者入口
        const isAdmin = currentUser.role === 'superadmin';
        const isAuthor = currentUser.role === 'author' || currentUser.role === 'superadmin';
        document.querySelectorAll('.admin-only').forEach(el => {
            el.style.display = isAdmin ? '' : 'none';
        });
        document.querySelectorAll('.author-only').forEach(el => {
            el.style.display = isAuthor ? '' : 'none';
        });
    } else {
        guest.style.display = 'flex';
        user.style.display = 'none';
        navDash.style.display = 'none';
        document.querySelectorAll('.admin-only').forEach(el => {
            el.style.display = 'none';
        });
        document.querySelectorAll('.author-only').forEach(el => {
            el.style.display = 'none';
        });
    }
}

function showAuthModal(tab = 'login') {
    document.getElementById('authModal').style.display = 'flex';
    switchAuthTab(tab);
}

function closeAuthModal() {
    document.getElementById('authModal').style.display = 'none';
}

function switchAuthTab(tab) {
    const loginForm = document.getElementById('loginForm');
    const regForm = document.getElementById('registerForm');
    const tabLogin = document.getElementById('tabLogin');
    const tabReg = document.getElementById('tabRegister');
    const footer = document.getElementById('authFooter');

    if (tab === 'login') {
        loginForm.style.display = 'block';
        regForm.style.display = 'none';
        tabLogin.classList.add('active');
        tabReg.classList.remove('active');
        footer.innerHTML = '还没有账号？<a href="#" onclick="switchAuthTab(\'register\')">立即注册</a>';
    } else {
        loginForm.style.display = 'none';
        regForm.style.display = 'block';
        tabReg.classList.add('active');
        tabLogin.classList.remove('active');
        footer.innerHTML = '已有账号？<a href="#" onclick="switchAuthTab(\'login\')">立即登录</a>';
    }
}

async function handleLogin(e) {
    e.preventDefault();
    const btn = document.getElementById('loginBtn');
    btn.textContent = '登录中...';
    btn.disabled = true;
    try {
        const data = await apiFetch('/auth/login', {
            method: 'POST',
            body: JSON.stringify({
                account: document.getElementById('loginAccount').value,
                password: document.getElementById('loginPassword').value,
            }),
        });
        accessToken = data.access_token;
        localStorage.setItem('store_token', accessToken);
        localStorage.setItem('store_refresh', data.refresh_token);
        currentUser = data.user;
        updateAuthUI();
        closeAuthModal();
        showToast('登录成功', 'success');
        await loadPlugins(); // 刷新列表（显示已购标记）
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        btn.textContent = '登录';
        btn.disabled = false;
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const btn = document.getElementById('regBtn');
    btn.textContent = '注册中...';
    btn.disabled = true;
    try {
        const data = await apiFetch('/auth/register', {
            method: 'POST',
            body: JSON.stringify({
                username: document.getElementById('regUsername').value,
                email: document.getElementById('regEmail').value,
                password: document.getElementById('regPassword').value,
            }),
        });
        accessToken = data.access_token;
        localStorage.setItem('store_token', accessToken);
        localStorage.setItem('store_refresh', data.refresh_token);
        currentUser = data.user;
        updateAuthUI();
        closeAuthModal();
        showToast('注册成功，欢迎加入！', 'success');
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        btn.textContent = '注册';
        btn.disabled = false;
    }
}

function logout() {
    accessToken = null;
    currentUser = null;
    localStorage.removeItem('store_token');
    localStorage.removeItem('store_refresh');
    updateAuthUI();
    // 如果在控制台页面，返回首页
    document.getElementById('dashboardSection').style.display = 'none';
    document.getElementById('hero').style.display = 'flex';
    document.getElementById('categories').style.display = 'block';
    document.getElementById('plugins').style.display = 'block';
}

function toggleDropdown() {
    document.getElementById('dropdownMenu').classList.toggle('open');
}
// 点击外部关闭 dropdown
document.addEventListener('click', (e) => {
    if (!e.target.closest('#userDropdown')) {
        document.getElementById('dropdownMenu')?.classList.remove('open');
    }
});

// ==================== 插件列表 ====================
async function loadPlugins() {
    const grid = document.getElementById('pluginsGrid');
    const loading = document.getElementById('loadingState');
    const empty = document.getElementById('emptyState');

    grid.innerHTML = '';
    loading.style.display = 'block';
    empty.style.display = 'none';

    try {
        const params = new URLSearchParams();
        if (currentFilter && currentFilter !== 'all') {
            if (['theme', 'payment', 'extension'].includes(currentFilter)) {
                params.set('type', currentFilter);
            } else if (currentFilter === 'free') {
                params.set('category', 'free');
            }
        }
        const keyword = document.getElementById('heroSearch')?.value;
        if (keyword) params.set('keyword', keyword);

        const data = await apiFetch(`/store/plugins?${params.toString()}`);
        pluginsData = data.items || [];
    } catch (err) {
        console.error('加载插件失败:', err);
        pluginsData = [];
    }

    loading.style.display = 'none';

    if (pluginsData.length === 0) {
        empty.style.display = 'block';
        return;
    }

    grid.innerHTML = pluginsData.map(p => renderPluginCard(p)).join('');
}

function renderPluginCard(p) {
    const typeClass = `tag-${p.type || 'extension'}`;
    const typeLabel = { theme: 'Theme', payment: 'Payment', extension: 'Plugin', notify: 'Notify', delivery: 'Delivery' }[p.type] || 'Plugin';
    const priceHtml = p.is_free
        ? '<span class="plugin-price">免费</span>'
        : `<span class="plugin-price paid">¥${p.price}</span>`;
    const purchasedBadge = p.purchased ? '<span class="plugin-tag tag-purchased">已购</span>' : '';
    const iconHtml = p.icon
        ? `<img src="${p.icon}" alt="${p.name}" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
        : '';

    return `<div class="plugin-card" onclick="showPluginDetail('${p.id}')">
        <div class="plugin-header">
            <div class="plugin-icon">
                ${iconHtml}
                <svg style="${p.icon ? 'display:none' : ''}" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4"/></svg>
            </div>
            <div class="plugin-info">
                <div class="plugin-name">${p.name}</div>
                <div class="plugin-author">${p.author || 'Unknown'}</div>
            </div>
        </div>
        <div class="plugin-desc">${p.description || '暂无描述'}</div>
        <div class="plugin-footer">
            ${priceHtml}
            <div style="display:flex;gap:6px;align-items:center">
                ${purchasedBadge}
                <span class="plugin-tag ${typeClass}">${typeLabel}</span>
            </div>
        </div>
    </div>`;
}

function filterByCategory(el, type) {
    document.querySelectorAll('.category-card').forEach(c => c.classList.remove('active'));
    el.classList.add('active');
    currentFilter = type;
    loadPlugins();
}

function searchPlugins() {
    loadPlugins();
}

// ==================== 插件详情 ====================
async function showPluginDetail(pluginId) {
    const modal = document.getElementById('pluginModal');
    const detail = document.getElementById('pluginDetail');
    modal.style.display = 'flex';
    detail.innerHTML = '<div class="loading-state"><div class="spinner"></div><p>加载中...</p></div>';

    try {
        const p = await apiFetch(`/store/plugins/${pluginId}`);
        const priceText = p.is_free ? '免费' : `¥${p.price}`;
        const priceClass = p.is_free ? '' : 'paid';

        let actionBtn = '';
        if (p.purchased) {
            actionBtn = '<button class="btn btn-outline" disabled>已购买</button>';
        } else if (p.is_free) {
            actionBtn = `<button class="btn btn-primary" onclick="purchasePlugin('${p.id}')">免费获取</button>`;
        } else {
            actionBtn = `<button class="btn btn-primary" onclick="purchasePlugin('${p.id}')">立即购买 ¥${p.price}</button>`;
        }

        if (p.website) {
            actionBtn += `<a href="${p.website}" target="_blank" class="btn btn-outline">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3"/></svg>
                官网
            </a>`;
        }

        detail.innerHTML = `
            <div class="detail-header">
                <div class="detail-icon">
                    ${p.icon ? `<img src="${p.icon}" alt="${p.name}">` : '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4"/></svg>'}
                </div>
                <div class="detail-info">
                    <div class="detail-name">${p.name}</div>
                    <div class="detail-meta">
                        <span>${p.author || 'Unknown'}</span>
                        <span>v${p.version}</span>
                        <span>${p.download_count || 0} 次安装</span>
                    </div>
                    <div class="detail-price ${priceClass}">${priceText}</div>
                </div>
            </div>
            <div class="detail-actions">${actionBtn}</div>
            <div class="detail-body">${p.detail_html || p.description || '暂无详细描述'}</div>
        `;
    } catch (err) {
        detail.innerHTML = `<div class="empty-state"><p>加载失败：${err.message}</p></div>`;
    }
}

function closePluginModal() {
    document.getElementById('pluginModal').style.display = 'none';
}

// ==================== 购买 ====================
let paymentPollTimer = null;

async function purchasePlugin(pluginId) {
    if (!currentUser) {
        closePluginModal();
        showAuthModal('login');
        showToast('请先登录后再购买', 'info');
        return;
    }

    try {
        const data = await apiFetch('/store/purchase', {
            method: 'POST',
            body: JSON.stringify({ plugin_id: pluginId }),
        });

        if (data.require_payment) {
            // 付费插件 → 显示支付弹窗
            closePluginModal();
            showPaymentModal(data);
        } else if (data.success !== false) {
            showToast(`购买成功！${data.plugin_name || ''}`, 'success');
            closePluginModal();
            await loadPlugins();
        } else {
            showToast(data.message || '购买失败', 'error');
        }
    } catch (err) {
        showToast(err.message, 'error');
    }
}

/** 显示支付弹窗 */
function showPaymentModal(data) {
    const modal = document.getElementById('paymentModal');
    if (!modal) {
        createPaymentModal();
    }
    const modal2 = document.getElementById('paymentModal');
    const gatewayOptions = (data.gateways || []).map(g =>
        `<option value="${g.name}">${g.display_name}</option>`
    ).join('');

    document.getElementById('payPluginName').textContent = data.plugin_name || '';
    document.getElementById('payAmount').textContent = `¥${data.price || 0}`;
    document.getElementById('payPluginId').value = data.plugin_id;
    const gatewaySelect = document.getElementById('payGateway');
    if (gatewaySelect) gatewaySelect.innerHTML = gatewayOptions;

    // 重置状态
    document.getElementById('payChoosing').style.display = 'block';
    document.getElementById('payWaiting').style.display = 'none';
    document.getElementById('paySuccess').style.display = 'none';
    document.getElementById('payExpired').style.display = 'none';

    modal2.style.display = 'flex';
}

/** 动态创建支付弹窗 HTML */
function createPaymentModal() {
    const div = document.createElement('div');
    div.id = 'paymentModal';
    div.className = 'modal-overlay';
    div.innerHTML = `
        <div class="modal-card" style="max-width:480px">
            <button class="modal-close" onclick="closePaymentModal()">&times;</button>
            <input type="hidden" id="payPluginId">

            <!-- 选择支付方式 -->
            <div id="payChoosing">
                <div style="background:linear-gradient(135deg,#667eea,#764ba2);border-radius:var(--radius-md);padding:20px 24px;color:#fff;margin-bottom:20px">
                    <div style="font-size:14px;opacity:.9;margin-bottom:4px">购买插件</div>
                    <div id="payPluginName" style="font-size:20px;font-weight:600"></div>
                    <div id="payAmount" style="font-size:28px;font-weight:700;margin-top:8px"></div>
                </div>
                <div style="margin-bottom:16px">
                    <label style="display:block;margin-bottom:6px;font-size:13px;color:var(--color-text-secondary)">支付网关</label>
                    <select id="payGateway" style="width:100%;padding:10px 14px;background:var(--color-surface);border:1px solid var(--color-border);border-radius:var(--radius-sm);color:var(--color-text);font-size:14px"></select>
                </div>
                <div style="margin-bottom:20px">
                    <label style="display:block;margin-bottom:6px;font-size:13px;color:var(--color-text-secondary)">支付方式</label>
                    <select id="payType" style="width:100%;padding:10px 14px;background:var(--color-surface);border:1px solid var(--color-border);border-radius:var(--radius-sm);color:var(--color-text);font-size:14px">
                        <option value="alipay">💳 支付宝</option>
                        <option value="wxpay">💬 微信支付</option>
                        <option value="qqpay">🐧 QQ 支付</option>
                    </select>
                </div>
                <button id="paySubmitBtn" class="btn btn-primary" style="width:100%;padding:14px;font-size:16px" onclick="submitPayment()">确认支付</button>
            </div>

            <!-- 等待支付 -->
            <div id="payWaiting" style="display:none;text-align:center;padding:40px 0">
                <div class="spinner" style="margin:0 auto 20px"></div>
                <div style="font-size:16px;font-weight:500;margin-bottom:12px">等待支付...</div>
                <p style="color:var(--color-text-secondary);font-size:14px">支付页面已在新窗口打开，请完成付款。<br>支付完成后此处将自动更新。</p>
                <a href="#" id="payReopenLink" onclick="event.preventDefault();reopenPayment()" style="color:var(--color-primary);font-size:14px">重新打开支付页面</a>
                <div style="margin-top:20px"><button class="btn btn-outline btn-sm" onclick="closePaymentModal()" style="color:#ff4d4f;border-color:#ff4d4f">取消支付</button></div>
            </div>

            <!-- 支付成功 -->
            <div id="paySuccess" style="display:none;text-align:center;padding:40px 0">
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#52c41a" stroke-width="2" style="margin-bottom:16px"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><path d="M22 4L12 14.01l-3-3"/></svg>
                <div style="font-size:20px;font-weight:600;margin-bottom:8px">支付成功！</div>
                <p style="color:var(--color-text-secondary);font-size:14px">插件已绑定到您的账号</p>
                <button class="btn btn-primary" style="margin-top:20px" onclick="closePaymentModal();loadPlugins()">完成</button>
            </div>

            <!-- 支付超时 -->
            <div id="payExpired" style="display:none;text-align:center;padding:40px 0">
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#faad14" stroke-width="2" style="margin-bottom:16px"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>
                <div style="font-size:20px;font-weight:600;margin-bottom:8px">支付超时</div>
                <p style="color:var(--color-text-secondary);font-size:14px">订单已过期，请重新发起购买</p>
                <button class="btn btn-primary" style="margin-top:20px" onclick="closePaymentModal()">关闭</button>
            </div>
        </div>
    `;
    document.body.appendChild(div);
}

let currentPaymentUrl = '';

/** 提交支付 → 创建支付订单 */
async function submitPayment() {
    const pluginId = document.getElementById('payPluginId').value;
    const gateway = document.getElementById('payGateway').value;
    const payType = document.getElementById('payType').value;
    const btn = document.getElementById('paySubmitBtn');

    btn.textContent = '创建订单中...';
    btn.disabled = true;

    try {
        const data = await apiFetch('/pay/create-order', {
            method: 'POST',
            body: JSON.stringify({
                plugin_id: pluginId,
                gateway: gateway,
                pay_type: payType,
            }),
        });

        if (data.success && data.payment_url) {
            currentPaymentUrl = data.payment_url;
            window.open(data.payment_url, '_blank');

            // 切换到等待状态
            document.getElementById('payChoosing').style.display = 'none';
            document.getElementById('payWaiting').style.display = 'block';

            // 开始轮询
            startPaymentPolling(data.order_no);
        } else {
            showToast(data.message || '创建支付订单失败', 'error');
        }
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        btn.textContent = '确认支付';
        btn.disabled = false;
    }
}

/** 重新打开支付页面 */
function reopenPayment() {
    if (currentPaymentUrl) {
        window.open(currentPaymentUrl, '_blank');
    }
}

/** 轮询订单状态 */
function startPaymentPolling(orderNo) {
    if (paymentPollTimer) clearInterval(paymentPollTimer);
    let attempts = 0;
    const maxAttempts = 120;

    paymentPollTimer = setInterval(async () => {
        attempts++;
        if (attempts > maxAttempts) {
            clearInterval(paymentPollTimer);
            paymentPollTimer = null;
            document.getElementById('payWaiting').style.display = 'none';
            document.getElementById('payExpired').style.display = 'block';
            return;
        }

        try {
            const data = await apiFetch(`/pay/status/${orderNo}`);
            if (data.status === 'paid') {
                clearInterval(paymentPollTimer);
                paymentPollTimer = null;
                document.getElementById('payWaiting').style.display = 'none';
                document.getElementById('paySuccess').style.display = 'block';
            } else if (data.status === 'expired' || data.status === 'closed') {
                clearInterval(paymentPollTimer);
                paymentPollTimer = null;
                document.getElementById('payWaiting').style.display = 'none';
                document.getElementById('payExpired').style.display = 'block';
            }
        } catch {
            // 继续轮询
        }
    }, 3000);
}

/** 关闭支付弹窗 */
function closePaymentModal() {
    if (paymentPollTimer) {
        clearInterval(paymentPollTimer);
        paymentPollTimer = null;
    }
    currentPaymentUrl = '';
    const modal = document.getElementById('paymentModal');
    if (modal) modal.style.display = 'none';
}

// ==================== 用户控制台 ====================
function showDashboard(tab = 'my-plugins') {
    if (!currentUser) {
        showAuthModal('login');
        return;
    }
    // 隐藏首页区域
    document.getElementById('hero').style.display = 'none';
    document.getElementById('categories').style.display = 'none';
    document.getElementById('plugins').style.display = 'none';
    // 显示控制台
    document.getElementById('dashboardSection').style.display = 'block';
    // 切换 tab
    switchDashTab(document.querySelector(`[data-tab="${tab}"]`), tab);
    // 关闭 dropdown
    document.getElementById('dropdownMenu')?.classList.remove('open');
}

function switchDashTab(el, tab) {
    document.querySelectorAll('.sidebar-link').forEach(l => l.classList.remove('active'));
    if (el) el.classList.add('active');

    const main = document.getElementById('dashboardMain');

    if (tab === 'my-plugins') loadMyPlugins(main);
    else if (tab === 'domains') loadDomainManagement(main);
    else if (tab === 'orders') loadOrders(main);
    else if (tab === 'author-finance') loadAuthorFinance(main);
    else if (tab === 'admin-withdrawals') loadAdminWithdrawals(main);
    else if (tab === 'admin-stats') loadAdminStats(main);
    else if (tab === 'admin-plugins') loadAdminPlugins(main);
    else if (tab === 'admin-users') loadAdminUsers(main);
}

async function loadMyPlugins(container) {
    container.innerHTML = '<div class="loading-state"><div class="spinner"></div></div>';
    try {
        const data = await apiFetch('/store/my-plugins');
        if (!data.items || data.items.length === 0) {
            container.innerHTML = `<div class="empty-state">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4"/></svg>
                <p>还没有购买任何插件</p>
                <button class="btn btn-primary btn-sm" onclick="goHome()" style="margin-top:12px">去逛逛</button>
            </div>`;
            return;
        }

        container.innerHTML = `
            <h3 style="margin-bottom:20px;font-size:18px">我的插件 (${data.items.length})</h3>
            <table class="dash-table">
                <thead><tr><th>插件</th><th>状态</th><th>绑定域名</th><th>换绑剩余</th><th>购买日期</th></tr></thead>
                <tbody>${data.items.map(p => `
                    <tr>
                        <td><strong>${p.name}</strong><br><span style="font-size:12px;color:var(--color-text-muted)">v${p.version}</span></td>
                        <td><span class="plugin-tag tag-purchased">${p.status_text}</span></td>
                        <td>${p.bound_domain || '<span style="color:var(--color-text-muted)">未绑定</span>'}</td>
                        <td>${p.rebind_remaining}/${p.max_rebinds}</td>
                        <td style="font-size:13px;color:var(--color-text-secondary)">${p.purchased_at ? new Date(p.purchased_at).toLocaleDateString() : '-'}</td>
                    </tr>
                `).join('')}</tbody>
            </table>
        `;
    } catch (err) {
        container.innerHTML = `<div class="empty-state"><p>加载失败：${err.message}</p></div>`;
    }
}

async function loadDomainManagement(container) {
    container.innerHTML = '<div class="loading-state"><div class="spinner"></div></div>';
    try {
        const data = await apiFetch('/store/my-plugins');
        const items = (data.items || []).filter(p => p.status === 1);

        if (items.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>还没有购买任何插件</p></div>';
            return;
        }

        container.innerHTML = `
            <h3 style="margin-bottom:20px;font-size:18px">域名管理</h3>
            <p style="color:var(--color-text-secondary);font-size:13px;margin-bottom:20px">每个插件可绑定一个域名，首次安装时自动绑定。如需更换可在下方操作。</p>
            ${items.map(p => `
                <div style="background:var(--color-bg);border-radius:var(--radius-md);padding:20px;margin-bottom:14px;border:1px solid var(--color-border)">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                        <strong>${p.name}</strong>
                        <span style="font-size:12px;color:var(--color-text-muted)">换绑剩余 ${p.rebind_remaining}/${p.max_rebinds}</span>
                    </div>
                    <div style="display:flex;gap:10px;align-items:center">
                        <input type="text" id="domain-${p.id}" value="${p.bound_domain || ''}" placeholder="例如：shop.example.com"
                            style="flex:1;padding:10px 14px;background:var(--color-surface);border:1px solid var(--color-border);border-radius:var(--radius-sm);color:var(--color-text);font-size:14px">
                        <button class="btn btn-primary btn-sm" onclick="handleDomainAction('${p.id}', ${p.bound_domain ? 'true' : 'false'})">
                            ${p.bound_domain ? '换绑' : '绑定'}
                        </button>
                    </div>
                </div>
            `).join('')}
        `;
    } catch (err) {
        container.innerHTML = `<div class="empty-state"><p>加载失败：${err.message}</p></div>`;
    }
}

async function handleDomainAction(pluginId, isRebind) {
    const domain = document.getElementById(`domain-${pluginId}`).value.trim();
    if (!domain) {
        showToast('请输入域名', 'error');
        return;
    }

    try {
        const endpoint = isRebind ? '/store/rebind-domain' : '/store/bind-domain';
        const body = isRebind
            ? { plugin_id: pluginId, new_domain: domain }
            : { plugin_id: pluginId, domain: domain };
        const data = await apiFetch(endpoint, {
            method: 'POST',
            body: JSON.stringify(body),
        });
        showToast(data.message, 'success');
        loadDomainManagement(document.getElementById('dashboardMain'));
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function loadOrders(container) {
    container.innerHTML = '<div class="loading-state"><div class="spinner"></div></div>';
    try {
        const data = await apiFetch('/pay/my-orders');
        if (!data.items || data.items.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>暂无订单记录</p></div>';
            return;
        }

        const statusMap = {
            pending: '<span class="plugin-tag" style="background:rgba(250,173,20,.15);color:#faad14">待支付</span>',
            paid: '<span class="plugin-tag tag-purchased">已支付</span>',
            expired: '<span class="plugin-tag" style="background:rgba(255,77,79,.15);color:#ff4d4f">已过期</span>',
            refunded: '<span class="plugin-tag" style="background:rgba(255,77,79,.15);color:#ff4d4f">已退款</span>',
            closed: '<span class="plugin-tag" style="background:rgba(150,150,150,.15);color:#999">已关闭</span>',
        };

        container.innerHTML = `
            <h3 style="margin-bottom:20px;font-size:18px">订单记录</h3>
            <table class="dash-table">
                <thead><tr><th>订单号</th><th>插件</th><th>金额</th><th>支付方式</th><th>状态</th><th>日期</th></tr></thead>
                <tbody>${data.items.map(o => `
                    <tr>
                        <td style="font-family:monospace;font-size:13px">${o.order_no || '-'}</td>
                        <td>${o.plugin_name || o.plugin_id}</td>
                        <td>¥${o.amount}</td>
                        <td>${o.pay_type || o.gateway || '-'}</td>
                        <td>${statusMap[o.status] || o.status}</td>
                        <td style="font-size:13px;color:var(--color-text-secondary)">${o.paid_at ? new Date(o.paid_at).toLocaleString() : (o.created_at ? new Date(o.created_at).toLocaleString() : '-')}</td>
                    </tr>
                `).join('')}</tbody>
            </table>
        `;
    } catch (err) {
        container.innerHTML = `<div class="empty-state"><p>加载失败：${err.message}</p></div>`;
    }
}

function goHome() {
    document.getElementById('dashboardSection').style.display = 'none';
    document.getElementById('hero').style.display = 'flex';
    document.getElementById('categories').style.display = 'block';
    document.getElementById('plugins').style.display = 'block';
}

// ==================== Toast ====================
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icons = {
        success: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><path d="M22 4L12 14.01l-3-3"/></svg>',
        error: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/></svg>',
        info: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>',
    };
    toast.innerHTML = `${icons[type] || icons.info}<span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(30px)';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// ==================== 工具函数 ====================
function animateNumber(id, target) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = target;
}

// ==================== 管理员面板 ====================

/** 数据概览 */
async function loadAdminStats(container) {
    container.innerHTML = '<div class="loading-state"><div class="spinner"></div></div>';
    try {
        const data = await apiFetch('/admin/stats');
        container.innerHTML = `
            <h3 style="margin-bottom:24px;font-size:18px">📊 数据概览</h3>
            <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;margin-bottom:32px">
                <div class="stat-card">
                    <div class="stat-card-num">${data.total_users || 0}</div>
                    <div class="stat-card-label">注册用户</div>
                </div>
                <div class="stat-card">
                    <div class="stat-card-num">${data.total_plugins || 0}</div>
                    <div class="stat-card-label">插件总数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-card-num">${data.total_orders || 0}</div>
                    <div class="stat-card-label">订单总数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-card-num">¥${data.total_revenue || 0}</div>
                    <div class="stat-card-label">累计收入</div>
                </div>
            </div>
        `;
    } catch (err) {
        container.innerHTML = `<div class="empty-state"><p>加载失败：${err.message}</p></div>`;
    }
}

/** 插件管理 */
async function loadAdminPlugins(container) {
    container.innerHTML = '<div class="loading-state"><div class="spinner"></div></div>';
    try {
        const data = await apiFetch('/store/plugins');
        const plugins = data.items || [];

        container.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px">
                <h3 style="font-size:18px;margin:0">📦 插件管理 (${plugins.length})</h3>
                <button class="btn btn-primary btn-sm" onclick="showAddPluginForm()">➕ 发布插件</button>
            </div>
            <div id="addPluginArea" style="display:none;margin-bottom:24px"></div>
            ${plugins.length === 0 ? '<div class="empty-state"><p>还没有插件，点击上方按钮发布第一个插件</p></div>' : `
            <table class="dash-table">
                <thead><tr><th>插件</th><th>类型</th><th>版本</th><th>价格</th><th>状态</th><th>购买数</th><th>操作</th></tr></thead>
                <tbody>${plugins.map(p => `
                    <tr>
                        <td><strong>${p.name}</strong><br><span style="font-size:12px;color:var(--color-text-muted)">${p.id}</span></td>
                        <td><span class="plugin-tag tag-${p.type}">${p.type}</span></td>
                        <td>v${p.version}</td>
                        <td>${p.is_free ? '<span style="color:#52c41a">免费</span>' : '<span style="color:#ff4d4f">¥' + p.price + '</span>'}</td>
                        <td><span class="plugin-tag ${p.status !== undefined && p.status !== 1 ? '' : 'tag-purchased'}">${p.status === 1 || p.status === undefined ? '已上架' : '未上架'}</span></td>
                        <td>${p.purchase_count || 0}</td>
                        <td>
                            <button class="btn btn-outline btn-sm" onclick="editPlugin('${p.id}')">编辑</button>
                        </td>
                    </tr>
                `).join('')}</tbody>
            </table>`}
        `;
    } catch (err) {
        container.innerHTML = `<div class="empty-state"><p>加载失败：${err.message}</p></div>`;
    }
}

/** 显示添加插件表单 */
function showAddPluginForm() {
    const area = document.getElementById('addPluginArea');
    if (area.style.display === 'block') {
        area.style.display = 'none';
        return;
    }
    area.style.display = 'block';
    area.innerHTML = `
        <div style="background:var(--color-surface);border:1px solid var(--color-border);border-radius:var(--radius-md);padding:24px">
            <h4 style="margin-bottom:16px">发布新插件</h4>
            <form id="addPluginForm" onsubmit="submitNewPlugin(event)">
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
                    <div class="form-group">
                        <label>插件 ID *</label>
                        <input type="text" id="np_id" placeholder="例如: theme_aurora" required style="width:100%;padding:10px 14px;background:var(--color-bg);border:1px solid var(--color-border);border-radius:var(--radius-sm);color:var(--color-text);font-size:14px">
                    </div>
                    <div class="form-group">
                        <label>插件名称 *</label>
                        <input type="text" id="np_name" placeholder="例如: Aurora 极光主题" required style="width:100%;padding:10px 14px;background:var(--color-bg);border:1px solid var(--color-border);border-radius:var(--radius-sm);color:var(--color-text);font-size:14px">
                    </div>
                    <div class="form-group">
                        <label>类型 *</label>
                        <select id="np_type" required style="width:100%;padding:10px 14px;background:var(--color-bg);border:1px solid var(--color-border);border-radius:var(--radius-sm);color:var(--color-text);font-size:14px">
                            <option value="theme">主题模板</option>
                            <option value="payment">支付接口</option>
                            <option value="extension">功能扩展</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>版本 *</label>
                        <input type="text" id="np_version" value="1.0.0" required style="width:100%;padding:10px 14px;background:var(--color-bg);border:1px solid var(--color-border);border-radius:var(--radius-sm);color:var(--color-text);font-size:14px">
                    </div>
                    <div class="form-group">
                        <label>价格 (¥)</label>
                        <input type="number" id="np_price" value="0" min="0" step="0.01" style="width:100%;padding:10px 14px;background:var(--color-bg);border:1px solid var(--color-border);border-radius:var(--radius-sm);color:var(--color-text);font-size:14px">
                    </div>
                    <div class="form-group">
                        <label>作者</label>
                        <input type="text" id="np_author" value="LecFaka Official" style="width:100%;padding:10px 14px;background:var(--color-bg);border:1px solid var(--color-border);border-radius:var(--radius-sm);color:var(--color-text);font-size:14px">
                    </div>
                </div>
                <div class="form-group" style="margin-top:16px">
                    <label>简介</label>
                    <input type="text" id="np_desc" placeholder="一句话描述插件功能" style="width:100%;padding:10px 14px;background:var(--color-bg);border:1px solid var(--color-border);border-radius:var(--radius-sm);color:var(--color-text);font-size:14px">
                </div>
                <div class="form-group" style="margin-top:16px">
                    <label>官网 URL</label>
                    <input type="url" id="np_website" placeholder="https://" style="width:100%;padding:10px 14px;background:var(--color-bg);border:1px solid var(--color-border);border-radius:var(--radius-sm);color:var(--color-text);font-size:14px">
                </div>
                <div class="form-group" style="margin-top:16px">
                    <label>详细描述 (HTML)</label>
                    <textarea id="np_detail" rows="4" placeholder="支持 HTML 格式" style="width:100%;padding:10px 14px;background:var(--color-bg);border:1px solid var(--color-border);border-radius:var(--radius-sm);color:var(--color-text);font-size:14px;resize:vertical"></textarea>
                </div>
                <div class="form-group" style="margin-top:16px">
                    <label>插件下载包 (ZIP)</label>
                    <input type="file" id="np_file" accept=".zip" style="padding:10px 0;color:var(--color-text);font-size:14px">
                </div>
                <div style="display:flex;gap:12px;margin-top:20px">
                    <button type="submit" class="btn btn-primary" id="npSubmitBtn">发布插件</button>
                    <button type="button" class="btn btn-outline" onclick="document.getElementById('addPluginArea').style.display='none'">取消</button>
                </div>
            </form>
        </div>
    `;
}

/** 提交新插件 */
async function submitNewPlugin(e) {
    e.preventDefault();
    const btn = document.getElementById('npSubmitBtn');
    btn.textContent = '发布中...';
    btn.disabled = true;

    try {
        const price = parseFloat(document.getElementById('np_price').value) || 0;
        const body = {
            plugin_id: document.getElementById('np_id').value.trim(),
            name: document.getElementById('np_name').value.trim(),
            type: document.getElementById('np_type').value,
            version: document.getElementById('np_version').value.trim(),
            price: price,
            is_free: price === 0,
            author_name: document.getElementById('np_author').value.trim(),
            description: document.getElementById('np_desc').value.trim(),
            website: document.getElementById('np_website').value.trim(),
            detail_html: document.getElementById('np_detail').value.trim(),
        };

        // 如果有文件，用 FormData
        const fileInput = document.getElementById('np_file');
        if (fileInput.files.length > 0) {
            const fd = new FormData();
            fd.append('file', fileInput.files[0]);
            fd.append('meta', JSON.stringify(body));
            const res = await fetch(`${API_BASE}/admin/plugins/upload`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${accessToken}` },
                body: fd,
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || '上传失败');
            showToast('插件发布成功！', 'success');
        } else {
            await apiFetch('/admin/plugins', {
                method: 'POST',
                body: JSON.stringify(body),
            });
            showToast('插件信息已保存！', 'success');
        }

        document.getElementById('addPluginArea').style.display = 'none';
        loadAdminPlugins(document.getElementById('dashboardMain'));
        await loadPlugins();
    } catch (err) {
        showToast(err.message, 'error');
    } finally {
        btn.textContent = '发布插件';
        btn.disabled = false;
    }
}

/** 编辑插件(简化版) */
function editPlugin(pluginId) {
    showToast('编辑功能开发中...', 'info');
}

/** 用户管理 */
async function loadAdminUsers(container) {
    container.innerHTML = '<div class="loading-state"><div class="spinner"></div></div>';
    try {
        const data = await apiFetch('/admin/users');
        const users = data.items || [];

        container.innerHTML = `
            <h3 style="margin-bottom:24px;font-size:18px">👥 用户管理 (${users.length})</h3>
            ${users.length === 0 ? '<div class="empty-state"><p>暂无用户</p></div>' : `
            <table class="dash-table">
                <thead><tr><th>ID</th><th>用户名</th><th>邮箱</th><th>角色</th><th>状态</th><th>注册时间</th><th>操作</th></tr></thead>
                <tbody>${users.map(u => `
                    <tr>
                        <td>${u.id}</td>
                        <td><strong>${u.username}</strong></td>
                        <td>${u.email}</td>
                        <td><span class="plugin-tag ${u.role === 'superadmin' ? 'tag-purchased' : ''}">${u.role}</span></td>
                        <td>${u.status === 1 ? '<span style="color:#52c41a">正常</span>' : '<span style="color:#ff4d4f">禁用</span>'}</td>
                        <td style="font-size:13px;color:var(--color-text-secondary)">${u.created_at ? new Date(u.created_at).toLocaleDateString() : '-'}</td>
                        <td>
                            ${u.role !== 'superadmin' ? `
                                <button class="btn btn-outline btn-sm" onclick="toggleUserStatus(${u.id}, ${u.status === 1 ? 0 : 1})">
                                    ${u.status === 1 ? '禁用' : '启用'}
                                </button>
                            ` : ''}
                        </td>
                    </tr>
                `).join('')}</tbody>
            </table>`}
        `;
    } catch (err) {
        container.innerHTML = `<div class="empty-state"><p>加载失败：${err.message}</p></div>`;
    }
}

async function toggleUserStatus(userId, newStatus) {
    try {
        await apiFetch(`/admin/users/${userId}/status`, {
            method: 'PUT',
            body: JSON.stringify({ status: newStatus }),
        });
        showToast('用户状态已更新', 'success');
        loadAdminUsers(document.getElementById('dashboardMain'));
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ==================== 收益与提现 ====================
async function loadAuthorFinance(container) {
    container.innerHTML = '<div class="loading-state"><div class="spinner"></div></div>';
    try {
        const stats = await apiFetch('/finance/stats');
        const list = await apiFetch('/finance/withdrawals');

        container.innerHTML = `
            <h2>收益中心</h2>
            <div class="stats-grid" style="margin-bottom:20px">
                <div class="stat-card">
                    <h3>可提现余额</h3>
                    <div class="stat-number" style="color:#52c41a">¥${stats.balance.toFixed(2)}</div>
                </div>
                <div class="stat-card">
                    <h3>总收入</h3>
                    <div class="stat-number">¥${stats.total_income.toFixed(2)}</div>
                </div>
                <div class="stat-card">
                    <h3>处理中的提现</h3>
                    <div class="stat-number" style="color:#faad14">¥${stats.pending_withdrawal.toFixed(2)}</div>
                </div>
            </div>
            
            <div style="margin-bottom:30px; background:var(--color-surface); padding:20px; border-radius:var(--radius-md);">
                <h3>申请提现</h3>
                <form id="withdrawForm" onsubmit="handleWithdraw(event)" style="display:flex; gap:10px; align-items:flex-end; margin-top:10px">
                    <div style="flex:1">
                        <label style="display:block;margin-bottom:5px;font-size:13px">提现金额 (¥)</label>
                        <input type="number" id="wAmount" min="1" max="${stats.balance}" step="0.01" style="width:100%;padding:8px" required>
                    </div>
                    <div style="flex:1">
                        <label style="display:block;margin-bottom:5px;font-size:13px">收款方式</label>
                        <select id="wType" style="width:100%;padding:8px">
                            <option value="alipay">支付宝</option>
                            <option value="wxpay">微信</option>
                            <option value="usdt">USDT</option>
                        </select>
                    </div>
                    <div style="flex:2">
                        <label style="display:block;margin-bottom:5px;font-size:13px">收款账号</label>
                        <input type="text" id="wAccount" style="width:100%;padding:8px" required>
                    </div>
                    <div>
                        <button type="submit" class="btn btn-primary" ${stats.balance <= 0 ? 'disabled' : ''}>提交申请</button>
                    </div>
                </form>
            </div>

            <h3>提现记录</h3>
            ${list.items.length === 0 ? '<div class="empty-state">暂无提现记录</div>' : `
            <table class="table">
                <thead><tr><th>时间</th><th>提现金额</th><th>收款信息</th><th>状态</th><th>处理要求</th></tr></thead>
                <tbody>${list.items.map(i => `
                    <tr>
                        <td>${formatDate(i.created_at)}</td>
                        <td style="font-weight:bold">¥${i.amount}</td>
                        <td>${i.account_type.toUpperCase()} - ${i.account_no}</td>
                        <td>
                            <span class="plugin-tag" style="background:${i.status === 'pending' ? '#fffbe6;color:#faad14' : i.status === 'approved' ? '#f6ffed;color:#52c41a' : '#fff1f0;color:#f5222d'}">
                                ${i.status}
                            </span>
                        </td>
                        <td>${i.reject_reason || '-'}</td>
                    </tr>
                `).join('')}</tbody>
            </table>`}
        `;
    } catch (err) {
        container.innerHTML = `<div class="empty-state"><p>加载失败：${err.message}</p></div>`;
    }
}

async function handleWithdraw(e) {
    e.preventDefault();
    try {
        const amount = document.getElementById('wAmount').value;
        const type = document.getElementById('wType').value;
        const account = document.getElementById('wAccount').value;
        await apiFetch('/finance/withdraw', {
            method: 'POST',
            body: JSON.stringify({
                amount: parseFloat(amount),
                account_type: type,
                account_no: account
            })
        });
        showToast('提现申请成功！', 'success');
        loadAuthorFinance(document.getElementById('dashboardMain'));
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function loadAdminWithdrawals(container) {
    container.innerHTML = '<div class="loading-state"><div class="spinner"></div></div>';
    try {
        const data = await apiFetch('/finance/admin/withdrawals');
        container.innerHTML = `
            <h2>提现审核</h2>
            ${data.items.length === 0 ? '<div class="empty-state">目前没有记录</div>' : `
            <table class="table">
                <thead><tr><th>用户</th><th>时间</th><th>金额</th><th>打款信息</th><th>状态</th><th>操作</th></tr></thead>
                <tbody>${data.items.map(i => `
                    <tr>
                        <td>${i.username}</td>
                        <td style="font-size:12px">${formatDate(i.created_at)}</td>
                        <td style="color:#d9363e;font-weight:bold">¥${i.amount}</td>
                        <td>${i.account_type} - ${i.account_no}</td>
                        <td>
                            <span class="plugin-tag" style="background:${i.status === 'pending' ? '#fffbe6;color:#faad14' : i.status === 'approved' ? '#f6ffed;color:#52c41a' : '#fff1f0;color:#f5222d'}">
                                ${i.status}
                            </span>
                            ${i.reject_reason ? `<br><small style="color:red">${i.reject_reason}</small>` : ''}
                        </td>
                        <td>
                            ${i.status === 'pending' ? `
                                <button class="btn btn-primary btn-sm" onclick="processWithdraw(${i.id}, 'approve')">通过/已打款</button>
                                <button class="btn btn-danger btn-sm" onclick="processWithdraw(${i.id}, 'reject')">拒绝</button>
                            ` : '-'}
                        </td>
                    </tr>
                `).join('')}</tbody>
            </table>`}
        `;
    } catch (err) {
        container.innerHTML = `<div class="empty-state"><p>加载失败：${err.message}</p></div>`;
    }
}

async function processWithdraw(id, action) {
    let reason = null;
    if (action === 'reject') {
        reason = prompt('请输入拒绝原因（资金将退回作者余额）：');
        if (reason === null) return;
    } else {
        if (!confirm('请确认您已经向作者打款完毕？点击确定将标记为已完成。')) return;
    }
    try {
        await apiFetch(`/finance/admin/withdrawals/${id}/process`, {
            method: 'POST',
            body: JSON.stringify({ action, reason })
        });
        showToast('处理成功', 'success');
        loadAdminWithdrawals(document.getElementById('dashboardMain'));
    } catch (err) {
        showToast('处理失败: ' + err.message, 'error');
    }
}
