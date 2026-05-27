
'''
导入模型配置面板
'''
import os
import shutil
import bpy

# 用于解决 AttributeError: 'IMPORT_MESH_OT_migoto_raw_buffers_mmt' object has no attribute 'filepath'
from bpy_extras.io_utils import ImportHelper

from ..utils.json_utils import JsonUtils
from ..utils.collection_utils import CollectionUtils, CollectionColor
from ..utils.timer_utils import TimerUtils
from ..utils.translate_utils import rpt_

from ..common.global_config import GlobalConfig
from ..common.ssmt_import_helper import SSMTImportHelper
from ..workspace.ssmt_workspace import SSMTWorkSpace, WorkSpaceModel
from ..blueprint.blueprint_export_helper import BlueprintExportHelper


# 全量导入逻辑
def ImprotFromWorkSpaceFull(self, context):
    
    # 创建 WorkSpaceModel 统一管理所有映射
    ws_model = WorkSpaceModel()

    # 这里先创建以当前工作空间为名称的集合，并且链接到scene，确保它存在
    workspace_collection = SSMTWorkSpace.create_and_get_workspace_collection()

    if not ws_model.lod_components:
        self.report({'ERROR'}, "当前工作空间未找到任何 LOD 目录（LOD0、LOD1…），请检查工作空间结构。")
        return

    # key: 新格式 submesh_name（如 "LOD0.94517393-0"）, value: gametype_name
    foldername_gametypename_dict = {}
    foldername_imported_obj_dict = {}
    all_submesh_display_names = []
    successful_import_count = 0

    for lod_name in sorted(ws_model.lod_components.keys()):
        # 为每个 LOD 创建蓝色子集合，挂在工作空间集合下面
        lod_collection = CollectionUtils.create_new_collection(
            collection_name=lod_name,
            color_tag=CollectionColor.Blue,
        )
        workspace_collection.children.link(lod_collection)

        drawib_components = ws_model.lod_components[lod_name]

        for draw_ib in sorted(drawib_components.keys()):
            comp_map = drawib_components[draw_ib]

            for comp_index in sorted(comp_map.keys()):
                old_folder_name = comp_map[comp_index]
                new_submesh_name = ws_model.get_new_submesh_name(lod_name, draw_ib, comp_index)
                display_name = ws_model.get_display_name(lod_name, draw_ib, comp_index)
                folder_path = ws_model.get_folder_path(lod_name, draw_ib, comp_index)

                if not folder_path or not os.path.isdir(folder_path):
                    continue

                print("Import FolderName: " + folder_path)

                # 获取导入的数据类型文件夹路径列表
                final_import_folder_path_list = SSMTWorkSpace.get_ordered_gpu_cpu_import_folderpath_list(folder_path)
                print("Final Import Folder Path List: " + str(final_import_folder_path_list))

                # 接下来开始导入，尝试对当前DrawIB的每个数据类型都进行导入
                for import_folder_path in final_import_folder_path_list:
                    gametype_name = import_folder_path.split("TYPE_")[1]

                    try:
                        print("尝试导入路径: " + import_folder_path)

                        json_file_path = os.path.join(import_folder_path, old_folder_name + ".json")
                        imported_obj = SSMTImportHelper.create_mesh_from_json(
                            json_file_path=json_file_path,
                            import_collection=lod_collection,
                        )
                        if imported_obj is not None:
                            imported_obj.name = display_name
                            imported_obj.data.name = imported_obj.name
                            foldername_imported_obj_dict[new_submesh_name] = (imported_obj, display_name)
                            all_submesh_display_names.append(display_name)
                            successful_import_count += 1

                        foldername_gametypename_dict[new_submesh_name] = gametype_name
                        self.report({'INFO'}, "成功导入 " + new_submesh_name + " 的数据类型: " + gametype_name)
                    except Exception as e:
                        print(f"Failed to import from {import_folder_path}: {e}")
                        continue
                    # 直到第一个导入成功就 Break
                    break

    if successful_import_count == 0:
        self.report({'ERROR'}, "当前工作空间没有成功导入任何模型，已跳过蓝图生成。")
        return

    # 保存工作空间级 Import.json 选择记录（使用新格式 key）
    save_import_json_path = os.path.join(GlobalConfig.path_workspace_folder(), "Import.json")
    JsonUtils.SaveToFile(json_dict=foldername_gametypename_dict, filepath=save_import_json_path)
    
    # 因为用户习惯了导入后就是全部选中的状态，所以默认选中所有导入的obj
    CollectionUtils.select_collection_objects(workspace_collection)

    # ==========================
    # 自动生成蓝图节点逻辑
    # ==========================
    try:
        # 创建蓝图，名称为当前工作空间名称
        tree_name = GlobalConfig.get_workspace_name()
        
        # Nico: 为了防止覆盖用户修改过的蓝图，始终创建新蓝图
        # 如果已存在同名蓝图，Blender会自动添加.001等后缀，从而保留旧蓝图
        try:
            tree = bpy.data.node_groups.new(name=tree_name, type='SSMTBlueprintTreeType')
        except Exception as e:
            print(f"Failed to create new node tree: {e}. Check if SSMTBlueprintTreeType is registered.")
            return
        tree.use_fake_user = True
        BlueprintExportHelper.set_tree_submesh_names(all_submesh_display_names, tree=tree)
        
        # 创建 Frame 框，包裹所有 Object Info 节点和 Group 节点
        frame = tree.nodes.new('NodeFrame')
        frame.label = "原始模型"
        frame.use_custom_color = True
        frame.color = (0.2, 0.35, 0.2)  # 深绿色调

        # 创建 Group 节点 (并在循环中连接)
        group_node = tree.nodes.new('SSMTNode_Object_Group')
        group_node.label = "Default Group"
        group_node.parent = frame
        
        # 3. 遍历导入的对象并创建对应节点
        current_x = 0
        current_y = 0
        y_gap = 200
        count = 0
        min_y = 0

        for new_submesh_name, (imported_obj, display_name) in foldername_imported_obj_dict.items():
            if imported_obj.type != 'MESH':
                continue

            # 通过 WorkSpaceModel 解析新格式名称获取 component 编号
            parsed = ws_model.parse_new_format_name(new_submesh_name)
            component_str = str(parsed["component"]) if parsed else "0"

            # 创建节点
            node = tree.nodes.new('SSMTNode_Object_Info')
            node.location = (current_x, current_y)
            node.parent = frame

            # 填充属性
            node.object_name = imported_obj.name
            node.original_object_name = imported_obj.name
            node.component = component_str
            node.submesh_name = display_name

            node.label = imported_obj.name

            # 如果 Group 最后一个插槽已被占用，手动扩展一个
            if group_node.inputs[-1].is_linked:
                group_node.inputs.new('SSMTSocketObject', f"Input {len(group_node.inputs) + 1}")

            tree.links.new(node.outputs[0], group_node.inputs[-1])

            count += 1
            current_y -= y_gap
            min_y = min(min_y, current_y)

        
        # 4. 放置 Group 和 Output 节点
        final_center_y = min_y / 2 if count <= 5 else -200

        group_node.location = (current_x + 400, final_center_y)

        output_node = tree.nodes.new('SSMTNode_Result_Output')
        output_node.location = (current_x + 800, final_center_y)
        output_node.label = "Generate Mod"
        
        # 连接 Group 到 Output
        if len(output_node.inputs) > 0 and len(group_node.outputs) > 0:
            tree.links.new(group_node.outputs[0], output_node.inputs[0])

        if hasattr(group_node, "update"):
            group_node.update()
        # 刷新 Frame 尺寸以包裹所有子节点
        if hasattr(frame, "update"):
            frame.update()

        BlueprintExportHelper.set_runtime_blueprint_tree(tree)

        global_properties = getattr(getattr(context, "scene", None), "global_properties", None)
        if global_properties:
            global_properties.selected_blueprint_name = tree.name

        print(f"Blueprint {tree_name} updated with imported objects.")
        
    except Exception as e:
        print(f"Error generating blueprint nodes: {e}")
        import traceback
        traceback.print_exc()
    


