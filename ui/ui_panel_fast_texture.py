'''
快速上贴图技术
直接从DedupedTextures文件夹里显示预览贴图
然后直接快速上贴图
此时不参与自动贴图ini流程
仅用于预览显示
'''

import bpy
import os
import shutil
from bpy.props import StringProperty, CollectionProperty, IntProperty, BoolProperty
from bpy.types import Operator, Panel, PropertyGroup, UIList
from bpy_extras.io_utils import ImportHelper
import bpy.utils.previews

from ..common.global_config import GlobalConfig

from ..utils.translate_utils import iface_, rpt_
from ..utils.json_utils import JsonUtils
from ..utils.collection_utils import CollectionUtils,CollectionColor

# 存储预览图集合
fast_preview_collections = {}


def get_workspace_preview_texture_folder():
    GlobalConfig.read_from_main_json_ssmt4()

    workspace_folder_path = GlobalConfig.path_workspace_folder()
    use_jpg_folder = bpy.app.version <= (4, 2, 0)
    folder_name = "DedupedTextures_jpg" if use_jpg_folder else "DedupedTextures"
    preview_folder_path = os.path.join(workspace_folder_path, folder_name + "\\")

    if os.path.exists(preview_folder_path):
        return preview_folder_path, folder_name

    return "", folder_name

# 定义图片列表项
class SSMT_ImportTexture_ImageListItem(PropertyGroup):
    name: StringProperty(name="图片名称") # type: ignore
    filepath: StringProperty(name="文件路径") # type: ignore

