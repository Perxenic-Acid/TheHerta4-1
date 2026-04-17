import os
import time
import uuid

import bpy
from bpy.types import NodeTree, Node, NodeSocket
from bpy_extras.io_utils import ImportHelper

from ..common.logic_name import LogicName
from ..common.global_config import GlobalConfig
from ..common.global_properties import GlobalProterties
from .blueprint_export_helper import BlueprintExportHelper
from .blueprint_node_base import SSMTBlueprintTree, SSMTNodeBase

BLENDER_VERSION = bpy.app.version[:2]
OBJECT_PERSISTENT_ID_KEY = "_ssmt_object_uuid"

_picking_node_name = None
_picking_tree_name = None
_is_viewing_group_objects = False


def _is_duplicate_object_persistent_id(target_obj, object_id):
    if not target_obj or not object_id:
        return False

    for obj in bpy.data.objects:
        if obj == target_obj:
            continue
        if str(obj.get(OBJECT_PERSISTENT_ID_KEY, "") or "") == object_id:
            return True
    return False


def ensure_object_persistent_id(obj):
    """
    获取或创建 Blender 物体的持久 UUID。

    注意：这个函数只能在允许写数据块的上下文里调用，
    不能在节点 draw 过程中直接调用。
    """
    if obj is None:
        return ""

    object_id = str(obj.get(OBJECT_PERSISTENT_ID_KEY, "") or "")
    if not object_id or _is_duplicate_object_persistent_id(obj, object_id):
        object_id = uuid.uuid4().hex
        obj[OBJECT_PERSISTENT_ID_KEY] = object_id
    return object_id


def find_object_by_persistent_id(object_id):
    if not object_id:
        return None

    for obj in bpy.data.objects:
        if str(obj.get(OBJECT_PERSISTENT_ID_KEY, "") or "") == str(object_id):
            return obj
    return None


def resolve_object_info_node_target(node, allow_name_fallback=True):
    if not node or getattr(node, "bl_idname", "") != 'SSMTNode_Object_Info':
        return None

    resolved_obj = None
    node_object_name = str(getattr(node, "object_name", "") or "")
    node_object_id = str(getattr(node, "object_id", "") or "")

    if allow_name_fallback and node_object_name:
        resolved_obj = bpy.data.objects.get(node_object_name)

    if resolved_obj is None and node_object_id:
        resolved_obj = find_object_by_persistent_id(node_object_id)

    return resolved_obj


def refresh_object_info_node(node, allow_name_fallback=True):
    """
    刷新单个 Object Info 节点。

    写入行为只放在安全时机里调用：
    1. 选择物体后。
    2. 用户手动执行“刷新物体节点信息”。
    3. 生成 Mod 前。
    4. 节点被点击后通过 timer 延迟调度，而不是在 draw 中直接写入。
    """
    result = {
        "found": False,
        "changed": False,
        "object": None,
        "elapsed_ms": 0.0,
    }

    start_time = time.perf_counter()

    resolved_obj = resolve_object_info_node_target(node, allow_name_fallback=allow_name_fallback)
    if resolved_obj is None:
        result["elapsed_ms"] = (time.perf_counter() - start_time) * 1000.0
        return result

    result["found"] = True
    result["object"] = resolved_obj

    persistent_id = ensure_object_persistent_id(resolved_obj)
    if str(getattr(node, "object_id", "") or "") != persistent_id:
        node.object_id = persistent_id
        result["changed"] = True

    if str(getattr(node, "object_name", "") or "") != resolved_obj.name:
        node.object_name = resolved_obj.name
        result["changed"] = True

    result["elapsed_ms"] = (time.perf_counter() - start_time) * 1000.0

    return result


