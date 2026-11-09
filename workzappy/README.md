# WorkZappy

Create a WorkZappy task for each action item from an Autohive meeting write-up.

## Connect WorkZappy

In WorkZappy, open **My Settings → Personal API Keys**. Enter the client ID and secret key in the Autohive connection. Use credentials with access to the destination project.

## Create Task

Supply the WorkZappy project ID, task type ID, and action item title. Include relevant context in the optional description. The action returns the created task ID. The destination task type must accept these fields and supply defaults for any other required fields.

See the [WorkZappy API reference](https://share.apidog.com/914815c2-d5fe-4c80-b298-5a6930c0d8d0/api-14974005) for the task endpoint and its project and task type lookup operations.

## Pilot with Autohive Meetings

Use one test project and a sample meeting with two distinct action items. After the meeting write-up is ready, pass each action item to **Create Task** with the same configured project and task type. Verify that both tasks appear in the intended project and capture their returned IDs. Only pass action titles and relevant details to WorkZappy.

The connector provides the task action. The post-meeting invocation and tracking of exported action items need to be configured in Autohive. WorkZappy does not document an idempotency key for task creation. If a request times out, check the destination project before rerunning it.

## Run the unit tests

From the repository root, install the integration and test dependencies, then run:

```sh
python -m pip install -r workzappy/requirements.txt pytest pytest-asyncio
python -m pytest workzappy/
```

The tests use mocked WorkZappy responses and require no credentials.
