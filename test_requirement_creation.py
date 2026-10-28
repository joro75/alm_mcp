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

    def test_supported_field_types_are_encoded(self):
        field_types = {
            "Notes": "formattedString",
            "Source": "user",
            "Owners": "userArray",
            "Story Points": "integer",
        }
        self.assertEqual(
            server._build_requirement_field("Notes", "text", field_types),
            {
                "label": "Notes",
                "type": "formattedString",
                "formattedString": {"isFormatted": False, "text": "text"},
            },
        )
        self.assertEqual(
            server._build_requirement_field("Source", "joro", field_types),
            {"label": "Source", "type": "user", "user": {"username": "joro"}},
        )
        self.assertEqual(
            server._build_requirement_field("Owners", [{"username": "joro"}], field_types),
            {"label": "Owners", "type": "userArray", "userArray": [{"username": "joro"}]},
        )
        self.assertEqual(
            server._build_requirement_field("Story Points", 3, field_types),
            {"label": "Story Points", "type": "integer", "integer": 3},
        )

    def test_non_dictionary_additional_fields_is_rejected_without_posting(self):
        with patch.object(server, "_get_token", return_value="test-token"), patch.object(
            server, "_request"
        ) as request:
            result = server.create_requirement(
                project_name="RadiMation",
                summary="Invalid input",
                additional_fields="{\"Importance\": \"Must\"}",
            )

        self.assertEqual(result, "Error: additional_fields must be a dictionary.")
        request.assert_not_called()

    def test_field_discovery_failure_falls_back_to_known_menu_types(self):
        with patch.object(server, "_request", return_value={"status": 500, "error": True}):
            field_types = server._requirement_field_types("RadiMation", "test-token")

        self.assertEqual(field_types, {})
        self.assertEqual(
            server._build_requirement_field("Importance", "Must", field_types),
            {"label": "Importance", "type": "menuItem", "menuItem": {"label": "Must"}},
        )

    def test_partial_create_response_reports_warnings(self):
        responses = [
            {"status": 200, "data": {"requirements": [{"id": 1}]}},
            {"status": 200, "data": {"fields": []}},
            {
                "status": 206,
                "error": True,
                "data": {
                    "requirements": [{"id": 3015, "tag": "BR-3015", "fields": []}],
                    "errors": [{"message": "Optional field ignored"}],
                },
            },
        ]

        with patch.object(server, "_get_token", return_value="test-token"), patch.object(
            server, "_request", side_effect=lambda *args, **kwargs: responses.pop(0)
        ):
            result = json.loads(
                server.create_requirement(project_name="RadiMation", summary="Partial create")
            )

        self.assertEqual(result["message"], "Requirement created with warnings")
        self.assertEqual(result["requirement"]["tag"], "BR-3015")
        self.assertEqual(result["warnings"][0]["message"], "Optional field ignored")

    def test_document_membership_uses_expanded_documents(self):
        responses = [
            {"status": 200, "data": {"documents": [{"id": 65, "fields": [{"label": "Name", "type": "string", "string": "Raditeq RadiPower-series"}]}]}},
            {
                "status": 200,
                "data": {
                    "paging": {"totalPages": 1},
                    "requirements": [{
                        "id": 3015,
                        "tag": "BR-3015",
                        "requirementType": {"label": "Business Requirement"},
                        "documents": {"documentsData": [{"documentID": 65}]},
                        "fields": [{"label": "Summary", "type": "string", "string": "A driver"}],
                    }],
                },
            },
        ]

        def fake_request(path, token=None, body=None, method="GET"):
            self.assertIn(path, {
                "RadiMation/documents",
                "RadiMation/requirements?expand=documents&per_page=300&page=1",
            })
            return responses.pop(0)

        with patch.object(server, "_get_token", return_value="test-token"), patch.object(
            server, "_request", side_effect=fake_request
        ):
            result = json.loads(
                server.get_document_requirements(
                    project_name="RadiMation",
                    document_name="Raditeq RadiPower-series",
                )
            )

        self.assertEqual(result["total_requirements"], 1)
        self.assertEqual(result["by_type"]["Business Requirement"][0]["tag"], "BR-3015")

    def test_tree_builder_uses_inline_child_nodes(self):
        nodes = [{
            "id": 13,
            "outlineNumber": "4",
            "requirementID": 1166,
            "tag": "BR-1166",
            "childNodes": {"childNodesData": [{
                "id": 40,
                "outlineNumber": "4.5",
                "requirementID": 3015,
                "tag": "BR-3015",
                "childNodes": {"childNodesData": []},
            }]},
        }]

        def fake_request(path, token=None, body=None, method="GET"):
            if "/requirements/" in path:
                requirement_id = int(path.rsplit("/", 1)[1])
                return {"status": 200, "data": {
                    "requirementType": {"label": "Business Requirement"},
                    "fields": [{"label": "Summary", "type": "string", "string": str(requirement_id)}],
                }}
            self.fail(f"unexpected tree request: {path}")

        with patch.object(server, "_request", side_effect=fake_request):
            tree = server._build_tree_recursive("RadiMation", "test-token", 65, None, 0, 3, nodes)

        self.assertEqual(tree[0]["children"][0]["tag"], "BR-3015")

    def test_tree_builder_can_omit_requirement_detail_requests(self):
        nodes = [{
            "id": 40,
            "outlineNumber": "4.5",
            "requirementID": 3015,
            "tag": "BR-3015",
            "childNodes": {"childNodesData": []},
        }]

        with patch.object(server, "_request") as request:
            tree = server._build_tree_recursive(
                "RadiMation", "test-token", 65, None, 0, 3, nodes,
                include_requirement_details=False,
            )

        self.assertEqual(tree[0]["tag"], "BR-3015")
        self.assertNotIn("summary", tree[0])
        request.assert_not_called()

    def test_description_length_options_and_truncation_notice(self):
        description = "A" * 301
        self.assertEqual(server._limit_description(description, 0), description)
        self.assertEqual(server._limit_description(description, None), description)
        self.assertEqual(server._limit_description("short", 300), "short")

        truncated = server._limit_description(description, 300)
        self.assertTrue(truncated.startswith("A" * 300))
        self.assertTrue(truncated.endswith(server._DESCRIPTION_TRUNCATION_NOTICE))
        self.assertEqual(
            truncated,
            "A" * 300 + " ... [TRUNCATED DESCRIPTION. Call `get_requirement` for the full description]",
        )

        custom_limit = server._limit_description(description, 10)
        self.assertEqual(
            custom_limit,
            "A" * 10 + " ... [TRUNCATED DESCRIPTION. Call `get_requirement` for the full description]",
        )

    def test_negative_description_length_is_rejected(self):
        with self.assertRaises(ValueError):
            server._limit_description("description", -1)

    def test_tree_builder_applies_custom_description_length(self):
        description = "A longer requirement description"
        nodes = [{
            "id": 40,
            "outlineNumber": "4.5",
            "requirementID": 3015,
            "tag": "BR-3015",
            "childNodes": {"childNodesData": []},
        }]

        def fake_request(path, token=None, body=None, method="GET"):
            return {"status": 200, "data": {
                "requirementType": {"label": "Business Requirement"},
                "fields": [{"label": "Description", "type": "formattedString", "formattedString": {"text": description}}],
            }}

        with patch.object(server, "_request", side_effect=fake_request):
            tree = server._build_tree_recursive(
                "RadiMation", "test-token", 65, None, 0, 3, nodes,
                max_description_length=10,
            )

        self.assertEqual(
            tree[0]["description"],
            "A longer r ... [TRUNCATED DESCRIPTION. Call `get_requirement` for the full description]",
        )


if __name__ == "__main__":
    unittest.main()
