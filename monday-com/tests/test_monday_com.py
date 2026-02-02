# -*- coding: utf-8 -*-
import unittest
from unittest.mock import Mock, patch, AsyncMock
from context import monday_com
import json


class TestMondayComIntegration(unittest.TestCase):
    """Test suite for Monday.com integration"""

    def test_integration_loaded(self):
        """Test that the integration loads successfully"""
        self.assertIsNotNone(monday_com)


class TestBuildHeaders(unittest.TestCase):
    """Test suite for build_headers function"""

    def test_build_headers_with_valid_context(self):
        """Test building headers with valid authentication context"""
        from monday_com import build_headers

        mock_context = Mock()
        mock_context.auth = {
            'credentials': {
                'access_token': 'test_token_12345'
            }
        }

        headers = build_headers(mock_context)

        self.assertEqual(headers['Authorization'], 'test_token_12345')
        self.assertEqual(headers['Content-Type'], 'application/json')
        self.assertEqual(headers['API-Version'], '2024-10')

    def test_build_headers_structure(self):
        """Test that headers contain all required fields"""
        from monday_com import build_headers

        mock_context = Mock()
        mock_context.auth = {
            'credentials': {
                'access_token': 'another_test_token'
            }
        }

        headers = build_headers(mock_context)

        self.assertIn('Authorization', headers)
        self.assertIn('Content-Type', headers)
        self.assertIn('API-Version', headers)


class TestExecuteGraphQLQuery(unittest.IsolatedAsyncioTestCase):
    """Test suite for execute_graphql_query function"""

    async def test_execute_query_success(self):
        """Test successful GraphQL query execution"""
        from monday_com import execute_graphql_query

        mock_context = Mock()
        mock_context.auth = {
            'credentials': {
                'access_token': 'test_token'
            }
        }
        mock_context.fetch = AsyncMock(return_value={'data': {'boards': []}})

        query = "query { boards { id } }"
        variables = {'limit': 10}

        result = await execute_graphql_query(query, variables, mock_context)

        self.assertEqual(result, {'data': {'boards': []}})
        mock_context.fetch.assert_called_once()

        call_args = mock_context.fetch.call_args
        self.assertEqual(call_args[0][0], 'https://api.monday.com/v2')
        self.assertEqual(call_args[1]['method'], 'POST')
        self.assertEqual(call_args[1]['json']['query'], query)
        self.assertEqual(call_args[1]['json']['variables'], variables)

    async def test_execute_query_with_correct_url(self):
        """Test that queries are sent to the correct API endpoint"""
        from monday_com import execute_graphql_query

        mock_context = Mock()
        mock_context.auth = {
            'credentials': {
                'access_token': 'test_token'
            }
        }
        mock_context.fetch = AsyncMock(return_value={'data': {}})

        await execute_graphql_query("query {}", {}, mock_context)

        call_args = mock_context.fetch.call_args
        self.assertEqual(call_args[0][0], 'https://api.monday.com/v2')


