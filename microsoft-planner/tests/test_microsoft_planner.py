import unittest
from unittest.mock import AsyncMock, Mock, patch
import json
from context import microsoft_planner


class TestMicrosoftPlannerIntegration(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures."""
        self.mock_context = Mock()
        self.mock_context.fetch = AsyncMock()


    # ---- User Lookup Tests ----

    async def test_get_user_by_email_success(self):
        """Test successful user lookup by email."""
        mock_response = {
            "value": [
                {
                    "id": "user-id-123",
                    "displayName": "John Doe",
                    "mail": "john.doe@example.com",
                    "userPrincipalName": "john.doe@example.com",
                    "jobTitle": "Software Engineer"
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft_planner.GetUserByEmailAction()
        inputs = {"email": "john.doe@example.com"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(result["user_id"], "user-id-123")
        self.assertEqual(result["display_name"], "John Doe")
        self.assertEqual(result["email"], "john.doe@example.com")

        # Verify API call with filter
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/users", call_args[0][0])
        self.assertIn("$filter", call_args[1]["params"])


    async def test_get_user_by_email_not_found(self):
        """Test user lookup by email when user doesn't exist."""
        mock_response = {"value": []}
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft_planner.GetUserByEmailAction()
        inputs = {"email": "nonexistent@example.com"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertFalse(result["result"])
        self.assertIn("not found", result["error"])


    async def test_search_users_success(self):
        """Test successful user search."""
        mock_response = {
            "value": [
                {
                    "id": "user-id-1",
                    "displayName": "John Doe",
                    "mail": "john.doe@example.com",
                    "jobTitle": "Software Engineer"
                },
                {
                    "id": "user-id-2",
                    "displayName": "Jane Doe",
                    "mail": "jane.doe@example.com",
                    "jobTitle": "Product Manager"
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft_planner.SearchUsersAction()
        inputs = {"query": "Doe", "limit": 10}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(len(result["users"]), 2)
        self.assertEqual(result["users"][0]["display_name"], "John Doe")
        self.assertEqual(result["users"][0]["user_id"], "user-id-1")

        # Verify API call with search parameter
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/users", call_args[0][0])
        self.assertIn("$search", call_args[1]["params"])
        self.assertIn("ConsistencyLevel", call_args[1]["headers"])


    async def test_get_current_user_success(self):
        """Test getting current authenticated user."""
        mock_response = {
            "id": "current-user-id",
            "displayName": "Current User",
            "mail": "current@example.com",
            "userPrincipalName": "current@example.com"
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft_planner.GetCurrentUserAction()
        inputs = {}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(result["user_id"], "current-user-id")
        self.assertEqual(result["display_name"], "Current User")
        self.assertEqual(result["email"], "current@example.com")

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/me", call_args[0][0])


    # ---- Group Tests ----

    async def test_list_groups_success(self):
        """Test successful group listing."""
        mock_response = {
            "value": [
                {
                    "id": "group-id-1",
                    "displayName": "Marketing Team",
                    "description": "Marketing group"
                },
                {
                    "id": "group-id-2",
                    "displayName": "Engineering Team",
                    "description": "Engineering group"
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft_planner.ListGroupsAction()
        inputs = {"limit": 100}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(len(result["groups"]), 2)
        self.assertEqual(result["groups"][0]["displayName"], "Marketing Team")

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/me/memberOf/microsoft.graph.group", call_args[0][0])
        self.assertEqual(call_args[1]["method"], "GET")


    # ---- Plan Tests ----

    async def test_list_plans_success(self):
        """Test successful plan listing for a group."""
        mock_response = {
            "value": [
                {
                    "id": "plan-id-1",
                    "title": "Marketing Plan Q1",
                    "owner": "group-id-1"
                },
                {
                    "id": "plan-id-2",
                    "title": "Product Launch",
                    "owner": "group-id-1"
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft_planner.ListPlansAction()
        inputs = {"group_id": "group-id-1"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(len(result["plans"]), 2)
        self.assertEqual(result["plans"][0]["title"], "Marketing Plan Q1")

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/groups/group-id-1/planner/plans", call_args[0][0])


    async def test_get_plan_success(self):
        """Test successful plan retrieval."""
        mock_response = {
            "id": "plan-id-1",
            "title": "Marketing Plan Q1",
            "owner": "group-id-1",
            "createdDateTime": "2024-01-15T10:00:00Z"
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft_planner.GetPlanAction()
        inputs = {"plan_id": "plan-id-1"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(result["plan"]["id"], "plan-id-1")
        self.assertEqual(result["plan"]["title"], "Marketing Plan Q1")

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/planner/plans/plan-id-1", call_args[0][0])


    # ---- Bucket Tests ----

    async def test_list_buckets_success(self):
        """Test successful bucket listing for a plan."""
        mock_response = {
            "value": [
                {
                    "id": "bucket-id-1",
                    "name": "To Do",
                    "planId": "plan-id-1",
                    "orderHint": "8585269235419339378"
                },
                {
                    "id": "bucket-id-2",
                    "name": "In Progress",
                    "planId": "plan-id-1",
                    "orderHint": "8585269235419339379"
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft_planner.ListBucketsAction()
        inputs = {"plan_id": "plan-id-1"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(len(result["buckets"]), 2)
        self.assertEqual(result["buckets"][0]["name"], "To Do")

        # Verify API call with filter
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/planner/buckets", call_args[0][0])
        self.assertIn("$filter", call_args[1]["params"])


    async def test_create_bucket_success(self):
        """Test successful bucket creation."""
        mock_response = {
            "id": "bucket-id-3",
            "name": "Done",
            "planId": "plan-id-1",
            "orderHint": "8585269235419339380"
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft_planner.CreateBucketAction()
        inputs = {
            "name": "Done",
            "plan_id": "plan-id-1",
            "order_hint": " !"
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(result["bucket"]["id"], "bucket-id-3")
        self.assertEqual(result["bucket"]["name"], "Done")

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/planner/buckets", call_args[0][0])
        self.assertEqual(call_args[1]["method"], "POST")

        # Verify body
        body = call_args[1]["json"]
        self.assertEqual(body["name"], "Done")
        self.assertEqual(body["planId"], "plan-id-1")


    async def test_update_bucket_success(self):
        """Test successful bucket update."""
        # Mock ETag fetch
        mock_etag_response = {
            "@odata.etag": "W/\"etag-value-123\"",
            "id": "bucket-id-1",
            "name": "To Do"
        }

        # Mock update response
        mock_update_response = {
            "id": "bucket-id-1",
            "name": "Backlog",
            "planId": "plan-id-1"
        }

        # First call returns ETag, second call returns updated bucket
        self.mock_context.fetch.side_effect = [mock_etag_response, mock_update_response]

        handler = microsoft_planner.UpdateBucketAction()
        inputs = {
            "bucket_id": "bucket-id-1",
            "name": "Backlog"
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(result["bucket"]["name"], "Backlog")

        # Verify API calls
        self.assertEqual(self.mock_context.fetch.call_count, 2)

        # Verify update call has If-Match header
        update_call = self.mock_context.fetch.call_args_list[1]
        self.assertIn("If-Match", update_call[1]["headers"])
        self.assertEqual(update_call[1]["headers"]["If-Match"], "W/\"etag-value-123\"")
        self.assertEqual(update_call[1]["method"], "PATCH")


    async def test_delete_bucket_success(self):
        """Test successful bucket deletion."""
        # Mock ETag fetch
        mock_etag_response = {
            "@odata.etag": "W/\"etag-value-456\"",
            "id": "bucket-id-1"
        }

        # First call returns ETag, second call deletes
        self.mock_context.fetch.side_effect = [mock_etag_response, None]

        handler = microsoft_planner.DeleteBucketAction()
        inputs = {"bucket_id": "bucket-id-1"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])

        # Verify API calls
        self.assertEqual(self.mock_context.fetch.call_count, 2)

        # Verify delete call has If-Match header
        delete_call = self.mock_context.fetch.call_args_list[1]
        self.assertIn("If-Match", delete_call[1]["headers"])
        self.assertEqual(delete_call[1]["method"], "DELETE")


    # ---- Task Tests ----

    async def test_list_tasks_success(self):
        """Test successful task listing for a plan."""
        mock_response = {
            "value": [
                {
                    "id": "task-id-1",
                    "title": "Create marketing materials",
                    "planId": "plan-id-1",
                    "bucketId": "bucket-id-1",
                    "percentComplete": 50
                },
                {
                    "id": "task-id-2",
                    "title": "Schedule campaign launch",
                    "planId": "plan-id-1",
                    "bucketId": "bucket-id-2",
                    "percentComplete": 0
                }
            ]
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft_planner.ListTasksAction()
        inputs = {"plan_id": "plan-id-1"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(len(result["tasks"]), 2)
        self.assertEqual(result["tasks"][0]["title"], "Create marketing materials")

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/planner/plans/plan-id-1/tasks", call_args[0][0])


    async def test_get_task_success(self):
        """Test successful task retrieval."""
        mock_response = {
            "id": "task-id-1",
            "title": "Create marketing materials",
            "planId": "plan-id-1",
            "bucketId": "bucket-id-1",
            "percentComplete": 50,
            "priority": 5,
            "assignments": {
                "user-id-1": {
                    "@odata.type": "#microsoft.graph.plannerAssignment",
                    "assignedDateTime": "2024-01-15T10:00:00Z"
                }
            }
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft_planner.GetTaskAction()
        inputs = {"task_id": "task-id-1"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(result["task"]["id"], "task-id-1")
        self.assertEqual(result["task"]["title"], "Create marketing materials")
        self.assertEqual(result["task"]["percentComplete"], 50)

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/planner/tasks/task-id-1", call_args[0][0])


    async def test_create_task_success(self):
        """Test successful task creation."""
        mock_response = {
            "id": "task-id-3",
            "title": "Review campaign results",
            "planId": "plan-id-1",
            "bucketId": "bucket-id-1",
            "percentComplete": 0,
            "priority": 3,
            "dueDateTime": "2024-12-31T17:00:00Z",
            "assignments": {
                "user-id-1": {
                    "@odata.type": "#microsoft.graph.plannerAssignment",
                    "orderHint": " !"
                }
            }
        }
        self.mock_context.fetch.return_value = mock_response

        handler = microsoft_planner.CreateTaskAction()
        inputs = {
            "plan_id": "plan-id-1",
            "bucket_id": "bucket-id-1",
            "title": "Review campaign results",
            "priority": 3,
            "due_date_time": "2024-12-31T17:00:00Z",
            "percent_complete": 0,
            "assignments": {
                "user-id-1": {
                    "@odata.type": "#microsoft.graph.plannerAssignment",
                    "orderHint": " !"
                }
            }
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(result["task"]["id"], "task-id-3")
        self.assertEqual(result["task"]["title"], "Review campaign results")
        self.assertEqual(result["task"]["priority"], 3)

        # Verify API call
        call_args = self.mock_context.fetch.call_args
        self.assertIn("/planner/tasks", call_args[0][0])
        self.assertEqual(call_args[1]["method"], "POST")

        # Verify body
        body = call_args[1]["json"]
        self.assertEqual(body["title"], "Review campaign results")
        self.assertEqual(body["planId"], "plan-id-1")
        self.assertEqual(body["bucketId"], "bucket-id-1")
        self.assertEqual(body["priority"], 3)


    async def test_update_task_success(self):
        """Test successful task update."""
        # Mock ETag fetch
        mock_etag_response = {
            "@odata.etag": "W/\"etag-value-789\"",
            "id": "task-id-1",
            "title": "Create marketing materials"
        }

        # Mock update response
        mock_update_response = {
            "id": "task-id-1",
            "title": "Create updated marketing materials",
            "percentComplete": 75,
            "priority": 1
        }

        # First call returns ETag, second call returns updated task
        self.mock_context.fetch.side_effect = [mock_etag_response, mock_update_response]

        handler = microsoft_planner.UpdateTaskAction()
        inputs = {
            "task_id": "task-id-1",
            "title": "Create updated marketing materials",
            "percent_complete": 75,
            "priority": 1
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertEqual(result["task"]["title"], "Create updated marketing materials")
        self.assertEqual(result["task"]["percentComplete"], 75)

        # Verify API calls
        self.assertEqual(self.mock_context.fetch.call_count, 2)

        # Verify update call has If-Match header
        update_call = self.mock_context.fetch.call_args_list[1]
        self.assertIn("If-Match", update_call[1]["headers"])
        self.assertEqual(update_call[1]["headers"]["If-Match"], "W/\"etag-value-789\"")
        self.assertEqual(update_call[1]["method"], "PATCH")

        # Verify body
        body = update_call[1]["json"]
        self.assertEqual(body["title"], "Create updated marketing materials")
        self.assertEqual(body["percentComplete"], 75)


    async def test_delete_task_success(self):
        """Test successful task deletion."""
        # Mock ETag fetch
        mock_etag_response = {
            "@odata.etag": "W/\"etag-value-999\"",
            "id": "task-id-1"
        }

        # First call returns ETag, second call deletes
        self.mock_context.fetch.side_effect = [mock_etag_response, None]

        handler = microsoft_planner.DeleteTaskAction()
        inputs = {"task_id": "task-id-1"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])

        # Verify API calls
        self.assertEqual(self.mock_context.fetch.call_count, 2)

        # Verify delete call has If-Match header
        delete_call = self.mock_context.fetch.call_args_list[1]
        self.assertIn("If-Match", delete_call[1]["headers"])
        self.assertEqual(delete_call[1]["method"], "DELETE")


    # ---- Error Handling Tests ----

    async def test_error_handling(self):
        """Test error handling in actions."""
        # Mock API error
        self.mock_context.fetch.side_effect = Exception("API Error: Unauthorized")

        handler = microsoft_planner.ListPlansAction()
        inputs = {"group_id": "invalid-group-id"}

        result = await handler.execute(inputs, self.mock_context)

        self.assertFalse(result["result"])
        self.assertIn("error", result)
        self.assertEqual(result["error"], "API Error: Unauthorized")


    async def test_update_without_etag_fails(self):
        """Test update fails when ETag cannot be retrieved."""
        # Mock ETag fetch returns None (error case)
        self.mock_context.fetch.return_value = {}

        handler = microsoft_planner.UpdateTaskAction()
        inputs = {
            "task_id": "task-id-1",
            "title": "Updated title"
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertFalse(result["result"])
        self.assertIn("Failed to retrieve task ETag", result["error"])


    # ---- Checklist Tests ----

    async def test_add_checklist_item_success(self):
        """Test successful addition of a checklist item."""
        # Mock current task details
        mock_current_details = {
            "@odata.etag": "W/\"etag-value-checklist\"",
            "id": "task-id-1",
            "checklist": {
                "existing-item-id": {
                    "@odata.type": "#microsoft.graph.plannerChecklistItem",
                    "title": "Existing item",
                    "isChecked": False,
                    "orderHint": "8585269235419339378"
                }
            }
        }

        # Mock update response
        mock_update_response = {
            "@odata.etag": "W/\"etag-value-checklist-new\"",
            "id": "task-id-1",
            "checklist": {
                "existing-item-id": {
                    "@odata.type": "#microsoft.graph.plannerChecklistItem",
                    "title": "Existing item",
                    "isChecked": False,
                    "orderHint": "8585269235419339378"
                }
            }
        }

        # First call returns current details, second call returns updated details
        self.mock_context.fetch.side_effect = [mock_current_details, mock_update_response]

        handler = microsoft_planner.AddChecklistItemAction()
        inputs = {
            "task_id": "task-id-1",
            "title": "New checklist item",
            "is_checked": False
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])
        self.assertIn("item_id", result)
        self.assertIsNotNone(result["item_id"])

        # Verify API calls
        self.assertEqual(self.mock_context.fetch.call_count, 2)

        # Verify update call has If-Match header
        update_call = self.mock_context.fetch.call_args_list[1]
        self.assertIn("If-Match", update_call[1]["headers"])
        self.assertEqual(update_call[1]["method"], "PATCH")

        # Verify checklist in body
        body = update_call[1]["json"]
        self.assertIn("checklist", body)
        # Should have 2 items now: existing + new
        self.assertEqual(len(body["checklist"]), 2)


    async def test_update_checklist_item_success(self):
        """Test successful update of a checklist item."""
        # Mock current task details
        mock_current_details = {
            "@odata.etag": "W/\"etag-value-checklist\"",
            "id": "task-id-1",
            "checklist": {
                "item-id-1": {
                    "@odata.type": "#microsoft.graph.plannerChecklistItem",
                    "title": "Old title",
                    "isChecked": False,
                    "orderHint": "8585269235419339378"
                }
            }
        }

        # Mock update response
        mock_update_response = {
            "@odata.etag": "W/\"etag-value-checklist-updated\"",
            "id": "task-id-1",
            "checklist": {
                "item-id-1": {
                    "@odata.type": "#microsoft.graph.plannerChecklistItem",
                    "title": "Updated title",
                    "isChecked": True,
                    "orderHint": "8585269235419339378"
                }
            }
        }

        # First call returns current details, second call returns updated details
        self.mock_context.fetch.side_effect = [mock_current_details, mock_update_response]

        handler = microsoft_planner.UpdateChecklistItemAction()
        inputs = {
            "task_id": "task-id-1",
            "item_id": "item-id-1",
            "title": "Updated title",
            "is_checked": True
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])

        # Verify API calls
        self.assertEqual(self.mock_context.fetch.call_count, 2)

        # Verify update call
        update_call = self.mock_context.fetch.call_args_list[1]
        self.assertIn("If-Match", update_call[1]["headers"])
        self.assertEqual(update_call[1]["method"], "PATCH")

        # Verify checklist in body has updated item
        body = update_call[1]["json"]
        self.assertIn("checklist", body)
        self.assertEqual(body["checklist"]["item-id-1"]["title"], "Updated title")
        self.assertEqual(body["checklist"]["item-id-1"]["isChecked"], True)


    async def test_update_checklist_item_not_found(self):
        """Test updating a non-existent checklist item."""
        # Mock current task details without the item
        mock_current_details = {
            "@odata.etag": "W/\"etag-value-checklist\"",
            "id": "task-id-1",
            "checklist": {}
        }

        self.mock_context.fetch.return_value = mock_current_details

        handler = microsoft_planner.UpdateChecklistItemAction()
        inputs = {
            "task_id": "task-id-1",
            "item_id": "non-existent-item-id",
            "title": "Updated title"
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertFalse(result["result"])
        self.assertIn("not found", result["error"])


    async def test_remove_checklist_item_success(self):
        """Test successful removal of a checklist item."""
        # Mock current task details
        mock_current_details = {
            "@odata.etag": "W/\"etag-value-checklist\"",
            "id": "task-id-1",
            "checklist": {
                "item-id-1": {
                    "@odata.type": "#microsoft.graph.plannerChecklistItem",
                    "title": "Item to remove",
                    "isChecked": False,
                    "orderHint": "8585269235419339378"
                },
                "item-id-2": {
                    "@odata.type": "#microsoft.graph.plannerChecklistItem",
                    "title": "Item to keep",
                    "isChecked": False,
                    "orderHint": "8585269235419339379"
                }
            }
        }

        # Mock update response
        mock_update_response = {
            "@odata.etag": "W/\"etag-value-checklist-removed\"",
            "id": "task-id-1",
            "checklist": {
                "item-id-2": {
                    "@odata.type": "#microsoft.graph.plannerChecklistItem",
                    "title": "Item to keep",
                    "isChecked": False,
                    "orderHint": "8585269235419339379"
                }
            }
        }

        # First call returns current details, second call returns updated details
        self.mock_context.fetch.side_effect = [mock_current_details, mock_update_response]

        handler = microsoft_planner.RemoveChecklistItemAction()
        inputs = {
            "task_id": "task-id-1",
            "item_id": "item-id-1"
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertTrue(result["result"])

        # Verify API calls
        self.assertEqual(self.mock_context.fetch.call_count, 2)

        # Verify update call
        update_call = self.mock_context.fetch.call_args_list[1]
        self.assertIn("If-Match", update_call[1]["headers"])
        self.assertEqual(update_call[1]["method"], "PATCH")

        # Verify checklist in body has item set to null (for removal)
        body = update_call[1]["json"]
        self.assertIn("checklist", body)
        self.assertIsNone(body["checklist"]["item-id-1"])


    async def test_remove_checklist_item_not_found(self):
        """Test removing a non-existent checklist item."""
        # Mock current task details without the item
        mock_current_details = {
            "@odata.etag": "W/\"etag-value-checklist\"",
            "id": "task-id-1",
            "checklist": {}
        }

        self.mock_context.fetch.return_value = mock_current_details

        handler = microsoft_planner.RemoveChecklistItemAction()
        inputs = {
            "task_id": "task-id-1",
            "item_id": "non-existent-item-id"
        }

        result = await handler.execute(inputs, self.mock_context)

        self.assertFalse(result["result"])
        self.assertIn("not found", result["error"])


if __name__ == '__main__':
    unittest.main()
