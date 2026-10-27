import json
import sys
import unittest
from unittest.mock import patch

import helix_alm_mcp as server


class RequirementCreationPayloadTests(unittest.TestCase):
    def setUp(self):
        self.posted_body = None

    def test_required_menu_fields_are_encoded_and_type_is_preserved(self):
        responses = [
            {"status": 200, "data": {"requirements": [{"id": 1}]}},
            {
                "status": 200,
                "data": {
                    "fields": [
                        {"label": "Importance", "type": "menuItem"},
                        {"label": "Release", "type": "menuItem"},
                    ]
                },
            },
            {
                "status": 201,
                "data": {
                    "requirements": [
                        {"id": 3015, "tag": "BR-3015", "fields": []}
                    ]
                },
            },
        ]

        def fake_request(path, token=None, body=None, method="GET"):
            self.assertEqual(token, "test-token")
            if method == "POST":
                self.posted_body = body
            return responses.pop(0)

        with patch.object(server, "_get_token", return_value="test-token"), patch.object(
            server, "_request", side_effect=fake_request
        ):
            result = server.create_requirement(
                project_name="RadiMation",
                summary="A driver is available",
                requirement_type="Business Requirement",
                additional_fields={
                    "Importance": "Must",
                    "Release": "<= 2021.3",
                },
            )

        self.assertEqual(json.loads(result)["requirement"]["tag"], "BR-3015")
        posted_body = self.posted_body
        self.assertIsNotNone(posted_body)
        assert posted_body is not None
        fields = {
            field["label"]: field
            for field in posted_body["requirements"][0]["fields"]
        }
        self.assertEqual(fields["Importance"]["type"], "menuItem")
        self.assertEqual(fields["Importance"]["menuItem"], {"label": "Must"})
        self.assertEqual(fields["Release"]["menuItem"], {"label": "<= 2021.3"})
        self.assertEqual(
            self.posted_body["requirements"][0]["requirementType"],
            {"label": "Business Requirement"},
        )


if __name__ == "__main__":
    unittest.main()