class TestGetBoards(unittest.IsolatedAsyncioTestCase):
    """Test suite for GetBoards action"""

    @patch('monday_com.execute_graphql_query')
    async def test_get_boards_success(self, mock_query):
        """Test successful retrieval of boards"""
        from monday_com import GetBoards

        mock_query.return_value = {
            'data': {
                'boards': [
                    {'id': '1', 'name': 'Board 1', 'description': 'Test board'},
                    {'id': '2', 'name': 'Board 2', 'description': 'Another board'}
                ]
            }
        }

        handler = GetBoards()
        mock_context = Mock()
        mock_context.auth = {'credentials': {'access_token': 'test_token'}}

        result = await handler.execute({}, mock_context)

        self.assertTrue(result.data['result'])
        self.assertEqual(result.data['board_count'], 2)
        self.assertEqual(len(result.data['boards']), 2)

    @patch('monday_com.execute_graphql_query')
    async def test_get_boards_with_pagination(self, mock_query):
        """Test boards retrieval with pagination parameters"""
        from monday_com import GetBoards

        mock_query.return_value = {
            'data': {
                'boards': [{'id': '1', 'name': 'Board 1'}]
            }
        }

        handler = GetBoards()
        mock_context = Mock()
        mock_context.auth = {'credentials': {'access_token': 'test_token'}}

        inputs = {'limit': 10, 'page': 2, 'board_kind': 'public'}
        result = await handler.execute(inputs, mock_context)

        self.assertTrue(result.data['result'])
        mock_query.assert_called_once()

    @patch('monday_com.execute_graphql_query')
    async def test_get_boards_api_error(self, mock_query):
        """Test handling of API errors in boards retrieval"""
        from monday_com import GetBoards

        mock_query.return_value = {
            'errors': [{'message': 'API Error'}]
        }

        handler = GetBoards()
        mock_context = Mock()
        mock_context.auth = {'credentials': {'access_token': 'test_token'}}

        result = await handler.execute({}, mock_context)

        self.assertFalse(result.data['result'])
        self.assertEqual(result.data['board_count'], 0)
        self.assertIn('error', result.data)

    @patch('monday_com.execute_graphql_query')
    async def test_get_boards_exception_handling(self, mock_query):
        """Test exception handling in boards retrieval"""
        from monday_com import GetBoards

        mock_query.side_effect = Exception('Network error')

        handler = GetBoards()
        mock_context = Mock()
        mock_context.auth = {'credentials': {'access_token': 'test_token'}}

        result = await handler.execute({}, mock_context)

        self.assertFalse(result.data['result'])
        self.assertEqual(result.data['board_count'], 0)
        self.assertIn('Network error', result.data['error'])


class TestGetItems(unittest.IsolatedAsyncioTestCase):
    """Test suite for GetItems action"""

    @patch('monday_com.execute_graphql_query')
    async def test_get_items_success(self, mock_query):
        """Test successful retrieval of items from a board"""
        from monday_com import GetItems

        mock_query.return_value = {
            'data': {
                'boards': [{
                    'items_page': {
                        'items': [
                            {'id': '1', 'name': 'Item 1'},
                            {'id': '2', 'name': 'Item 2'}
                        ],
                        'cursor': 'next_page_cursor'
                    }
                }]
            }
        }

        handler = GetItems()
        mock_context = Mock()
        mock_context.auth = {'credentials': {'access_token': 'test_token'}}

        result = await handler.execute({'board_id': '123'}, mock_context)

        self.assertTrue(result.data['result'])
        self.assertEqual(result.data['item_count'], 2)
        self.assertEqual(result.data['cursor'], 'next_page_cursor')

    @patch('monday_com.execute_graphql_query')
    async def test_get_items_with_cursor(self, mock_query):
        """Test items retrieval with pagination cursor"""
        from monday_com import GetItems

        mock_query.return_value = {
            'data': {
                'boards': [{
                    'items_page': {
                        'items': [{'id': '3', 'name': 'Item 3'}],
                        'cursor': None
                    }
                }]
            }
        }

        handler = GetItems()
        mock_context = Mock()
        mock_context.auth = {'credentials': {'access_token': 'test_token'}}

        inputs = {'board_id': '123', 'cursor': 'previous_cursor', 'limit': 50}
        result = await handler.execute(inputs, mock_context)

        self.assertTrue(result.data['result'])
        self.assertIsNone(result.data['cursor'])

    @patch('monday_com.execute_graphql_query')
    async def test_get_items_empty_board(self, mock_query):
        """Test retrieval from an empty board"""
        from monday_com import GetItems

        mock_query.return_value = {
            'data': {
                'boards': [{
                    'items_page': {
                        'items': [],
                        'cursor': None
                    }
                }]
            }
        }

        handler = GetItems()
        mock_context = Mock()
        mock_context.auth = {'credentials': {'access_token': 'test_token'}}

        result = await handler.execute({'board_id': '123'}, mock_context)

        self.assertTrue(result.data['result'])
        self.assertEqual(result.data['item_count'], 0)

    @patch('monday_com.execute_graphql_query')
    async def test_get_items_api_error(self, mock_query):
        """Test handling of API errors in items retrieval"""
        from monday_com import GetItems

        mock_query.return_value = {
            'errors': [{'message': 'Board not found'}]
        }

        handler = GetItems()
        mock_context = Mock()
        mock_context.auth = {'credentials': {'access_token': 'test_token'}}

        result = await handler.execute({'board_id': '999'}, mock_context)

        self.assertFalse(result.data['result'])
        self.assertEqual(result.data['item_count'], 0)