def refresh_all_object_info_nodes(context=None, tree=None, include_all_blueprints=False, source="unknown"):
    """
    刷新蓝图中的所有 Object Info 节点。

    导出前必须调一次，保证节点中的 object_name 能跟随 UUID 回写为最新名称。
    """
    checked_count = 0
    updated_count = 0
    missing_count = 0
    start_time = time.perf_counter()

    trees = []
    if include_all_blueprints:
        trees = [node_group for node_group in bpy.data.node_groups if getattr(node_group, "bl_idname", "") == 'SSMTBlueprintTreeType']
    else:
        tree = tree or BlueprintExportHelper.get_current_blueprint_tree(context=context)
        if tree:
            trees = [tree]

    for blueprint_tree in trees:
        for node in blueprint_tree.nodes:
            if getattr(node, "bl_idname", "") != 'SSMTNode_Object_Info':
                continue

            checked_count += 1
            refresh_result = refresh_object_info_node(node, allow_name_fallback=True)

            if refresh_result["changed"]:
                updated_count += 1

            has_reference = bool(str(getattr(node, "object_name", "") or "") or str(getattr(node, "object_id", "") or ""))
            if has_reference and not refresh_result["found"]:
                missing_count += 1

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    summary = {
        "checked_count": checked_count,
        "updated_count": updated_count,
        "missing_count": missing_count,
        "elapsed_ms": elapsed_ms,
        "source": source,
    }

    print(
        f"[ObjectInfoRefresh:{source}] checked={checked_count}, updated={updated_count}, "
        f"missing={missing_count}, elapsed={elapsed_ms:.3f} ms"
    )

    return summary


class SSMT_OT_RefreshNodeObjectIDs(bpy.types.Operator):
    '''刷新蓝图中所有物体节点的对象引用信息'''
    bl_idname = "ssmt.refresh_node_object_ids"
    bl_label = "刷新物体节点信息"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        refresh_summary = refresh_all_object_info_nodes(include_all_blueprints=True, source="manual")

        if refresh_summary["missing_count"] > 0:
            self.report({'WARNING'}, f"已刷新 {refresh_summary['updated_count']} 个物体节点，另有 {refresh_summary['missing_count']} 个节点未找到对应物体，耗时 {refresh_summary['elapsed_ms']:.3f} ms")
        elif refresh_summary["updated_count"] > 0:
            self.report({'INFO'}, f"已刷新 {refresh_summary['updated_count']} 个物体节点，耗时 {refresh_summary['elapsed_ms']:.3f} ms")
        else:
            self.report({'INFO'}, f"所有物体节点都已是最新状态，耗时 {refresh_summary['elapsed_ms']:.3f} ms")
        
        return {'FINISHED'}


class SSMT_OT_SelectNodeObject(bpy.types.Operator):
    '''Select this object in 3D View'''
    bl_idname = "ssmt.select_node_object"
    bl_label = "Select Object"
    
    object_name: bpy.props.StringProperty() # type: ignore
    object_id: bpy.props.StringProperty() # type: ignore

    def execute(self, context):
        obj = None
        if self.object_name:
            obj = bpy.data.objects.get(self.object_name)
        if obj is None and self.object_id:
            obj = find_object_by_persistent_id(self.object_id)

        if not obj:
            return {'CANCELLED'}

        if obj:
            try:
                bpy.ops.object.select_all(action='DESELECT')
            except:
                pass
                
            obj.select_set(True)
            context.view_layer.objects.active = obj
            self.report({'INFO'}, f"Selected: {obj.name}")
        else:
            self.report({'WARNING'}, "Object not found")
        
        return {'FINISHED'}


class SSMT_OT_StartPickObject(bpy.types.Operator):
    '''Start picking an object from 3D View'''
    bl_idname = "ssmt.start_pick_object"
    bl_label = "Pick Object"
    bl_description = "点击后在3D视图中选择一个物体"
    
    node_name: bpy.props.StringProperty() # type: ignore
    
    def execute(self, context):
        global _picking_node_name, _picking_tree_name
        
        tree = getattr(context.space_data, "edit_tree", None) or getattr(context.space_data, "node_tree", None)
        
        if not tree:
            self.report({'WARNING'}, "无法获取节点树上下文")
            return {'CANCELLED'}
        
        _picking_node_name = self.node_name
        _picking_tree_name = tree.name
        self.report({'INFO'}, "请在3D视图中点击选择一个物体")
        
        bpy.ops.ssmt.pick_object_modal('INVOKE_DEFAULT')
        
        return {'FINISHED'}


