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
        self.assertEqual(fields["Category"]["menuItem"], {"id": 3, "label": "Investigation"})
        self.assertEqual(fields["Summary"]["string"], "Investigate failure")
        self.assertEqual(fields["Summary"]["string"], "Investigate failure")
        self.assertNotIn("type", fields["Category"])
        self.assertNotIn("id", fields["Category"])
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

    def test_configured_field_ids_are_included_in_create_payload(self):
        definitions = [field | {"id": index + 1}
                       for index, field in enumerate(self.definitions())]
        responses = [
            {"data": {"itemsData": [{"id": 3, "label": "Investigation"}]}},
            {"status": 201, "data": {"issues": [{"id": 42, "tag": "IS-42", "fields": []}]}},
        ]
        with patch.object(server, "_get_token", return_value="token"), \
             patch.object(server, "_configured_fields", return_value=definitions), \
             patch.object(server, "_request", side_effect=responses) as request:
            server.create_issue("Demo", "With IDs", "Details",
                                additional_fields={"Category": "Investigation"})

        fields = request.call_args.args[2]["issues"][0]["fields"]
        self.assertEqual({field["label"]: field.get("id") for field in fields},
                         {"Category": 3, "Summary": 1})

    def test_free_form_menu_is_encoded_as_menu_item(self):
        definition = {"label": "Version Found", "id": 12, "editable": True,
                      "type": "menu", "outputType": "string",
                      "menu": {"id": 2147483647, "required": True}}
        value = server._serialise_configured_field(
            "Demo", "token", definition, "MCP live test")
        self.assertEqual(value["type"], "string")
        self.assertEqual(value["string"], "MCP live test")

    def test_issue_description_and_version_are_sent_in_found_by_record(self):
        definitions = [
            {"label": "Summary", "id": 2, "editable": True,
             "type": "singleLineString", "outputType": "string",
             "singleLineString": {"required": True}},
            {"label": "Description", "id": 54, "editable": True,
             "type": "multiLineString", "outputType": "formattedString",
             "multiLineString": {"required": True}},
            {"label": "Version Found", "id": 12, "editable": True,
             "type": "menu", "outputType": "string",
             "menu": {"id": 99, "required": True}},
            {"label": "Found by", "id": 9, "editable": True,
             "type": "userMenu", "outputType": "user",
             "userMenu": {"required": True}},
        ]
        response = {"status": 201, "data": {"issues": [{"id": 42, "tag": "#-42", "fields": []}]}}
        with patch.object(server, "_get_token", return_value="token"), \
             patch.object(server, "_configured_fields", return_value=definitions), \
             patch.object(server, "_request", return_value=response) as request:
            server.create_issue("Demo", "Summary", "Description",
                                additional_fields={
                                    "Version Found": "3.3.x",
                                    "Found by": {"username": "joro"},
                                })
        issue = request.call_args.args[2]["issues"][0]
        self.assertNotIn("Description", [f["label"] for f in issue["fields"]])
        found_by = issue["foundByRecords"]["foundByRecordsData"][0]
        self.assertEqual(found_by["versionFound"], "3.3.x")
        self.assertEqual(found_by["foundBy"], {"username": "joro"})
        self.assertEqual(found_by["description"]["text"], "Description")


if __name__ == "__main__":
    unittest.main()
