import os
import tempfile
import unittest

from common.m_ini_builder import M_IniBuilder, M_IniSection, M_SectionType


class MIniBuilderTests(unittest.TestCase):
    def test_not_reorder_reopens_non_contiguous_named_sections(self):
        builder = M_IniBuilder()

        constants = M_IniSection(M_SectionType.Constants)
        constants.SectionName = "Constants"
        constants.append("global $first = 1")
        builder.append_section(constants)

        key = M_IniSection(M_SectionType.Key)
        key.append("[KeySwap_0]")
        key.append("key = k")
        builder.append_section(key)

        later_constants = M_IniSection(M_SectionType.Constants)
        later_constants.SectionName = "Constants"
        later_constants.append("global $second = 1")
        builder.append_section(later_constants)

        with tempfile.TemporaryDirectory() as tmpdir:
            ini_path = os.path.join(tmpdir, "test.ini")
            builder.save_to_file_not_reorder(ini_path)

            with open(ini_path, "r", encoding="utf-8") as ini_file:
                content = ini_file.read()

        self.assertEqual(content.count("[Constants]"), 2)
        self.assertLess(content.index("[KeySwap_0]"), content.rindex("[Constants]"))

    def test_clear_resets_written_section_names_for_reused_builder(self):
        builder = M_IniBuilder()

        with tempfile.TemporaryDirectory() as tmpdir:
            first_path = os.path.join(tmpdir, "first.ini")
            second_path = os.path.join(tmpdir, "second.ini")

            first_constants = M_IniSection(M_SectionType.Constants)
            first_constants.SectionName = "Constants"
            first_constants.append("global $first = 1")
            builder.append_section(first_constants)
            builder.save_to_file_not_reorder(first_path)

            builder.clear()

            second_constants = M_IniSection(M_SectionType.Constants)
            second_constants.SectionName = "Constants"
            second_constants.append("global $second = 1")
            builder.append_section(second_constants)
            builder.save_to_file_not_reorder(second_path)

            with open(second_path, "r", encoding="utf-8") as ini_file:
                second_content = ini_file.read()

        self.assertIn("[Constants]", second_content)
        self.assertIn("global $second = 1", second_content)


if __name__ == "__main__":
    unittest.main()