class SSMT_OT_PickObjectModal(bpy.types.Operator):
    '''Modal operator for picking objects in 3D View'''
    bl_idname = "ssmt.pick_object_modal"
    bl_label = "Pick Object"
    bl_options = {'REGISTER', 'INTERNAL'}
    
    def invoke(self, context, event):
        global _picking_node_name
        
        if not _picking_node_name:
            return {'CANCELLED'}
        
        self._initial_selected_objs = set(context.selected_objects)
        if context.selected_objects:
            self._last_selected_obj = context.selected_objects[0]
        else:
            self._last_selected_obj = None
        
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
    
    def modal(self, context, event):
        global _picking_node_name, _picking_tree_name
        
        if event.type == 'ESC':
            _picking_node_name = None
            _picking_tree_name = None
            return {'CANCELLED'}
        
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                    if region and area.x <= event.mouse_x <= area.x + area.width and area.y <= event.mouse_y <= area.y + area.height:
                        return {'PASS_THROUGH'}
        
        if event.type == 'MOUSEMOVE':
            current_selected = context.selected_objects
            if current_selected:
                current_obj = current_selected[0]
                if current_obj != self._last_selected_obj and current_obj not in self._initial_selected_objs:
                    tree = bpy.data.node_groups.get(_picking_tree_name)
                    if tree:
                        node = tree.nodes.get(_picking_node_name)
                        if node:
                            node.object_name = current_obj.name
                            node.object_id = ensure_object_persistent_id(current_obj)
                            self.report({'INFO'}, f"已选择物体: {current_obj.name}")
                    
                    _picking_node_name = None
                    _picking_tree_name = None
                    return {'FINISHED'}
        
        return {'PASS_THROUGH'}


def draw_view3d_header(self, context):
    global _picking_node_name
    if _picking_node_name:
        self.layout.label(text="请在3D视图中点击选择一个物体...", icon='EYEDROPPER')


class SSMTNode_Object_Info(SSMTNodeBase):
    '''Object Info Node'''
    bl_idname = 'SSMTNode_Object_Info'
    bl_label = 'Object Info'
    bl_icon = 'OBJECT_DATAMODE'
    bl_width_min = 300

    def _refresh_display_fields(self):
        self.draw_ib = ""
        self.index_count = ""
        self.first_index = ""
        self.alias_name = ""

        if self.object_name:
            self.label = self.object_name
            if "-" in self.object_name:
                obj_name_total_split = self.object_name.split(".")
                obj_name_split = obj_name_total_split[0].split("-")

                if len(obj_name_split) >= 3:
                    self.draw_ib = obj_name_split[0]
                    self.index_count = obj_name_split[1]
                    self.first_index = obj_name_split[2]

                if len(obj_name_total_split) >= 2:
                    self.alias_name = ".".join(obj_name_total_split[1:])
        else:
            self.label = "Object Info"

        self.update_node_width([self.object_name, self.draw_ib, self.index_count, self.first_index, self.alias_name])

    def update_object_name(self, context):
        self._refresh_display_fields()

        if self.object_name:
            obj = bpy.data.objects.get(self.object_name)
            if obj:
                self.object_id = ensure_object_persistent_id(obj)
        else:
            self.object_id = ""

    object_name: bpy.props.StringProperty(name="Object Name", default="", update=update_object_name) #type: ignore
    object_id: bpy.props.StringProperty(name="Object ID", default="") #type: ignore
    original_object_name: bpy.props.StringProperty(name="Original Object Name", default="") #type: ignore


    draw_ib: bpy.props.StringProperty(name="DrawIB", default="") # type: ignore
    index_count: bpy.props.StringProperty(name="IndexCount", default="") # type: ignore
    first_index: bpy.props.StringProperty(name="FirstIndex", default="") # type: ignore
    alias_name: bpy.props.StringProperty(name="Alias Name", default="") # type: ignore

    def init(self, context):
        self.outputs.new('SSMTSocketObject', "Object")

    def draw_buttons(self, context, layout):
        row = layout.row(align=True)

        row.prop_search(self, "object_name", bpy.data, "objects", text="", icon='OBJECT_DATA')
        
        op = row.operator("ssmt.start_pick_object", text="", icon='EYEDROPPER')
        op.node_name = self.name

        if self.object_name or self.object_id:
            op = row.operator("ssmt.select_node_object", text="", icon='RESTRICT_SELECT_OFF')
            op.object_name = self.object_name
            op.object_id = self.object_id

        # Display as read-only labels to prevent user edits in the UI
        layout.label(text=f"DrawIB: {self.draw_ib}")
        layout.label(text=f"IndexCount: {self.index_count}")
        layout.label(text=f"FirstIndex: {self.first_index}")
        layout.label(text=f"Alias Name: {self.alias_name}")


