'''
存放一些构建SSMT蓝图架构的基础节点
每种节点放在单独的py文件中
方便阅读理解
'''
import bpy
from bpy.types import NodeTree, Node, NodeSocket, PropertyGroup

from ..common.global_config import GlobalConfig



# Custom Socket Types
class SSMTSubmeshListItem(PropertyGroup):
    name: bpy.props.StringProperty(name="Submesh", default="") # type: ignore


class SSMTSocketObject(NodeSocket):
    '''Custom Socket for Object Data'''
    bl_idname = 'SSMTSocketObject'
    bl_label = '物体插槽'

    def draw_color(self, context, node):
        return (0.0, 0.8, 0.8, 1.0) # Cyan/Teal

    def draw(self, context, layout, node, text):
        layout.label(text=text)

# 1. 定义自定义节点树类型
class SSMTBlueprintTree(NodeTree):
    '''SSMT Mod Logic Blueprint'''
    bl_idname = 'SSMTBlueprintTreeType'
    bl_label = 'SSMT蓝图'
    bl_icon = 'NODETREE'


# 2. 定义基础节点
class SSMTNodeBase(Node):
    @classmethod
    def poll(cls, ntree):
        return ntree.bl_idname == 'SSMTBlueprintTreeType'
    
    def calculate_text_width(self, text, padding=40):
        """计算文本所需的宽度（估算值）"""
        if not text:
            return 200
        
        # 中文字符宽度约为英文字符的2倍
        char_count = 0
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                char_count += 2
            else:
                char_count += 1
        
        # 每个字符约占用8像素宽度（估算值）
        width = char_count * 8 + padding
        
        # 确保最小宽度为200
        return max(200, width)
    
    def update_node_width(self, texts):
        """根据文本内容更新节点宽度"""
        if not texts:
            return
        
        max_width = 200
        for text in texts:
            width = self.calculate_text_width(text)
            if width > max_width:
                max_width = width
        
        self.width = max_width
    

class THEHERTA3_OT_OpenPersistentBlueprint(bpy.types.Operator):
    bl_idname = "theherta3.open_persistent_blueprint"
    bl_label = "打开蓝图界面"
    bl_description = "打开一个独立的蓝图窗口，用于配置Mod逻辑"

    blueprint_name: bpy.props.StringProperty(
        name="Blueprint Name",
        default="",
        options={'SKIP_SAVE'},
    ) # type: ignore
    
    def execute(self, context):
        # 1. 获取或创建蓝图树
        GlobalConfig.read_from_main_json_ssmt4()
        requested_tree_name = str(self.blueprint_name or "").strip()
        tree_name = requested_tree_name or GlobalConfig.workspacename
        
        # 查找是否存在同名的 NodeGroup
        tree = bpy.data.node_groups.get(tree_name)
        if tree and getattr(tree, "bl_idname", "") != 'SSMTBlueprintTreeType':
            tree = None

        if not tree and requested_tree_name:
            from .blueprint_export_helper import BlueprintExportHelper
            tree = BlueprintExportHelper.get_selected_blueprint_tree(requested_tree_name, context=context)

        if not tree:
            # 创建新的 NodeTree，类型必须是我们定义的 bl_idname
            tree = bpy.data.node_groups.new(name=tree_name, type='SSMTBlueprintTreeType')
            tree.use_fake_user = True

        from .blueprint_export_helper import BlueprintExportHelper
        BlueprintExportHelper.set_runtime_blueprint_tree(tree)

        global_properties = getattr(getattr(context, "scene", None), "global_properties", None)
        if global_properties and getattr(global_properties, "selected_blueprint_name", "") != tree.name:
            global_properties.selected_blueprint_name = tree.name
        
        # 1.5 检查是否存在已开启的窗口
        # Blender API 无法直接控制 OS 窗口置顶。为了实现"如果存在则置顶"的效果，
        # 我们先查找并关闭那个旧窗口，然后重新创建一个新的。
        target_window = None
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'NODE_EDITOR':
                    for space in area.spaces:
                        if space.type == 'NODE_EDITOR' and space.node_tree == tree:
                            target_window = window
                            break
                if target_window: break
            if target_window: break
            
        if target_window:
            # 只有当存在多个窗口时才允许关闭，避免误关主程序
            if len(context.window_manager.windows) > 1:
                try:
                    # 尝试关闭旧窗口
                    if hasattr(context, 'temp_override'):
                        with context.temp_override(window=target_window):
                            bpy.ops.wm.window_close()
                    else:
                        override = context.copy()
                        override['window'] = target_window
                        override['screen'] = target_window.screen
                        bpy.ops.wm.window_close(override)
                except Exception as e:
                    print(f"SSMT: Failed to close existing window, creating new one anyway. Error: {e}")

        # 2. 打开新窗口 (复制当前Context)
        old_windows = set(context.window_manager.windows)
        
        bpy.ops.wm.window_new()
        
        new_windows = set(context.window_manager.windows)
        created_window = (new_windows - old_windows).pop() if (new_windows - old_windows) else None
        
        if created_window:
            screen = created_window.screen
            
            target_area = max(screen.areas, key=lambda a: a.width * a.height)
            
            if target_area:
                target_area.ui_type = 'SSMTBlueprintTreeType' # 似乎不起作用，NodeEditor需要指定tree type
                target_area.type = 'NODE_EDITOR'
                
                # 设置空间属性
                for space in target_area.spaces:
                    if space.type == 'NODE_EDITOR':
                        space.tree_type = 'SSMTBlueprintTreeType' # 关键：切换到自定义树类型
                        space.node_tree = tree # 设置要编辑的数据块
                        space.pin = True # 锁定
                        
                        # 尝试调整视图 (可选)
                        
        return {'FINISHED'}