class TestCreateItem(unittest.IsolatedAsyncioTestCase):
    """Test suite for CreateItem action"""

    @patch('monday_com.execute_graphql_query')
    async def test_create_item_success(self, mock_query):
        """Test successful item creation"""
        from monday_com import CreateItem

        mock_query.return_value = {
            'data': {
                'create_item': {
                    'id': '456',
                    'name': 'New Item',
                    'state': 'active'
                }
            }
        }

        handler = CreateItem()
        mock_context = Mock()
        mock_context.auth = {'credentials': {'access_token': 'test_token'}}

        inputs = {
            'board_id': '123',
            'item_name': 'New Item',
            'group_id': 'group1'
        }
        result = await handler.execute(inputs, mock_context)

        self.assertTrue(result.data['result'])
        self.assertEqual(result.data['item']['id'], '456')
        self.assertEqual(result.data['item']['name'], 'New Item')

    @patch('monday_com.execute_graphql_query')
    async def test_create_item_with_column_values(self, mock_query):
        """Test item creation with column values"""
        from monday_com import CreateItem

        mock_query.return_value = {
            'data': {
                'create_item': {
                    'id': '789',
                    'name': 'Item with values',
                    'column_values': [
                        {'id': 'status', 'text': 'Done'}
                    ]
                }
            }
        }

        handler = CreateItem()
        mock_context = Mock()
        mock_context.auth = {'credentials': {'access_token': 'test_token'}}

        inputs = {
            'board_id': '123',
            'item_name': 'Item with values',
            'column_values': json.dumps({'status': 'Done'})
        }
        result = await handler.execute(inputs, mock_context)

        self.assertTrue(result.data['result'])

    @patch('monday_com.execute_graphql_query')
    async def test_create_item_api_error(self, mock_query):
        """Test handling of API errors in item creation"""
        from monday_com import CreateItem

        mock_query.return_value = {
            'errors': [{'message': 'Invalid board_id'}]
        }

        handler = CreateItem()
        mock_context = Mock()
        mock_context.auth = {'credentials': {'access_token': 'test_token'}}

        inputs = {'board_id': 'invalid', 'item_name': 'Test'}
        result = await handler.execute(inputs, mock_context)

        self.assertFalse(result.data['result'])
        self.assertIsNone(result.data['item'])


class TestUpdateItem(unittest.IsolatedAsyncioTestCase):
    """Test suite for UpdateItem action"""

    @patch('monday_com.execute_graphql_query')
    async def test_update_item_success(self, mock_query):
        """Test successful item update"""
        from monday_com import UpdateItem

        mock_query.return_value = {
            'data': {
                'change_multiple_column_values': {
                    'id': '456',
                    'name': 'Updated Item',
                    'updated_at': '2024-01-01T00:00:00Z'
                }
            }
        }

        handler = UpdateItem()
        mock_context = Mock()
        mock_context.auth = {'credentials': {'access_token': 'test_token'}}

        inputs = {
            'board_id': '123',
            'item_id': '456',
            'column_values': json.dumps({'status': 'Done'})
        }
        result = await handler.execute(inputs, mock_context)

        self.assertTrue(result.data['result'])
        self.assertEqual(result.data['item']['id'], '456')

    @patch('monday_com.execute_graphql_query')
    async def test_update_item_api_error(self, mock_query):
        """Test handling of API errors in item update"""
        from monday_com import UpdateItem

        mock_query.return_value = {
            'errors': [{'message': 'Item not found'}]
        }

        handler = UpdateItem()
        mock_context = Mock()
        mock_context.auth = {'credentials': {'access_token': 'test_token'}}

        inputs = {
            'board_id': '123',
            'item_id': '999',
            'column_values': '{}'
        }
        result = await handler.execute(inputs, mock_context)

        self.assertFalse(result.data['result'])
        self.assertIsNone(result.data['item'])

    @patch('monday_com.execute_graphql_query')
    async def test_update_item_exception_handling(self, mock_query):
        """Test exception handling in item update"""
        from monday_com import UpdateItem

        mock_query.side_effect = Exception('Connection timeout')

        handler = UpdateItem()
        mock_context = Mock()
        mock_context.auth = {'credentials': {'access_token': 'test_token'}}

        inputs = {
            'board_id': '123',
            'item_id': '456',
            'column_values': '{}'
        }
        result = await handler.execute(inputs, mock_context)

        self.assertFalse(result.data['result'])
        self.assertIn('Connection timeout', result.data['error'])


