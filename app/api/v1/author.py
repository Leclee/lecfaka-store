"""
插件作者 API — author 和 superadmin 可访问

功能：
- 查看自己发布的插件列表
- 上传新插件（需审核后上架）
- 更新已有插件版本
"""

import json
import os
import shutil
import zipfile
import tempfile
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.plugin import StoreUser, StorePlugin
from ...core.auth import get_current_user, require_role

router = APIRouter()
logger = logging.getLogger("lecfaka_store.author")

## 插件包上传目录（与 admin.py 共用）
UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "uploads", "plugins",
)
os.makedirs(UPLOAD_DIR, exist_ok=True)

## zip 规范化时需要忽略的文件/目录
_IGNORED_DIRS = {"__pycache__", ".git", ".DS_Store"}
_IGNORED_FILES = {".DS_Store", "Thumbs.db"}


# ==================== 权限依赖 ====================

async def require_author(user: StoreUser = Depends(get_current_user)):
    """
    @brief 作者权限检查（author 和 superadmin 均可通过）
    """
    require_role(user, ["author", "superadmin"])
    return user


# ==================== 通用工具 ====================

def _normalize_zip(raw_zip_path: str, plugin_id: str, dest_path: str):
    """
    @brief 将原始 zip 解压后规范化重新打包
    @param raw_zip_path 原始 zip 路径
    @param plugin_id    插件 ID（作为顶级目录名）
    @param dest_path    规范化 zip 的输出路径

    规范化规则：
    1. 确保顶级目录为 {plugin_id}/
    2. 剔除 __pycache__/.git/.DS_Store 等垃圾
    3. 验证 plugin.json 存在
    """
    extract_tmp = None
    try:
        with zipfile.ZipFile(raw_zip_path, "r") as z:
            names = z.namelist()

            ## 查找 plugin.json
            plugin_json_entry = None
            for n in names:
                if n.endswith("/"):
                    continue
                parts = n.replace("\\", "/").split("/")
                if parts[-1] == "plugin.json":
                    plugin_json_entry = n
                    break

            if not plugin_json_entry:
                raise ValueError("zip 包中缺少 plugin.json")

            extract_tmp = tempfile.mkdtemp(prefix="author_upload_")
            z.extractall(extract_tmp)

        ## 定位 plugin.json 所在目录
        prefix_dir = os.path.dirname(plugin_json_entry.replace("/", os.sep))
        if prefix_dir:
            source_dir = os.path.join(extract_tmp, prefix_dir)
        else:
            source_dir = extract_tmp

        if not os.path.exists(os.path.join(source_dir, "plugin.json")):
            raise ValueError("解压后找不到 plugin.json")

        ## 重新打包
        with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for root, dirs, files in os.walk(source_dir):
                dirs[:] = [d for d in dirs if d not in _IGNORED_DIRS]
                for fname in files:
                    if fname in _IGNORED_FILES:
                        continue
                    abs_path = os.path.join(root, fname)
                    rel_path = os.path.relpath(abs_path, source_dir)
                    arcname = os.path.join(plugin_id, rel_path).replace("\\", "/")
                    zout.write(abs_path, arcname)

        logger.info(
            f"[normalize] 规范化完成: plugin_id={plugin_id}, "
            f"文件数={len(zipfile.ZipFile(dest_path, 'r').namelist())}"
        )
    finally:
        if extract_tmp and os.path.exists(extract_tmp):
            shutil.rmtree(extract_tmp, ignore_errors=True)


# ==================== 我发布的插件 ====================

