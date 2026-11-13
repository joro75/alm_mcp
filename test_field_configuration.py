"""Regression checks for configuration discovery and typed requirement fields."""
import json
import unittest
from unittest.mock import patch

import helix_alm_mcp as server


def menu_field(label="Release", multi=False):
    return {"label": label, "editable": True, "type": "menu",
            "outputType": "menuItemArray" if multi else "menuItem",
            "menu": {"id": 11, "required": True}}


class FieldConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.state = patch.dict(server._session, {
            "default_project": "Demo", "helix_field_definitions": {},
            "helix_menu_items": {},
        })
        self.state.start()
        self.addCleanup(self.state.stop)

    def test_fields_use_config_endpoints_and_preserve_metadata(self):
        field = menu_field()
        responses = [
            {"data": {"systemFieldsData": []}},
            {"data": {"customFieldsData": [field]}},
        ]
        with patch.object(server, "_request", side_effect=responses) as request:
            result = server._configured_fields("Demo", "token", "requirements")
        self.assertEqual(result, [field])
        self.assertEqual(request.call_args_list[0].args[0],
                         "Demo/configs/fields/requirementFields/systemFields")
        result[0]["menu"]["required"] = False
        self.assertTrue(server._configured_fields("Demo", "token", "requirements")[0]["menu"]["required"])

    def test_failed_metadata_is_not_cached_as_empty(self):
        with patch.object(server, "_request", return_value={"error": True, "status": 403}):
            with self.assertRaises(ValueError):
                server._configured_fields("Demo", "token", "requirements")
        self.assertFalse(server._session["helix_field_definitions"])

    def test_menu_values_include_unused_configured_options(self):
        with patch.object(server, "_get_token", return_value="token"), \
             patch.object(server, "_configured_fields", return_value=[menu_field()]), \
             patch.object(server, "_request", return_value={"data": {
                 "itemsData": [{"id": 1, "label": "Unused release"}]}}) as request:
            result = json.loads(server.get_field_values("Demo", "requirements", "Release"))
        self.assertEqual(result["values"], ["Unused release"])
        self.assertEqual(request.call_args.args[0], "Demo/configs/menus/11/items")

    def test_requirement_types_include_unused_types(self):
        with patch.object(server, "_get_token", return_value="token"), \
             patch.object(server, "_request", return_value={"data": {
                 "requirementTypesData": [{"id": 6, "label": "Critical Design", "active": True}]}}) as request:
            result = json.loads(server.get_requirement_types("Demo"))
        self.assertEqual(result["requirement_types"][0]["label"], "Critical Design")
        self.assertEqual(request.call_args.args[0], "Demo/configs/requirementTypes")

    def test_menu_label_and_id_are_encoded_as_menu_items(self):
        with patch.object(server, "_configured_menu_items", return_value=[{"id": 1, "label": "Future"}]):
            for value in ("Future", 1, {"id": 1, "label": "Future"}):
                field = server._serialise_configured_field("Demo", "token", menu_field(), value)
                self.assertEqual(field["type"], "menuItem")
                self.assertEqual(field["menuItem"], {"id": 1, "label": "Future"})
                self.assertNotIn("string", field)

    def test_invalid_menu_value_is_rejected_before_mutation(self):
        with patch.object(server, "_configured_menu_items", return_value=[{"id": 1, "label": "Future"}]):
            with self.assertRaisesRegex(ValueError, "Invalid value"):
                server._serialise_configured_field("Demo", "token", menu_field(), "Typo")

    def test_optional_menu_is_cleared_using_the_api_unset_item(self):
        definition = menu_field()
        definition["menu"]["required"] = False
        value = server._serialise_configured_field("Demo", "token", definition, None)
        self.assertEqual(value["menuItem"], {"id": 0, "label": ""})
        with self.assertRaisesRegex(ValueError, "required"):
            server._serialise_configured_field("Demo", "token", menu_field(), None)

    def test_read_only_fields_are_rejected(self):
        field = {"label": "Status", "editable": False}
        with self.assertRaisesRegex(ValueError, "read-only"):
            server._serialise_configured_field("Demo", "token", field, "Approved")

    def test_user_arrays_and_formatted_strings_have_correct_types(self):
        owners = {"label": "Owners", "type": "userMenu", "editable": True,
                  "outputType": "userArray", "userMenu": {}}
        value = server._serialise_configured_field("Demo", "token", owners, ["voko"])
        self.assertEqual(value["userArray"], [{"username": "voko"}])
        description = {"label": "Description", "type": "multiLineString",
                       "editable": True, "outputType": "formattedString"}
        value = server._serialise_configured_field("Demo", "token", description, "<p>test</p>")
        self.assertTrue(value["formattedString"]["isFormatted"])

    def test_summary_length_is_validated(self):
        summary = {"label": "Summary", "type": "singleLineString", "editable": True,
                   "outputType": "string", "singleLineString": {"length": 3}}
        with self.assertRaisesRegex(ValueError, "maximum length"):
            server._serialise_configured_field("Demo", "token", summary, "long")

    def test_empty_required_string_is_rejected(self):
        summary = {"label": "Summary", "type": "singleLineString", "editable": True,
                   "outputType": "string", "singleLineString": {"required": True}}
        with self.assertRaisesRegex(ValueError, "required"):
            server._serialise_configured_field("Demo", "token", summary, "")

    def test_optional_user_clear_uses_an_unset_user_object(self):
        source = {"label": "Source", "type": "userMenu", "editable": True,
                  "outputType": "user", "userMenu": {"required": False}}
        value = server._serialise_configured_field("Demo", "token", source, None)
        self.assertEqual(value["user"]["id"], 0)

    def test_unknown_field_is_rejected(self):
        with patch.object(server, "_configured_fields", return_value=[]):
            with self.assertRaisesRegex(ValueError, "Unknown requirement fields"):
                server._requirement_field_payload("Demo", "token", {"Typo": "value"})

    def test_create_sends_typed_required_fields(self):
        definitions = [menu_field("Importance"), menu_field("Release"), {
            "label": "Summary", "editable": True, "type": "singleLineString",
            "outputType": "string", "singleLineString": {"required": True, "length": 255}}]
        with patch.object(server, "_get_token", return_value="token"), \
             patch.object(server, "_configured_fields", return_value=definitions), \
             patch.object(server, "_configured_menu_items", return_value=[{"id": 1, "label": "Future"}]), \
             patch.object(server, "_configured_requirement_types", return_value=[{"id": 2, "label": "Functional Requirement"}]), \
             patch.object(server, "_request", return_value={"data": {"requirements": [{"id": 1}]}}) as request:
            result = server.create_requirement("Demo", "test", priority="Future",
                                               additional_fields={"Release": "Future"})
        self.assertIn("successfully", result)
        fields = request.call_args.args[2]["requirements"][0]["fields"]
        self.assertEqual([field["type"] for field in fields], ["menuItem", "string", "menuItem"])

    def test_update_can_add_an_unset_configured_field(self):
        with patch.object(server, "_get_token", return_value="token"), \
             patch.object(server, "_resolve_requirement_id", return_value=1), \
             patch.object(server, "_configured_fields", return_value=[menu_field()]), \
             patch.object(server, "_configured_menu_items", return_value=[{"id": 1, "label": "Future"}]), \
             patch.object(server, "_request", side_effect=[{"data": {"fields": []}}, {"data": {}}]) as request:
            result = server.update_requirement("Demo", "FR-1", additional_fields='{"Release":"Future"}')
        self.assertIn("successfully", result)
        self.assertEqual(request.call_args.args[2]["fields"][0]["menuItem"]["label"], "Future")


if __name__ == "__main__":
    unittest.main()
