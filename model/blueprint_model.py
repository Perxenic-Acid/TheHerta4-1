
import bpy
import copy

from ..utils.log_utils import LOG

from ..common.m_key import M_Key
from .draw_call_model import DrawCallModel
from .submesh_model import SubMeshModel
from .drawib_model import DrawIBModel
from ..common.global_config import GlobalConfig
from ..blueprint.blueprint_export_helper import BlueprintExportHelper

from ..blueprint.blueprint_node_obj import SSMTNode_Object_Group, SSMTNode_SwitchKey, SSMTNode_Object_Info, SSMTNode_Result_Output


class BluePrintModel:

    
    def __init__(self, tree=None, context=None):
        # 全局按键名称和按键属性字典
        self.keyname_mkey_dict:dict[str,M_Key] = {} 

        # 全局obj_model列表，主要是obj_model里装了每个obj的生效条件。
        self.ordered_draw_obj_data_model_list:list[DrawCallModel] = [] 

        # 从输出节点开始递归解析所有的节点
        tree = tree or BlueprintExportHelper.get_current_blueprint_tree(context=context)
        if not tree:
            raise ValueError("未找到当前蓝图树，请先打开正确的蓝图编辑器")

        print(tree)
        output_node = BlueprintExportHelper.get_node_from_bl_idname(tree, SSMTNode_Result_Output.bl_idname)
        if not output_node:
            raise ValueError("当前蓝图缺少 Generate Mod 输出节点")

        print("BluePrintModel: 输出节点连接的节点数量: " + str(len(BlueprintExportHelper.get_connected_nodes(output_node))))
        self.parse_current_node(output_node, [])

    def parse_current_node(self, current_node:bpy.types.Node, chain_key_list:list[M_Key]):
        for unknown_node in BlueprintExportHelper.get_connected_nodes(current_node):
            self.parse_single_node(unknown_node, chain_key_list)

    def parse_single_node(self, unknown_node:bpy.types.Node, chain_key_list:list[M_Key]):
        '''
        这个是递归方法
        解析当前节点，获取其连接的所有节点的信息,分类进行解析
        '''
        
        if unknown_node.mute:
            return

        if unknown_node.bl_idname == SSMTNode_Object_Group.bl_idname:
            # 如果是单纯的分组节点，则不进行任何处理直接传递下去
            self.parse_current_node(unknown_node, chain_key_list)

        elif unknown_node.bl_idname == SSMTNode_SwitchKey.bl_idname:
            # 如果是按键切换节点，则该节点所有的分支节点，并逐个处理
            # 这里我们直接遍历所有的inputs，而不是get_connected_nodes，
            # 因为get_connected_nodes会忽略未连接(空)的端口，导致分支数量计算错误
            
            # 获取有效的分支数量（除去最后一个为了方便添加而存在的空端口）
            # 只有当最后一个端口确实没有连接的时候才能排除，虽然Node定义里是这样写的逻辑，但最好判断一下link
            # valid_input_sockets = unknown_node.inputs[:-1] if (len(unknown_node.inputs) > 1 and not unknown_node.inputs[-1].is_linked) else unknown_node.inputs[:]
            
            # 修正：对于SwitchKey节点，所有的Input都是有效的分支，因为可以手动添加/删除Socket，且空Socket代表空状态（什么都不显示）
            valid_input_sockets = unknown_node.inputs[:]
            
            # 如果所有端口都没有连接，则直接跳过
            is_all_socket_linked = False
            for sock in valid_input_sockets:
                if sock.is_linked:
                    is_all_socket_linked = True
                    break
            
            if not is_all_socket_linked:
                # 如果没有任何连接，不做处理
                return

            if len(valid_input_sockets) == 1:
                # 如果只有 1 个有效分支端口：
                # 1. 如果它是连接的 -> 视为 Group 节点透传
                # 2. 如果它是断开的 -> 视为无意义，不做处理(上面all_socket_linked已过滤)
                if valid_input_sockets[0].is_linked:
                        for link in valid_input_sockets[0].links:
                            self.parse_single_node(link.from_node, chain_key_list)
            else:
                # 如果有 > 1 个有效分支端口，则必须创建 Key，哪怕某些端口是空的（代表空分支）
                m_key = M_Key()
                current_add_key_index = len(self.keyname_mkey_dict.keys())
                m_key.key_name = "$swapkey" + str(GlobalConfig.global_key_index)

                # 值列表就是分支索引的列表 [0, 1, 2, ...]
                m_key.value_list = list(range(len(valid_input_sockets)))

                m_key.initialize_vk_str = unknown_node.key_name
                m_key.initialize_value = 0  # 默认选择第一个分支

                # 设置备注信息
                m_key.comment = getattr(unknown_node, 'comment', '')

                # 创建的key加入全局key列表
                self.keyname_mkey_dict[m_key.key_name] = m_key

                # 更新全局key索引
                if len(self.keyname_mkey_dict.keys()) > current_add_key_index:
                    GlobalConfig.global_key_index = GlobalConfig.global_key_index + 1

                # 逐个处理每个分支节点（包括空分支）
                key_tmp_value = 0
                for socket in valid_input_sockets:
                    # 无论这个 socket 是否连接了节点，或者是空的，都对应一个 key value
                    
                    if socket.is_linked:
                        # 如果连接了节点，则需要把这个 value 对应的 key 传递下去解析
                        for link in socket.links:
                            # 为每个分支创建一个临时key传递下去
                            chain_tmp_key = copy.deepcopy(m_key)
                            chain_tmp_key.tmp_value = key_tmp_value # 当前分支对应的 value

                            tmp_chain_key_list = copy.deepcopy(chain_key_list)
                            tmp_chain_key_list.append(chain_tmp_key)

                            # 递归解析连接的节点
                            # 注意：这里我们调用 parse_single_node，因为我们直接找到了目标节点
                            self.parse_single_node(link.from_node, tmp_chain_key_list)
                    else:
                        # 如果是空端口（没有连接），则代表这个 value 对应的是空物体
                        # 我们不需要做任何 parse 操作，因为没有任何 obj 需要在这个条件下生成
                        # 这个 key value 存在于 key.value_list 中，但没有任何 obj 的 condition 会匹配到这个 value
                        # 这样就实现了“切换到这个分支时，什么都不显示”的效果
                        pass

                    key_tmp_value = key_tmp_value + 1


        elif unknown_node.bl_idname == SSMTNode_Object_Info.bl_idname:
            obj = bpy.data.objects.get(unknown_node.object_name)

            # 解析蓝图时提前过滤空网格，避免后续导出阶段触发全部顶点组已被锁定错误。
            if obj is None or obj.type != 'MESH' or obj.data is None or len(obj.data.vertices) == 0:
                LOG.info("BluePrintModel: 跳过空网格或无效对象: " + str(unknown_node.object_name))
                return

            obj_model = DrawCallModel(
                obj_name=unknown_node.object_name,
                submesh_name=getattr(unknown_node, 'submesh_name', ''),
            )
            
            if hasattr(unknown_node, 'original_object_name') and unknown_node.original_object_name:
                obj_model.display_name = unknown_node.original_object_name

            obj_model.work_key_list = copy.deepcopy(chain_key_list)
            
            self.ordered_draw_obj_data_model_list.append(obj_model)

    def parse_submesh_model_list(self) -> list[SubMeshModel]:
        """
        从当前 BluePrintModel 解析出 SubMeshModel 列表。
        将相同 submesh_name 的 DrawCallModel 分在一起，每个组创建一个 SubMeshModel。
        """
        from ..workspace.ssmt_workspace import WorkSpaceModel

        submesh_model_list: list[SubMeshModel] = []
        draw_call_model_dict: dict[str, list[DrawCallModel]] = {}

        for draw_call_model in self.ordered_draw_obj_data_model_list:
            submesh_name = draw_call_model.get_submesh_name()
            draw_call_model_list = draw_call_model_dict.get(submesh_name, [])
            draw_call_model_list.append(draw_call_model)
            draw_call_model_dict[submesh_name] = draw_call_model_list

        # 创建 WorkSpaceModel 用于修正新格式的 IndexCount/FirstIndex
        workspace_model = WorkSpaceModel()

        for submesh_name, draw_call_model_list in draw_call_model_dict.items():
            submesh_model = SubMeshModel(drawcall_model_list=draw_call_model_list)
            # 新格式下 match_index_count/match_first_index 初始为 -1，用 WorkSpaceModel 修正
            submesh_model.fix_indices_from_workspace(workspace_model)
            submesh_model_list.append(submesh_model)

        # 按 match_first_index 升序排序，确保 DrawIB-0 (FirstIndex 最小的) 排在前面
        # match_first_index 为 -1（未设置）的排到最后
        submesh_model_list.sort(key=lambda sm: sm.match_first_index if sm.match_first_index >= 0 else float('inf'))

        return submesh_model_list

    def parse_drawib_model_list(self, combine_ib: bool = False) -> list[DrawIBModel]:
        """
        从当前 BluePrintModel 解析出 DrawIBModel 列表。
        适用于需要将多个 SubMesh 组合成一个 DrawIB 导出的游戏。
        """
        drawib_model_list: list[DrawIBModel] = []
        draw_ib_submesh_model_list_dict: dict[str, list[SubMeshModel]] = {}

        for submesh_model in self.parse_submesh_model_list():
            draw_ib = submesh_model.match_draw_ib
            tmp_submesh_model_list = draw_ib_submesh_model_list_dict.get(draw_ib, [])
            tmp_submesh_model_list.append(submesh_model)
            draw_ib_submesh_model_list_dict[draw_ib] = tmp_submesh_model_list

        for draw_ib, submesh_model_list in draw_ib_submesh_model_list_dict.items():
            drawib_model = DrawIBModel(submesh_model_list=submesh_model_list, combine_ib=combine_ib)
            drawib_model_list.append(drawib_model)

        return drawib_model_list
