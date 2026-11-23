import json
import unittest
from unittest.mock import patch

import helix_alm_mcp as server


class IssueCreationTests(unittest.TestCase):
    def setUp(self):
        self.state = patch.dict(server._session, {
            "default_project": "Demo",
            "helix_field_definitions": {},
            "helix_menu_items": {},
        })
        self.state.start()
        self.addCleanup(self.state.stop)

    @staticmethod
    def definitions():
        return [
            {"label": "Summary", "editable": True, "type": "singleLineString",
             "outputType": "string", "singleLineString": {"required": True}},
            {"label": "Description", "editable": True, "type": "multiLineString",
             "outputType": "formattedString", "multiLineString": {}},
            {"label": "Category", "editable": True, "type": "menu",
             "outputType": "menuItem", "menu": {"id": 7, "required": True}},
        ]

    def test_create_issue_encodes_required_configured_fields(self):
        responses = [
            {"data": {"itemsData": [{"id": 3, "label": "Investigation"}]}},
            {"status": 201, "data": {"issues": [{"id": 42, "tag": "IS-42", "fields": []}]}},
        ]

        with patch.object(server, "_get_token", return_value="token"), \
             patch.object(server, "_configured_fields", return_value=self.definitions()), \
             patch.object(server, "_request", side_effect=responses) as request:
            result = json.loads(server.create_issue(
                "Demo", "Investigate failure", "Details", "",
                {"Category": "Investigation"}))

        self.assertEqual(result["message"], "Issue created successfully")
        payload = request.call_args.args[2]
        fields = {field["label"]: field for field in payload["issues"][0]["fields"]}
        self.assertEqual(fields["Category"]["type"], "menuItem")
        self.assertEqual(fields["Category"]["menuItem"], {"id": 3, "label": "Investigation"})
        self.assertEqual(fields["Summary"]["string"], "Investigate failure")
        self.assertEqual(fields["Description"]["formattedString"]["text"], "Details")
        self.assertEqual(request.call_args.args[0], "Demo/issues")
        self.assertEqual(request.call_args.args[3], "POST")

    def test_required_issue_fields_are_reported_before_posting(self):
        definitions = self.definitions() + [{
            "label": "Severity", "editable": True, "type": "menu",
            "outputType": "menuItem", "menu": {"id": 8, "required": True},
        }]
        with patch.object(server, "_get_token", return_value="token"), \
             patch.object(server, "_configured_fields", return_value=definitions), \
             patch.object(server, "_request") as request:
            result = server.create_issue("Demo", "Missing field")

        self.assertIn("Severity", result)
        request.assert_not_called()

    def test_non_dictionary_additional_fields_are_rejected(self):
        with patch.object(server, "_get_token", return_value="token"), \
             patch.object(server, "_request") as request:
            result = server.create_issue(  # type: ignore[reportArgumentType]
                "Demo", "Invalid", additional_fields="not a dict")

        self.assertEqual(result, "Error: additional_fields must be a dictionary.")
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
