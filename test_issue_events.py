import json
import unittest
from unittest.mock import patch

import helix_alm_mcp as server


class IssueEventTests(unittest.TestCase):
    def test_add_issue_event_builds_typed_fields_and_notes(self):
        response = {"status": 201, "data": {"eventsData": [{"id": 1, "name": "Release to customer"}]}}
        fields = {
            "Release": {"type": "menuItem", "menuItem": {"label": "Beta release"}},
            "Release to customer testing by": {
                "type": "user", "user": {"id": 12, "username": "joro"}},
            "Date": {"type": "dateTime", "dateTime": "2026-11-24T00:00:00Z"},
            "Version": {"type": "string", "string": "2026.1.6"},
        }
        with patch.object(server, "_resolve_project", return_value="Demo"), \
             patch.object(server, "_get_token", return_value="token"), \
             patch.object(server, "_resolve_issue_id", return_value=42), \
             patch.object(server, "_request", return_value=response) as request:
            result = json.loads(server.add_issue_event(
                "Demo", "#-42", "Release to customer",
                notes="Available to customers.", additional_fields=fields))

        self.assertEqual(result["message"], "Event 'Release to customer' added to issue #-42")
        payload = request.call_args.args[2]
        sent = payload["eventsData"][0]["fields"]
        self.assertEqual(sent[0]["label"], "Release")
        self.assertEqual(sent[1]["type"], "user")
        self.assertEqual(sent[-1], {"label": "Notes", "type": "string", "string": "Available to customers."})

    def test_add_issue_event_rejects_non_dictionary_fields_before_network(self):
        with patch.object(server, "_get_token") as token:
            result = server.add_issue_event(
                "Demo", "#-42", "Comment", additional_fields="bad"  # type: ignore[arg-type]
            )
        self.assertEqual(result, "Error: additional_fields must be a dictionary.")
        token.assert_not_called()

    def test_add_issue_event_rejects_missing_type_before_network(self):
        with patch.object(server, "_get_token") as token:
            result = server.add_issue_event(
                "Demo", "#-42", "Comment", additional_fields={"Date": {"dateTime": "2026-11-24"}})
        self.assertIn("requires a type", result)
        token.assert_not_called()

    def test_add_issue_event_rejects_duplicate_notes(self):
        with patch.object(server, "_get_token") as token:
            result = server.add_issue_event(
                "Demo", "#-42", "Comment", notes="one",
                additional_fields={"Notes": {"type": "string", "string": "two"}})
        self.assertIn("either through notes or additional_fields", result)
        token.assert_not_called()


if __name__ == "__main__":
    unittest.main()