@router.get("/plugins")
async def my_published_plugins(
    author: StoreUser = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    """获取当前作者发布的所有插件"""
    result = await db.execute(
        select(StorePlugin)
        .where(StorePlugin.author_id == author.id)
        .order_by(StorePlugin.created_at.desc())
    )
    plugins = result.scalars().all()

    status_map = {0: "已下架", 1: "已上架", 2: "审核中"}

    return {
        "items": [
            {
                "plugin_id": p.plugin_id,
                "name": p.name,
                "type": p.type,
                "version": p.version,
                "description": p.description,
                "price": float(p.price),
                "is_free": p.is_free,
                "status": p.status,
                "status_text": status_map.get(p.status, "未知"),
                "download_count": p.download_count,
                "purchase_count": p.purchase_count,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            }
            for p in plugins
        ]
    }


# ==================== 上传新插件 ====================

@router.post("/plugins/upload")
async def author_upload_plugin(
    file: UploadFile = File(...),
    meta: str = Form(...),
    author: StoreUser = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    """
    作者上传新插件

    上传后默认进入 **审核中** 状态 (status=2)。
    superadmin 上传也走此接口时同样进入审核（管理员直接上架请用 /admin/plugins/upload）。

    前端通过 FormData 发送：
    - file: ZIP 文件
    - meta: JSON 字符串，包含插件元数据
    """
    ## 1. 解析元数据
    try:
        meta_data = json.loads(meta)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="元数据 JSON 格式错误")

    plugin_id = meta_data.get("plugin_id", "").strip()
    if not plugin_id:
        raise HTTPException(status_code=400, detail="plugin_id 不能为空")

    name = meta_data.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="插件名称不能为空")

    ## 2. 验证文件类型
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="只支持 ZIP 格式")

    ## 3. 检查 plugin_id 是否已被其他人使用
    existing = await db.execute(
        select(StorePlugin).where(StorePlugin.plugin_id == plugin_id)
    )
    existing_plugin = existing.scalar_one_or_none()
    if existing_plugin and existing_plugin.author_id != author.id:
        raise HTTPException(
            status_code=400,
            detail=f"插件 ID '{plugin_id}' 已被其他开发者占用",
        )

    ## 4. 保存原始 zip 到临时文件
    raw_content = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_raw:
        tmp_raw.write(raw_content)
        tmp_raw_path = tmp_raw.name

    try:
        ## 5. 规范化打包
        version = meta_data.get("version", "1.0.0")
        plugin_dir = os.path.join(UPLOAD_DIR, plugin_id)
        os.makedirs(plugin_dir, exist_ok=True)
        final_path = os.path.join(plugin_dir, f"{plugin_id}_v{version}.zip")

        _normalize_zip(tmp_raw_path, plugin_id, final_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        try:
            os.unlink(tmp_raw_path)
        except OSError:
            pass

    ## 6. 生成下载 URL
    download_url = f"/uploads/plugins/{plugin_id}/{os.path.basename(final_path)}"

    ## 7. 创建或更新数据库记录
    price = Decimal(str(meta_data.get("price", 0)))
    is_free = meta_data.get("is_free", price == 0)

    if existing_plugin:
        ## 更新（作者更新自己的插件）
        existing_plugin.name = name
        existing_plugin.type = meta_data.get("type", existing_plugin.type)
        existing_plugin.version = version
        existing_plugin.description = meta_data.get("description", existing_plugin.description)
        existing_plugin.detail_html = meta_data.get("detail_html", existing_plugin.detail_html)
        existing_plugin.website = meta_data.get("website", existing_plugin.website)
        existing_plugin.download_url = download_url
        existing_plugin.price = price
        existing_plugin.is_free = is_free
        existing_plugin.updated_at = datetime.utcnow()
        ## 更新后重新进入审核
        existing_plugin.status = 2
        msg = f"插件 '{name}' 已更新，等待审核"
    else:
        ## 新建
        new_plugin = StorePlugin(
            plugin_id=plugin_id,
            name=name,
            type=meta_data.get("type", "extension"),
            version=version,
            author_id=author.id,
            author_name=meta_data.get("author_name", author.username),
            description=meta_data.get("description", ""),
            detail_html=meta_data.get("detail_html", ""),
            icon=meta_data.get("icon"),
            website=meta_data.get("website"),
            download_url=download_url,
            price=price,
            is_free=is_free,
            is_official=False,  ## 作者上传的不是官方插件
            category=meta_data.get("category"),
            status=2,  ## 审核中
        )
        db.add(new_plugin)
        msg = f"插件 '{name}' 提交成功，等待管理员审核"

    await db.commit()

    logger.info(
        f"[author_upload] user={author.username}(id={author.id}), "
        f"plugin_id={plugin_id}, version={version}, action={'update' if existing_plugin else 'create'}"
    )

    return {
        "success": True,
        "message": msg,
        "plugin_id": plugin_id,
        "download_url": download_url,
    }


# ==================== 更新已有插件版本 ====================

@router.post("/plugins/{plugin_id}/update")
async def author_update_plugin_version(
    plugin_id: str,
    file: UploadFile = File(...),
    version: str = Form(...),
    changelog: str = Form(""),
    author: StoreUser = Depends(require_author),
    db: AsyncSession = Depends(get_db),
):
    """
    作者更新已发布插件的版本

    仅允许更新自己发布的插件。更新后进入审核状态。
    """
    ## 1. 验证归属
    result = await db.execute(
        select(StorePlugin).where(StorePlugin.plugin_id == plugin_id)
    )
    plugin = result.scalar_one_or_none()
    if not plugin:
        raise HTTPException(status_code=404, detail="插件不存在")

    if plugin.author_id != author.id and author.role != "superadmin":
        raise HTTPException(status_code=403, detail="无权更新此插件")

    ## 2. 验证文件
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="只支持 ZIP 格式")

    ## 3. 规范化打包
    raw_content = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_raw:
        tmp_raw.write(raw_content)
        tmp_raw_path = tmp_raw.name

    try:
        plugin_dir = os.path.join(UPLOAD_DIR, plugin_id)
        os.makedirs(plugin_dir, exist_ok=True)
        final_path = os.path.join(plugin_dir, f"{plugin_id}_v{version}.zip")
        _normalize_zip(tmp_raw_path, plugin_id, final_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        try:
            os.unlink(tmp_raw_path)
        except OSError:
            pass

    ## 4. 更新数据库
    plugin.version = version
    plugin.download_url = f"/uploads/plugins/{plugin_id}/{os.path.basename(final_path)}"
    plugin.updated_at = datetime.utcnow()
    plugin.status = 2  ## 更新后重新审核

    await db.commit()

    logger.info(
        f"[author_update] user={author.username}(id={author.id}), "
        f"plugin_id={plugin_id}, new_version={version}"
    )

    return {
        "success": True,
        "message": f"插件 {plugin.name} 已更新至 v{version}，等待审核",
        "plugin_id": plugin_id,
        "version": version,
    }