class THEHERTA3_OT_DeletePersistentBlueprint(bpy.types.Operator):
    bl_idname = "theherta3.delete_persistent_blueprint"
    bl_label = "删除蓝图"
    bl_description = "删除当前选中的蓝图"
    bl_options = {'REGISTER', 'INTERNAL'}

    blueprint_name: bpy.props.StringProperty(
        name="Blueprint Name",
        default="",
        options={'SKIP_SAVE'},
    ) # type: ignore

    def _get_target_tree(self, context):
        from .blueprint_export_helper import BlueprintExportHelper

        requested_tree_name = str(self.blueprint_name or "").strip()
        if requested_tree_name == "__NONE__":
            return None

        return BlueprintExportHelper.get_selected_blueprint_tree(requested_tree_name, context=context)

    def invoke(self, context, event):
        target_tree = self._get_target_tree(context)
        if not target_tree:
            self.report({'WARNING'}, "当前没有蓝图可删除！")
            return {'CANCELLED'}

        self.blueprint_name = target_tree.name
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        layout.label(text="确认删除当前选中的蓝图吗？", icon='TRASH')
        layout.label(text=self.blueprint_name)
        layout.label(text="删除后无法恢复，请确认不是误操作。", icon='ERROR')

    def execute(self, context):
        from .blueprint_export_helper import BlueprintExportHelper

        target_tree = self._get_target_tree(context)
        if not target_tree:
            self.report({'WARNING'}, "当前没有蓝图可删除！")
            return {'CANCELLED'}

        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type != 'NODE_EDITOR':
                    continue
                for space in area.spaces:
                    if space.type != 'NODE_EDITOR':
                        continue
                    if getattr(space, "node_tree", None) == target_tree:
                        space.node_tree = None

        if BlueprintExportHelper.runtime_blueprint_tree_name == target_tree.name:
            BlueprintExportHelper.runtime_blueprint_tree_name = ""

        deleted_blueprint_name = target_tree.name
        bpy.data.node_groups.remove(target_tree)

        global_properties = getattr(getattr(context, "scene", None), "global_properties", None)
        preferred_blueprint_name = BlueprintExportHelper.get_preferred_blueprint_name(context=context)
        if global_properties:
            global_properties.selected_blueprint_name = preferred_blueprint_name or "__NONE__"

        for window in context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()

        self.report({'INFO'}, "已删除蓝图: " + deleted_blueprint_name)
        return {'FINISHED'}


