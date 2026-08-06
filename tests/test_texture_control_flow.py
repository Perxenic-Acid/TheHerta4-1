import sys
import types
import unittest

sys.modules.setdefault("bpy", types.SimpleNamespace())

from common.m_control_flow import M_ControlFlow
from common.m_ini_builder import M_IniBuilder, M_IniSection, M_SectionType
from common.m_key import M_Key
from common.m_texture_helper import HashTextureBinding, M_TextureHelper
from common.texture_naming import default_texture_filename, default_texture_resource_name


class _TextureNode:
    def __init__(self, texture_hash, resource_name, filename, mark_name=""):
        self.texture_hash = texture_hash
        self.resource_name = resource_name
        self.texture_filename = filename
        self.mark_name = mark_name

    def get_resource_name(self):
        return self.resource_name

    def get_texture_filename(self):
        return self.texture_filename


def _key(name, value):
    return M_Key(key_name=name, tmp_value=value)


class _DrawCall:
    def __init__(self, name, keys, draw):
        self.obj_name = name
        self.display_name = name
        self.vertex_count = 3
        self.work_key_list = keys
        self._draw = draw

    def get_condition_str(self):
        return " && ".join(f"{key.key_name} == {key.tmp_value}" for key in self.work_key_list)

    def get_drawindexed_str(self, _offsets=None):
        return self._draw


class _SlotItem:
    def __init__(self, key, slot_type="PS_T"):
        self.effective_slot_key = key
        self.slot_type = slot_type


class _SubMesh:
    def __init__(self, bindings):
        self._bindings = bindings

    def get_slot_texture_node_list(self):
        return self._bindings


class _DrawIB:
    def __init__(self, bindings):
        self.submesh_model_list = [_SubMesh(bindings)]


