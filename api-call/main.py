import sys
import os
import traceback

# Add dependencies directory to Python path
# Needs to be done above the import of integration otherwise it will throw an error as it can't find the dependencies
dependencies_path = os.path.join(os.path.dirname(__file__), "dependencies")
sys.path.insert(0, dependencies_path)

import json
import asyncio
import importlib
from typing import Dict, Any
from autohive_integrations_sdk import ExecutionContext, ValidationError

async def execute_integration(event: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an integration operation based on the event data"""
    try:
        # Load integration module

        integration_name = os.environ.get("ENTRY_POINT")
        module = importlib.import_module(integration_name)
        integration = getattr(module, integration_name)

        # Get operation type and details
        operation_type = event.get('type', 'action')
        if operation_type not in ['action', 'polling_trigger', 'webhook_trigger']:
            raise ValidationError(f"Invalid operation type: {operation_type}")

        metadata = event.get('metadata', {})

        # Get auth token from event or environment
        auth_required = os.environ.get("AUTH_REQUIRED", "false")
        context = None
        if auth_required == "true":
            auth = event.get('auth', {})
            context = ExecutionContext(
                auth=auth,
                metadata=metadata
            )
        else:
            context = ExecutionContext(metadata=metadata)

        async with context:
            if operation_type == 'action':
                return await handle_action(integration, event, context)
            elif operation_type == 'polling_trigger':
                return await handle_polling_trigger(integration, event, context)
            else:  # webhook_trigger
                return await handle_webhook_trigger(integration, event, context)

    except ValidationError as e:
        return {
            'statusCode': 400,
            'body': json.dumps({
                'success': False,
                'error': {
                    'type': 'ValidationError',
                    'message': str(e),
                    'property': getattr(e, 'property', None),
                    'value': getattr(e, 'value', None)
                }
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': {
                    'type': type(e).__name__,
                    'message': str(e),
                    'traceback': traceback.format_exc()
                }
            })
        }

async def handle_action(integration, event: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
    """Handle action execution"""
    action = event.get('action')
    if not action:
        raise ValidationError("Missing required field 'action'")

    inputs = event.get('inputs', {})

    result = await integration.execute_action(action, inputs, context)
    return {
        'statusCode': 200,
        'body': json.dumps({
            'success': True,
            'result': result
        })
    }

async def handle_polling_trigger(integration, event: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
    """Handle polling trigger execution"""
    trigger = event.get('trigger')
    if not trigger:
        raise ValidationError("Missing required field 'trigger'")

    # Get trigger state from event
    trigger_state = event.get('trigger_state', {})

    # Execute polling trigger
    results = await integration.execute_polling_trigger(trigger, trigger_state, context)

    # Return results and updated state
    return {
        'statusCode': 200,
        'body': json.dumps({
            'success': True,
            'results': results,
            'trigger_state': trigger_state  # This might have been modified during execution
        })
    }

async def handle_webhook_trigger(integration, event: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
    """Handle webhook trigger operations"""
    trigger = event.get('trigger')
    if not trigger:
        raise ValidationError("Missing required field 'trigger'")

    operation = event.get('operation')
    if not operation:
        raise ValidationError("Missing required field 'operation'")

    if operation == 'subscribe':
        webhook_url = event.get('webhook_url')
        if not webhook_url:
            raise ValidationError("Missing required field 'webhook_url'")

        subscription_data = await integration.subscribe_webhook(trigger, webhook_url, context)
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'subscription_data': subscription_data
            })
        }

    elif operation == 'unsubscribe':
        subscription_data = event.get('subscription_data')
        if not subscription_data:
            raise ValidationError("Missing required field 'subscription_data'")

        await integration.unsubscribe_webhook(trigger, subscription_data, context)
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True
            })
        }

    elif operation == 'handle':
        webhook_event = event.get('webhook_event')
        if not webhook_event:
            raise ValidationError("Missing required field 'webhook_event'")

        result = await integration.handle_webhook_event(trigger, webhook_event, context)
        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'result': result
            })
        }

    else:
        raise ValidationError(f"Invalid webhook operation: {operation}")

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda handler for integration execution"""
    # Parse event body if from API Gateway
    if isinstance(event.get('body'), str):
        event = json.loads(event['body'])

    # Run async execution
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(execute_integration(event))
    finally:
        loop.close()
