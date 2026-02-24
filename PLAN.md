# 插件商店完善计划

## 📋 需求分析

### 当前问题
1. **商店前端**：Hero 区域显示了插件数量、用户数、安装数等统计 → 需要移除
2. **管理控制台**：Store 的管理后台页面未实现 → 需要新建
3. **插件安装流程**：用户购买后无法在线安装到主站 → 需要实现完整闭环
4. **主题插件架构**：当前一个主题插件 = 一个主题 → 需要改为一个主题插件包含多个主题

---

## 🔨 实施计划

### Phase 1: 快速修复 — 移除统计数字
- [x] 移除 `index.html` 中 `.hero-stats` 区域
- [x] 移除 `store.js` 中 `animateNumber` 相关调用

### Phase 2: Store 管理控制台页面
管理员（superadmin）登录后可在控制台看到额外的管理选项：

#### 2.1 管理控制台界面 (index.html + store.js)
- 在 dashboard sidebar 增加「管理面板」入口（仅 superadmin 可见）
- 管理面板包含以下 Tab：
  - **数据概览**：用户数、插件数、订单数、收入统计
  - **插件管理**：列表、发布/下架、上传新插件、编辑插件信息
  - **用户管理**：列表、角色调整、启用/禁用

#### 2.2 插件上传 API (store 后端)
- `POST /api/v1/admin/plugins/upload` — 上传插件包（ZIP）
- `POST /api/v1/admin/plugins` — 创建/编辑插件条目
- `PUT /api/v1/admin/plugins/{plugin_id}` — 更新插件信息
- 插件 ZIP 包格式要求：包含 `plugin.json` 元数据

### Phase 3: 主题插件多主题架构
- 一个主题插件包（如 aurora_premium）可以包含多个主题变体
- `plugin.json` 中新增 `themes` 数组字段描述所有主题
- 用户购买一个主题包 = 获得包内所有主题的使用权
- 作者更新插件包时可以添加新主题
- 主站前端主题切换 UI 展示该包下所有可用主题

### Phase 4: 在线安装流程
- 用户在主站管理后台「应用商店」购买后，点击「安装」
- 主站后端从 Store 下载插件 ZIP 包
- 解压到 `plugins/installed/` 目录
- 自动注册并启用插件

---

## 📁 文件修改清单

### lecfaka-store (商店)
| 文件 | 操作 | 说明 |
|------|------|------|
| `app/static/index.html` | 修改 | 移除统计区域,增加管理入口 |
| `app/static/js/store.js` | 修改 | 移除统计相关代码,添加管理面板逻辑 |
| `app/static/css/store.css` | 修改 | 添加管理面板样式 |
| `app/api/v1/admin.py` | 修改 | 添加插件上传/管理 API |
| `app/api/v1/store.py` | 修改 | 移除 user_count 返回 |

### lecfaka (主站)
| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/plugins/sdk/base.py` | 修改 | ThemePluginBase 支持多主题 |
| `backend/app/plugins/__init__.py` | 修改 | PluginManager 适配多主题 |
| `backend/app/api/v1/admin/plugins.py` | 修改 | 主题列表/切换 API |