class TestCreateUpdate(unittest.IsolatedAsyncioTestCase):
    """Test suite for CreateUpdate action"""

    @patch('monday_com.execute_graphql_query')
    async def test_create_update_success(self, mock_query):
        """Test successful update/comment creation"""
        from monday_com import CreateUpdate

        mock_query.return_value = {
            'data': {
                'create_update': {
                    'id': '789',
                    'body': 'This is a comment',
                    'created_at': '2024-01-01T00:00:00Z',
                    'creator': {'id': '1', 'name': 'Test User'}
                }
            }
        }

        handler = CreateUpdate()
        mock_context = Mock()
        mock_context.auth = {'credentials': {'access_token': 'test_token'}}

        inputs = {
            'item_id': '456',
            'body': 'This is a comment'
        }
        result = await handler.execute(inputs, mock_context)

        self.assertTrue(result.data['result'])
        self.assertEqual(result.data['update']['body'], 'This is a comment')

    @patch('monday_com.execute_graphql_query')
    async def test_create_update_api_error(self, mock_query):
        """Test handling of API errors in update creation"""
        from monday_com import CreateUpdate

        mock_query.return_value = {
            'errors': [{'message': 'Item not found'}]
        }

        handler = CreateUpdate()
        mock_context = Mock()
        mock_context.auth = {'credentials': {'access_token': 'test_token'}}

        inputs = {'item_id': '999', 'body': 'Comment'}
        result = await handler.execute(inputs, mock_context)

        self.assertFalse(result.data['result'])
        self.assertIsNone(result.data['update'])


class TestGetUsers(unittest.IsolatedAsyncioTestCase):
    """Test suite for GetUsers action"""

    @patch('monday_com.execute_graphql_query')
    async def test_get_users_success(self, mock_query):
        """Test successful retrieval of users"""
        from monday_com import GetUsers

        mock_query.return_value = {
            'data': {
                'users': [
                    {'id': '1', 'name': 'User 1', 'email': 'user1@example.com'},
                    {'id': '2', 'name': 'User 2', 'email': 'user2@example.com'}
                ]
            }
        }

        handler = GetUsers()
        mock_context = Mock()
        mock_context.auth = {'credentials': {'access_token': 'test_token'}}

        result = await handler.execute({}, mock_context)

        self.assertTrue(result.data['result'])
        self.assertEqual(result.data['user_count'], 2)
        self.assertEqual(len(result.data['users']), 2)

    @patch('monday_com.execute_graphql_query')
    async def test_get_users_with_pagination(self, mock_query):
        """Test users retrieval with pagination"""
        from monday_com import GetUsers

        mock_query.return_value = {
            'data': {
                'users': [{'id': '1', 'name': 'User 1'}]
            }
        }

        handler = GetUsers()
        mock_context = Mock()
        mock_context.auth = {'credentials': {'access_token': 'test_token'}}

        inputs = {'limit': 50, 'page': 3}
        result = await handler.execute(inputs, mock_context)

        self.assertTrue(result.data['result'])

    @patch('monday_com.execute_graphql_query')
    async def test_get_users_api_error(self, mock_query):
        """Test handling of API errors in users retrieval"""
        from monday_com import GetUsers

        mock_query.return_value = {
            'errors': [{'message': 'Unauthorized'}]
        }

        handler = GetUsers()
        mock_context = Mock()
        mock_context.auth = {'credentials': {'access_token': 'invalid_token'}}

        result = await handler.execute({}, mock_context)

        self.assertFalse(result.data['result'])
        self.assertEqual(result.data['user_count'], 0)

    @patch('monday_com.execute_graphql_query')
    async def test_get_users_exception_handling(self, mock_query):
        """Test exception handling in users retrieval"""
        from monday_com import GetUsers

        mock_query.side_effect = Exception('API unavailable')

        handler = GetUsers()
        mock_context = Mock()
        mock_context.auth = {'credentials': {'access_token': 'test_token'}}

        result = await handler.execute({}, mock_context)

        self.assertFalse(result.data['result'])
        self.assertIn('API unavailable', result.data['error'])


if __name__ == '__main__':
    unittest.main()
