"""
插件 ZIP 包规范化工具

@brief 将上传的原始 ZIP 解压后，验证并重新打包为标准结构
@details 确保顶级目录为 {plugin_id}/，剔除垃圾文件，验证 plugin.json 合法性
"""

import json
import os
import shutil
import zipfile
import tempfile
import logging
from typing import Optional, Set

logger = logging.getLogger("lecfaka_store.zip_utils")

## 规范化时需要忽略的文件/目录
IGNORED_DIRS: Set[str] = {"__pycache__", ".git", ".DS_Store", "node_modules", ".venv"}
IGNORED_FILES: Set[str] = {".DS_Store", "Thumbs.db", ".gitignore"}


def normalize_zip(raw_zip_path: str, plugin_id: str, dest_path: str) -> dict:
    """
    @brief 将原始 zip 解压后规范化重新打包
    @param raw_zip_path 原始 zip 路径
    @param plugin_id    插件 ID（作为顶级目录名）
    @param dest_path    规范化 zip 的输出路径
    @return dict 包含 plugin.json 中的元数据

    规范化规则：
    1. 确保顶级目录为 {plugin_id}/
    2. 剔除 __pycache__/.git/.DS_Store 等垃圾
    3. 验证 plugin.json 存在且 id 字段与 plugin_id 一致

    @throws ValueError 当 zip 内容不合法时
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

            extract_tmp = tempfile.mkdtemp(prefix="plugin_upload_")
            z.extractall(extract_tmp)

        ## 定位 plugin.json 所在目录
        prefix_dir = os.path.dirname(plugin_json_entry.replace("/", os.sep))
        if prefix_dir:
            source_dir = os.path.join(extract_tmp, prefix_dir)
        else:
            source_dir = extract_tmp

        pj_path = os.path.join(source_dir, "plugin.json")
        if not os.path.exists(pj_path):
            raise ValueError("解压后找不到 plugin.json")

        ## 读取并验证 plugin.json
        with open(pj_path, "r", encoding="utf-8") as f:
            try:
                pj_data = json.loads(f.read())
            except json.JSONDecodeError as e:
                raise ValueError(f"plugin.json 格式错误: {e}")

        zip_plugin_id = pj_data.get("id", "").strip()
        if zip_plugin_id and zip_plugin_id != plugin_id:
            raise ValueError(
                f"plugin.json 中的 id '{zip_plugin_id}' 与声明的 plugin_id '{plugin_id}' 不一致"
            )

        ## 重新打包
        file_count = 0
        with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for root, dirs, files in os.walk(source_dir):
                dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
                for fname in files:
                    if fname in IGNORED_FILES:
                        continue
                    abs_path = os.path.join(root, fname)
                    rel_path = os.path.relpath(abs_path, source_dir)
                    arcname = os.path.join(plugin_id, rel_path).replace("\\", "/")
                    zout.write(abs_path, arcname)
                    file_count += 1

        logger.info(
            f"[normalize_zip] 规范化完成: plugin_id={plugin_id}, 文件数={file_count}"
        )
        return pj_data

    finally:
        if extract_tmp and os.path.exists(extract_tmp):
            shutil.rmtree(extract_tmp, ignore_errors=True)
