from ..common.global_config import GlobalConfig

from ..utils.json_utils import JsonUtils
from ..utils.collection_utils import CollectionUtils, CollectionColor
from ..utils.ssmt_error_utils import SSMTErrorUtils
import os
import bpy
from typing import List, Dict, Union
from dataclasses import dataclass, field, asdict

@dataclass
class DedupedTextureInfo:
    original_hash:str = field(default="",init=False)
    render_hash:str = field(default="",init=False)
    format:str = field(default="",init=False)
    componet_count_list_str:str = field(default="",init=False)


class SSMTWorkSpace:

    @staticmethod
    def get_object_display_name(submesh_folder_name: str, drawib_aliasname_dict: Dict[str, str] | None = None) -> str:
        normalized_folder_name = str(submesh_folder_name or "").strip()
        if not normalized_folder_name:
            return ""

        drawib_aliasname_dict = drawib_aliasname_dict or SSMTWorkSpace.get_drawib_aliasname_dict()
        folder_prefix, _, folder_alias = normalized_folder_name.partition(".")
        draw_ib = folder_prefix.split("-")[0]

        # 优先使用 Config.json 里显式配置的别名。
        configured_alias = str(drawib_aliasname_dict.get(draw_ib, "")).strip()
        if configured_alias:
            return configured_alias

        # 如果名称里已经带了别名后缀，则沿用它。
        if folder_alias.strip():
            return folder_alias.strip()

        # 无别名时回退为原始对象名称，避免写入“自定义名称”。
        return folder_prefix

    @staticmethod
    def get_display_submesh_name(submesh_folder_name: str, drawib_aliasname_dict: Dict[str, str] | None = None) -> str:
        normalized_folder_name = str(submesh_folder_name or "").strip()
        if not normalized_folder_name:
            return ""

        alias_name = SSMTWorkSpace.get_object_display_name(
            normalized_folder_name,
            drawib_aliasname_dict=drawib_aliasname_dict,
        )
        if not alias_name or alias_name == normalized_folder_name:
            return normalized_folder_name

        name_prefix, _, _ = normalized_folder_name.partition(".")
        return name_prefix + "." + alias_name

    @staticmethod
    def get_ordered_gpu_cpu_import_folderpath_list(submesh_folderpath:str)-> List[str]:
        # 导入时，要按照先GPU类型，再CPU类型进行排序
        gpu_import_folder_path_list = []
        cpu_import_folder_path_list = []

        dirs = os.listdir(submesh_folderpath)
        for dirname in dirs:
            if not dirname.startswith("TYPE_"):
                continue
            final_import_folder_path = os.path.join(submesh_folderpath,dirname)
            if dirname.startswith("TYPE_GPU"):
                gpu_import_folder_path_list.append(final_import_folder_path)
            elif dirname.startswith("TYPE_CPU"):
                cpu_import_folder_path_list.append(final_import_folder_path)

        final_import_folder_path_list = []
        for gpu_path in gpu_import_folder_path_list:
            final_import_folder_path_list.append(gpu_path)
        for cpu_path in cpu_import_folder_path_list:
            final_import_folder_path_list.append(cpu_path)

        return final_import_folder_path_list

    @staticmethod
    def parse_lod_submesh_name(submesh_name: str):
        '''
        解析 submesh_name，返回 (lod_name, bare_name)。
        如果有 LOD 前缀（如 "LOD0.67f829fc-2653-0"），返回 ("LOD0", "67f829fc-2653-0")；
        否则返回 ("", submesh_name)。
        '''
        if submesh_name and submesh_name.upper().startswith("LOD") and "." in submesh_name:
            dot_idx = submesh_name.index(".")
            potential_lod = submesh_name[:dot_idx]
            lod_suffix = potential_lod[3:]
            if lod_suffix.isdigit():
                return potential_lod, submesh_name[dot_idx + 1:]
        return "", submesh_name

    @staticmethod
    def get_submesh_folder_path(submesh_name: str) -> str:
        '''
        根据 submesh_name（可带 LOD 前缀）返回工作空间内实际的 submesh 文件夹路径。
        LOD0.67f829fc-2653-0 → workspace/LOD0/67f829fc-2653-0/
        67f829fc-2653-0      → workspace/67f829fc-2653-0/
        '''
        lod_name, bare_name = SSMTWorkSpace.parse_lod_submesh_name(submesh_name)
        workspace_folder = GlobalConfig.path_workspace_folder()
        if lod_name:
            return os.path.join(workspace_folder, lod_name, bare_name)
        return os.path.join(workspace_folder, bare_name)

    @staticmethod
    def create_and_get_workspace_collection() -> bpy.types.Collection:
        # 这里先创建以当前工作空间为名称的集合，并且链接到scene，确保它存在
        workspace_collection = CollectionUtils.create_new_collection(collection_name=GlobalConfig.get_workspace_name(),color_tag=CollectionColor.Red)
        bpy.context.scene.collection.children.link(workspace_collection)
        return workspace_collection

    @staticmethod
    def _get_submesh_folderpath_list_from(base_folder: str) -> List[str]:
        '''
        从指定目录中获取所有 SubMesh 文件夹（名字包含至少两个 '-' 的目录）。
        '''
        result = []
        if not os.path.isdir(base_folder):
            return result
        for f in os.scandir(base_folder):
            if not f.is_dir():
                continue
            if len(f.name.split('-')) >= 3:
                result.append(f.path)
        return result

    @staticmethod
    def get_lod_folderpath_list() -> List[str]:
        '''
        获取当前工作空间目录下所有以 "LOD" 开头（后接数字）的目录，按名称排序。
        '''
        lod_folders = []
        workspace_folder = GlobalConfig.path_workspace_folder()
        if not os.path.isdir(workspace_folder):
            return lod_folders
        for f in os.scandir(workspace_folder):
            if not f.is_dir():
                continue
            name = f.name
            if name.upper().startswith("LOD") and name[3:].isdigit():
                lod_folders.append(f.path)
        lod_folders.sort(key=lambda p: int(os.path.basename(p)[3:]))
        return lod_folders

    @staticmethod
    def get_lod_submesh_folderpath_dict() -> Dict[str, List[str]]:
        '''
        返回 {lod_name: [submesh_folder_path, ...]} 字典，按 LOD 排序。
        '''
        result: Dict[str, List[str]] = {}
        for lod_folder_path in SSMTWorkSpace.get_lod_folderpath_list():
            lod_name = os.path.basename(lod_folder_path)
            result[lod_name] = SSMTWorkSpace._get_submesh_folderpath_list_from(lod_folder_path)
        return result

    @staticmethod
    def get_submesh_folderpath_list() -> List[str]:
        '''
        获取当前工作空间文件夹下面的所有SubMesh文件夹（兼容旧版无LOD结构）。
        新版工作空间请使用 get_lod_submesh_folderpath_dict()。
        '''
        submesh_folderpath_list = []
        for f in os.scandir(GlobalConfig.path_workspace_folder()):
            if not f.is_dir():
                continue
            name_splits = f.name.split('-')
            if len(name_splits) >= 3:
                submesh_folderpath_list.append(f.path)
            
        return submesh_folderpath_list

    @staticmethod
    def get_drawib_aliasname_dict_for_path(folder_path: str) -> Dict[str, str]:
        '''
        从指定目录下的 Config.json 里读取 DrawIB 和别名的对应关系。
        '''
        drawib_aliasname_dict = {}
        config_json_path = os.path.join(folder_path, "Config.json")
        if os.path.exists(config_json_path):
            config_json = JsonUtils.LoadFromFile(config_json_path)
            if isinstance(config_json, list):
                for item in config_json:
                    if not isinstance(item, dict):
                        continue
                    draw_ib = str(item.get("DrawIB", "")).strip()
                    alias_name = str(item.get("Alias", "")).strip()
                    if draw_ib:
                        drawib_aliasname_dict[draw_ib] = alias_name
        return drawib_aliasname_dict

    @staticmethod
    def get_drawib_aliasname_dict() -> Dict[str,str]:
        '''
        从当前工作空间目录下的Config.json里读取DrawIB和别名的对应关系
        '''
        drawib_aliasname_dict = {}

        # 如果工作空间下存在Config.json就尝试获取其别名
        config_json_path = GlobalConfig.path_drawib_config_json_path()
        if os.path.exists(config_json_path):
            config_json = JsonUtils.LoadFromFile(config_json_path)
            # 读取每个DrawIB的别名到字典里，键是DrawIB名称，值是别名
            if isinstance(config_json, list):
                for item in config_json:
                    if not isinstance(item, dict):
                        continue
                    draw_ib = str(item.get("DrawIB", "")).strip()
                    alias_name = str(item.get("Alias", "")).strip()
                    if draw_ib:
                        drawib_aliasname_dict[draw_ib] = alias_name
        return drawib_aliasname_dict
    

    @staticmethod
    def check_and_get_submesh_json_path(submesh_name: str) -> str:
        """
        根据 submesh_name 查找对应的 SubmeshJson 文件路径。
        找到返回路径，找不到抛出 SSMTErrorUtils 错误。
        """
        workspace_folder = GlobalConfig.path_workspace_folder()

        lod_name, bare_name = SSMTWorkSpace.parse_lod_submesh_name(submesh_name)
        submesh_folder = SSMTWorkSpace.get_submesh_folder_path(submesh_name)

        if not os.path.exists(submesh_folder):
            SSMTErrorUtils.raise_fatal(
                f"submesh_name '{submesh_name}' 没有找到对应的提取数据。\n"
                + "请确保已从游戏中提取模型并执行「一键导入当前工作空间内容」操作。"
            )

        workspace_import_json_path = os.path.join(workspace_folder, "Import.json")
        workspace_import_json = JsonUtils.LoadFromFile(workspace_import_json_path) if os.path.exists(workspace_import_json_path) else {}
        gametype_name = workspace_import_json.get(submesh_name, "")

        if gametype_name:
            submesh_json_path = os.path.join(submesh_folder, "TYPE_" + gametype_name, bare_name + ".json")
            if os.path.exists(submesh_json_path):
                return submesh_json_path

        found_type_paths = []
        found_types = []
        for dirname in os.listdir(submesh_folder):
            if not dirname.startswith("TYPE_"):
                continue

            submesh_json_path = os.path.join(submesh_folder, dirname, bare_name + ".json")
            if os.path.exists(submesh_json_path):
                found_type_paths.append(submesh_json_path)
                found_types.append(dirname.replace("TYPE_", ""))

        if len(found_type_paths) == 1:
            return found_type_paths[0]

        if len(found_type_paths) > 1:
            SSMTErrorUtils.raise_fatal(
                f"submesh_name '{submesh_name}' 找到以下数据类型但没有在 Import.json 中记录: {', '.join(found_types)}\n"
                + "请尝试重新执行「一键导入当前工作空间内容」操作。"
            )

        SSMTErrorUtils.raise_fatal(
            f"submesh_name '{submesh_name}' 没有找到对应的 SubmeshJson。\n"
            + "请确保已从游戏中提取模型并执行「一键导入当前工作空间内容」操作。"
        )

    @staticmethod
    def get_hash_deduped_texture_info_dict(submesh_folder_name:str) -> Dict[str,DedupedTextureInfo]:

        draw_ib_folder_path = os.path.dirname(SSMTWorkSpace.get_submesh_folder_path(submesh_folder_name)) + "\\"
        # 接下来计算ComponentList，也就是当前DrawIB使用到这个贴图的所有Component的Count，从1开始
        component_name__drawcall_indexlist_json_path = os.path.join(draw_ib_folder_path,"ComponentName_DrawCallIndexList.json")
        trianglelist_deduped_filename_json_path = os.path.join(draw_ib_folder_path,"TrianglelistDedupedFileName.json")

        component_name__drawcall_indexlist_json_dict = JsonUtils.LoadFromFile(component_name__drawcall_indexlist_json_path)

        drawcall_component_count_dict = {}
        for component_index, (_, drawcall_indexlist) in enumerate(component_name__drawcall_indexlist_json_dict.items(), start=1):
            for drawcall_index in drawcall_indexlist:
                drawcall_component_count_dict[drawcall_index] = str(component_index)

        trianglelist_deduped_filename_json_dict = JsonUtils.LoadFromFile(trianglelist_deduped_filename_json_path)


        deduped_filename_drawcall_index_list_dict = {}
        for trianglelist_deduped_filename,deduped_kv_dict in trianglelist_deduped_filename_json_dict.items():
            deduped_filename:str = deduped_kv_dict["FALogDedupedFileName"]
            draw_call_index:str = trianglelist_deduped_filename[0:6]

            drawcall_index_list = deduped_filename_drawcall_index_list_dict.get(deduped_filename,[])
            if draw_call_index not in drawcall_index_list:
                drawcall_index_list.append(draw_call_index)

            deduped_filename_drawcall_index_list_dict[deduped_filename] = drawcall_index_list

        hash_deduped_texture_info_dict = {}

        for deduped_filename, drawcall_index_list in deduped_filename_drawcall_index_list_dict.items():
            used_component_count_list = []

            filename_parts = deduped_filename.split("_")
            original_hash = filename_parts[0] if len(filename_parts) > 0 else ""
            render_hash = filename_parts[1].split("-")[0] if len(filename_parts) > 1 else ""

            # 从类似于 "b7ff7a6e_03d46264-R8G8B8A8_UNORM_SRGB.dds" 的文件名中
            # 提取出 "R8G8B8A8_UNORM_SRGB" 部分：
            # - 去掉扩展名
            # - 找到第一个下划线 `_` 的位置
            # - 从该下划线之后查找第一个连字符 `-`，并取其后到文件名末尾的子串
            # - 如果找不到上述模式，则退回到以最后一个 `-` 分割并取最后一段的策略
            base_name = os.path.splitext(deduped_filename)[0]
            fmt = ""
            try:
                first_underscore = base_name.find("_")
                if first_underscore != -1:
                    dash_after_underscore = base_name.find("-", first_underscore + 1)
                    if dash_after_underscore != -1:
                        fmt = base_name[dash_after_underscore + 1:]
                # fallback: use last '-' part
                if not fmt:
                    if "-" in base_name:
                        fmt = base_name.rsplit("-", 1)[-1]
                    else:
                        # as ultimate fallback, if there is an underscore then maybe format is after the second underscore
                        parts = base_name.split("_")
                        if len(parts) > 2:
                            fmt = parts[-1]
                        else:
                            fmt = ""
                # strip any stray whitespace
                fmt = fmt.strip()
            except Exception:
                fmt = ""

            format = fmt

            print(format)

            for draw_call_index in drawcall_index_list:
                matched_component_count = drawcall_component_count_dict.get(draw_call_index,"")
                if matched_component_count != "":
                    if matched_component_count not in used_component_count_list:
                        used_component_count_list.append(matched_component_count)

            used_component_count_list.sort()
            # print(used_component_count_list)

            

            componet_count_list_str = ""
            for unique_component_count_str in used_component_count_list:
                componet_count_list_str = componet_count_list_str + unique_component_count_str + "."

            deduped_texture_info = DedupedTextureInfo()
            deduped_texture_info.original_hash = original_hash
            deduped_texture_info.render_hash = render_hash
            deduped_texture_info.format = format
            deduped_texture_info.componet_count_list_str = componet_count_list_str

            hash_deduped_texture_info_dict[original_hash] = deduped_texture_info
    
        return hash_deduped_texture_info_dict