class SSMTNode_Object_Group(SSMTNodeBase):
    '''单纯用于分组的节点，可以接受任何节点作为输入，放在一个组里'''
    bl_idname = 'SSMTNode_Object_Group'
    bl_label = 'Group'
    bl_icon = 'GROUP'

    def init(self, context):
        self.inputs.new('SSMTSocketObject', "Input 1")
        self.outputs.new('SSMTSocketObject', "Output")
        self.width = 200

    def draw_buttons(self, context, layout):
        layout.operator("ssmt.view_group_objects", text="查看递归解析预览", icon='HIDE_OFF').node_name = self.name

    def update(self):
        if self.inputs and self.inputs[-1].is_linked:
            self.inputs.new('SSMTSocketObject', f"Input {len(self.inputs) + 1}")
        
        if len(self.inputs) > 1 and not self.inputs[-1].is_linked and not self.inputs[-2].is_linked:
             self.inputs.remove(self.inputs[-1])




class SSMT_OT_SwitchKey_AddSocket(bpy.types.Operator):
    '''Add a new socket to the switch node'''
    bl_idname = "ssmt.switch_add_socket"
    bl_label = "Add Socket"
    
    node_name: bpy.props.StringProperty() # type: ignore

    def execute(self, context):
        tree = getattr(context.space_data, "edit_tree", None) or getattr(context.space_data, "node_tree", None)
        if not tree:
             return {'CANCELLED'}
        node = tree.nodes.get(self.node_name)
        if node:
             node.inputs.new('SSMTSocketObject', f"Status {len(node.inputs)}")
        return {'FINISHED'}


class SSMT_OT_SwitchKey_RemoveSocket(bpy.types.Operator):
    '''Remove the last socket from the switch node'''
    bl_idname = "ssmt.switch_remove_socket"
    bl_label = "Remove Socket"
    
    node_name: bpy.props.StringProperty() # type: ignore

    def execute(self, context):
        tree = getattr(context.space_data, "edit_tree", None) or getattr(context.space_data, "node_tree", None)
        if not tree:
             return {'CANCELLED'}
        node = tree.nodes.get(self.node_name)
        if node and len(node.inputs) > 0:
            node.inputs.remove(node.inputs[-1])
        return {'FINISHED'}


class SSMTNode_SwitchKey(SSMTNodeBase):
    '''【按键切换】会把每个连入的分支分配到单独的变量'''
    bl_idname = 'SSMTNode_SwitchKey'
    bl_label = 'Switch Key'
    bl_icon = 'GROUP'

    def update_key_name(self, context):
        self.update_node_width([self.key_name, self.comment])
    
    def update_comment(self, context):
        self.update_node_width([self.key_name, self.comment])
    
    key_name: bpy.props.StringProperty(name="Key Name", default="", update=update_key_name) # type: ignore
    comment: bpy.props.StringProperty(name="备注", description="备注信息，会以注释形式生成到配置表中", default="", update=update_comment) # type: ignore
    
    def init(self, context):
        self.label = "按键切换"
        self.inputs.new('SSMTSocketObject', "Status 0")
        self.outputs.new('SSMTSocketObject', "Output")
        self.width = 200
        self.use_custom_color = True
        self.color = (0.34, 0.54, 0.34)

    def draw_buttons(self, context, layout):
        row = layout.row(align=True)
        row.prop(self, "key_name", text="按键")
        row.operator("wm.url_open", text="", icon='HELP').url = "https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes"
        
        layout.prop(self, "comment", text="备注")
        
        row = layout.row(align=True)
        op_add = row.operator("ssmt.switch_add_socket", text="Add", icon='ADD')
        op_add.node_name = self.name
        
        op_rem = row.operator("ssmt.switch_remove_socket", text="Remove", icon='REMOVE')
        op_rem.node_name = self.name


