import json
import unittest
from unittest.mock import patch

import helix_alm_mcp as server


class AssignmentTests(unittest.TestCase):
    def setUp(self):
        server._session.update({
            "helix_alm_url": "https://alm.example/helix-alm/api/v0/",
            "helix_alm_api_key": "key",
            "helix_alm_api_secret": "secret",
            "default_project": "Demo",
        })

    def test_assign_issue_resolves_user_and_posts_assign_event(self):
        responses = [
            {"status": 200, "data": {"accessToken": "token"}},
            {"status": 200, "data": {"issues": []}},
            {"status": 200, "data": {"id": 42}},
            {"status": 200, "data": {"fields": [{"label": "Currently Assigned To", "userArray": [{"id": 12, "firstName": "John", "lastName": "de Rooij", "username": "joro"}]}]}},
            {"status": 200, "data": {"eventsData": [{"name": "Assign"}]}},
        ]
        with patch.object(server, "_request", side_effect=responses) as request:
            result = json.loads(server.assign_issue("", "42", "John de Rooij", "Please investigate"))

        self.assertEqual(result["assignee"]["id"], 12)
        payload = request.call_args_list[4].args[2]
        self.assertEqual(payload["eventsData"][0]["name"], "Assign")
        self.assertEqual(payload["eventsData"][0]["fields"][0]["userArray"][0]["id"], 12)
        self.assertEqual(payload["eventsData"][0]["fields"][1]["string"], "Please investigate")

    def test_assign_issue_rejects_unknown_user_without_posting(self):
        responses = [
            {"status": 200, "data": {"accessToken": "token"}},
            {"status": 200, "data": {"issues": []}},
            {"status": 200, "data": {"id": 42}},
            {"status": 200, "data": {"fields": []}},
        ]
        with patch.object(server, "_request", side_effect=responses) as request:
            result = server.assign_issue("", "42", "Unknown User")

        self.assertIn("Could not resolve", result)
        self.assertEqual(request.call_count, 4)


if __name__ == "__main__":
    unittest.main()
