# LecFaka Store - 插件商店与授权服务器

为 [LecFaka](https://github.com/Leclee/lecfaka) 提供插件分发和授权验证服务。

## API

| 端点 | 说明 |
|------|------|
| `GET /api/v1/store/plugins` | 插件列表（支持 type/keyword/category 筛选） |
| `GET /api/v1/store/plugins/{id}` | 插件详情 |
| `POST /api/v1/license/verify` | 验证授权码 |
| `POST /api/v1/license/bind` | 绑定域名 |

## 部署

```bash
docker compose up -d
```

服务运行在 `http://localhost:8001`。
