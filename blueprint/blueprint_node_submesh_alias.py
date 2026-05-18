'''
自定义Submesh名称节点
允许用户为每个 unique_str（如 LOD0.5a4c1ef3-318-46683）起别名（如 身体）
生成Mod时，文件名前缀使用别名，路径解析仍用原始 unique_str
'''
import os
import bpy
from bpy.types import PropertyGroup

from ..utils.translate_utils import iface_, rpt_
from ..workspace.workspace_helper import SSMTWorkSpace
from .blueprint_node_base import SSMTNodeBase


class SSMTAliasItem(PropertyGroup):
    '''别名列表中的一项：submesh_name + alias_name'''
    submesh_name: bpy.props.StringProperty(
        name="Submesh",
        description="原始 Submesh 唯一标识（如 LOD0.5a4c1ef3-318-46683）",
        default="",
    ) # type: ignore

    alias_name: bpy.props.StringProperty(
        name="别名",
        description="别名（如 身体）。若填写则用于文件名前缀，留空表示使用原始名称",
        default="",
    ) # type: ignore


class SSMT_OT_RefreshSubmeshAlias(bpy.types.Operator):
    '''刷新别名节点的 Submesh 列表（从工作空间目录重新扫描）'''
    bl_idname = "ssmt.refresh_submesh_alias"
    bl_label = "刷新列表"
    bl_options = {'REGISTER', 'UNDO'}

    node_name: bpy.props.StringProperty(default="") # type: ignore
    tree_name: bpy.props.StringProperty(default="") # type: ignore

    def execute(self, context):
        tree = bpy.data.node_groups.get(self.tree_name)
        if not tree:
            self.report({'WARNING'}, rpt_("未找到蓝图树: {name}").format(name=self.tree_name))
            return {'CANCELLED'}

        node = tree.nodes.get(self.node_name)
        if not node or node.bl_idname != 'SSMTNode_Submesh_Alias':
            self.report({'WARNING'}, rpt_("未找到目标节点"))
            return {'CANCELLED'}

        # 从工作空间扫描所有 LOD 下的 submesh unique_str
        all_unique_strs = []
        lod_submesh_dict = SSMTWorkSpace.get_lod_submesh_folderpath_dict()
        if lod_submesh_dict:
            for lod_name, submesh_folder_paths in lod_submesh_dict.items():
                for folder_path in submesh_folder_paths:
                    bare_name = os.path.basename(folder_path)
                    all_unique_strs.append(lod_name + "." + bare_name)
        else:
            # 兼容旧版无 LOD 结构
            for folder_path in SSMTWorkSpace.get_submesh_folderpath_list():
                all_unique_strs.append(os.path.basename(folder_path))

        # 保留已有别名，只增量合并新的 unique_str
        existing = {item.submesh_name: item.alias_name for item in node.alias_items}
        node.alias_items.clear()
        for ustr in all_unique_strs:
            item = node.alias_items.add()
            item.submesh_name = ustr
            item.alias_name = existing.get(ustr, "")

        self.report(
            {'INFO'},
            rpt_("已刷新别名列表，共 {count} 项").format(count=len(all_unique_strs)),
        )
        return {'FINISHED'}


class SSMTNode_Submesh_Alias(SSMTNodeBase):
    '''自定义Submesh名称节点：为每个 Submesh 配置别名，用于文件名生成'''
    bl_idname = 'SSMTNode_Submesh_Alias'
    bl_label = '自定义Submesh名称'
    bl_icon = 'FONT_DATA'

    alias_items: bpy.props.CollectionProperty(type=SSMTAliasItem) # type: ignore

    def init(self, context):
        self.width = 380

    def draw_buttons(self, context, layout):
        # 标题行 + 刷新按钮
        row = layout.row(align=True)
        row.label(text=iface_("Submesh → 别名"), icon='FONT_DATA')
        op = row.operator(
            "ssmt.refresh_submesh_alias",
            text="",
            icon='FILE_REFRESH',
        )
        op.node_name = self.name
        op.tree_name = self.id_data.name if self.id_data else ""

        if not self.alias_items:
            box = layout.box()
            box.label(text=iface_("列表为空，点击刷新按钮扫描工作空间"), icon='INFO')
            return

        # 列头
        header = layout.row(align=True)
        header.label(text=iface_("Submesh"))
        header.label(text=iface_("别名（留空=使用原名）"))

        # 每行一个 submesh
        for item in self.alias_items:
            row = layout.row(align=True)
            row.label(text=item.submesh_name, icon='OUTLINER_COLLECTION')
            row.prop(item, "alias_name", text="")


classes = (
    SSMTAliasItem,
    SSMT_OT_RefreshSubmeshAlias,
    SSMTNode_Submesh_Alias,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
