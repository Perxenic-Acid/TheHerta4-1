import os

import bpy
from ..common.global_config import GlobalConfig
from ..common.m_key import M_Key
from ..common.draw_call_model import DrawCallModel
from ..common.workspace_helper import WorkSpaceHelper

class BlueprintExportHelper:

    # 静态变量，用于多文件导出功能
    # 存储当前导出次数（从1开始）
    current_export_index = 1
    
    # 静态变量，存储最大导出次数
    max_export_count = 1

    # 运行时记录当前操作对应的蓝图树，避免按钮触发后丢失上下文
    runtime_blueprint_tree_name = ""

    @staticmethod
    def _is_valid_blueprint_tree(tree):
        return tree is not None and getattr(tree, "bl_idname", "") == 'SSMTBlueprintTreeType'

    @staticmethod
    def get_all_blueprint_trees():
        blueprint_trees = [
            node_group for node_group in bpy.data.node_groups
            if BlueprintExportHelper._is_valid_blueprint_tree(node_group)
        ]
        blueprint_trees.sort(key=lambda tree: tree.name.casefold())
        return blueprint_trees

    @staticmethod
    def get_blueprint_tree_by_name(tree_name):
        if not tree_name:
            return None

        tree = bpy.data.node_groups.get(tree_name)
        if BlueprintExportHelper._is_valid_blueprint_tree(tree):
            return tree

        return None

    @staticmethod
    def get_preferred_blueprint_name(selected_name="", context=None):
        selected_tree = BlueprintExportHelper.get_blueprint_tree_by_name(selected_name)
        if selected_tree:
            return selected_tree.name

        current_tree = BlueprintExportHelper._get_blueprint_tree_from_context(context)
        if BlueprintExportHelper._is_valid_blueprint_tree(current_tree):
            return current_tree.name

        runtime_tree = BlueprintExportHelper.get_blueprint_tree_by_name(
            BlueprintExportHelper.runtime_blueprint_tree_name,
        )
        if runtime_tree:
            return runtime_tree.name

        workspace_tree = BlueprintExportHelper.get_blueprint_tree_by_name(GlobalConfig.get_workspace_name())
        if workspace_tree:
            return workspace_tree.name

        all_blueprints = BlueprintExportHelper.get_all_blueprint_trees()
        if all_blueprints:
            return all_blueprints[0].name

        return ""

    @staticmethod
    def get_blueprint_enum_items(context=None):
        items = []
        preferred_name = BlueprintExportHelper.get_preferred_blueprint_name(context=context)

        for tree in BlueprintExportHelper.get_all_blueprint_trees():
            description = "当前默认蓝图" if tree.name == preferred_name else "选择该蓝图进行打开或生成 Mod"
            items.append((tree.name, tree.name, description))

        if not items:
            items.append(("__NONE__", "当前没有蓝图", "当前没有可选蓝图，请先打开蓝图界面或执行一键导入"))

        return items

    @staticmethod
    def set_runtime_blueprint_tree(tree):
        if BlueprintExportHelper._is_valid_blueprint_tree(tree):
            BlueprintExportHelper.runtime_blueprint_tree_name = tree.name

    @staticmethod
    def _get_blueprint_tree_from_context(context):
        if not context:
            return None

        space_data = getattr(context, "space_data", None)
        if space_data and getattr(space_data, "type", None) == 'NODE_EDITOR':
            node_tree = getattr(space_data, "edit_tree", None) or getattr(space_data, "node_tree", None)
            if BlueprintExportHelper._is_valid_blueprint_tree(node_tree):
                return node_tree

        window_manager = getattr(context, "window_manager", None)
        if not window_manager:
            return None

        for window in window_manager.windows:
            for area in window.screen.areas:
                if area.type != 'NODE_EDITOR':
                    continue
                for space in area.spaces:
                    if space.type != 'NODE_EDITOR':
                        continue
                    node_tree = getattr(space, "edit_tree", None) or getattr(space, "node_tree", None)
                    if BlueprintExportHelper._is_valid_blueprint_tree(node_tree):
                        return node_tree

        return None
    
    @staticmethod
    def get_current_blueprint_tree(context=None):
        """获取当前工作空间对应的蓝图树"""
        tree = BlueprintExportHelper._get_blueprint_tree_from_context(context)
        if BlueprintExportHelper._is_valid_blueprint_tree(tree):
            BlueprintExportHelper.set_runtime_blueprint_tree(tree)
            return tree

        runtime_tree_name = BlueprintExportHelper.runtime_blueprint_tree_name
        if runtime_tree_name:
            tree = bpy.data.node_groups.get(runtime_tree_name)
            if BlueprintExportHelper._is_valid_blueprint_tree(tree):
                return tree

        tree_name = GlobalConfig.get_workspace_name()
        if not tree_name:
            return None
        
        tree = bpy.data.node_groups.get(tree_name)
        if BlueprintExportHelper._is_valid_blueprint_tree(tree):
            BlueprintExportHelper.set_runtime_blueprint_tree(tree)
            return tree

        return None

    @staticmethod
    def get_selected_blueprint_tree(selected_name="", context=None):
        preferred_name = BlueprintExportHelper.get_preferred_blueprint_name(
            selected_name=selected_name,
            context=context,
        )
        return BlueprintExportHelper.get_blueprint_tree_by_name(preferred_name)

    @staticmethod
    def get_tree_submesh_names(tree=None, context=None):
        current_tree = tree or BlueprintExportHelper.get_current_blueprint_tree(context=context)
        if not BlueprintExportHelper._is_valid_blueprint_tree(current_tree):
            return []

        return [str(item.name) for item in getattr(current_tree, "ssmt_submesh_items", []) if getattr(item, "name", "")]

    @staticmethod
    def set_tree_submesh_names(submesh_names, tree=None, context=None):
        current_tree = tree or BlueprintExportHelper.get_current_blueprint_tree(context=context)
        if not BlueprintExportHelper._is_valid_blueprint_tree(current_tree):
            return []

        normalized_names = []
        seen_names = set()
        for submesh_name in submesh_names:
            normalized_name = str(submesh_name or "").strip()
            if not normalized_name or normalized_name in seen_names:
                continue
            seen_names.add(normalized_name)
            normalized_names.append(normalized_name)

        current_tree.ssmt_submesh_items.clear()
        for submesh_name in normalized_names:
            item = current_tree.ssmt_submesh_items.add()
            item.name = submesh_name

        BlueprintExportHelper.set_runtime_blueprint_tree(current_tree)
        return normalized_names

    @staticmethod
    def refresh_tree_submesh_list(tree=None, context=None):
        current_tree = tree or BlueprintExportHelper.get_current_blueprint_tree(context=context)
        if not BlueprintExportHelper._is_valid_blueprint_tree(current_tree):
            return []

        all_display_names = []
        lod_submesh_dict = WorkSpaceHelper.get_lod_submesh_folderpath_dict()
        if lod_submesh_dict:
            for lod_name, submesh_folder_paths in lod_submesh_dict.items():
                lod_folder_path = os.path.join(GlobalConfig.path_workspace_folder(), lod_name)
                drawib_aliasname_dict = WorkSpaceHelper.get_drawib_aliasname_dict_for_path(lod_folder_path)
                for folder_path in submesh_folder_paths:
                    bare_name = os.path.basename(folder_path)
                    display_name = lod_name + "." + WorkSpaceHelper.get_display_submesh_name(
                        bare_name,
                        drawib_aliasname_dict=drawib_aliasname_dict,
                    )
                    all_display_names.append(display_name)
        else:
            # 兼容旧版无LOD结构
            drawib_aliasname_dict = WorkSpaceHelper.get_drawib_aliasname_dict()
            all_display_names = [
                WorkSpaceHelper.get_display_submesh_name(
                    os.path.basename(folder_path),
                    drawib_aliasname_dict=drawib_aliasname_dict,
                )
                for folder_path in WorkSpaceHelper.get_submesh_folderpath_list()
            ]

        return BlueprintExportHelper.set_tree_submesh_names(all_display_names, tree=current_tree)

    @staticmethod
    def find_node_in_all_blueprints(node_name):
        """在所有蓝图中查找指定名称的节点"""
        for node_group in bpy.data.node_groups:
            if node_group.bl_idname == 'SSMTBlueprintTreeType':
                node = node_group.nodes.get(node_name)
                if node:
                    return node
        return None

    @staticmethod
    def get_node_from_bl_idname(tree, node_type:str):
        """在树中查找输出节点 (假设只有一个)"""
        if not tree:
            return None
        for node in tree.nodes:
            if node.bl_idname == node_type:
                return node
        return None
    
    @staticmethod
    def get_nodes_from_bl_idname(tree, node_type:str):
        """在树中查找所有匹配的节点"""
        if not tree:
            return []
        nodes = []
        for node in tree.nodes:
            if node.bl_idname == node_type:
                nodes.append(node)
        return nodes

    @staticmethod
    def get_active_mod_panel_nodes(context=None, tree=None):
        current_tree = tree or BlueprintExportHelper.get_current_blueprint_tree(context=context)
        if not current_tree:
            return []

        panel_nodes = BlueprintExportHelper.get_nodes_from_bl_idname(current_tree, 'SSMTNode_ModPanel')
        return [node for node in panel_nodes if not getattr(node, "mute", False)]

    @staticmethod
    def has_mod_panel_node(context=None, tree=None):
        return len(BlueprintExportHelper.get_active_mod_panel_nodes(context=context, tree=tree)) > 0

    @staticmethod
    def is_mod_panel_flow_effect_enabled(context=None, tree=None):
        panel_nodes = BlueprintExportHelper.get_active_mod_panel_nodes(context=context, tree=tree)
        if not panel_nodes:
            return False
        return any(getattr(node, "enable_flow_effect", True) for node in panel_nodes)
    
    @staticmethod
    def get_connected_groups(output_node):
        """
        获取连接到输出节点的所有 Group 节点。
        按照 Input 插槽的顺序返回列表。
        """
        connected_groups = []
        if not output_node:
            return connected_groups
            
        # 遍历 Output 节点的所有输入插槽
        for socket in output_node.inputs:
            if socket.is_linked:
                # 遍历连线 (通常一个插槽只有一个连线，但数据结构是列表)
                for link in socket.links:
                    source_node = link.from_node
                    # 确保来源是 Group 节点
                    if source_node.bl_idname == 'SSMTNode_Object_Group':
                         connected_groups.append(source_node)
        
        return connected_groups
    
    @staticmethod
    def get_connected_nodes(current_node):
        """
        按照插槽顺序返回所有连接的节点
        """
        connected_groups = []
        if not current_node:
            return connected_groups
            
        # 遍历 Output 节点的所有输入插槽
        for socket in current_node.inputs:
            if socket.is_linked:
                # 遍历连线 (通常一个插槽只有一个连线，但数据结构是列表)
                for link in socket.links:
                    source_node = link.from_node
                    connected_groups.append(source_node)
        
        return connected_groups
    
    @staticmethod
    def get_objects_from_group(group_node):
        """
        获取连接到某个 Group 节点的所有 Object Info 节点中的物体名称信息。
        """
        objects_info = []
        if not group_node:
            return objects_info

        for socket in group_node.inputs:
            if socket.is_linked:
                for link in socket.links:
                    source_node = link.from_node
                    # 确保来源是 Object Info 节点
                    if source_node.bl_idname == 'SSMTNode_Object_Info':
                        draw_ib = ""
                        submesh_name = str(getattr(source_node, "submesh_name", "") or "")
                        if submesh_name:
                            draw_ib = DrawCallModel(obj_name=str(getattr(source_node, "object_name", "") or ""), submesh_name=submesh_name).match_draw_ib

                        info = {
                            "object_name": source_node.object_name,
                            "draw_ib": draw_ib,
                            "component": source_node.component,
                            "node": source_node
                        }
                        objects_info.append(info)
        return objects_info
    

    @staticmethod
    def get_current_shapekeyname_mkey_dict(context=None):
        """获取当前蓝图及所有嵌套蓝图中所有 ShapeKey 节点的形态键名称和按键列表"""
        tree = BlueprintExportHelper.get_current_blueprint_tree(context=context)
        if not tree:
            return {}
        
        shapekey_name_mkey_dict = {}
        visited_blueprints = set()
        key_index = 0
        
        def collect_shapekey_nodes(current_tree):
            """递归收集形态键节点"""
            nonlocal key_index
            
            if current_tree.name in visited_blueprints:
                return
            visited_blueprints.add(current_tree.name)
            
            shapekey_output_node = None
            for node in current_tree.nodes:
                if node.bl_idname == 'SSMTNode_ShapeKey_Output':
                    shapekey_output_node = node
                    break
            
            if not shapekey_output_node:
                return
            
            shapekey_nodes = BlueprintExportHelper.get_connected_nodes(shapekey_output_node)
            
            for shapekey_node in shapekey_nodes:
                if shapekey_node.mute:
                    continue
                if shapekey_node.bl_idname != 'SSMTNode_ShapeKey':
                    continue
                
                shapekey_name = shapekey_node.shapekey_name
                key = shapekey_node.key
                comment = getattr(shapekey_node, 'comment', '')

                m_key = M_Key()
                m_key.key_name = "$shapekey" + str(key_index)
                m_key.initialize_value = 0
                m_key.initialize_vk_str = key
                m_key.comment = comment

                shapekey_name_mkey_dict[shapekey_name] = m_key
                key_index += 1
            
  
        
        collect_shapekey_nodes(tree)
        return shapekey_name_mkey_dict

    @staticmethod
    def get_datatype_node_info(context=None):
        """获取当前蓝图及所有嵌套蓝图中连接到输出节点的数据类型节点信息"""
        tree = BlueprintExportHelper.get_current_blueprint_tree(context=context)
        if not tree:
            return None
        
        visited_blueprints = set()
        datatype_nodes = []
        
        def collect_datatype_nodes(current_tree):
            """递归收集数据类型节点"""
            if current_tree.name in visited_blueprints:
                return
            visited_blueprints.add(current_tree.name)
            
            output_node = None
            for node in current_tree.nodes:
                if node.bl_idname == 'SSMTNode_Result_Output':
                    output_node = node
                    break
            
            if output_node:
                nodes = BlueprintExportHelper._find_datatype_nodes_connected_to_output(output_node)
                datatype_nodes.extend(nodes)

        
        collect_datatype_nodes(tree)
        
        if not datatype_nodes:
            return None
        
        node_info_list = []
        for node in datatype_nodes:
            node_info_list.append({
                "draw_ib_match": node.draw_ib_match,
                "tmp_json_path": node.tmp_json_path,
                "loaded_data": node.loaded_data,
                "node": node
            })
        
        return node_info_list
    
    @staticmethod
    def _find_datatype_nodes_connected_to_output(node, visited=None):
        """递归查找连接到输出节点的所有数据类型节点"""
        if visited is None:
            visited = set()
        
        if node.name in visited:
            return []
        
        if node.mute:
            return []
        
        visited.add(node.name)
        datatype_nodes = []
        
        # 如果当前节点是数据类型节点，添加到列表
        if node.bl_idname == 'SSMTNode_DataType':
            datatype_nodes.append(node)
        
        # 递归查找连接的节点
        connected_nodes = BlueprintExportHelper.get_connected_nodes(node)
        for connected_node in connected_nodes:
            datatype_nodes.extend(BlueprintExportHelper._find_datatype_nodes_connected_to_output(connected_node, visited))
        
        return datatype_nodes
    



            
        