import json
import unittest
from unittest.mock import patch

import helix_alm_mcp as server


class IssueAttachmentTests(unittest.TestCase):
    def setUp(self):
        server._session.update({
            "helix_alm_url": "https://alm.example/helix-alm/api/v0/",
            "helix_alm_api_key": "key",
            "helix_alm_api_secret": "secret",
            "default_project": "Demo",
        })

    def test_get_issue_attachments_returns_metadata_and_download_path(self):
        responses = [
            {"status": 200, "data": {"accessToken": "token"}},
            {"status": 200, "data": {"issues": []}},
            {"status": 200, "data": {"id": 42}},
            {"status": 200, "data": {"attachmentsData": [
                {"id": 7, "filename": "log.txt", "encodedFileID": "a/b", "size": 12}
            ]}},
        ]
        with patch.object(server, "_request", side_effect=responses) as request:
            result = json.loads(server.get_issue_attachments("", "42"))

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["attachments"][0]["filename"], "log.txt")
        self.assertEqual(result["attachments"][0]["download_path"], "Demo/files/a%2Fb")
        self.assertEqual(request.call_args_list[3].args[0], "Demo/issues/42/attachments")

    def test_get_issue_attachments_accepts_legacy_attachments_key(self):
        responses = [
            {"status": 200, "data": {"accessToken": "token"}},
            {"status": 200, "data": {"issues": []}},
            {"status": 200, "data": {"id": 42}},
            {"status": 200, "data": {"attachments": [
                {"id": 7, "filename": "log.txt"}
            ]}},
        ]
        with patch.object(server, "_request", side_effect=responses):
            result = json.loads(server.get_issue_attachments("", "42"))

        self.assertEqual(result["count"], 1)

    def test_get_issue_attachments_reports_api_errors(self):
        with patch.object(server, "_request", side_effect=[
            {"status": 200, "data": {"accessToken": "token"}},
            {"status": 200, "data": {"issues": []}},
            {"status": 200, "data": {"id": 42}},
            {"status": 403, "data": {"message": "denied"}, "error": True},
        ]):
            result = server.get_issue_attachments("", "42")

        self.assertIn("permission", result)


if __name__ == "__main__":
    unittest.main()