# 自定义UI列表显示图片和缩略图
class SSMT_UL_FastImportTextureList(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        pcoll = fast_preview_collections["main"]
        
        if self.layout_type in {'DEFAULT', 'Expand'}:
            # 尝试获取预览图标
            if item.name in pcoll:
                layout.template_icon(icon_value=pcoll[item.name].icon_id, scale=1.0)
            else:
                layout.label(text="", icon='IMAGE_DATA')
            
            layout.label(text=item.name)
            
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            if item.name in pcoll:
                layout.template_icon(icon_value=pcoll[item.name].icon_id, scale=6.0)
            else:
                layout.label(text="", icon='IMAGE_DATA')


# 自动检测并设置DedupedTextures文件夹
class SSMT_ImportTexture_WM_OT_AutoDetectTextureFolder(Operator):
    bl_idname = "ssmt.auto_detect_texture_folder"
    bl_label = "读取DedupedTextures"
    
    def execute(self, context):
        deduped_textures_folder_path, folder_name = get_workspace_preview_texture_folder()

        if not deduped_textures_folder_path:
            self.report({'ERROR'}, f"未找到当前工作空间下的 {folder_name} 文件夹")
            return {'CANCELLED'}
        
        # 清空之前的列表和预览
        bpy.context.scene.image_list.clear()
        pcoll = fast_preview_collections["main"]
        pcoll.clear()
        
        # 支持的图片格式
        image_extensions = ('.dds', '.jpg', '.jpeg', '.png', '.tga', '.bmp', '.tiff', '.exr', '.hdr')
        
        # 遍历文件夹，收集图片文件
        image_count = 0
        for filename in os.listdir(deduped_textures_folder_path):
            if filename.lower().endswith(image_extensions):
                full_path = os.path.join(deduped_textures_folder_path, filename)
                if os.path.isfile(full_path):
                    item = bpy.context.scene.image_list.add()
                    item.name = filename
                    item.filepath = full_path
                    
                    # 加载预览图
                    try:
                        thumb = pcoll.load(filename, full_path, 'IMAGE')
                        image_count += 1
                    except Exception as e:
                        print(f"Could not load preview for {filename}: {e}")

        self.report({'INFO'}, f"已从当前工作空间的 {folder_name} 文件夹加载 {image_count} 张图片。")

        return {'FINISHED'}
    

# 应用图片到材质操作符
class SSMT_ImportTexture_WM_OT_ApplyImageToMaterial(Operator):
    bl_idname = "ssmt.apply_image_to_material"
    bl_label = "应用贴图到选中的物体"
    
    def execute(self, context):
        scene = context.scene
        selected_index = scene.image_list_index
        
        if selected_index < 0 or selected_index >= len(scene.image_list):
            self.report({'ERROR'}, rpt_("列表中未选择任何图片。"))
            return {'CANCELLED'}
        
        selected_image = scene.image_list[selected_index]
        image_path = selected_image.filepath
        
        # 获取或创建图像数据块
        image_data = bpy.data.images.load(image_path, check_existing=True)
        
        selected_objects = context.selected_objects
        if not selected_objects:
            self.report({'ERROR'}, rpt_("没有选中的对象！"))
            return {'CANCELLED'}
        
        applied_count = 0
        for obj in selected_objects:
            if obj.type != 'MESH':
                continue  # 跳过非网格对象
            
            # 确保对象有材质数据块
            if not obj.data.materials:
                mat = bpy.data.materials.new(name=f"Mat_{selected_image.name}")
                obj.data.materials.append(mat)
            else:
                # 使用第一个材质槽
                mat = obj.data.materials[0]
                # 如果第一个槽位是空的(None)，创建一个新材质并填入
                if mat is None:
                    mat = bpy.data.materials.new(name=f"Mat_{selected_image.name}")
                    obj.data.materials[0] = mat
            
            # 确保材质使用节点
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            
            # 查找或创建Principled BSDF节点
            bsdf_node = nodes.get("Principled BSDF")
            if not bsdf_node:
                # 这里是根据名称获取，所以中英文都要添加支持
                print("疑似英文Principled BSDF无法获取，尝试获取中文的原理化 BSDF")
                bsdf_node = nodes.get("原理化 BSDF")
            
            # 3.6的原理化没有空格，他娘滴，每个版本还不一样
            if not bsdf_node:
                # 这里是根据名称获取，所以中英文都要添加支持
                print("疑似英文Principled BSDF无法获取，尝试获取中文的原理化 BSDF")
                bsdf_node = nodes.get("原理化BSDF")

            if not bsdf_node:
                print("BSDF not exists ,ready to create one.")
                bsdf_node = nodes.new(type='ShaderNodeBsdfPrincipled')
                bsdf_node.location = (0, 0)
                
                # 获取材质输出节点
                output_node = nodes.get("Material Output")
                if not output_node:
                    output_node = nodes.new(type='ShaderNodeOutputMaterial')
                    output_node.location = (400, 0)
                
                # 连接到输出
                links.new(bsdf_node.outputs['BSDF'], output_node.inputs['Surface'])
            
            # 创建图像纹理节点
            tex_image = nodes.new('ShaderNodeTexImage')
            tex_image.image = image_data
            tex_image.location = (-300, 0)
            
            # 将图像纹理节点的Color输出连接到BSDF的Base Color输入
            links.new(tex_image.outputs['Color'], bsdf_node.inputs['Base Color'])
            links.new(tex_image.outputs['Alpha'], bsdf_node.inputs['Alpha'])

            applied_count += 1
        
        self.report({'INFO'}, rpt_("已将 {image_name} 应用到 {count} 个物体。").format(image_name=selected_image.name, count=applied_count))
        return {'FINISHED'}


# 面板UI布局
class SSMT_ImportTexture_VIEW3D_PT_ImageMaterialPanel(Panel):
    bl_label = "快速上预览贴图"
    bl_idname = "VIEW3D_PT_fast_preview_texture"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'TheHerta4'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # 自动检测按钮
        row = layout.row()

        row.operator("ssmt.auto_detect_texture_folder")
        
        # 显示图片数量信息
        if scene.image_list:
            layout.label(text=iface_("已找到 {count} 张图片").format(count=len(scene.image_list)))
        
        # 显示图片列表
        if scene.image_list:
            row = layout.row()
            row.template_list(
                "SSMT_UL_FastImportTextureList",  # 修正为正确的类名
                iface_("图片列表"), 
                scene, 
                "image_list", 
                scene, 
                "image_list_index",
                rows=6
            )
        else:
            layout.label(text=iface_("未找到图片，请先选择文件夹。"))
        
        # 应用材质按钮
        row = layout.row()
        row.operator("ssmt.apply_image_to_material", icon='MATERIAL_DATA')

        
        # 显示当前选中图片的预览
        if scene.image_list and scene.image_list_index >= 0 and scene.image_list_index < len(scene.image_list):
            selected_item = scene.image_list[scene.image_list_index]
            pcoll = fast_preview_collections["main"]
            
            if selected_item.name in pcoll:
                box = layout.box()
                box.label(text=iface_("预览:"))
                box.template_icon(icon_value=pcoll[selected_item.name].icon_id, scale=10.0)



def register():
    # 注册预览图集合
    fast_pcoll = bpy.utils.previews.new()
    fast_preview_collections["main"] = fast_pcoll

    bpy.utils.register_class(SSMT_ImportTexture_ImageListItem)
    bpy.utils.register_class(SSMT_UL_FastImportTextureList)
    bpy.utils.register_class(SSMT_ImportTexture_WM_OT_ApplyImageToMaterial)
    bpy.utils.register_class(SSMT_ImportTexture_WM_OT_AutoDetectTextureFolder)
    bpy.utils.register_class(SSMT_ImportTexture_VIEW3D_PT_ImageMaterialPanel)

    bpy.types.Scene.image_list = CollectionProperty(type=SSMT_ImportTexture_ImageListItem)
    bpy.types.Scene.image_list_index = IntProperty(default=0)

def unregister():
    try:
        del bpy.types.Scene.image_list
        del bpy.types.Scene.image_list_index
    except Exception:
        pass

    # 移除预览图集合
    for pcoll in fast_preview_collections.values():
        try:
            bpy.utils.previews.remove(pcoll)
        except Exception:
            pass
    fast_preview_collections.clear()

    bpy.utils.unregister_class(SSMT_ImportTexture_VIEW3D_PT_ImageMaterialPanel)
    bpy.utils.unregister_class(SSMT_ImportTexture_WM_OT_AutoDetectTextureFolder)
    bpy.utils.unregister_class(SSMT_ImportTexture_WM_OT_ApplyImageToMaterial)
    bpy.utils.unregister_class(SSMT_UL_FastImportTextureList)
    bpy.utils.unregister_class(SSMT_ImportTexture_ImageListItem)