'''
Texture 节点相关的导出辅助函数。
所有贴图 INI 段落与文件复制均从蓝图 SSMTNode_Texture 节点驱动。
'''
import os
import shutil
import struct
import subprocess
from pathlib import Path

import bpy

from .m_ini_builder import M_IniBuilder, M_IniSection, M_SectionType
from .global_config import GlobalConfig


class M_TextureHelper:
    """负责把蓝图中的 Texture 节点转换成 3Dmigoto INI 段并复制贴图文件。"""

    # 常见 DXGI 格式 -> 可作为 texconv -f 参数的字符串
    _KNOWN_FORMATS = {
        'BC7_UNORM', 'BC7_UNORM_SRGB', 'R8G8B8A8_UNORM', 'R8G8B8A8_UNORM_SRGB',
        'R10G10B10A2_UNORM', 'R11G11B10_FLOAT', 'BC5_UNORM', 'BC5_SNORM',
        'BC1_UNORM', 'BC1_UNORM_SRGB', 'BC3_UNORM', 'BC3_UNORM_SRGB',
    }

    @classmethod
    def _get_texconv_path(cls) -> str:
        """查找内置 texconv.exe 路径。"""
        # 优先 TheHerta4 自身 resources
        addon_dir = Path(__file__).parent.parent.resolve()
        candidates = [
            addon_dir / 'resources' / 'texconv.exe',
            addon_dir / '..' / 'resources' / 'texconv.exe',
        ]
        # 其次 SSMT4 工作空间常见位置
        ssmt_candidates = [
            Path('C:/Users/angel/Desktop/github/ssmt4-alpha/src-tauri/resources/texconv.exe'),
            Path('C:/Users/angel/Desktop/github/ssmt4-alpha/src-tauri/target/debug/resources/texconv.exe'),
        ]
        for p in candidates + ssmt_candidates:
            if p.exists():
                return str(p)
        # 最后尝试 PATH
        for path_env in os.environ.get('PATH', '').split(os.pathsep):
            p = Path(path_env) / 'texconv.exe'
            if p.exists():
                return str(p)
        return ''

    @classmethod
    def detect_dds_format(cls, dds_path: str) -> str:
        """从 DDS 文件头解析 DXGI format，解析失败返回空字符串。"""
        try:
            with open(dds_path, 'rb') as f:
                data = f.read(148)
            if len(data) < 128 or data[:4] != b'DDS ':
                return ''
            # pixel format fourcc at offset 84
            pf_fourcc = struct.unpack_from('<I', data, 84)[0]
            if pf_fourcc.to_bytes(4, 'little') != b'DX10':
                return ''
            dxgi_format = struct.unpack_from('<I', data, 128)[0]
            format_map = {
                28: 'R8G8B8A8_UNORM',
                29: 'R8G8B8A8_UNORM_SRGB',
                24: 'R10G10B10A2_UNORM',
                26: 'R11G11B10_FLOAT',
                98: 'BC7_UNORM',
                99: 'BC7_UNORM_SRGB',
                80: 'BC4_UNORM',
                81: 'BC4_SNORM',
                83: 'BC5_UNORM',
                84: 'BC5_SNORM',
                71: 'BC1_UNORM',
                72: 'BC1_UNORM_SRGB',
                77: 'BC3_UNORM',
                78: 'BC3_UNORM_SRGB',
            }
            return format_map.get(dxgi_format, '')
        except Exception as e:
            print(f"[M_TextureHelper] 解析 DDS 格式失败: {dds_path}, {e}")
            return ''

    @classmethod
    def convert_texture_with_texconv(cls, source_path: str, target_path: str, target_format: str) -> bool:
        """调用 texconv 将源贴图转换为目标格式。成功返回 True。"""
        target_format = target_format.strip()
        if not target_format:
            return False
        texconv = cls._get_texconv_path()
        if not texconv:
            print("[M_TextureHelper] 未找到 texconv.exe，跳过格式转换")
            return False
        if not os.path.exists(source_path):
            return False

        target_dir = os.path.dirname(target_path)
        target_filename = os.path.basename(target_path)
        base_name, _ = os.path.splitext(target_filename)

        args = [
            texconv,
            source_path.replace('/', '\\'),
            '-ft', 'dds',
            '-f', target_format,
            '-o', target_dir.replace('/', '\\'),
            '-n', base_name,
            '-y',
        ]
        try:
            print(f"[M_TextureHelper] 转换贴图: {source_path} -> {target_format}")
            result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            if result.returncode != 0:
                print(f"[M_TextureHelper] texconv 失败: {result.stderr}")
                return False
            return True
        except Exception as e:
            print(f"[M_TextureHelper] texconv 调用异常: {e}")
            return False

    @staticmethod
    def _node_hash(texture_node):
        return str(getattr(texture_node, "texture_hash", "") or "").strip()

    @staticmethod
    def _node_resource_name(texture_node):
        return texture_node.get_resource_name() if hasattr(texture_node, "get_resource_name") else ""

    @staticmethod
    def _node_texture_filename(texture_node):
        return texture_node.get_texture_filename() if hasattr(texture_node, "get_texture_filename") else ""

    @staticmethod
    def _node_source_path(texture_node):
        path = str(getattr(texture_node, "texture_filepath", "") or "").strip()
        if path:
            path = os.path.abspath(bpy.path.abspath(path))
        return path

    @classmethod
    def _node_target_format(cls, texture_node) -> str:
        """获取节点上配置的目标格式，优先使用 effective_texture_format 属性。"""
        if hasattr(texture_node, "effective_texture_format"):
            fmt = str(texture_node.effective_texture_format or "").strip()
            if fmt:
                return fmt
        return str(getattr(texture_node, "texture_format", "") or "").strip()

    @classmethod
    def copy_texture_files(cls, texture_node_list, output_texture_folder):
        """把 Texture 节点指定的源文件拷贝/转换到生成目录的 Textures 文件夹。"""
        if not os.path.exists(output_texture_folder):
            os.makedirs(output_texture_folder, exist_ok=True)

        for texture_node in texture_node_list:
            source_path = cls._node_source_path(texture_node)
            if not source_path or not os.path.exists(source_path):
                print(f"[M_TextureHelper] 源贴图文件不存在，跳过: {source_path}")
                continue

            target_filename = cls._node_texture_filename(texture_node)
            target_path = os.path.join(output_texture_folder, target_filename)
            if os.path.exists(target_path):
                continue

            target_format = cls._node_target_format(texture_node)
            source_ext = os.path.splitext(source_path)[1].lower()
            source_format = ''
            if source_ext == '.dds':
                source_format = cls.detect_dds_format(source_path)

            converted = False
            if target_format and (source_format != target_format or source_ext != '.dds'):
                converted = cls.convert_texture_with_texconv(source_path, target_path, target_format)

            if not converted:
                try:
                    shutil.copy2(source_path, target_path)
                    print(f"[M_TextureHelper] 复制贴图: {source_path} -> {target_path}")
                except Exception as e:
                    print(f"[M_TextureHelper] 复制贴图失败: {source_path} -> {target_path}, 错误: {e}")

    @classmethod
    def generate_hash_texture_sections(cls, texture_node_list, ini_builder: M_IniBuilder):
        """为通过 Hash 出口参与链路的 Texture 节点生成独立段。"""
        section = M_IniSection(M_SectionType.ResourceAndTextureOverride_Texture)
        seen_hashes = set()

        for texture_node in texture_node_list:
            tex_hash = cls._node_hash(texture_node)
            if not tex_hash:
                continue
            if tex_hash in seen_hashes:
                continue
            seen_hashes.add(tex_hash)

            resource_name = cls._node_resource_name(texture_node) or f"Resource_Texture_{tex_hash}"
            filename = cls._node_texture_filename(texture_node) or f"{tex_hash}_texture.dds"
            mark_name = str(getattr(texture_node, "mark_name", "") or "").strip()

            section.append(f"[Resource_Texture_{tex_hash}]")
            section.append(f"filename = Textures/{filename}")
            section.new_line()

            section.append(f"[TextureOverride_{tex_hash}]")
            if mark_name:
                section.append(f"; {mark_name}")
            section.append(f"hash = {tex_hash}")
            section.append("match_priority = 0")
            section.append(f"this = {resource_name}")
            section.new_line()

        if seen_hashes:
            ini_builder.append_section(section)

    @classmethod
    def get_slot_texture_lines_for_submesh(cls, submesh_model) -> list[str]:
        """返回该 SubMesh 下所有 slot texture 节点对应的 INI 行（聚合去重）。"""
        lines = []
        seen_keys = set()
        for slot_item, texture_node in submesh_model.get_slot_texture_node_list():
            tex_hash = cls._node_hash(texture_node)
            if not tex_hash:
                continue
            resource_name = cls._node_resource_name(texture_node) or f"Resource_Texture_{tex_hash}"
            slot_key = getattr(slot_item, "effective_slot_key", f"ps-t{slot_item.slot_index}") if slot_item else "ps-t0"
            key = (slot_key, resource_name)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            value_prefix = "" if slot_key.startswith("ps-t") else "ref "
            lines.append(f"{slot_key} = {value_prefix}{resource_name}")
        return lines

    @classmethod
    def collect_all_texture_nodes(cls, blueprint_model, drawib_model_list) -> list:
        """收集当前生成范围内所有被引用的 Texture 节点（Hash + Slot），按 id 去重。"""
        seen_ids = set()
        result = []
        for texture_node in getattr(blueprint_model, "hash_texture_node_list", []):
            node_id = id(texture_node)
            if node_id in seen_ids:
                continue
            seen_ids.add(node_id)
            result.append(texture_node)
        for drawib_model in drawib_model_list:
            for submesh_model in getattr(drawib_model, "submesh_model_list", []):
                for slot_item, texture_node in submesh_model.get_slot_texture_node_list():
                    node_id = id(texture_node)
                    if node_id in seen_ids:
                        continue
                    seen_ids.add(node_id)
                    result.append(texture_node)
        return result

    @classmethod
    def generate_slot_texture_resource_sections(cls, drawib_model, blueprint_model, ini_builder: M_IniBuilder):
        """为所有被 Slot 方式引用的 Texture 节点生成 [Resource_...] 段。"""
        section = M_IniSection(M_SectionType.ResourceTexture)
        seen_resources = set()

        # 从所有 SubMesh 的 slot texture 节点中收集
        for submesh_model in drawib_model.submesh_model_list:
            for slot_item, texture_node in submesh_model.get_slot_texture_node_list():
                tex_hash = cls._node_hash(texture_node)
                if not tex_hash:
                    continue
                resource_name = cls._node_resource_name(texture_node) or f"Resource_Texture_{tex_hash}"
                if resource_name in seen_resources:
                    continue
                seen_resources.add(resource_name)
                filename = cls._node_texture_filename(texture_node) or f"{tex_hash}_texture.dds"
                section.append(f"[{resource_name}]")
                section.append(f"filename = Textures/{filename}")
                section.new_line()


        # Hash 出口的 Texture 节点由 generate_hash_texture_sections 统一生成 [Resource_...] 与 [TextureOverride_...]，
        # 这里只负责 Slot 方式的资源段，避免重复。

        if seen_resources:
            ini_builder.append_section(section)

    @classmethod
    def get_slot_texture_lines_for_drawcall(cls, drawcall_model) -> list[str]:
        """返回单个 DrawCallModel 对应的 slot texture INI 行。

        用于在每次 drawindexed 调用前单独设置槽位。
        """
        lines = []
        seen_keys = set()
        for slot_item, texture_node in getattr(drawcall_model, "slot_texture_node_list", []):
            tex_hash = cls._node_hash(texture_node)
            if not tex_hash:
                continue
            resource_name = cls._node_resource_name(texture_node) or f"Resource_Texture_{tex_hash}"
            slot_key = getattr(slot_item, "effective_slot_key", f"ps-t{slot_item.slot_index}") if slot_item else f"ps-t{0}"
            key = (slot_key, resource_name)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            value_prefix = "" if slot_key.startswith("ps-t") else "ref "
            lines.append(f"{slot_key} = {value_prefix}{resource_name}")
        return lines