class SSMT4ImportAllFromCurrentWorkSpaceBlueprint(bpy.types.Operator):
    bl_idname = "ssmt4.import_all_from_workspace"
    bl_label = "一键导入SSMT工作空间内容"
    bl_description = "一键导入当前工作空间文件夹下所有的内容"
    bl_options = {'REGISTER','UNDO'}

    def execute(self, context):
        # print("Current WorkSpace: " + GlobalConfig.get_workspace_name())
        # print("Current Game: " + GlobalConfig.gamename)
        if GlobalConfig.get_workspace_name() == "":
            self.report({"ERROR"}, rpt_("请先在SSMT中选择当前工作空间后再导入。"))
        elif not os.path.exists(GlobalConfig.path_workspace_folder()):
            self.report({"ERROR"}, rpt_("工作空间文件夹不存在，请先在SSMT中创建工作空间: {path}").format(path=GlobalConfig.path_workspace_folder()))
        else:
            TimerUtils.Start("ImportFromWorkSpaceBlueprint")
            ImprotFromWorkSpaceFull(self, context)
            TimerUtils.End("ImportFromWorkSpaceBlueprint")
        
        return {'FINISHED'}
    

class SSMT4ImportRaw(bpy.types.Operator, ImportHelper):
    bl_idname = "ssmt4.import_raw"
    bl_label = "导入SSMT格式模型"
    bl_description = "导入SSMT格式的模型文件, 只需选择.json文件即可"
    bl_options = {'REGISTER','UNDO'}

    filter_glob: bpy.props.StringProperty(
        default='*.json',
        options={'HIDDEN'},
    ) # type: ignore

    files: bpy.props.CollectionProperty(
        name="File Path",
        type=bpy.types.OperatorFileListElement,
    ) # type: ignore

    def execute(self, context):
        # 我们需要添加到一个新建的集合里，方便后续操作
        # 这里集合的名称需要为当前文件夹的名称
        dirname = os.path.dirname(self.filepath)

        collection_name = os.path.basename(dirname)
        collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(collection)

        # 如果用户不选择任何json文件，则默认返回读取所有的json文件。
        import_filename_list = []
        if len(self.files) == 1:
            if str(self.filepath).endswith(".json"):
                import_filename_list.append(self.filepath)
            else:
                for filename in os.listdir(self.filepath):
                    if filename.endswith(".json"):
                        import_filename_list.append(filename)
        else:
            for json_file in self.files:
                import_filename_list.append(json_file.name)

        # 逐个json文件导入
        for json_file_name in import_filename_list:
            if os.path.isabs(json_file_name):
                json_file_path = json_file_name
            else:
                json_file_path = os.path.join(dirname, json_file_name)
            SSMTImportHelper.create_mesh_from_json(json_file_path=json_file_path, import_collection=collection)

        # Select all objects under collection (因为用户习惯了导入后就是全部选中的状态). 
        CollectionUtils.select_collection_objects(collection)

        return {'FINISHED'}

