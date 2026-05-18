import os
import shutil

from .m_ini_builder import *
from .m_key import M_Key
from .draw_call_model import DrawCallModel
from .drawib_model import DrawIBModel
from ..utils.json_utils import JsonUtils
from ..utils.format_utils import Fatal
from .global_config import GlobalConfig
from .global_properties import GlobalProterties
from ..workspace.workspace_helper import WorkSpaceHelper
from ..blueprint.blueprint_export_helper import BlueprintExportHelper
from .texture_metadata_helper import TextureMetadataResolver, TextureMarkUpInfo

class M_IniHelper:
    @classmethod
    def _get_aliased_texture_output_filename(cls, mark_filename: str, submesh_model) -> str:
        '''
        若 submesh_model 已应用别名（display_str != unique_str），则将 mark_filename 的
        bare_unique_str 前缀替换为 display_str，以便输出文件名使用别名。
        例：mark_filename="5a4c1ef3-318-46683-DiffuseMap.dds", display_str="LOD0.身体"
        → 返回 "LOD0.身体-DiffuseMap.dds"
        若无别名（display_str == unique_str），原样返回。
        '''
        display_str = getattr(submesh_model, "display_str", "")
        unique_str = getattr(submesh_model, "unique_str", "")
        if not display_str or not unique_str or display_str == unique_str:
            return mark_filename
        _, bare_unique_str = WorkSpaceHelper.parse_lod_unique_str(unique_str)
        old_prefix = bare_unique_str + "-"
        if mark_filename.startswith(old_prefix):
            return display_str + "-" + mark_filename[len(old_prefix):]
        return mark_filename

    @classmethod
    def _count_marked_textures(cls, draw_ib_model: DrawIBModel, mark_type: str | None = None) -> int:
        count = 0
        for submesh_model in getattr(draw_ib_model, "submesh_model_list", []):
            texture_info_list = draw_ib_model.get_submesh_texture_markup_info_list(submesh_model)
            for texture_info in texture_info_list:
                if mark_type is not None and getattr(texture_info, "mark_type", "") != mark_type:
                    continue
                count += 1
        return count

    @classmethod
    def _get_extract_gametype_folder_path(cls, draw_ib_model: DrawIBModel) -> str:
        primary_submesh_metadata = getattr(draw_ib_model, "primary_submesh_metadata", None)
        if primary_submesh_metadata is not None:
            extract_gametype_folder_path = getattr(primary_submesh_metadata, "extract_gametype_folder_path", "")
            if extract_gametype_folder_path:
                return extract_gametype_folder_path

        submesh_model_list = getattr(draw_ib_model, "submesh_model_list", [])
        if submesh_model_list:
            first_submesh_model = submesh_model_list[0]
            unique_str = getattr(first_submesh_model, "unique_str", "")
            d3d11_game_type = getattr(first_submesh_model, "d3d11_game_type", None)
            if unique_str and d3d11_game_type is not None:
                return os.path.join(
                    WorkSpaceHelper.get_submesh_folder_path(unique_str),
                    "TYPE_" + d3d11_game_type.GameTypeName,
                    "",
                )

        d3d11_game_type = getattr(draw_ib_model, "d3d11_game_type", getattr(draw_ib_model, "d3d11GameType", None))
        if d3d11_game_type is None:
            return ""

        return GlobalConfig.path_extract_gametype_folder(
            draw_ib=draw_ib_model.draw_ib,
            gametype_name=d3d11_game_type.GameTypeName,
        )

    @classmethod
    def _get_part_extract_gametype_folder_path(cls, draw_ib_model: DrawIBModel, part_name: str) -> str:
        print("[TRACE] _get_part_extract_gametype_folder_path: part_name=" + str(part_name))
        part_name_submesh_dict = getattr(draw_ib_model, "part_name_submesh_dict", {})
        print("[TRACE]   part_name_submesh_dict keys: " + str(list(part_name_submesh_dict.keys())))
        submesh_model = part_name_submesh_dict.get(part_name)
        if submesh_model is None:
            print("[TRACE]   part_name 未匹配到 submesh_model，返回空字符串!")
            return ""

        print("[TRACE]   匹配到 submesh_model, unique_str=" + str(getattr(submesh_model, "unique_str", "<无>")))

        d3d11_game_type = getattr(submesh_model, "d3d11_game_type", None)
        print("[TRACE]   submesh.d3d11_game_type: " + str(d3d11_game_type))
        if d3d11_game_type is None:
            d3d11_game_type = getattr(draw_ib_model, "d3d11_game_type", getattr(draw_ib_model, "d3d11GameType", None))
            print("[TRACE]   降级使用 draw_ib_model.d3d11_game_type: " + str(d3d11_game_type))
        unique_str = getattr(submesh_model, "unique_str", "")
        if d3d11_game_type is None or unique_str == "":
            print("[TRACE]   返回空字符串! d3d11_game_type=" + str(d3d11_game_type) + ", unique_str=" + str(unique_str))
            return ""

        submesh_folder = WorkSpaceHelper.get_submesh_folder_path(unique_str)
        result = os.path.join(submesh_folder, "TYPE_" + d3d11_game_type.GameTypeName, "")
        print("[TRACE]   构造路径: " + result)
        print("[TRACE]   路径是否存在: " + str(os.path.exists(result)))
        return result

    @classmethod
    def _get_slot_texture_source_path(cls, draw_ib_model: DrawIBModel, part_name: str, texture_markup_info) -> str:
        print("[TRACE] _get_slot_texture_source_path 入口:")
        print("[TRACE]   DrawIB: " + draw_ib_model.draw_ib)
        print("[TRACE]   part_name: " + str(part_name))
        print("[TRACE]   mark_filename: " + texture_markup_info.mark_filename)
        print("[TRACE]   mark_hash: " + str(getattr(texture_markup_info, "mark_hash", "<无>")))

        # 策略1: 通过 part_name 精确定位
        extract_gametype_folder_path = cls._get_part_extract_gametype_folder_path(draw_ib_model, part_name)
        print("[TRACE] 策略1 _get_part_extract_gametype_folder_path 返回: '" + extract_gametype_folder_path + "'")
        if extract_gametype_folder_path:
            source_path = extract_gametype_folder_path + texture_markup_info.mark_filename
            print("[TRACE] 策略1 source_path: " + source_path)
            print("[TRACE] 策略1 source_path 文件存在: " + str(os.path.exists(source_path)))
            if os.path.exists(source_path):
                print("[TRACE] 策略1 命中! 返回: " + source_path)
                return source_path
            else:
                print("[TRACE] 策略1 路径已构造但文件不存在，尝试列出目录内容:")
                if os.path.exists(extract_gametype_folder_path):
                    files_in_dir = os.listdir(extract_gametype_folder_path)
                    print("[TRACE]   目录存在，文件列表(前20个): " + str(files_in_dir[:20]))
                    print("[TRACE]   目录总文件数: " + str(len(files_in_dir)))
                else:
                    print("[TRACE]   目录本身不存在: " + extract_gametype_folder_path)
        else:
            print("[TRACE] 策略1 返回空字符串，进入策略2")

        # 策略2: 遍历所有 submesh 的 TYPE_<gametype> 目录
        print("[TRACE] 策略2: 遍历 submesh_model_list 查找贴图文件")
        submesh_list = getattr(draw_ib_model, "submesh_model_list", [])
        print("[TRACE]   submesh_model_list 数量: " + str(len(submesh_list)))
        for si, submesh_model in enumerate(submesh_list):
            d3d11_game_type = getattr(submesh_model, "d3d11_game_type", None)
            if d3d11_game_type is None:
                d3d11_game_type = getattr(draw_ib_model, "d3d11_game_type", getattr(draw_ib_model, "d3d11GameType", None))
            unique_str = getattr(submesh_model, "unique_str", "")
            print("[TRACE]   策略2 submesh[" + str(si) + "]: unique_str=" + unique_str + ", d3d11_game_type=" + str(d3d11_game_type))
            if d3d11_game_type is None or unique_str == "":
                print("[TRACE]   策略2 submesh[" + str(si) + "]: 跳过 (d3d11_game_type=None 或 unique_str为空)")
                continue

            candidate_source_path = os.path.join(
                WorkSpaceHelper.get_submesh_folder_path(unique_str),
                "TYPE_" + d3d11_game_type.GameTypeName,
                texture_markup_info.mark_filename,
            )
            print("[TRACE]   策略2 submesh[" + str(si) + "]: 候选路径=" + candidate_source_path)
            print("[TRACE]   策略2 submesh[" + str(si) + "]: 文件存在=" + str(os.path.exists(candidate_source_path)))
            if os.path.exists(candidate_source_path):
                print("[TRACE] 策略2 命中! 返回: " + candidate_source_path)
                return candidate_source_path

        print("[TRACE] 策略1和策略2均未找到贴图源文件!")
        print("[TRACE]   DrawIB: " + draw_ib_model.draw_ib)
        print("[TRACE]   part_name: " + str(part_name))
        print("[TRACE]   文件: " + texture_markup_info.mark_filename)
        return ""

    @classmethod
    def _get_hash_texture_source_path(cls, draw_ib_model: DrawIBModel, part_name: str, texture_markup_info) -> str:
        print("-" * 40)
        print("[TRACE] _get_hash_texture_source_path 入口 (Hash贴图源路径解析):")
        print("[TRACE]   DrawIB: " + draw_ib_model.draw_ib)
        print("[TRACE]   part_name: " + str(part_name))
        print("[TRACE]   mark_filename: " + texture_markup_info.mark_filename)
        print("[TRACE]   mark_hash: " + str(getattr(texture_markup_info, "mark_hash", "<无>")))
        print("[TRACE]   委托给 _get_slot_texture_source_path (Hash和Slot共用源路径解析):")
        result = cls._get_slot_texture_source_path(draw_ib_model, part_name, texture_markup_info)
        print("[TRACE] _get_hash_texture_source_path 最终返回: '" + result + "'")
        print("-" * 40)
        return result

    @classmethod
    def _get_part_submesh_folder_name(cls, draw_ib_model: DrawIBModel, part_name: str) -> str:
        part_name_submesh_dict = getattr(draw_ib_model, "part_name_submesh_dict", {})
        submesh_model = part_name_submesh_dict.get(part_name)
        if submesh_model is None:
            print("M_IniHelper: part_name 未匹配到 submesh，DrawIB: " + draw_ib_model.draw_ib + "，Part: " + str(part_name))
            return ""

        submesh_folder_name = getattr(submesh_model, "unique_str", "")
        print("M_IniHelper: Part " + str(part_name) + " 对应 unique_str: " + submesh_folder_name)
        return submesh_folder_name

    @classmethod
    def _get_hash_deduped_texture_info(cls, draw_ib_model: DrawIBModel, mark_hash: str):
        for submesh_model in getattr(draw_ib_model, "submesh_model_list", []):
            submesh_folder_name = getattr(submesh_model, "unique_str", "")
            if not submesh_folder_name:
                continue

            hash_deduped_texture_info_dict = WorkSpaceHelper.get_hash_deduped_texture_info_dict(submesh_folder_name=submesh_folder_name)
            deduped_texture_info = hash_deduped_texture_info_dict.get(mark_hash, None)
            if deduped_texture_info is not None:
                print(
                    "M_IniHelper: 在 unique_str "
                    + submesh_folder_name
                    + " 中找到 Hash 去重信息，Hash: "
                    + mark_hash
                )
                return deduped_texture_info

        print("M_IniHelper: 当前 DrawIB 的所有 unique_str 中都未找到 Hash 去重信息，Hash: " + mark_hash)
        return None

    @classmethod
    def get_drawindexed_str_list(
        cls,
        ordered_draw_obj_model_list: list[DrawCallModel],
        obj_name_draw_offset_dict: dict[str, int] | None = None,
    ) -> list[str]:
        # 传统的使用DrawIndexed方式调用这个
        # 在输出之前，我们需要根据condition对obj_model进行分组
        condition_str_obj_model_list_dict:dict[str,list[DrawCallModel]] = {}
        for obj_model in ordered_draw_obj_model_list:
            condition_str = obj_model.get_condition_str()

            obj_model_list = condition_str_obj_model_list_dict.get(condition_str,[])
            
            obj_model_list.append(obj_model)
            condition_str_obj_model_list_dict[condition_str] = obj_model_list
        
        drawindexed_str_list:list[str] = []
        for condition_str, obj_model_list in condition_str_obj_model_list_dict.items():
            if condition_str != "":
                drawindexed_str_list.append("if " + condition_str)
                for obj_model in obj_model_list:
                    display_name = str(getattr(obj_model, 'obj_name', '') or getattr(obj_model, 'display_name', '') or '')
                    drawindexed_str_list.append("  ; [mesh:" + display_name + "] [vertex_count:" + str(obj_model.vertex_count) + "]" )
                    drawindexed_str_list.append("  " + obj_model.get_drawindexed_str(obj_name_draw_offset_dict))
                drawindexed_str_list.append("endif")
            else:
                for obj_model in obj_model_list:
                    display_name = str(getattr(obj_model, 'obj_name', '') or getattr(obj_model, 'display_name', '') or '')
                    drawindexed_str_list.append("; [mesh:" + display_name + "] [vertex_count:" + str(obj_model.vertex_count) + "]" )
                    drawindexed_str_list.append(obj_model.get_drawindexed_str(obj_name_draw_offset_dict))
            drawindexed_str_list.append("")

        return drawindexed_str_list
    
    @classmethod
    def get_drawindexed_instanced_str_list(
        cls,
        ordered_draw_obj_model_list: list[DrawCallModel],
        obj_name_draw_offset_dict: dict[str, int] | None = None,
    ) -> list[str]:
        # 使用DrawIndexedInstanced方式调用这个
        # 在输出之前，我们需要根据condition对obj_model进行分组
        condition_str_obj_model_list_dict:dict[str,list[DrawCallModel]] = {}
        for obj_model in ordered_draw_obj_model_list:
            condition_str = obj_model.get_condition_str()

            obj_model_list = condition_str_obj_model_list_dict.get(condition_str,[])
            
            obj_model_list.append(obj_model)
            condition_str_obj_model_list_dict[condition_str] = obj_model_list
        
        drawindexed_str_list:list[str] = []
        for condition_str, obj_model_list in condition_str_obj_model_list_dict.items():
            if condition_str != "":
                drawindexed_str_list.append("if " + condition_str)
                for obj_model in obj_model_list:
                    display_name = str(getattr(obj_model, 'obj_name', '') or getattr(obj_model, 'display_name', '') or '')
                    drawindexed_str_list.append("  ; [mesh:" + display_name + "] [vertex_count:" + str(obj_model.vertex_count) + "]" )
                    drawindexed_str_list.append("  " + obj_model.get_drawindexed_instanced_str(obj_name_draw_offset_dict))
                drawindexed_str_list.append("endif")
            else:
                for obj_model in obj_model_list:
                    display_name = str(getattr(obj_model, 'obj_name', '') or getattr(obj_model, 'display_name', '') or '')
                    drawindexed_str_list.append("; [mesh:" + display_name + "] [vertex_count:" + str(obj_model.vertex_count) + "]" )
                    drawindexed_str_list.append("  " + obj_model.get_drawindexed_instanced_str(obj_name_draw_offset_dict))
            drawindexed_str_list.append("")

        return drawindexed_str_list

    @classmethod
    def generate_hash_style_texture_ini(cls,ini_builder:M_IniBuilder,drawib_drawibmodel_dict:dict[str,DrawIBModel]):
        '''
        Hash风格贴图
        '''
        print("=" * 60)
        print("[TRACE] generate_hash_style_texture_ini() 入口")
        print("[TRACE]   DrawIB 总数: " + str(len(drawib_drawibmodel_dict)))
        print("[TRACE]   DrawIB 列表: " + str(list(drawib_drawibmodel_dict.keys())))
        print("=" * 60)

        if GlobalProterties.forbid_auto_texture_ini():
            print("[TRACE] generate_hash_style_texture_ini: forbid_auto_texture_ini=True, 跳过!")
            return

        # 先统计当前标记的具有Slot风格的Hash值，后续Render里搞图片的时候跳过这些
        slot_style_texture_hash_list = []
        for draw_ib_model in drawib_drawibmodel_dict.values():
            for submesh_model in getattr(draw_ib_model, "submesh_model_list", []):
                for texture_markup_info in draw_ib_model.get_submesh_texture_markup_info_list(submesh_model):
                    if texture_markup_info.mark_type == "Slot":
                        slot_style_texture_hash_list.append(texture_markup_info.mark_hash)

        print("slot_style_texture_hash_list:" + str(slot_style_texture_hash_list))
        print("M_IniHelper: 开始生成 Hash 风格贴图配置，DrawIB 数量: " + str(len(drawib_drawibmodel_dict)))

        repeat_hash_list = []
        hash_copied = 0
        hash_skipped_exists = 0
        hash_skipped_no_source = 0
        hash_skipped_repeat = 0
        hash_skipped_non_hash = 0

        # 遍历当前drawib的Render文件夹
        for draw_ib,draw_ib_model in drawib_drawibmodel_dict.items():
            marked_hash_count = cls._count_marked_textures(draw_ib_model, mark_type="Hash")
            print("M_IniHelper: DrawIB " + draw_ib + " 的 Hash 标记数量: " + str(marked_hash_count))

            submesh_list = getattr(draw_ib_model, "submesh_model_list", [])
            print("[TRACE] generate_hash_style_texture_ini: DrawIB " + draw_ib + " submesh 数量: " + str(len(submesh_list)))

            # 添加标记的Hash风格贴图
            for si, submesh_model in enumerate(submesh_list):
                texture_markup_info_list = draw_ib_model.get_submesh_texture_markup_info_list(submesh_model)
                unique_str = getattr(submesh_model, "unique_str", "<无>")
                print("[TRACE]   submesh[" + str(si) + "]: unique_str=" + unique_str + ", 贴图数=" + str(len(texture_markup_info_list)))

                if not texture_markup_info_list:
                    continue
                    
                part_name = draw_ib_model.get_submesh_part_name(submesh_model)
                submesh_folder_name = getattr(submesh_model, "unique_str", "")
                if not submesh_folder_name:
                    print("M_IniHelper: 跳过 Hash 贴图处理，未找到 unique_str，Part: " + str(part_name))
                    continue

                hash_deduped_texture_info_dict = WorkSpaceHelper.get_hash_deduped_texture_info_dict(submesh_folder_name=submesh_folder_name)
                print(
                    "M_IniHelper: 已读取 Hash 去重信息，unique_str: "
                    + submesh_folder_name
                    + "，记录数: "
                    + str(len(hash_deduped_texture_info_dict))
                )

                for ti, texture_markup_info in enumerate(texture_markup_info_list):
                    print("[TRACE]     Hash贴图[" + str(ti) + "]: mark_type=" + texture_markup_info.mark_type
                          + " mark_filename=" + texture_markup_info.mark_filename
                          + " mark_hash=" + str(getattr(texture_markup_info, "mark_hash", "<无>")))

                    if texture_markup_info.mark_type != "Hash":
                        print("[TRACE]     跳过: mark_type 不是 Hash (实际=" + texture_markup_info.mark_type + ")")
                        hash_skipped_non_hash += 1
                        continue

                    texture_output_folder = GlobalConfig.path_generatemod_texture_folder(draw_ib=draw_ib)
                    print("M_IniHelper: Hash 贴图输出目录: " + texture_output_folder)

                    if texture_markup_info.mark_hash in repeat_hash_list:
                        print("[TRACE]     跳过: mark_hash 重复: " + texture_markup_info.mark_hash)
                        hash_skipped_repeat += 1
                        continue
                    else:
                        repeat_hash_list.append(texture_markup_info.mark_hash)

                    d3d11_game_type = getattr(draw_ib_model, "d3d11_game_type", getattr(draw_ib_model, "d3d11GameType", None))
                    print("[TRACE]     d3d11_game_type: " + str(d3d11_game_type))
                    if d3d11_game_type is None:
                        print("[TRACE]     跳过: d3d11_game_type 为 None!")
                        hash_skipped_no_source += 1
                        continue

                    print("[TRACE]     调用 _get_hash_texture_source_path...")
                    original_texture_file_path = cls._get_hash_texture_source_path(
                        draw_ib_model=draw_ib_model,
                        part_name=part_name,
                        texture_markup_info=texture_markup_info,
                    )
                    print("[TRACE]     _get_hash_texture_source_path 返回: '" + original_texture_file_path + "'")
                    if not original_texture_file_path or not os.path.exists(original_texture_file_path):
                        print("[TRACE]     跳过: 源文件不存在或路径为空: '" + original_texture_file_path + "'")
                        hash_skipped_no_source += 1
                        continue

                    hash_style_texture_filename = ""
                    hash_style_texture_filename = hash_style_texture_filename + draw_ib + "_" + draw_ib_model.draw_ib_alias + "_"

                    deduped_texture_info = hash_deduped_texture_info_dict.get(texture_markup_info.mark_hash,None)
                    if deduped_texture_info is None:
                        deduped_texture_info = cls._get_hash_deduped_texture_info(
                            draw_ib_model=draw_ib_model,
                            mark_hash=texture_markup_info.mark_hash,
                        )

                    if deduped_texture_info is None:
                        print(
                            "M_IniHelper: 未找到 Hash 去重信息，降级使用原始标记文件名继续导出。DrawIB: "
                            + draw_ib
                            + "，文件名: "
                            + texture_markup_info.mark_filename
                            + "，Hash: "
                            + texture_markup_info.mark_hash
                        )
                        hash_style_texture_filename = texture_markup_info.mark_filename
                        hash_style_texture_filename = cls._get_aliased_texture_output_filename(hash_style_texture_filename, submesh_model)
                    else:
                        component_count_list_str = deduped_texture_info.componet_count_list_str
                        hash_style_texture_filename = hash_style_texture_filename + "_" + component_count_list_str + "_"
                        hash_style_texture_filename = hash_style_texture_filename + deduped_texture_info.original_hash + "_" + deduped_texture_info.render_hash + "_" + deduped_texture_info.format + "_" + texture_markup_info.mark_name
                        hash_style_texture_filename = hash_style_texture_filename + "." + texture_markup_info.mark_filename.split(".")[1]
                    print("[TRACE]     输出文件名: " + hash_style_texture_filename)

                    target_texture_file_path = GlobalConfig.path_generatemod_texture_folder(draw_ib=draw_ib) + hash_style_texture_filename
                    print("[TRACE]     目标路径: " + target_texture_file_path)
                    print("[TRACE]     目标已存在: " + str(os.path.exists(target_texture_file_path)))

                    resource_and_textureoverride_texture_section = M_IniSection(M_SectionType.ResourceAndTextureOverride_Texture)
                    resource_and_textureoverride_texture_section.append("[Resource_Texture_" + texture_markup_info.mark_hash + "]")
                    resource_and_textureoverride_texture_section.append("filename = Textures/" + hash_style_texture_filename)
                    resource_and_textureoverride_texture_section.new_line()

                    resource_and_textureoverride_texture_section.append("[TextureOverride_" + texture_markup_info.mark_hash + "]")
                    resource_and_textureoverride_texture_section.append("; " + texture_markup_info.mark_filename)
                    resource_and_textureoverride_texture_section.append("hash = " + texture_markup_info.mark_hash)
                    resource_and_textureoverride_texture_section.append("match_priority = 0")
                    resource_and_textureoverride_texture_section.append("this = Resource_Texture_" + texture_markup_info.mark_hash)
                    resource_and_textureoverride_texture_section.new_line()

                    ini_builder.append_section(resource_and_textureoverride_texture_section)

                    # copy only if target not exists avoid overwrite texture manually replaced by mod author.
                    if not os.path.exists(target_texture_file_path):
                        print("[TRACE] >>> 执行 shutil.copy2: " + original_texture_file_path + " -> " + target_texture_file_path)
                        try:
                            shutil.copy2(original_texture_file_path,target_texture_file_path)
                            print("[TRACE] <<< shutil.copy2 成功: " + target_texture_file_path)
                            hash_copied += 1
                        except Exception as e:
                            print("[TRACE] <<< shutil.copy2 失败! 异常: " + str(e))
                    else:
                        print("[TRACE]     跳过复制: 目标已存在")
                        hash_skipped_exists += 1

        print("[TRACE] generate_hash_style_texture_ini() 汇总:")
        print("[TRACE]   Hash 复制成功: " + str(hash_copied))
        print("[TRACE]   Hash 跳过(目标已存在): " + str(hash_skipped_exists))
        print("[TRACE]   Hash 跳过(源文件缺失): " + str(hash_skipped_no_source))
        print("[TRACE]   Hash 跳过(重复hash): " + str(hash_skipped_repeat))
        print("[TRACE]   Hash 跳过(非Hash类型): " + str(hash_skipped_non_hash))
        print("=" * 60)

        # if len(repeat_hash_list) != 0:
        #     texture_ini_builder.save_to_file(MainConfig.path_generate_mod_folder() + MainConfig.workspacename + "_Texture.ini")

    @classmethod
    def move_slot_style_textures(cls,draw_ib_model:DrawIBModel):
        '''
        Move all textures from extracted game type folder to generate mod Texture folder.
        Only works in default slot style texture.
        '''
        print("=" * 60)
        print("[TRACE] move_slot_style_textures() 入口 - DrawIB: " + draw_ib_model.draw_ib)
        print("=" * 60)

        if GlobalProterties.forbid_auto_texture_ini():
            print("[TRACE] move_slot_style_textures: forbid_auto_texture_ini=True, 跳过所有贴图复制!")
            return

        marked_slot_count = cls._count_marked_textures(draw_ib_model, mark_type="Slot")
        print("M_IniHelper: 开始复制 Slot 贴图，DrawIB: " + draw_ib_model.draw_ib + "，Slot 标记数量: " + str(marked_slot_count))

        submesh_model_list = getattr(draw_ib_model, "submesh_model_list", [])
        print("[TRACE] move_slot_style_textures: submesh_model_list 数量 = " + str(len(submesh_model_list)))

        slot_copied = 0
        slot_skipped_exists = 0
        slot_skipped_no_source = 0
        slot_skipped_non_slot = 0

        for idx, submesh_model in enumerate(submesh_model_list):
            texture_markup_info_list = draw_ib_model.get_submesh_texture_markup_info_list(submesh_model)
            unique_str = getattr(submesh_model, "unique_str", "<无>")
            print("[TRACE] submesh[" + str(idx) + "] unique_str=" + unique_str + ", 贴图标记数=" + str(len(texture_markup_info_list)))

            if not texture_markup_info_list:
                print("[TRACE] submesh[" + str(idx) + "] 无贴图标记，跳过")
                continue

            part_name = draw_ib_model.get_submesh_part_name(submesh_model) or submesh_model.unique_str
            for ti, texture_markup_info in enumerate(texture_markup_info_list):
                print("[TRACE]   贴图[" + str(ti) + "]: mark_type=" + texture_markup_info.mark_type
                      + ", mark_filename=" + texture_markup_info.mark_filename
                      + ", mark_hash=" + str(getattr(texture_markup_info, "mark_hash", "<无>")))

                if texture_markup_info.mark_type != "Slot":
                    print("[TRACE]   贴图[" + str(ti) + "]: mark_type 不是 Slot (实际=" + texture_markup_info.mark_type + ")，跳过")
                    slot_skipped_non_slot += 1
                    continue

                texture_output_folder = GlobalConfig.path_generatemod_texture_folder(draw_ib=draw_ib_model.draw_ib)
                print("M_IniHelper: Slot 贴图输出目录: " + texture_output_folder)
                print("[TRACE] Slot 贴图输出目录是否存在: " + str(os.path.exists(texture_output_folder)))

                aliased_texture_filename = cls._get_aliased_texture_output_filename(texture_markup_info.mark_filename, submesh_model)
                if aliased_texture_filename != texture_markup_info.mark_filename:
                    print("[TRACE] Slot 贴图别名替换: " + texture_markup_info.mark_filename + " -> " + aliased_texture_filename)

                target_path = GlobalConfig.path_generatemod_texture_folder(draw_ib=draw_ib_model.draw_ib) + aliased_texture_filename
                source_path = cls._get_slot_texture_source_path(draw_ib_model, part_name, texture_markup_info)
                print("[TRACE] Slot 贴图 source_path 解析结果: '" + source_path + "'")
                print("[TRACE] Slot 贴图 target_path: '" + target_path + "'")
                print("[TRACE] source_path 存在: " + str(os.path.exists(source_path) if source_path else "N/A (空字符串)"))
                print("[TRACE] target_path 存在: " + str(os.path.exists(target_path)))

                if os.path.exists(target_path):
                    print("[TRACE] Slot 贴图目标已存在，跳过复制: " + target_path)
                    slot_skipped_exists += 1
                else:
                    if source_path == "":
                        print("[TRACE] Slot 贴图 source_path 为空字符串，跳过! mark_filename=" + texture_markup_info.mark_filename)
                        slot_skipped_no_source += 1
                        continue
                    if not os.path.exists(source_path):
                        print("[TRACE] Slot 贴图 source_path 文件不存在，跳过! source_path=" + source_path)
                        slot_skipped_no_source += 1
                        continue
                    print("[TRACE] >>> 执行 shutil.copy2: " + source_path + " -> " + target_path)
                    try:
                        shutil.copy2(source_path,target_path)
                        print("[TRACE] <<< shutil.copy2 成功: " + target_path)
                        slot_copied += 1
                    except Exception as e:
                        print("[TRACE] <<< shutil.copy2 失败! 异常: " + str(e))

        print("[TRACE] move_slot_style_textures() 汇总 - DrawIB: " + draw_ib_model.draw_ib)
        print("[TRACE]   Slot 复制成功: " + str(slot_copied))
        print("[TRACE]   Slot 跳过(目标已存在): " + str(slot_skipped_exists))
        print("[TRACE]   Slot 跳过(源文件缺失): " + str(slot_skipped_no_source))
        print("[TRACE]   Slot 跳过(非Slot类型): " + str(slot_skipped_non_slot))
        print("=" * 60)
    
    @classmethod
    def add_shapekey_ini_sections(cls, ini_builder:M_IniBuilder,drawib_drawibmodel_dict:dict[str,DrawIBModel]):
        shapekeyname_mkey_dict = BlueprintExportHelper.get_current_shapekeyname_mkey_dict()
        if len(shapekeyname_mkey_dict.keys()) == 0:
            return

        # [Constants]
        constants_section = M_IniSection(M_SectionType.Constants)
        constants_section.append("[Constants]")
        constants_section.append("global persist $shapekey_first_run = 1")

        for shapekey_name, m_key in shapekeyname_mkey_dict.items():
            constants_section.append("; ShapeKey: " + shapekey_name)
            constants_section.append("global persist " + m_key.key_name + " = " + str(m_key.initialize_value))
            constants_section.new_line()

        ini_builder.append_section(constants_section)

        # [Present]
        present_section = M_IniSection(M_SectionType.Present)
        present_section.append("[Present]")
        present_section.append("if $shapekey_first_run")

        ib_number = 1
        for drawib, drawib_model in drawib_drawibmodel_dict.items():
            shapekey_buffer_dict = getattr(drawib_model, "shapekey_name_bytelist_dict", {})

            # 如果当前DrawIB没有生成形态键数据，则跳过不处理
            if not shapekey_buffer_dict:
                continue

            original_position_buffer_resource_name ="Resource" + drawib + "Position"     
            duplicated_position_buffer_resource_name = "Resource" + drawib + "Position.1"

            present_section.append("  " + original_position_buffer_resource_name + " = copy " + duplicated_position_buffer_resource_name)
            present_section.append("  run = CustomShaderComputeShapes" + str(ib_number))

            ib_number += 1
        
        present_section.append("  $shapekey_first_run = 0")
        present_section.append("endif")

        ib_number = 1
        for drawib, drawib_model in drawib_drawibmodel_dict.items():
            shapekey_buffer_dict = getattr(drawib_model, "shapekey_name_bytelist_dict", {})

            # 如果当前DrawIB没有生成形态键数据，则跳过不处理
            if not shapekey_buffer_dict:
                continue

            present_section.append("  run = CustomShaderComputeShapes" + str(ib_number))
            ib_number += 1

        ini_builder.append_section(present_section)
        
        # [CustomShaderComputeShapes]
        customshader_section = M_IniSection(M_SectionType.CommandList)

        ib_number = 1
        for drawib, drawib_model in drawib_drawibmodel_dict.items():
            shapekey_buffer_dict = getattr(drawib_model, "shapekey_name_bytelist_dict", {})
            d3d11_game_type = getattr(drawib_model, "d3d11_game_type", getattr(drawib_model, "d3d11GameType", None))
            draw_number = getattr(drawib_model, "draw_number", getattr(drawib_model, "vertex_count", 0))

            # 如果当前DrawIB没有生成形态键数据，则跳过不处理
            if not shapekey_buffer_dict or d3d11_game_type is None:
                continue

            customshader_section.append("[CustomShaderComputeShapes" + str(ib_number) + "]")
            customshader_section.append("cs = ./res/Shapes.hlsl")
            customshader_section.append("cs-u5 = copy " + "Resource" + drawib + "Position.1")
            customshader_section.new_line()

            # 对于每个形态键buffer都进行计算
            for shapekey_name, m_key in shapekeyname_mkey_dict.items():
                # 这里很显然有问题，如果一个DrawIB有这个形态键，另一个DrawIB没有这个形态键呢？
                # 那这里就会导致游戏内没有这个形态键的模型出现异常
                # 所以如果这个DrawIB内没有这个形态键的话，就不需要生成它的计算代码
                if shapekey_buffer_dict.get(shapekey_name, None) is None:
                    continue

                customshader_section.append("x88 = " + m_key.key_name)
                customshader_section.append("cs-t50 = copy " + "Resource" + drawib + "Position.1")
                customshader_section.append("cs-t51 = copy " + "Resource" + drawib + "Position." + shapekey_name)
                customshader_section.append("Resource" + drawib + "Position = ref cs-u5")
                customshader_section.append("Dispatch = " + str(draw_number) + " ,1 ,1")
                customshader_section.new_line()

            ib_number += 1

            customshader_section.append("cs-u5 = null")
            customshader_section.append("cs-t50 = null")
            customshader_section.append("cs-t51 = null")

        ini_builder.append_section(customshader_section)

        # [Resources]
        resource_section = M_IniSection(M_SectionType.ResourceBuffer)


        ib_number = 1
        for drawib, drawib_model in drawib_drawibmodel_dict.items():
            shapekey_buffer_dict = getattr(drawib_model, "shapekey_name_bytelist_dict", {})
            d3d11_game_type = getattr(drawib_model, "d3d11_game_type", getattr(drawib_model, "d3d11GameType", None))

            # 如果当前DrawIB没有生成形态键数据，则跳过不处理
            if not shapekey_buffer_dict or d3d11_game_type is None:
                continue

            # 原本的Buffer
            resource_section.append("[Resource" + drawib + "Position.1]")
            resource_section.append("type = buffer")
            resource_section.append("stride = " + str(d3d11_game_type.CategoryStrideDict["Position"]))
            resource_section.append("filename = Meshes\\" + drawib + "-" + "Position.buf")
            resource_section.new_line()

            # 各个形态键的Buffer
            for shapekey_name, m_key in shapekeyname_mkey_dict.items():
                # 这里很显然有问题，如果一个DrawIB有这个形态键，另一个DrawIB没有这个形态键呢？
                # 那这里就会导致游戏内没有这个形态键的模型出现异常
                # 所以如果这个DrawIB内没有这个形态键的话，就不需要生成它的计算代码
                if shapekey_buffer_dict.get(shapekey_name, None) is None:
                    continue
                
                resource_section.append("[Resource" + drawib + "Position." + shapekey_name + "]")
                resource_section.append("type = buffer")
                resource_section.append("stride = " + str(d3d11_game_type.CategoryStrideDict["Position"]))
                resource_section.append("filename = Meshes\\" + drawib + "-" + "Position." + shapekey_name + ".buf")
                resource_section.new_line()

            ib_number += 1
        
        ini_builder.append_section(resource_section)

        # [Key]
        # 用于按下测试的Key，也可以作为在没有面板时的按键切换形态键快捷键
        key_section = M_IniSection(M_SectionType.Key)
        for shapekey_name, m_key in shapekeyname_mkey_dict.items():
            if m_key.initialize_vk_str != "":
                key_section.append("[Key_ShapeKey_" +shapekey_name + "]")
                
                # 添加备注信息
                comment = getattr(m_key, 'comment', '')
                if comment:
                    key_section.append("; " + comment)
                
                key_section.append("key = " + m_key.initialize_vk_str)
                key_section.append("type = cycle")
                key_section.append(m_key.key_name + " = 0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1")
                key_section.new_line()

        ini_builder.append_section(key_section)



    @classmethod
    def add_branch_key_sections(cls,ini_builder:M_IniBuilder,key_name_mkey_dict:dict[str,M_Key]):

        if len(key_name_mkey_dict.keys()) != 0:
            constants_section = M_IniSection(M_SectionType.Constants)
            constants_section.SectionName = "Constants"

            for i in range(GlobalConfig.generated_mod_number):
                constants_section.append("global $active" + str(i))

            for mkey in key_name_mkey_dict.values():
                key_str = "global persist " + mkey.key_name + " = " + str(mkey.initialize_value)
                constants_section.append(key_str) 

            ini_builder.append_section(constants_section)


        if len(key_name_mkey_dict.keys()) != 0:
            present_section = M_IniSection(M_SectionType.Present)
            present_section.SectionName = "Present"

            for i in range(GlobalConfig.generated_mod_number):
                present_section.append("post $active" + str(i) + " = 0")
            ini_builder.append_section(present_section)
        
        key_number = 0
        if len(key_name_mkey_dict.keys()) != 0:

            for mkey in key_name_mkey_dict.values():
                key_section = M_IniSection(M_SectionType.Key)
                key_section.append("[KeySwap_" + str(key_number) + "]")
                
                # 添加备注信息
                comment = getattr(mkey, 'comment', '')
                if comment:
                    key_section.append("; " + comment)
                
                # key_section.append("condition = $active" + str(key_number) + " == 1")

                # XXX 这里由于有BUG，我们固定用$active0来检测激活，不搞那么复杂了。
                key_section.append("condition = $active0 == 1")

                if mkey.initialize_vk_str != "":
                    key_section.append("key = " + mkey.initialize_vk_str)
                else:
                    key_section.append("key = " + mkey.key_value)
                key_section.append("type = cycle")

                key_value_number = len(mkey.value_list)
                key_cycle_str = ""
                for i in range(key_value_number):
                    if i < key_value_number + 1:
                        key_cycle_str = key_cycle_str + str(i) + ","
                    else:
                        key_cycle_str = key_cycle_str + str(i)
                key_section.append(mkey.key_name + " = " + key_cycle_str)
                key_section.new_line()
                ini_builder.append_section(key_section)

                key_number = key_number + 1