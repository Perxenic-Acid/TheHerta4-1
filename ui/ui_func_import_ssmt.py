
'''
导入模型配置面板
'''
import os
import bpy

# 用于解决 AttributeError: 'IMPORT_MESH_OT_migoto_raw_buffers_mmt' object has no attribute 'filepath'
from bpy_extras.io_utils import ImportHelper

from ..utils.json_utils import JsonUtils
from ..utils.collection_utils import CollectionUtils, CollectionColor
from ..utils.timer_utils import TimerUtils
from ..utils.translate_utils import rpt_

from ..common.global_config import GlobalConfig
from ..common.ssmt_import_helper import SSMTImportHelper
from ..workspace.ssmt_workspace import SSMTWorkSpace
from ..blueprint.blueprint_export_helper import BlueprintExportHelper


# 全量导入逻辑
def ImprotFromWorkSpaceFull(self, context):
    
    # 这里先创建以当前工作空间为名称的集合，并且链接到scene，确保它存在
    workspace_collection = SSMTWorkSpace.create_and_get_workspace_collection()

    # 获取当前工作空间下的所有 LOD 目录及其 submesh 子目录
    lod_submesh_dict = SSMTWorkSpace.get_lod_submesh_folderpath_dict()

    if not lod_submesh_dict:
        self.report({'ERROR'}, "当前工作空间未找到任何 LOD 目录（LOD0、LOD1…），请检查工作空间结构。")
        return

    # 读取时保存每个导入文件夹里导入的 GameType 名称到工作空间根目录的 Import.json
    # 生成 Mod 时会用它来确定应该进入哪个 TYPE_xxx 目录读取 SubmeshJson
    # key: LOD 前缀的 submesh_name（如 "LOD0.67f829fc-2653-0"）, value: gametype_name
    foldername_gametypename_dict = {}
    foldername_imported_obj_dict = {}
    all_submesh_display_names = []
    successful_import_count = 0

    for lod_name, submesh_folder_paths in lod_submesh_dict.items():
        # 为每个 LOD 创建蓝色子集合，挂在工作空间集合下面
        lod_collection = CollectionUtils.create_new_collection(
            collection_name=lod_name,
            color_tag=CollectionColor.Blue,
        )
        workspace_collection.children.link(lod_collection)

        # 读取该 LOD 目录下的 Config.json 里的 DrawIB -> 别名映射
        lod_folder_path = os.path.join(GlobalConfig.path_workspace_folder(), lod_name)
        drawib_aliasname_dict = SSMTWorkSpace.get_drawib_aliasname_dict_for_path(lod_folder_path)

        for submesh_folder_path in submesh_folder_paths:
            submesh_folder_name = os.path.basename(submesh_folder_path)
            # 带 LOD 前缀的唯一标识，如 "LOD0.67f829fc-2653-0"
            lod_prefixed_name = lod_name + "." + submesh_folder_name
            print("Import FolderName: " + lod_prefixed_name)

            # 获取导入的数据类型文件夹路径列表
            final_import_folder_path_list = SSMTWorkSpace.get_ordered_gpu_cpu_import_folderpath_list(submesh_folder_path)
            print("Final Import Folder Path List: " + str(final_import_folder_path_list))

            # 接下来开始导入，尝试对当前DrawIB的每个数据类型都进行导入
            for import_folder_path in final_import_folder_path_list:
                gametype_name = import_folder_path.split("TYPE_")[1]

                try:
                    print("尝试导入路径: " + import_folder_path)
                    # 构造显示名称，带 LOD 前缀
                    bare_display_name = SSMTWorkSpace.get_display_submesh_name(
                        submesh_folder_name,
                        drawib_aliasname_dict=drawib_aliasname_dict,
                    )
                    object_display_name = lod_name + "." + bare_display_name

                    json_file_path = os.path.join(import_folder_path, submesh_folder_name + ".json")
                    imported_obj = SSMTImportHelper.create_mesh_from_json(
                        json_file_path=json_file_path,
                        import_collection=lod_collection,
                    )
                    if imported_obj is not None:
                        imported_obj.name = object_display_name
                        imported_obj.data.name = imported_obj.name
                        foldername_imported_obj_dict[lod_prefixed_name] = imported_obj
                        all_submesh_display_names.append(object_display_name)
                        successful_import_count += 1

                    foldername_gametypename_dict[lod_prefixed_name] = gametype_name
                    self.report({'INFO'}, "成功导入 " + lod_prefixed_name + " 的数据类型: " + gametype_name)
                except Exception as e:
                    print(f"Failed to import from {import_folder_path}: {e}")
                    continue
                # 直到第一个导入成功就 Break
                break

    if successful_import_count == 0:
        self.report({'ERROR'}, "当前工作空间没有成功导入任何模型，已跳过蓝图生成。")
        return

    # 保存工作空间级 Import.json 选择记录（key 带 LOD 前缀）
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
        
        # 创建 Group 节点 (并在循环中连接)
        group_node = tree.nodes.new('SSMTNode_Object_Group')
        group_node.label = "Default Group"
        
        # 3. 遍历导入的对象并创建对应节点
        current_x = 0
        current_y = 0
        y_gap = 200
        count = 0
        min_y = 0

        for lod_prefixed_name, imported_obj in foldername_imported_obj_dict.items():
            if imported_obj.type != 'MESH':
                continue

            # 解析裸 submesh_name 用于获取 component 编号
            _, bare_submesh_name = SSMTWorkSpace.parse_lod_submesh_name(lod_prefixed_name)
            namesplits = bare_submesh_name.split('-')

            # 创建节点
            node = tree.nodes.new('SSMTNode_Object_Info')
            node.location = (current_x, current_y)

            # 填充属性
            node.object_name = imported_obj.name
            node.original_object_name = imported_obj.name

            if len(namesplits) >= 2:
                node.component = namesplits[1]
            else:
                node.component = "1"

            node.submesh_name = imported_obj.name  # 已带 LOD 前缀

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

def register():
    bpy.utils.register_class(SSMT4ImportRaw)
    bpy.utils.register_class(SSMT4ImportAllFromCurrentWorkSpaceBlueprint)


def unregister():
    bpy.utils.unregister_class(SSMT4ImportRaw)
    bpy.utils.unregister_class(SSMT4ImportAllFromCurrentWorkSpaceBlueprint)
