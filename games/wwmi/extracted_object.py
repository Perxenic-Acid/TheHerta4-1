import os 
import json

from typing import List, Dict, Union
from dataclasses import dataclass, field, asdict

from ...utils.format_utils import Fatal
from enum import Enum

    
@dataclass
class ExtractedObjectBufferSemantic:
    name: str
    index: int
    format: str
    stride: int = 0

    def __post_init__(self):
        if self.stride == 0:
            self.stride = self.format.byte_width

@dataclass
class ExtractedObjectBuffer:
    semantics: List[ExtractedObjectBufferSemantic]


    
@dataclass
class ExtractedObjectComponent:
    vertex_offset: int
    vertex_count: int
    index_offset: int
    index_count: int
    vg_offset: int
    vg_count: int
    vg_map: Dict[int, int]


@dataclass
class ExtractedObjectShapeKeys:
    offsets_hash: str = ''
    scale_hash: str = ''
    vertex_count: int = 0
    dispatch_y: int = 0
    checksum: int = 0


@dataclass
class ExtractedObject:
    vb0_hash: str
    cb4_hash: str
    vertex_count: int
    index_count: int
    components: List[ExtractedObjectComponent]
    shapekeys: ExtractedObjectShapeKeys
    export_format: Dict[str, ExtractedObjectBuffer]

    def __post_init__(self):
        if isinstance(self.shapekeys, dict):
            self.components = [ExtractedObjectComponent(**component) for component in self.components]
            self.shapekeys = ExtractedObjectShapeKeys(**self.shapekeys)

    def as_json(self):
        return json.dumps(asdict(self), indent=4)


class ExtractedObjectHelper:
    '''
    不用类包起来难受，还是做成工具类好一点。。
    '''
    @classmethod
    def read_metadata(cls,metadata_path: str) -> ExtractedObject:
        if not os.path.exists(metadata_path):
            raise Fatal("无法找到Metadata.json文件，请确认是否存在该文件。")
        
        with open(metadata_path) as f:
            return ExtractedObject(**json.load(f))

    @classmethod
    def build_from_submesh_metadata_list(cls, metadata_list: list) -> ExtractedObject:
        if not metadata_list:
            raise Fatal("No SubmeshMetadata provided to build ExtractedObject.")

        first_json = metadata_list[0].submesh_json
        vb0_hash = first_json.VertexLimitVB
        cb4_hash = first_json.CB4Hash

        components = []
        total_index_count = 0
        max_vertex_end = 0

        for meta in metadata_list:
            j = meta.submesh_json
            vertex_offset = j.VertexOffset
            vertex_count = max(j.VertexCount, 0)
            index_offset = int(j.JsonDict.get("IndexOffset", 0))
            index_count = int(j.JsonDict.get("IndexCount", 0))
            vg_offset = j.VGOffset
            vg_count = j.VGCount
            vg_map = {str(k): int(v) for k, v in j.VGMap.items()}

            component = ExtractedObjectComponent(
                vertex_offset=vertex_offset,
                vertex_count=vertex_count,
                index_offset=index_offset,
                index_count=index_count,
                vg_offset=vg_offset,
                vg_count=vg_count,
                vg_map=vg_map,
            )
            components.append(component)
            total_index_count += index_count
            max_vertex_end = max(max_vertex_end, vertex_offset + vertex_count)

        sk_info = first_json.ShapeKeysInfo
        shapekeys = ExtractedObjectShapeKeys(
            offsets_hash=sk_info.get("offsets_hash", ""),
            scale_hash=sk_info.get("scale_hash", ""),
            vertex_count=sk_info.get("vertex_count", 0),
            dispatch_y=sk_info.get("dispatch_y", 0),
            checksum=sk_info.get("checksum", 0),
        )

        return ExtractedObject(
            vb0_hash=vb0_hash,
            cb4_hash=cb4_hash,
            vertex_count=max_vertex_end,
            index_count=total_index_count,
            components=components,
            shapekeys=shapekeys,
            export_format={},
        )
        