# =============================================================================
# 筛选导入逻辑 — 只导入指定的 submesh 文件夹列表
# =============================================================================
def _get_or_create_lod_collection(workspace_collection, lod_name):
    '''查找或创建 LOD 子集合（重用已有集合，避免重复创建）。'''
    if lod_name in workspace_collection.children:
        return workspace_collection.children[lod_name]
    # 检查 bpy.data.collections 中是否已存在
    if lod_name in bpy.data.collections:
        existing = bpy.data.collections[lod_name]
        # 如果已存在但尚未挂到 workspace 下，则链接
        if existing.name not in workspace_collection.children:
            workspace_collection.children.link(existing)
        return existing
    lod_collection = CollectionUtils.create_new_collection(
        collection_name=lod_name,
        color_tag=CollectionColor.Blue,
    )
    workspace_collection.children.link(lod_collection)
    return lod_collection


def _get_or_create_workspace_collection():
    '''查找或创建工作空间集合（重用已有集合，避免重复创建）。'''
    workspace_name = GlobalConfig.get_workspace_name()
    if workspace_name in bpy.data.collections:
        ws_coll = bpy.data.collections[workspace_name]
        # 确保链接到 scene
        if ws_coll.name not in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.link(ws_coll)
        return ws_coll
    return SSMTWorkSpace.create_and_get_workspace_collection()


