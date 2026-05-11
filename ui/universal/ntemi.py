import os

from ...blueprint.blueprint_model import BluePrintModel
from ...common.drawib_model import DrawIBModel
from ...common.global_config import GlobalConfig
from ...common.global_properties import GlobalProterties
from ...common.buffer_export_helper import BufferExportHelper
from ...common.global_key_count_helper import GlobalKeyCountHelper
from ...common.m_ini_builder import M_IniBuilder, M_IniSection, M_SectionType
from ...common.m_ini_helper import M_IniHelper
from ...common.m_ini_helper_gui import M_IniHelperGUI
from .export_helper import ExportHelper
from ...blueprint.blueprint_export_helper import BlueprintExportHelper
from ...common.workspace_helper import WorkSpaceHelper

from dataclasses import dataclass, field


@dataclass
class ExportNTEMI:

    blueprint_model: BluePrintModel
    drawib_model_list: list[DrawIBModel] = field(default_factory=list, init=False)

    def __post_init__(self):
        self.drawib_model_list = ExportHelper.parse_drawib_model_list_from_blueprint_model(
            self.blueprint_model, combine_ib=False,
        )
        print(f"ExportNTEMI: 解析完成，共 {len(self.drawib_model_list)} 个 DrawIBModel")

        alias_dict = BlueprintExportHelper.get_alias_dict()
        if alias_dict:
            for drawib_model in self.drawib_model_list:
                drawib_model.apply_alias_dict(alias_dict)
                for submesh_model in drawib_model.submesh_model_list:
                    unique_str = submesh_model.unique_str
                    alias = str(alias_dict.get(unique_str, "") or "").strip()
                    if alias:
                        lod_name, _ = WorkSpaceHelper.parse_lod_unique_str(unique_str)
                        submesh_model.display_str = (lod_name + "." + alias) if lod_name else alias

    def generate_buffer_files(self):
        buf_output_folder = GlobalConfig.path_generatemod_buffer_folder()

        for submesh_model in self._iter_all_submesh_models():
            # Write index buffer (per submesh, NTEMI uses submesh-level IB files)
            ib_filename = submesh_model.display_str + "-Index.buf"
            ib_filepath = os.path.join(buf_output_folder, ib_filename)
            BufferExportHelper.write_buf_ib_r32_uint(submesh_model.ib, ib_filepath)

            # Write category buffers per submesh
            for category_name, category_buf in submesh_model.category_buffer_dict.items():
                category_buf_filename = (
                    submesh_model.display_str + "-" + category_name + ".buf"
                )
                category_buf_filepath = os.path.join(
                    buf_output_folder, category_buf_filename
                )
                with open(category_buf_filepath, "wb") as f:
                    category_buf.tofile(f)

    def generate_ini_file(self):
        ini_builder = M_IniBuilder()

        drawib_drawibmodel_dict: dict[str, DrawIBModel] = {}
        draw_ib_active_index_dict: dict[str, int] = {}
        for index, drawib_model in enumerate(self.drawib_model_list):
            draw_ib = drawib_model.draw_ib
            drawib_drawibmodel_dict[draw_ib] = drawib_model
            draw_ib_active_index_dict[draw_ib] = index

        self._add_constants_section(ini_builder)
        self._add_present_section(ini_builder)
        self._add_commandlist_ntmi_sections(ini_builder)
        self._add_texture_override_ib_sections(
            ini_builder, drawib_drawibmodel_dict, draw_ib_active_index_dict,
        )
        self._add_resource_buffer_sections(ini_builder, drawib_drawibmodel_dict)

        if not GlobalProterties.forbid_auto_texture_ini():
            self._add_resource_texture_sections(ini_builder)

        # Auto texture handling
        M_IniHelper.generate_hash_style_texture_ini(
            ini_builder=ini_builder,
            drawib_drawibmodel_dict=drawib_drawibmodel_dict,
        )

        for drawib_model in self.drawib_model_list:
            M_IniHelper.move_slot_style_textures(draw_ib_model=drawib_model)

        GlobalKeyCountHelper.generated_mod_number = len(self.drawib_model_list)
        M_IniHelper.add_branch_key_sections(
            ini_builder=ini_builder,
            key_name_mkey_dict=self.blueprint_model.keyname_mkey_dict,
        )
        M_IniHelperGUI.add_branch_mod_gui_section(
            ini_builder=ini_builder,
            key_name_mkey_dict=self.blueprint_model.keyname_mkey_dict,
        )

        ini_filepath = os.path.join(
            GlobalConfig.path_generate_mod_folder(),
            GlobalConfig.get_workspace_name() + ".ini",
        )
        ini_builder.save_to_file(ini_filepath)

    def _add_constants_section(self, ini_builder: M_IniBuilder):
        constants_section = M_IniSection(M_SectionType.Constants)
        constants_section.append("[Constants]")
        constants_section.append("global $ntemi_mod_enabled = 0")

        if GlobalProterties.generate_branch_mod_gui():
            constants_section.append("global $ActiveCharacter = 1")

        constants_section.new_line()
        ini_builder.append_section(constants_section)

    def _add_present_section(self, ini_builder: M_IniBuilder):
        present_section = M_IniSection(M_SectionType.Present)
        present_section.append("[Present]")
        present_section.append("if $ntemi_mod_enabled")
        present_section.append("  run = CommandListNTMISetupResources")
        present_section.append("endif")
        present_section.new_line()
        ini_builder.append_section(present_section)

    def _add_commandlist_ntmi_sections(self, ini_builder: M_IniBuilder):
        cmd_list_section = M_IniSection(M_SectionType.CommandList)
        cmd_list_section.append("[CommandListNTMISetupResources]")
        cmd_list_section.append("$ntemi_mod_enabled = 1")
        cmd_list_section.new_line()
        ini_builder.append_section(cmd_list_section)

    def _add_texture_override_ib_sections(
        self,
        ini_builder: M_IniBuilder,
        drawib_drawibmodel_dict: dict[str, DrawIBModel],
        draw_ib_active_index_dict: dict[str, int],
    ):
        texture_override_ib_section = M_IniSection(M_SectionType.TextureOverrideIB)

        for submesh_model in self._iter_all_submesh_models():
            drawib_model = drawib_drawibmodel_dict.get(submesh_model.match_draw_ib)
            if drawib_model is None:
                continue
            active_index = draw_ib_active_index_dict.get(submesh_model.match_draw_ib, 0)
            part_name = drawib_model.get_submesh_part_name(submesh_model)

            texture_override_ib_section.append(
                "[TextureOverride_"
                + drawib_model.get_submesh_texture_override_suffix(submesh_model)
                + "]"
            )
            texture_override_ib_section.append(
                "hash = " + submesh_model.match_draw_ib
            )
            texture_override_ib_section.append(
                "match_first_index = " + str(submesh_model.match_first_index)
            )
            texture_override_ib_section.append(
                "match_index_count = " + str(submesh_model.match_index_count)
            )
            texture_override_ib_section.append("handling = skip")

            # Override IB and VB slots
            ib_resource_name = drawib_model.get_submesh_ib_resource_name(submesh_model)
            texture_override_ib_section.append("ib = " + ib_resource_name)

            for category in submesh_model.category_buffer_dict.keys():
                category_slot = submesh_model.d3d11_game_type.CategoryExtractSlotDict.get(
                    category, "unknown_slot"
                )
                category_resource_name = (
                    "Resource_"
                    + drawib_model.get_submesh_unique_key(submesh_model)
                    + "_"
                    + category
                )
                texture_override_ib_section.append(
                    category_slot + " = " + category_resource_name
                )

            # Texture bindings
            if not GlobalProterties.forbid_auto_texture_ini() and drawib_model is not None:
                texture_markup_info_list = drawib_model.get_submesh_texture_markup_info_list(submesh_model)
                for texture_markup_info in texture_markup_info_list:
                    if getattr(texture_markup_info, "mark_type", "") != "Slot":
                        continue
                    texture_override_ib_section.append(
                        texture_markup_info.mark_slot
                        + " = "
                        + texture_markup_info.get_resource_name()
                    )

            # Draw commands
            for draw_line in M_IniHelper.get_drawindexed_instanced_str_list(
                submesh_model.drawcall_model_list
            ):
                texture_override_ib_section.append(draw_line)

            if len(self.blueprint_model.keyname_mkey_dict.keys()) != 0:
                texture_override_ib_section.append(
                    "$active" + str(active_index) + " = 1"
                )

            texture_override_ib_section.new_line()

        ini_builder.append_section(texture_override_ib_section)

    def _add_resource_buffer_sections(
        self,
        ini_builder: M_IniBuilder,
        drawib_drawibmodel_dict: dict[str, DrawIBModel],
    ):
        resource_buffer_section = M_IniSection(M_SectionType.ResourceBuffer)

        for submesh_model in self._iter_all_submesh_models():
            drawib_model = drawib_drawibmodel_dict.get(submesh_model.match_draw_ib)
            submesh_unique_key = (
                drawib_model.get_submesh_unique_key(submesh_model)
                if drawib_model
                else submesh_model.display_str.replace("-", "_")
            )

            ib_resource_name = "Resource_" + submesh_unique_key + "_Index"
            resource_buffer_section.append("[" + ib_resource_name + "]")
            resource_buffer_section.append("type = Buffer")
            resource_buffer_section.append("format = DXGI_FORMAT_R32_UINT")
            resource_buffer_section.append(
                "filename = Meshes\\"
                + submesh_model.display_str
                + "-Index.buf"
            )
            resource_buffer_section.new_line()

            for category in submesh_model.category_buffer_dict.keys():
                category_resource_name = (
                    "Resource_" + submesh_unique_key + "_" + category
                )
                stride = submesh_model.d3d11_game_type.CategoryStrideDict.get(category, 0)
                resource_buffer_section.append("[" + category_resource_name + "]")
                resource_buffer_section.append("type = Buffer")
                resource_buffer_section.append("stride = " + str(stride))
                resource_buffer_section.append(
                    "filename = Meshes\\"
                    + submesh_model.display_str
                    + "-"
                    + category
                    + ".buf"
                )
                resource_buffer_section.new_line()

        ini_builder.append_section(resource_buffer_section)

    def _add_resource_texture_sections(self, ini_builder: M_IniBuilder):
        resource_texture_section = M_IniSection(M_SectionType.ResourceTexture)
        appended_resource_names: set[str] = set()

        for drawib_model in self.drawib_model_list:
            for submesh_model in drawib_model.submesh_model_list:
                for texture_markup_info in drawib_model.get_submesh_texture_markup_info_list(submesh_model):
                    if getattr(texture_markup_info, "mark_type", "") != "Slot":
                        continue
                    resource_name = texture_markup_info.get_resource_name()
                    if resource_name in appended_resource_names:
                        continue
                    appended_resource_names.add(resource_name)
                    resource_texture_section.append(
                        "[" + resource_name + "]"
                    )
                    resource_texture_section.append(
                        "filename = Textures\\"
                        + texture_markup_info.mark_filename
                    )
                    resource_texture_section.new_line()

        ini_builder.append_section(resource_texture_section)

    def _iter_all_submesh_models(self):
        for drawib_model in self.drawib_model_list:
            for submesh_model in drawib_model.submesh_model_list:
                yield submesh_model

    def export(self):
        self.generate_buffer_files()
        self.generate_ini_file()