class SSMTNode_Result_Output(SSMTNodeBase):
    '''Result Output Node'''
    bl_idname = 'SSMTNode_Result_Output'
    bl_label = 'Generate Mod'
    bl_icon = 'EXPORT'

    def init(self, context):
        self.inputs.new('SSMTSocketObject', "Group 1")
        self.width = 400

    def draw_buttons(self, context, layout):
        layout.operator("ssmt.generate_mod_blueprint", text="Generate Mod", icon='EXPORT')
        
        if GlobalConfig.logic_name == LogicName.WWMI:
            layout.prop(context.scene.global_properties, "ignore_muted_shape_keys")
            layout.prop(context.scene.global_properties, "apply_all_modifiers")
            layout.prop(context.scene.global_properties, "export_add_missing_vertex_groups")

        layout.prop(context.scene.global_properties, 
                    "forbid_auto_texture_ini",text="禁止自动贴图流程")

        if GlobalConfig.logic_name != LogicName.GF2:
            layout.prop(context.scene.global_properties,
                        "recalculate_tangent",text="向量归一化法线存入TANGENT(全局)")

        if GlobalConfig.logic_name == LogicName.HIMI:
            layout.prop(context.scene.global_properties,
                        "recalculate_color",text="算术平均归一化法线存入COLOR(全局)")

        if GlobalConfig.logic_name == LogicName.ZZMI:
            layout.prop(context.scene.global_properties, "zzz_use_slot_fix")

        if GlobalConfig.logic_name == LogicName.GIMI:
            layout.prop(context.scene.global_properties, "gimi_use_orfix")

        layout.prop(context.scene.global_properties, "open_mod_folder_after_generate_mod",text="生成Mod后打开Mod所在文件夹")

        layout.prop(context.scene.global_properties, "use_specific_generate_mod_folder_path")

        if GlobalProterties.use_specific_generate_mod_folder_path():
            box = layout.box()
            box.label(text="当前生成Mod位置文件夹:")
            box.label(text=context.scene.global_properties.generate_mod_folder_path)

            layout.operator("ssmt.select_generate_mod_folder", icon='FILE_FOLDER')
        
        # 添加返回上一层级按钮
        layout.separator()
        row = layout.row(align=True)
        row.operator("ssmt.blueprint_nest_navigate", text="返回上一层级", icon='BACK')

    def update(self):
        if self.inputs and self.inputs[-1].is_linked:
            self.inputs.new('SSMTSocketObject', f"Group {len(self.inputs) + 1}")
        
        if len(self.inputs) > 1 and not self.inputs[-1].is_linked and not self.inputs[-2].is_linked:
             self.inputs.remove(self.inputs[-1])