def ImprotFromWorkSpaceSelected(self, context, submesh_lod_info_list, force_gametype_name=None):
    '''
    仅导入指定的 submesh 列表。
    submesh_lod_info_list: [(lod_name, submesh_folder_path), ...]
    例如: [("LOD0", r"D:\SSMTCacheFolder\WorkSpace\GF2\Default\LOD0\3ed2b2ba-2592-76086"), ...]
    force_gametype_name: 如果指定（如 "CPU_P12_N12_TA16_C16_T4_"），
      则强制所有 submesh 只尝试该数据类型（用于 DrawIB 统一类型场景）。
      传入 "__AUTO__" 表示：第一个 submesh 正常尝试所有类型，
      确定哪个类型可用，后续 submesh 全部使用同一类型。
    '''
    ws_model = WorkSpaceModel()
    workspace_collection = _get_or_create_workspace_collection()

    foldername_gametypename_dict = {}
    foldername_imported_obj_dict = {}
    all_submesh_display_names = []
    successful_import_count = 0

    # 当 force_gametype_name == "__AUTO__" 时，第一个成功后锁定该类型
    locked_gametype = None

    # 按 LOD 分组
    lod_submesh_map: dict[str, list[str]] = {}
    for lod_name, submesh_folder_path in submesh_lod_info_list:
        if lod_name not in lod_submesh_map:
            lod_submesh_map[lod_name] = []
        lod_submesh_map[lod_name].append(submesh_folder_path)

    for lod_name, submesh_folder_paths in lod_submesh_map.items():
        # 查找或创建 LOD 子集合（复用已有的）
        lod_collection = _get_or_create_lod_collection(workspace_collection, lod_name)

        for submesh_folder_path in submesh_folder_paths:
            submesh_folder_name = os.path.basename(submesh_folder_path)
            print("Re-Import FolderName: " + submesh_folder_name)

            # 通过 WorkSpaceModel 获取 Component 序号和新格式名称
            old_folder_draw_ib = submesh_folder_name.split("-")[0]
            comp_index = ws_model.get_component_index(lod_name, old_folder_draw_ib, submesh_folder_name)
            if comp_index < 0:
                comp_index = 0

            new_submesh_name = ws_model.get_new_submesh_name(lod_name, old_folder_draw_ib, comp_index)
            display_name = ws_model.get_display_name(lod_name, old_folder_draw_ib, comp_index)

            # 确定要尝试的数据类型文件夹列表
            if locked_gametype is not None:
                final_import_folder_path_list = [
                    os.path.join(submesh_folder_path, "TYPE_" + locked_gametype)
                ]
            elif force_gametype_name and force_gametype_name != "__AUTO__":
                final_import_folder_path_list = [
                    os.path.join(submesh_folder_path, "TYPE_" + force_gametype_name)
                ]
            else:
                final_import_folder_path_list = SSMTWorkSpace.get_ordered_gpu_cpu_import_folderpath_list(submesh_folder_path)
            print("Re-Import Folder Path List: " + str(final_import_folder_path_list))

            for import_folder_path in final_import_folder_path_list:
                if not os.path.isdir(import_folder_path):
                    print(f"数据类型文件夹不存在，跳过: {import_folder_path}")
                    continue
                gametype_name = import_folder_path.split("TYPE_")[1]

                try:
                    print("尝试导入路径: " + import_folder_path)

                    json_file_path = os.path.join(import_folder_path, submesh_folder_name + ".json")
                    imported_obj = SSMTImportHelper.create_mesh_from_json(
                        json_file_path=json_file_path,
                        import_collection=lod_collection,
                    )
                    if imported_obj is not None:
                        imported_obj.name = display_name
                        imported_obj.data.name = imported_obj.name
                        foldername_imported_obj_dict[new_submesh_name] = (imported_obj, display_name)
                        all_submesh_display_names.append(display_name)
                        successful_import_count += 1

                    foldername_gametypename_dict[new_submesh_name] = gametype_name
                    self.report({'INFO'}, "成功导入 " + new_submesh_name + " 的数据类型: " + gametype_name)

                    # 如果是 __AUTO__ 模式且第一次成功，锁定该类型供后续使用
                    if locked_gametype is None and force_gametype_name == "__AUTO__":
                        locked_gametype = gametype_name
                        self.report({'INFO'}, f"DrawIB 统一类型锁定为: {locked_gametype}，后续 submesh 全部使用此类型")
                except Exception as e:
                    print(f"Failed to re-import from {import_folder_path}: {e}")
                    continue
                break

    if successful_import_count == 0:
        self.report({'ERROR'}, "所选 submesh 没有成功导入任何模型。")
        return

    # 更新 Import.json（保留已有记录，覆盖本次导入的）
    save_import_json_path = os.path.join(GlobalConfig.path_workspace_folder(), "Import.json")
    existing_import_json = {}
    if os.path.exists(save_import_json_path):
        try:
            existing_import_json = JsonUtils.LoadFromFile(save_import_json_path) or {}
        except Exception:
            existing_import_json = {}
    existing_import_json.update(foldername_gametypename_dict)
    JsonUtils.SaveToFile(json_dict=existing_import_json, filepath=save_import_json_path)

    CollectionUtils.select_collection_objects(workspace_collection)

    # 生成蓝图
    _generate_blueprint_for_imported_objects(context, foldername_imported_obj_dict, all_submesh_display_names)


