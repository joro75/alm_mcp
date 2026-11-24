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
                "type": "user", "user": {"id": 12, "username": "testuser"}},
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
        self.assertEqual(sent[0], {
            "label": "Release",
            "type": "menuItem",
            "menuItem": {"label": "Beta release"},
        })
        self.assertEqual(sent[1], {
            "label": "Release to customer testing by",
            "type": "user",
            "user": {"id": 12, "username": "testuser"},
        })
        self.assertEqual(sent[2], {
            "label": "Date",
            "type": "dateTime",
            "dateTime": "2026-11-24T00:00:00Z",
        })
        self.assertEqual(sent[3], {
            "label": "Version",
            "type": "string",
            "string": "2026.1.6",
        })
        self.assertEqual(sent[-1], {"label": "Notes", "type": "string", "string": "Available to customers."})

    def test_add_issue_event_without_optional_fields_preserves_legacy_empty_fields_payload(self):
        response = {"status": 201, "data": {}}
        with patch.object(server, "_resolve_project", return_value="Demo"), \
             patch.object(server, "_get_token", return_value="token"), \
             patch.object(server, "_resolve_issue_id", return_value=42), \
             patch.object(server, "_request", return_value=response) as request:
            result = json.loads(server.add_issue_event("Demo", "#-42", "Comment"))

        self.assertEqual(result["message"], "Event 'Comment' added to issue #-42")
        self.assertEqual(request.call_args.args[2], {
            "eventsData": [{"name": "Comment", "fields": []}]
        })

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

    def test_add_issue_event_rejects_non_dictionary_field_value_before_network(self):
        with patch.object(server, "_get_token") as token:
            result = server.add_issue_event(
                "Demo", "#-42", "Comment",
                additional_fields={"Version": "2026.1.6"}  # type: ignore[arg-type]
            )
        self.assertIn("must be a field dictionary", result)
        token.assert_not_called()

    def test_add_issue_event_rejects_mismatched_field_label_before_network(self):
        with patch.object(server, "_get_token") as token:
            result = server.add_issue_event(
                "Demo", "#-42", "Comment",
                additional_fields={"Version": {
                    "label": "Release", "type": "string", "string": "2026.1.6"
                }})
        self.assertIn("mismatched label", result)
        token.assert_not_called()

    def test_add_issue_event_rejects_empty_field_label_before_network(self):
        with patch.object(server, "_get_token") as token:
            result = server.add_issue_event(
                "Demo", "#-42", "Comment",
                additional_fields={"": {"type": "string", "string": "value"}})
        self.assertIn("labels must be non-empty strings", result)
        token.assert_not_called()

    def test_add_issue_event_accepts_notes_as_an_explicit_typed_field(self):
        response = {"status": 201, "data": {}}
        with patch.object(server, "_resolve_project", return_value="Demo"), \
             patch.object(server, "_get_token", return_value="token"), \
             patch.object(server, "_resolve_issue_id", return_value=42), \
             patch.object(server, "_request", return_value=response) as request:
            server.add_issue_event(
                "Demo", "#-42", "Comment",
                additional_fields={"Notes": {"type": "string", "string": "typed note"}})

        self.assertEqual(request.call_args.args[2]["eventsData"][0]["fields"], [{
            "label": "Notes", "type": "string", "string": "typed note"
        }])

    def test_add_issue_event_does_not_post_when_issue_cannot_be_resolved(self):
        with patch.object(server, "_resolve_project", return_value="Demo"), \
             patch.object(server, "_get_token", return_value="token"), \
             patch.object(server, "_resolve_issue_id", return_value=None), \
             patch.object(server, "_request") as request:
            result = server.add_issue_event("Demo", "#-999", "Comment")

        self.assertIn("Could not find issue", result)
        request.assert_not_called()

    def test_add_issue_event_returns_friendly_api_error(self):
        response = {
            "status": 400,
            "error": True,
            "data": {"message": "Event is not available for this issue"},
        }
        with patch.object(server, "_resolve_project", return_value="Demo"), \
             patch.object(server, "_get_token", return_value="token"), \
             patch.object(server, "_resolve_issue_id", return_value=42), \
             patch.object(server, "_request", return_value=response):
            result = server.add_issue_event("Demo", "#-42", "Release to customer")

        self.assertIn("Could not add event 'Release to customer' to the issue", result)
        self.assertIn("Event is not available for this issue", result)

    def test_add_issue_event_rejects_invalid_fields_before_api_error_or_post(self):
        with patch.object(server, "_request") as request, \
             patch.object(server, "_get_token") as token:
            result = server.add_issue_event(
                "Demo", "#-42", "Comment",
                additional_fields={"Date": {"type": "dateTime"}})

        self.assertIn("requires", result)
        token.assert_not_called()
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
