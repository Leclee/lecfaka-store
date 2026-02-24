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
    } else {
        guest.style.display = 'flex';
        user.style.display = 'none';
        navDash.style.display = 'none';
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

        // 更新统计数字
        const total = pluginsData.length;
        animateNumber('statPlugins', total);
        animateNumber('statUsers', data.user_count || 0);
        animateNumber('statDownloads', pluginsData.reduce((s, p) => s + (p.download_count || 0), 0));
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
    if (!el || target === 0) {
        if (el) el.textContent = target;
        return;
    }
    const duration = 800;
    const start = performance.now();
    const from = parseInt(el.textContent) || 0;
    function update(now) {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic
        el.textContent = Math.round(from + (target - from) * eased);
        if (progress < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}