def _generate_blueprint_for_imported_objects(context, foldername_imported_obj_dict, all_submesh_display_names):
    '''更新已存在的蓝图节点（不新建），若没有已有蓝图则跳过。'''
    tree_name = GlobalConfig.get_workspace_name()
    if not tree_name:
        return

    # 查找已有蓝图，不存在则跳过
    tree = bpy.data.node_groups.get(tree_name)
    if not tree:
        print(f"未找到已有蓝图 '{tree_name}'，跳过蓝图更新")
        return
    if not BlueprintExportHelper._is_valid_blueprint_tree(tree):
        print(f"已有节点组 '{tree_name}' 不是有效的 SSMT 蓝图，跳过")
        return

    try:
        # 清空所有节点和连接
        tree.nodes.clear()

        tree.use_fake_user = True
        BlueprintExportHelper.set_tree_submesh_names(all_submesh_display_names, tree=tree)

        # 创建 Frame 框，包裹所有 Object Info 节点和 Group 节点
        frame = tree.nodes.new('NodeFrame')
        frame.label = "原始模型"
        frame.use_custom_color = True
        frame.color = (0.2, 0.35, 0.2)  # 深绿色调

        group_node = tree.nodes.new('SSMTNode_Object_Group')
        group_node.label = "Default Group"
        group_node.parent = frame

        current_x = 0
        current_y = 0
        y_gap = 200
        count = 0
        min_y = 0

        ws_model = WorkSpaceModel()

        for new_submesh_name, (imported_obj, display_name) in foldername_imported_obj_dict.items():
            if imported_obj.type != 'MESH':
                continue

            # 通过 WorkSpaceModel 解析新格式名称获取 component 编号
            parsed = ws_model.parse_new_format_name(new_submesh_name)
            component_str = str(parsed["component"]) if parsed else "0"

            node = tree.nodes.new('SSMTNode_Object_Info')
            node.location = (current_x, current_y)
            node.parent = frame

            node.object_name = imported_obj.name
            node.original_object_name = imported_obj.name
            node.component = component_str
            node.submesh_name = display_name

            node.label = imported_obj.name

            if group_node.inputs[-1].is_linked:
                group_node.inputs.new('SSMTSocketObject', f"Input {len(group_node.inputs) + 1}")

            tree.links.new(node.outputs[0], group_node.inputs[-1])

            count += 1
            current_y -= y_gap
            min_y = min(min_y, current_y)

        final_center_y = min_y / 2 if count <= 5 else -200
        group_node.location = (current_x + 400, final_center_y)

        output_node = tree.nodes.new('SSMTNode_Result_Output')
        output_node.location = (current_x + 800, final_center_y)
        output_node.label = "Generate Mod"

        if len(output_node.inputs) > 0 and len(group_node.outputs) > 0:
            tree.links.new(group_node.outputs[0], output_node.inputs[0])

        if hasattr(group_node, "update"):
            group_node.update()
        if hasattr(frame, "update"):
            frame.update()

        BlueprintExportHelper.set_runtime_blueprint_tree(tree)

        global_properties = getattr(getattr(context, "scene", None), "global_properties", None)
        if global_properties:
            global_properties.selected_blueprint_name = tree.name

        print(f"Blueprint {tree_name} updated with imported objects.")
    except Exception as e:
        print(f"Error updating blueprint nodes: {e}")
        import traceback
        traceback.print_exc()