class SSMT_OT_View_Group_Objects(bpy.types.Operator):
    '''递归解析当前组下面所有的物体并在当前3D视图中展示，点击切换局部视图，注意组节点最好不要包含按键切换，否则会同时展示所有切换分支内容'''
    bl_idname = "ssmt.view_group_objects"
    bl_label = "View Group Objects"
    
    node_name: bpy.props.StringProperty() # type: ignore

    def execute(self, context):
        tree = getattr(context.space_data, "edit_tree", None) or getattr(context.space_data, "node_tree", None)
        if not tree:
             return {'CANCELLED'}
        node = tree.nodes.get(self.node_name)
        if not node:
             return {'CANCELLED'}

        view_3d_area = None
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    view_3d_area = area
                    break
            if view_3d_area:
                break
        
        if not view_3d_area:
            self.report({'WARNING'}, "No 3D View found")
            return {'CANCELLED'}

        in_local_view = False
        for space in view_3d_area.spaces:
            if space.type == 'VIEW_3D' and space.local_view:
                in_local_view = True
                break
        
        if in_local_view:
            with context.temp_override(area=view_3d_area):
                bpy.ops.view3d.localview()
            self.report({'INFO'}, "Exited local view")
            return {'FINISHED'}

        objects_to_show = set()
        checked_nodes = set()
        visited_blueprints = set()

        def collect_objects(current_node):
            if current_node in checked_nodes: 
                return
            checked_nodes.add(current_node)

            if getattr(current_node, "bl_idname", "") == 'SSMTNode_Object_Info':
                obj_name = getattr(current_node, "object_name", "")
                if obj_name:
                    obj = bpy.data.objects.get(obj_name)
                    if obj:
                        objects_to_show.add(obj)


            if hasattr(current_node, "inputs"):
                for inp in current_node.inputs:
                    if inp.is_linked:
                        for link in inp.links:
                            collect_objects(link.from_node)

        collect_objects(node)
        
        if not objects_to_show:
            self.report({'WARNING'}, "No objects found in this group")
            return {'CANCELLED'}

        def deselect_all_safe():
            for o in bpy.context.selected_objects:
                o.select_set(False)

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        deselect_all_safe()
        for obj in objects_to_show:
            obj.select_set(True)

        region = next((r for r in view_3d_area.regions if r.type == 'WINDOW'), None)
        if region:
            with context.temp_override(area=view_3d_area, region=region):
                try:
                    bpy.ops.view3d.localview()
                    bpy.ops.view3d.view_axis(type='FRONT')
                    bpy.ops.view3d.view_selected()
                    if view_3d_area.spaces.active:
                        view_3d_area.spaces.active.shading.type = 'SOLID'
                except Exception as e:
                    print(f"View setup warning: {e}")

        self.report({'INFO'}, f"Showing {len(objects_to_show)} objects in local view")
        return {'FINISHED'}


class SSMT_OT_SelectGenerateModFolder(bpy.types.Operator, ImportHelper):
    '''选择生成 Mod 的目标文件夹'''
    bl_idname = "ssmt.select_generate_mod_folder"
    bl_label = "选择生成Mod文件夹"

    directory: bpy.props.StringProperty(subtype='DIR_PATH') # type: ignore
    filter_folder: bpy.props.BoolProperty(default=True, options={'HIDDEN'}) # type: ignore
    filter_image: bpy.props.BoolProperty(default=False, options={'HIDDEN'}) # type: ignore

    def invoke(self, context, event):
        current_directory = context.scene.global_properties.generate_mod_folder_path
        if current_directory:
            self.directory = bpy.path.abspath(current_directory)
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        selected_directory = bpy.path.abspath(self.directory).rstrip("\\/")
        if not selected_directory:
            self.report({'ERROR'}, "请选择有效的文件夹")
            return {'CANCELLED'}

        os.makedirs(selected_directory, exist_ok=True)
        context.scene.global_properties.generate_mod_folder_path = selected_directory
        self.report({'INFO'}, f"生成Mod文件夹已设置为: {selected_directory}")
        return {'FINISHED'}

classes = (
    SSMT_OT_SelectGenerateModFolder,
    SSMT_OT_RefreshNodeObjectIDs,
    SSMT_OT_SelectNodeObject,
    SSMT_OT_StartPickObject,
    SSMT_OT_PickObjectModal,
    SSMT_OT_View_Group_Objects,
    SSMTNode_Object_Info,
    SSMTNode_Object_Group,
    SSMTNode_Result_Output,
    SSMTNode_SwitchKey,
    SSMT_OT_SwitchKey_AddSocket,
    SSMT_OT_SwitchKey_RemoveSocket,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.VIEW3D_HT_header.append(draw_view3d_header)


def unregister():
    bpy.types.VIEW3D_HT_header.remove(draw_view3d_header)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