class THEHERTA3_OT_RenamePersistentBlueprint(bpy.types.Operator):
    bl_idname = "theherta3.rename_persistent_blueprint"
    bl_label = "重命名蓝图"
    bl_description = "重命名当前选中的蓝图"
    bl_options = {'REGISTER', 'INTERNAL'}

    blueprint_name: bpy.props.StringProperty(
        name="Blueprint Name",
        default="",
        options={'SKIP_SAVE'},
    ) # type: ignore

    new_blueprint_name: bpy.props.StringProperty(
        name="新蓝图名称",
        default="",
    ) # type: ignore

    def _get_target_tree(self, context):
        from .blueprint_export_helper import BlueprintExportHelper

        requested_tree_name = str(self.blueprint_name or "").strip()
        if requested_tree_name == "__NONE__":
            return None

        return BlueprintExportHelper.get_selected_blueprint_tree(requested_tree_name, context=context)

    def invoke(self, context, event):
        target_tree = self._get_target_tree(context)
        if not target_tree:
            self.report({'WARNING'}, "当前没有蓝图可重命名！")
            return {'CANCELLED'}

        self.blueprint_name = target_tree.name
        self.new_blueprint_name = target_tree.name
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        layout = self.layout
        layout.label(text="请输入新的蓝图名称", icon='GREASEPENCIL')
        layout.prop(self, "new_blueprint_name", text="名称")

    def execute(self, context):
        from .blueprint_export_helper import BlueprintExportHelper

        target_tree = self._get_target_tree(context)
        if not target_tree:
            self.report({'WARNING'}, "当前没有蓝图可重命名！")
            return {'CANCELLED'}

        new_name = str(self.new_blueprint_name or "").strip()
        if not new_name:
            self.report({'ERROR'}, "蓝图名称不能为空！")
            return {'CANCELLED'}

        if new_name == "__NONE__":
            self.report({'ERROR'}, "蓝图名称不能使用保留值 __NONE__！")
            return {'CANCELLED'}

        if new_name == target_tree.name:
            self.report({'INFO'}, "蓝图名称未发生变化")
            return {'CANCELLED'}

        existing_tree = bpy.data.node_groups.get(new_name)
        if existing_tree and existing_tree != target_tree:
            self.report({'ERROR'}, "已存在同名蓝图，请使用其他名称！")
            return {'CANCELLED'}

        old_name = target_tree.name
        target_tree.name = new_name

        if BlueprintExportHelper.runtime_blueprint_tree_name == old_name:
            BlueprintExportHelper.runtime_blueprint_tree_name = target_tree.name

        global_properties = getattr(getattr(context, "scene", None), "global_properties", None)
        if global_properties:
            global_properties.selected_blueprint_name = target_tree.name

        for window in context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()

        self.report({'INFO'}, "已将蓝图重命名为: " + target_tree.name)
        return {'FINISHED'}
    
def register():
    bpy.utils.register_class(SSMTSubmeshListItem)
    bpy.utils.register_class(SSMTBlueprintTree)
    bpy.utils.register_class(SSMTSocketObject)
    bpy.utils.register_class(THEHERTA3_OT_OpenPersistentBlueprint)
    bpy.utils.register_class(THEHERTA3_OT_DeletePersistentBlueprint)
    bpy.utils.register_class(THEHERTA3_OT_RenamePersistentBlueprint)
    SSMTBlueprintTree.ssmt_submesh_items = bpy.props.CollectionProperty(type=SSMTSubmeshListItem) # type: ignore[attr-defined]


def unregister():
    del SSMTBlueprintTree.ssmt_submesh_items
    bpy.utils.unregister_class(THEHERTA3_OT_RenamePersistentBlueprint)
    bpy.utils.unregister_class(THEHERTA3_OT_DeletePersistentBlueprint)
    bpy.utils.unregister_class(SSMTSocketObject)
    bpy.utils.unregister_class(THEHERTA3_OT_OpenPersistentBlueprint)
    bpy.utils.unregister_class(SSMTBlueprintTree)
    bpy.utils.unregister_class(SSMTSubmeshListItem)