# =============================================================================
# 工具函数 — 删除物体
# =============================================================================
def _delete_objects(obj_names_to_delete: list[str]):
    '''删除 Blender 场景中指定名称列表的所有物体。'''
    for obj_name in obj_names_to_delete:
        if obj_name in bpy.data.objects:
            obj = bpy.data.objects[obj_name]
            # 从所有集合中移除
            for coll in list(obj.users_collection):
                coll.objects.unlink(obj)
            bpy.data.objects.remove(obj, do_unlink=True)


def _count_type_folders(submesh_folder_path: str) -> int:
    '''统计 submesh 文件夹下 TYPE_ 开头的文件夹数量。'''
    count = 0
    if not os.path.isdir(submesh_folder_path):
        return 0
    for entry in os.scandir(submesh_folder_path):
        if entry.is_dir() and entry.name.startswith("TYPE_"):
            count += 1
    return count


def _show_last_type_warning(submesh_folder_name: str):
    '''弹出警告对话框：该 submesh 只剩下最后一个数据类型，无法删除。'''
    def draw_popup(self, context):
        self.layout.label(
            text=f"Submesh '{submesh_folder_name}' 只剩下最后一个数据类型文件夹，"
        )
        self.layout.label(
            text="无法删除该类型。如果没有正确数据类型，请联系SSMT开发者添加。"
        )
    bpy.context.window_manager.popup_menu(draw_popup, title="警告", icon='ERROR')


