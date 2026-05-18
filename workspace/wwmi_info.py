from dataclasses import dataclass, field
from typing import Dict, List


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


class ExtractedObjectHelper:
    @classmethod
    def build_from_submesh_metadata_list(cls, submesh_json_list: list) -> ExtractedObject:
        if not submesh_json_list:
            raise ValueError("No SubmeshJson provided to build ExtractedObject.")

        first_json = submesh_json_list[0]
        vb0_hash = first_json.VertexLimitVB
        cb4_hash = first_json.CB4Hash

        components = []
        total_index_count = 0
        max_vertex_end = 0

        for j in submesh_json_list:
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
        )
