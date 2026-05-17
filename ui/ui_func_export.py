import bpy

from ..utils.timer_utils import TimerUtils
from ..utils.command_utils import CommandUtils
from ..utils.translate_utils import rpt_

from ..common.global_config import GlobalConfig
from ..common.global_config import GlobalConfig
from ..common.global_config import LogicName

from .universal.efmi import ExportEFMI
from .universal.gimi import ExportGIMI
from .universal.himi import ExportHIMI
from .universal.identityv import ExportIdentityV
from .universal.snowbreak import ExportSnowBreak
from .universal.srmi import ExportSRMI
from .universal.unity import ExportUnity
from .wwmi.wwmi_export import ExportWWMI
from .universal.ntemi import ExportNTEMI
from .universal.yysls import ExportYYSLS
from .universal.zzmi import ExportZZMI

from ..blueprint.blueprint_model import BluePrintModel
from ..blueprint.blueprint_export_helper import BlueprintExportHelper
from ..blueprint.blueprint_node_obj import refresh_all_object_info_nodes


def generate_mod_from_tree(tree, context, report_callback):
    if not tree:
        report_callback({'ERROR'}, "未找到有效的蓝图")
        return {'CANCELLED'}

    TimerUtils.Start("GenerateMod Mod")

    # 每次生成 Mod 都必须重置全局按键计数，
    # 否则会沿用上一次导出的 $swapkey / $active 索引，导致本次 ini 变量编号错乱。
    GlobalConfig.initialize_key_count()
    BlueprintExportHelper.set_runtime_blueprint_tree(tree)

    # 导出前强制同步一次 Object Info 节点。
    # 蓝图后续解析主要仍读取 node.object_name，
    # 因此必须先通过持久 object_id 把改名后的真实物体名称回写到节点上，
    # 避免用户改名后蓝图仍使用旧名称导出。
    refresh_summary = refresh_all_object_info_nodes(tree=tree, source="export")
    if refresh_summary["missing_count"] > 0:
        report_callback(
            {'WARNING'},
            f"导出前刷新了 {refresh_summary['updated_count']} 个物体节点，但有 {refresh_summary['missing_count']} 个节点未找到对应物体",
        )

    try:
        blueprint_model = BluePrintModel(tree=tree, context=context)
    except ValueError as error:
        TimerUtils.End("GenerateMod Mod")
        report_callback({'ERROR'}, str(error))
        return {'CANCELLED'}

    print("当前蓝图: " + str(blueprint_model))

    # 2.根据不同的逻辑进行不同的导出器初始化和调用
    if GlobalConfig.logic_name == LogicName.EFMI:
        export_efmi = ExportEFMI(blueprint_model=blueprint_model)
        export_efmi.export()
    elif GlobalConfig.logic_name == LogicName.GIMI:
        export_gimi = ExportGIMI(blueprint_model=blueprint_model)
        export_gimi.export()
    elif GlobalConfig.logic_name == LogicName.HIMI:
        export_himi = ExportHIMI(blueprint_model=blueprint_model)
        export_himi.export()
    elif GlobalConfig.logic_name == LogicName.IdentityV:
        export_identityv = ExportIdentityV(blueprint_model=blueprint_model)
        export_identityv.export()
    elif GlobalConfig.logic_name == LogicName.SRMI:
        export_srmi = ExportSRMI(blueprint_model=blueprint_model)
        export_srmi.export()
    elif GlobalConfig.logic_name == LogicName.ZZMI:
        export_zzmi = ExportZZMI(blueprint_model=blueprint_model)
        export_zzmi.export()
    elif GlobalConfig.logic_name == LogicName.WWMI:
        export_wwmi = ExportWWMI(blueprint_model=blueprint_model)
        export_wwmi.export()
    elif GlobalConfig.logic_name == LogicName.NTEMI:
        export_ntemi = ExportNTEMI(blueprint_model=blueprint_model)
        export_ntemi.export()
    elif GlobalConfig.logic_name == LogicName.SnowBreak:
        export_snowbreak = ExportSnowBreak(blueprint_model=blueprint_model)
        export_snowbreak.export()
    elif GlobalConfig.logic_name == LogicName.YYSLS:
        export_yysls = ExportYYSLS(blueprint_model=blueprint_model)
        export_yysls.export()
    elif GlobalConfig.logic_name == LogicName.Naraka or GlobalConfig.logic_name == LogicName.NarakaM or GlobalConfig.logic_name == LogicName.GF2 or GlobalConfig.logic_name == LogicName.AILIMIT:
        export_unity = ExportUnity(blueprint_model=blueprint_model)
        export_unity.export()
    else:
        TimerUtils.End("GenerateMod Mod")
        report_callback({'ERROR'}, "当前游戏预设暂不支持生成Mod")
        return {'FINISHED'}

    TimerUtils.End("GenerateMod Mod")
    report_callback({'INFO'}, rpt_("生成Mod成功！"))
    CommandUtils.OpenGeneratedModFolder()
    return {'FINISHED'}


class SSMTGenerateModBlueprint(bpy.types.Operator):
    bl_idname = "ssmt.generate_mod_blueprint"
    bl_label = "生成Mod"
    bl_description = "根据当前工作空间对应的蓝图架构生成对应的Mod文件"
    bl_options = {'REGISTER','UNDO'}

    def execute(self, context):
        tree = BlueprintExportHelper.get_current_blueprint_tree(context=context)
        if not tree:
            self.report({'ERROR'}, "未找到当前蓝图，请在蓝图编辑器中点击“生成Mod”")
            return {'CANCELLED'}
        return generate_mod_from_tree(tree=tree, context=context, report_callback=self.report)


class SSMTGenerateSelectedBlueprintMod(bpy.types.Operator):
    bl_idname = "ssmt.generate_selected_blueprint_mod"
    bl_label = "生成Mod"
    bl_description = "根据当前选中的蓝图快捷生成对应的Mod文件"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        global_properties = getattr(getattr(context, "scene", None), "global_properties", None)
        selected_name = getattr(global_properties, "selected_blueprint_name", "") if global_properties else ""

        tree = BlueprintExportHelper.get_selected_blueprint_tree(
            selected_name=selected_name,
            context=context,
        )
        if not tree:
            self.report({'ERROR'}, "请选择有效的蓝图")
            return {'CANCELLED'}

        if global_properties and global_properties.selected_blueprint_name != tree.name:
            global_properties.selected_blueprint_name = tree.name

        return generate_mod_from_tree(tree=tree, context=context, report_callback=self.report)
    
def register():
    bpy.utils.register_class(SSMTGenerateModBlueprint)
    bpy.utils.register_class(SSMTGenerateSelectedBlueprintMod)


def unregister():
    bpy.utils.unregister_class(SSMTGenerateSelectedBlueprintMod)
    bpy.utils.unregister_class(SSMTGenerateModBlueprint)