# =============================================================================
# Operator — 该DrawIB数据类型不正确
# =============================================================================
class SSMT4FixDrawIBDataType(bpy.types.Operator):
    bl_idname = "ssmt4.fix_drawib_datatype"
    bl_label = "修复DrawIB数据类型"
    bl_description = "该DrawIB数据类型不正确：删除该DrawIB下所有对应数据类型的文件夹，删除相关Mesh，并重新导入"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_objects = context.selected_objects
        if not selected_objects:
            self.report({'ERROR'}, "请先选中一个或多个物体")
            return {'CANCELLED'}

        from ..workspace.ssmt_workspace import SSMTWorkSpace

        workspace_folder = GlobalConfig.path_workspace_folder()
        if not workspace_folder or not os.path.exists(workspace_folder):
            self.report({'ERROR'}, "工作空间文件夹不存在，请先设置工作空间")
            return {'CANCELLED'}

        ws_model = WorkSpaceModel()

        # 1. 解析每个选中物体，收集 {lod_name: set_of_drawib}
        lod_drawib_set: dict[str, set[str]] = {}
        # 同时记录要删除的物体名称
        all_obj_info = []  # [(obj_name, lod_name, submesh_folder_name, draw_ib, gametypename)]
        for obj in selected_objects:
            gametypename = obj.get("3DMigoto:GameTypeName", "")
            if not gametypename:
                self.report({'WARNING'}, f"物体 '{obj.name}' 没有数据类型属性，已跳过")
                continue

            parsed = ws_model.parse_any_format_name(obj.name)
            if not parsed or not parsed["lod"] or not parsed["draw_ib"]:
                self.report({'WARNING'}, f"无法解析物体 '{obj.name}' 的名称，已跳过")
                continue

            submesh_folder_path = ws_model.get_folder_path(parsed["lod"], parsed["draw_ib"], parsed["component"])
            submesh_folder_name = os.path.basename(submesh_folder_path) if submesh_folder_path else ""

            all_obj_info.append((obj.name, parsed["lod"], submesh_folder_name, parsed["draw_ib"], gametypename))
            if parsed["lod"] not in lod_drawib_set:
                lod_drawib_set[parsed["lod"]] = set()
            lod_drawib_set[parsed["lod"]].add(parsed["draw_ib"])

        if not all_obj_info:
            self.report({'ERROR'}, "未能从选中物体中解析出任何有效信息")
            return {'CANCELLED'}

        # 2. 预检：收集该 DrawIB 下所有 submesh 文件夹
        all_submesh_entries: list[tuple[str, str, str]] = []  # [(lod_name, submesh_folder_name, submesh_folder_path)]
        for lod_name, draw_ib_set in lod_drawib_set.items():
            lod_folder_path = os.path.join(workspace_folder, lod_name)
            if not os.path.isdir(lod_folder_path):
                self.report({'WARNING'}, f"LOD 目录不存在: {lod_folder_path}")
                continue
            for entry in os.scandir(lod_folder_path):
                if not entry.is_dir():
                    continue
                folder_draw_ib = entry.name.split("-")[0]
                if folder_draw_ib in draw_ib_set:
                    all_submesh_entries.append((lod_name, entry.name, entry.path))

        if not all_submesh_entries:
            self.report({'ERROR'}, "没有找到对应的 submesh 文件夹")
            return {'CANCELLED'}

        # 3. 预检：检查是否有 submesh 只剩最后一个数据类型
        for lod_name, submesh_folder_name, submesh_folder_path in all_submesh_entries:
            for _, o_lod, o_submesh, o_draw_ib, gametypename in all_obj_info:
                type_folder_path = os.path.join(submesh_folder_path, "TYPE_" + gametypename)
                if os.path.exists(type_folder_path) and _count_type_folders(submesh_folder_path) <= 1:
                    _show_last_type_warning(submesh_folder_name=submesh_folder_name)
                    self.report({'WARNING'}, f"Submesh '{submesh_folder_name}' 只剩下最后一个数据类型，已中止操作")
                    return {'CANCELLED'}

        # 4. 执行删除：删除 TYPE 文件夹
        for lod_name, submesh_folder_name, submesh_folder_path in all_submesh_entries:
            for _, o_lod, o_submesh, o_draw_ib, gametypename in all_obj_info:
                if o_lod != lod_name:
                    continue
                type_folder_path = os.path.join(submesh_folder_path, "TYPE_" + gametypename)
                if os.path.exists(type_folder_path):
                    shutil.rmtree(type_folder_path)
                    self.report({'INFO'}, f"已删除数据类型文件夹: {type_folder_path}")

        # 5. 收集需要删除的物体名称（当前工作空间集合中所有属于该 DrawIB 的物体）
        submesh_to_reimport = [(ln, fp) for ln, _, fp in all_submesh_entries]
        all_obj_to_delete: list[str] = []
        workspace_collection_name = GlobalConfig.get_workspace_name()
        if workspace_collection_name in bpy.data.collections:
            ws_coll = bpy.data.collections[workspace_collection_name]
            for obj in ws_coll.all_objects:
                if obj.type != 'MESH':
                    continue
                parsed = ws_model.parse_any_format_name(obj.name)
                if not parsed or not parsed["draw_ib"]:
                    continue
                for _, draw_ib_set in lod_drawib_set.items():
                    if parsed["draw_ib"] in draw_ib_set:
                        all_obj_to_delete.append(obj.name)
                        break

        # 去重
        all_obj_to_delete = list(dict.fromkeys(all_obj_to_delete))
        submesh_to_reimport = list(dict.fromkeys(submesh_to_reimport))

        # 6. 删除物体
        if all_obj_to_delete:
            _delete_objects(all_obj_to_delete)
            self.report({'INFO'}, f"已删除 {len(all_obj_to_delete)} 个物体")

        # 5. 重新导入（DrawIB 模式：自动统一类型，所有 submesh 使用同一数据类型）
        if submesh_to_reimport:
            ImprotFromWorkSpaceSelected(self, context, submesh_to_reimport, force_gametype_name="__AUTO__")
            self.report({'INFO'}, f"已重新导入 {len(submesh_to_reimport)} 个 submesh（DrawIB 统一类型）")
        else:
            self.report({'WARNING'}, "没有找到需要重新导入的 submesh")

        return {'FINISHED'}


