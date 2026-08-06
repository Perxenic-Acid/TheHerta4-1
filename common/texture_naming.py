"""Texture 节点的默认命名规则。"""

import re


def normalize_texture_role(mark_name: str) -> str:
    role = re.sub(r"[^A-Za-z0-9]+", "_", str(mark_name or "").strip()).strip("_")
    return role or "Texture"


def default_texture_resource_name(texture_hash: str, mark_name: str = "") -> str:
    return f"Resource_{normalize_texture_role(mark_name)}_{texture_hash or 'unnamed'}"


def default_texture_filename(texture_hash: str, mark_name: str = "") -> str:
    return f"{texture_hash or 'unnamed'}_{normalize_texture_role(mark_name)}.dds"
