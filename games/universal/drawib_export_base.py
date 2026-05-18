from ...model.blueprint_model import BluePrintModel
from ...blueprint.blueprint_export_helper import BlueprintExportHelper
from ...model.draw_call_model import DrawCallModel
from ...model.submesh_model import SubMeshModel
from ...model.drawib_model import DrawIBModel
from ...common.buffer_export_helper import BufferExportHelper

import os


class DrawIBExportBase:
    @staticmethod
    def parse_submesh_model_list_from_blueprint_model(blueprint_model: BluePrintModel) -> list[SubMeshModel]:
        '''
        从蓝图中解析出一个Submesh Model列表
        如果是Submesh可以直接导出的游戏，例如EFMI，则调用处拿到后直接导出
        如果是Submesh需要组合成DrawIB级别再导出，例如米游、Unity系列游戏，则调用处拿到后再进行整合
        这样拆分流程更加清晰，逻辑更容易理解
        '''
        submesh_model_list: list[SubMeshModel] = []

        # 根据唯一标识符，把相同的DrawCallModel分在一起，形成SubMeshModel
        draw_call_model_dict: dict[str, list[DrawCallModel]] = {}

        # 拿到BlueprintModel后，开始解析SubMeshModel列表
        for draw_call_model in blueprint_model.ordered_draw_obj_data_model_list:
            # 获取独立标识
            unique_str = draw_call_model.get_unique_str()

            # 根据unique_str，加入到字典中，这样每个unique_str都对应一个DrawCallModel列表，用于初始化SubMeshModel
            draw_call_model_list = draw_call_model_dict.get(unique_str, [])
            draw_call_model_list.append(draw_call_model)
            draw_call_model_dict[unique_str] = draw_call_model_list

        # 根据draw_call_model_dict，初始化SubMeshModel列表
        for unique_str, draw_call_model_list in draw_call_model_dict.items():
            submesh_model = SubMeshModel(drawcall_model_list=draw_call_model_list)
            submesh_model_list.append(submesh_model)

        return submesh_model_list

    @staticmethod
    def parse_drawib_model_list_from_blueprint_model(blueprint_model: BluePrintModel, combine_ib: bool) -> list[DrawIBModel]:
        '''
        从蓝图中解析出一个DrawIB Model列表
        适用于米游、Unity等等常见的需要将多个SubMesh组合成一个DrawIB进行导出的游戏
        '''
        drawib_model_list: list[DrawIBModel] = []

        # 先把Submesh Model按照DrawIB分在一起
        draw_ib_submesh_model_list_dict: dict[str, list[SubMeshModel]] = {}
        for submesh_model in DrawIBExportBase.parse_submesh_model_list_from_blueprint_model(blueprint_model):
            draw_ib = submesh_model.match_draw_ib
            tmp_submesh_model_list = draw_ib_submesh_model_list_dict.get(draw_ib, [])
            tmp_submesh_model_list.append(submesh_model)
            draw_ib_submesh_model_list_dict[draw_ib] = tmp_submesh_model_list

        # 随后直接用SubmeshModelList来初始化DrawIBModel
        for draw_ib, submesh_model_list in draw_ib_submesh_model_list_dict.items():
            drawib_model = DrawIBModel(submesh_model_list=submesh_model_list, combine_ib=combine_ib)
            drawib_model_list.append(drawib_model)

        return drawib_model_list

    def __init__(self, blueprint_model: BluePrintModel, combine_ib: bool = False):
        self.blueprint_model = blueprint_model
        self.drawib_model_list: list[DrawIBModel] = DrawIBExportBase.parse_drawib_model_list_from_blueprint_model(
            blueprint_model=blueprint_model,
            combine_ib=combine_ib,
        )
        # 从蓝图树中读取别名字典，并应用到每个 DrawIBModel 的 submesh_model.display_str
        alias_dict = BlueprintExportHelper.get_alias_dict()
        if alias_dict:
            for drawib_model in self.drawib_model_list:
                drawib_model.apply_alias_dict(alias_dict)

    def generate_buffer_files(self, output_folder: str):
        for drawib_model in self.drawib_model_list:
            draw_ib = drawib_model.draw_ib

            if drawib_model.combine_ib:
                ib_filename = draw_ib + "-Index.buf"
                ib_filepath = os.path.join(output_folder, ib_filename)
                BufferExportHelper.write_buf_ib_r32_uint(drawib_model.ib, ib_filepath)
            else:
                for submesh_model in drawib_model.submesh_model_list:
                    ib = drawib_model.submesh_ib_dict.get(submesh_model.unique_str, [])
                    ib_filename = submesh_model.display_str + "-Index.buf"
                    ib_filepath = os.path.join(output_folder, ib_filename)
                    BufferExportHelper.write_buf_ib_r32_uint(ib, ib_filepath)

            for category, category_buf in drawib_model.category_buffer_dict.items():
                category_buf_filename = draw_ib + "-" + category + ".buf"
                category_buf_filepath = os.path.join(output_folder, category_buf_filename)
                with open(category_buf_filepath, 'wb') as file_obj:
                    category_buf.tofile(file_obj)

            for shapekey_name, shapekey_buf in drawib_model.shapekey_name_bytelist_dict.items():
                shapekey_buf_filename = draw_ib + "-Position." + shapekey_name + ".buf"
                shapekey_buf_filepath = os.path.join(output_folder, shapekey_buf_filename)
                with open(shapekey_buf_filepath, 'wb') as file_obj:
                    shapekey_buf.tofile(file_obj)

    def export(self):
        raise NotImplementedError()