# =============================================================================
# Operator — 该Submesh数据类型不正确
# =============================================================================
class SSMT4FixSubmeshDataType(bpy.types.Operator):
    bl_idname = "ssmt4.fix_submesh_datatype"
    bl_label = "修复Submesh数据类型"
    bl_description = "该Submesh数据类型不正确：删除对应数据类型的文件夹，删除该Mesh，并重新导入"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        selected_objects = context.selected_objects
        if not selected_objects:
            self.report({'ERROR'}, "请先选中一个或多个物体")
            return {'CANCELLED'}

        from ..workspace.ssmt_workspace import SSMTWorkSpace

        workspace_folder = GlobalConfig.path_workspace_folder()
        if not workspace_folder or not os.path.exists(workspace_folder):
            self.report({'ERROR'}, "工作空间文件夹不存在，请先设置工作空间")
            return {'CANCELLED'}

        ws_model = WorkSpaceModel()

        # 1. 解析每个选中物体，并预检
        submesh_entries: list[tuple[str, str, str, str]] = []  # [(obj_name, lod_name, submesh_folder_path, gametypename)]

        for obj in selected_objects:
            gametypename = obj.get("3DMigoto:GameTypeName", "")
            if not gametypename:
                self.report({'WARNING'}, f"物体 '{obj.name}' 没有数据类型属性，已跳过")
                continue

            parsed = ws_model.parse_any_format_name(obj.name)
            if not parsed or not parsed["lod"] or not parsed["draw_ib"]:
                self.report({'WARNING'}, f"无法解析物体 '{obj.name}' 的名称，已跳过")
                continue

            submesh_folder_path = ws_model.get_folder_path(parsed["lod"], parsed["draw_ib"], parsed["component"])
            if not submesh_folder_path or not os.path.isdir(submesh_folder_path):
                self.report({'WARNING'}, f"找不到物体 '{obj.name}' 对应的 submesh 文件夹，已跳过")
                continue

            submesh_entries.append((obj.name, parsed["lod"], submesh_folder_path, gametypename))

        if not submesh_entries:
            self.report({'ERROR'}, "未能从选中物体中解析出任何有效信息")
            return {'CANCELLED'}

        # 2. 预检：检查是否有 submesh 只剩最后一个数据类型
        for obj_name, lod_name, submesh_folder_path, gametypename in submesh_entries:
            type_folder_path = os.path.join(submesh_folder_path, "TYPE_" + gametypename)
            if os.path.exists(type_folder_path) and _count_type_folders(submesh_folder_path) <= 1:
                submesh_folder_name = os.path.basename(submesh_folder_path)
                _show_last_type_warning(submesh_folder_name=submesh_folder_name)
                self.report({'WARNING'}, f"Submesh '{submesh_folder_name}' 只剩下最后一个数据类型，已中止操作")
                return {'CANCELLED'}

        # 3. 执行删除：删除 TYPE 文件夹
        submesh_to_reimport: list[tuple[str, str]] = []
        obj_names_to_delete: list[str] = []

        for obj_name, lod_name, submesh_folder_path, gametypename in submesh_entries:
            type_folder_path = os.path.join(submesh_folder_path, "TYPE_" + gametypename)
            if os.path.exists(type_folder_path):
                shutil.rmtree(type_folder_path)
                self.report({'INFO'}, f"已删除数据类型文件夹: {type_folder_path}")

            submesh_to_reimport.append((lod_name, submesh_folder_path))
            obj_names_to_delete.append(obj_name)

        if not submesh_to_reimport:
            self.report({'ERROR'}, "没有找到需要处理的 submesh")
            return {'CANCELLED'}

        # 4. 删除物体
        if obj_names_to_delete:
            _delete_objects(obj_names_to_delete)
            self.report({'INFO'}, f"已删除 {len(obj_names_to_delete)} 个物体")

        # 4. 重新导入
        ImprotFromWorkSpaceSelected(self, context, submesh_to_reimport)
        self.report({'INFO'}, f"已重新导入 {len(submesh_to_reimport)} 个 submesh")

        return {'FINISHED'}


def register():
    bpy.utils.register_class(SSMT4ImportRaw)
    bpy.utils.register_class(SSMT4ImportAllFromCurrentWorkSpaceBlueprint)
    bpy.utils.register_class(SSMT4FixDrawIBDataType)
    bpy.utils.register_class(SSMT4FixSubmeshDataType)


def unregister():
    bpy.utils.unregister_class(SSMT4ImportRaw)
    bpy.utils.unregister_class(SSMT4ImportAllFromCurrentWorkSpaceBlueprint)
    bpy.utils.unregister_class(SSMT4FixDrawIBDataType)
    bpy.utils.unregister_class(SSMT4FixSubmeshDataType)
