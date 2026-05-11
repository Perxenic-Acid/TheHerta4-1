import os
from dataclasses import dataclass, field

from ..utils.format_utils import Fatal
from ..utils.json_utils import JsonUtils
from .d3d11_gametype import D3D11GameType
from .global_config import GlobalConfig
from .submesh_json import SubmeshJson
from .workspace_helper import WorkSpaceHelper


def check_and_get_submesh_json_path(unique_str: str) -> tuple[bool, str, str]:
    workspace_folder = GlobalConfig.path_workspace_folder()

    # 解析 LOD 前缀（如 "LOD0.67f829fc-2653-0" → lod_name="LOD0", bare="67f829fc-2653-0"）
    lod_name, bare_unique_str = WorkSpaceHelper.parse_lod_unique_str(unique_str)

    # 实际 submesh 文件夹路径（workspace/LOD0/67f829fc-2653-0 或 workspace/67f829fc-2653-0）
    unique_str_folder = WorkSpaceHelper.get_submesh_folder_path(unique_str)

    if not os.path.exists(unique_str_folder):
        return False, (
            f"unique_str '{unique_str}' 没有找到对应的提取数据。\n"
            + "请确保已从游戏中提取模型并执行「一键导入当前工作空间内容」操作。"
        ), ""

    workspace_import_json_path = os.path.join(workspace_folder, "Import.json")
    workspace_import_json = JsonUtils.LoadFromFile(workspace_import_json_path) if os.path.exists(workspace_import_json_path) else {}
    gametype_name = workspace_import_json.get(unique_str, "")

    if gametype_name:
        submesh_json_path = os.path.join(unique_str_folder, "TYPE_" + gametype_name, bare_unique_str + ".json")
        if os.path.exists(submesh_json_path):
            return True, "", submesh_json_path

    found_type_paths = []
    found_types = []
    for dirname in os.listdir(unique_str_folder):
        if not dirname.startswith("TYPE_"):
            continue

        submesh_json_path = os.path.join(unique_str_folder, dirname, bare_unique_str + ".json")
        if os.path.exists(submesh_json_path):
            found_type_paths.append(submesh_json_path)
            found_types.append(dirname.replace("TYPE_", ""))

    if len(found_type_paths) == 1:
        return True, "", found_type_paths[0]

    if len(found_type_paths) > 1:
        return False, (
            f"unique_str '{unique_str}' 找到以下数据类型但没有在 Import.json 中记录: {', '.join(found_types)}\n"
            + "请尝试重新执行「一键导入当前工作空间内容」操作。"
        ), ""

    return False, (
        f"unique_str '{unique_str}' 没有找到对应的 SubmeshJson。\n"
        + "请确保已从游戏中提取模型并执行「一键导入当前工作空间内容」操作。"
    ), ""


@dataclass
class SubmeshMetadata:
    unique_str: str

    submesh_json_path: str = field(init=False, default="")
    extract_gametype_folder_path: str = field(init=False, default="")
    submesh_json: SubmeshJson = field(init=False, repr=False)
    submesh_json_dict: dict = field(init=False, repr=False, default_factory=dict)
    d3d11_game_type: D3D11GameType = field(init=False, repr=False)
    work_game_type: str = field(init=False, default="")
    vertex_limit_hash: str = field(init=False, default="")
    category_hash_dict: dict = field(init=False, default_factory=dict)
    texture_markup_info_list: list = field(init=False, default_factory=list)
    part_name: str = field(init=False, default="")

    def __post_init__(self):
        exists, error_msg, submesh_json_path = check_and_get_submesh_json_path(self.unique_str)
        if not exists:
            raise Fatal(error_msg)

        self.submesh_json_path = submesh_json_path
        self.extract_gametype_folder_path = os.path.join(os.path.dirname(submesh_json_path), "")
        self.submesh_json = SubmeshJson(submesh_json_path)
        self.submesh_json_dict = self.submesh_json.JsonDict
        self.work_game_type = self.submesh_json.WorkGameType
        self.vertex_limit_hash = self.submesh_json.VertexLimitVB
        self.category_hash_dict = dict(self.submesh_json.CategoryHash)
        self.texture_markup_info_list = list(self.submesh_json.TextureMarkUpInfoList)
        self.part_name = str(
            self.submesh_json_dict.get("PartName")
            or self.submesh_json_dict.get("ComponentName")
            or self.unique_str
        )
        self.d3d11_game_type = self._build_d3d11_game_type()

    def _build_d3d11_game_type(self) -> D3D11GameType:
        return D3D11GameType.from_submesh_json_dict(
            submesh_json_dict=self.submesh_json_dict,
            file_path=self.submesh_json_path,
        )


class SubmeshMetadataResolver:
    @staticmethod
    def resolve(unique_str: str) -> SubmeshMetadata:
        return SubmeshMetadata(unique_str=unique_str)