
import bpy

from ..utils.translate_utils import iface_
from .blueprint_node_base import SSMTNodeBase


# ── 形态键列表项 ──
class SSMTShapeKeyListItem(bpy.types.PropertyGroup):
    enabled: bpy.props.BoolProperty(name="", default=False) # type: ignore
    shapekey_name: bpy.props.StringProperty(name="形态键名称", default="") # type: ignore
    key: bpy.props.StringProperty(name="按键", default="") # type: ignore


# ── 刷新形态键列表 ──
class SSMT_OT_RefreshShapeKeyList(bpy.types.Operator):
    bl_idname = "ssmt.refresh_shapekey_list"
    bl_label = "刷新形态键列表"
    bl_description = "扫描蓝图中的所有物体节点，提取形态键列表"
    bl_options = {'REGISTER', 'UNDO'}

    @staticmethod
    def _get_shapekeys_from_object(obj):
        """返回物体所有形态键名称（跳过第一个，即 Basis / 基型）。"""
        if not obj or obj.type != 'MESH':
            return []
        shape_keys = getattr(obj.data, 'shape_keys', None)
        if not shape_keys:
            return []
        return [kb.name for kb in list(shape_keys.key_blocks)[1:]]

    def execute(self, context):
        tree = context.space_data.edit_tree
        if not tree or getattr(tree, 'bl_idname', '') != 'SSMTBlueprintTreeType':
            self.report({'WARNING'}, "请在 SSMT 蓝图编辑器中执行")
            return {'CANCELLED'}

        gen_node = None
        for node in tree.nodes:
            if node.bl_idname == 'SSMTNode_GenerateShapeKey':
                gen_node = node
                break
        if not gen_node:
            self.report({'WARNING'}, "请先在蓝图中添加一个「生成形态键」节点")
            return {'CANCELLED'}

        seen = set()
        gen_node.shapekey_items.clear()
        for node in tree.nodes:
            if node.bl_idname != 'SSMTNode_Object_Info':
                continue
            obj = bpy.data.objects.get(node.object_name)
            for sk_name in self._get_shapekeys_from_object(obj):
                if sk_name in seen:
                    continue
                seen.add(sk_name)
                item = gen_node.shapekey_items.add()
                item.shapekey_name = sk_name

        self.report({'INFO'}, f"已刷新 {len(gen_node.shapekey_items)} 个形态键")
        return {'FINISHED'}


# ── 生成形态键节点 ──
class SSMTNode_GenerateShapeKey(SSMTNodeBase):
    '''生成形态键 Mod 节点：扫描蓝图物体，勾选需要生成的形态键并绑定按键'''
    bl_idname = 'SSMTNode_GenerateShapeKey'
    bl_label = '生成形态键'
    bl_icon = 'SHAPEKEY_DATA'

    shapekey_items: bpy.props.CollectionProperty(type=SSMTShapeKeyListItem) # type: ignore

    def init(self, context):
        self.width = 320

    def draw_buttons(self, context, layout):
        box = layout.box()
        row = box.row(align=True)
        row.operator("ssmt.refresh_shapekey_list", text=iface_("刷新列表"), icon='FILE_REFRESH')
        if not self.shapekey_items:
            row.label(text=iface_("（空）"), icon='BLANK1')
        else:
            row.label(text=f"共 {len(self.shapekey_items)} 个", icon='SHAPEKEY_DATA')

        for item in self.shapekey_items:
            row = layout.row(align=True)
            row.prop(item, "enabled", text="")
            row.label(text=item.shapekey_name, icon='SHAPEKEY_DATA')
            row.prop(item, "key", text="", placeholder="VK键值（可选）")
            op = row.operator("wm.url_open", text="", icon='HELP')
            op.url = "https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes"


classes = (
    SSMTShapeKeyListItem,
    SSMT_OT_RefreshShapeKeyList,
    SSMTNode_GenerateShapeKey,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