class TextureControlFlowTests(unittest.TestCase):
    def test_default_texture_names_include_map_role(self):
        self.assertEqual(
            default_texture_resource_name("3a482e27", "NormalMap"),
            "Resource_NormalMap_3a482e27",
        )
        self.assertEqual(
            default_texture_filename("3a482e27", "NormalMap"),
            "3a482e27_NormalMap.dds",
        )

    def test_resource_sections_are_deduplicated_across_slot_and_hash_exports(self):
        node = _TextureNode("3a482e27", "", "", "DiffuseMap")
        binding = (_SlotItem("ps-t0"), node)
        builder = M_IniBuilder()
        M_TextureHelper.generate_slot_texture_resource_sections(_DrawIB([binding]), None, builder)
        M_TextureHelper.generate_slot_texture_resource_sections(_DrawIB([binding]), None, builder)
        M_TextureHelper.generate_hash_texture_sections([HashTextureBinding(node)], builder)

        lines = [line for section in builder.ini_section_list for line in section.SectionLineList]
        self.assertEqual(lines.count("[Resource_DiffuseMap_3a482e27]"), 1)

    def test_normal_map_detection_uses_texture_semantics_not_resource_name(self):
        normal_node = _TextureNode("normalhash", "Resource2", "renamed.dds", "NormalMap")
        diffuse_node = _TextureNode("diffusehash", "Resource1", "diffuse.dds", "DiffuseMap")
        normal_draw = _DrawCall("normal", [], "drawindexed = n,n,n")
        normal_draw.slot_texture_node_list = [(_SlotItem("ps-t0"), normal_node)]
        diffuse_draw = _DrawCall("diffuse", [], "drawindexed = d,d,d")
        diffuse_draw.slot_texture_node_list = [(_SlotItem("ps-t0"), diffuse_node)]

        self.assertTrue(M_TextureHelper.drawcall_has_normal_map(normal_draw))
        self.assertFalse(M_TextureHelper.drawcall_has_normal_map(diffuse_draw))

    def test_slot_texture_lines_remain_scoped_to_each_complex_condition(self):
        draws = [
            _DrawCall("a0", [_key("$a", 0)], "drawindexed = a,a,a"),
            _DrawCall("a1", [_key("$a", 1)], "drawindexed = b,b,b"),
            _DrawCall("b0", [_key("$b", 0)], "drawindexed = c,c,c"),
            _DrawCall("c1", [_key("$c", 1)], "drawindexed = d,d,d"),
            _DrawCall("nested", [_key("$a", 1), _key("$b", 0)], "drawindexed = e,e,e"),
        ]
        slot_lines = {
            "a0": ["ps-t0 = Resource1"],
            "a1": ["ps-t0 = Resource2", "ps-t1 = Resource3"],
            "b0": ["ps-t0 = Resource1"],
            "c1": ["ps-t0 = Resource2", "ps-t1 = Resource3"],
            "nested": ["ps-t2 = Resource4"],
        }
        section = M_IniSection(M_SectionType.TextureOverrideIB)

        M_ControlFlow.append_drawindexed_with_slot_lines(
            section,
            draws,
            lambda draw: slot_lines[draw.obj_name],
        )

        lines = section.SectionLineList
        for condition in ("$a == 0", "$a == 1", "$b == 0", "$c == 1", "$a == 1 && $b == 0"):
            self.assertIn(f"if {condition}", lines)
        self.assertEqual(lines.count("endif"), len(draws))
        self.assertLess(lines.index("  ps-t0 = Resource1"), lines.index("  drawindexed = a,a,a"))
        self.assertLess(lines.index("  ps-t1 = Resource3"), lines.index("  drawindexed = b,b,b"))
        self.assertLess(lines.index("  ps-t2 = Resource4"), lines.index("  drawindexed = e,e,e"))

    def test_hash_texture_preserves_independent_and_nested_branch_conditions(self):
        builder = M_IniBuilder()
        resource_1 = _TextureNode("1234abcd", "Resource1", "one.dds", "one")
        resource_2 = _TextureNode("1234abcd", "Resource2", "two.dds")
        resource_3 = _TextureNode("1234abcd", "Resource3", "three.dds")

        M_TextureHelper.generate_hash_texture_sections(
            [
                HashTextureBinding(resource_1, [_key("$a", 0)]),
                HashTextureBinding(resource_2, [_key("$a", 1), _key("$b", 0)]),
                HashTextureBinding(resource_3, [_key("$a", 1), _key("$c", 1)]),
            ],
            builder,
        )

        section = builder.ini_section_list[0]
        self.assertEqual(section.SectionLineList.count("[TextureOverride_1234abcd]"), 1)
        self.assertIn("[Resource1]", section.SectionLineList)
        self.assertIn("[Resource2]", section.SectionLineList)
        self.assertIn("[Resource3]", section.SectionLineList)
        self.assertIn("if $a == 0", section.SectionLineList)
        self.assertIn("if $a == 1 && $b == 0", section.SectionLineList)
        self.assertIn("if $a == 1 && $c == 1", section.SectionLineList)
        self.assertEqual(section.SectionLineList.count("endif"), 3)

    def test_hash_texture_rejects_conflicting_resource_definitions(self):
        builder = M_IniBuilder()
        with self.assertRaisesRegex(ValueError, "ResourceShared"):
            M_TextureHelper.generate_hash_texture_sections(
                [
                    HashTextureBinding(_TextureNode("aaaa", "ResourceShared", "one.dds")),
                    HashTextureBinding(_TextureNode("bbbb", "ResourceShared", "two.dds")),
                ],
                builder,
            )

    def test_hash_texture_generates_distinct_default_resources_for_branch_variants(self):
        builder = M_IniBuilder()
        M_TextureHelper.generate_hash_texture_sections(
            [
                HashTextureBinding(_TextureNode("1234abcd", "", "one.dds"), [_key("$a", 0)]),
                HashTextureBinding(_TextureNode("1234abcd", "", "two.dds"), [_key("$a", 1)]),
            ],
            builder,
        )

        lines = builder.ini_section_list[0].SectionLineList
        self.assertIn("[Resource_Texture_1234abcd]", lines)
        self.assertIn("[Resource_Texture_1234abcd_2]", lines)
        self.assertIn("  this = Resource_Texture_1234abcd", lines)
        self.assertIn("  this = Resource_Texture_1234abcd_2", lines)


if __name__ == "__main__":
    unittest.main()
