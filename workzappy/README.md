# WorkZappy

Manage WorkZappy projects, tasks, and comments from Autohive workflows.

## Connect WorkZappy

In WorkZappy, open **My Settings → Personal API Keys**. Enter the client ID and secret key in the Autohive connection. Use credentials with access to the destination project.

## Create Task

Supply the WorkZappy project ID, task type ID, and action item title. Include relevant context in the optional description. The action returns the created task ID. The destination task type must accept these fields and supply defaults for any other required fields.

See the [WorkZappy API reference](https://share.apidog.com/914815c2-d5fe-4c80-b298-5a6930c0d8d0/api-14974005) for the task endpoint and its project and task type lookup operations.

## Available actions

| Area | Actions |
| --- | --- |
| Projects | List Projects, Get Project, Create Project, Update Project |
| Project setup | List Project Members, List Task Types, Get Task Scheme, List Project Phases, List Project Tags |
| Tasks | Create Task, Get Task, Search Tasks, Update Task, Remove Task |
| Comments | List Task Comments, Add Task Comment |

Use List Projects and List Task Types to find the IDs for Create Task. Use Get Task Scheme to identify the field codes and required values for a task type. Update Task accepts WorkZappy field codes and values, such as `summary`, `assignee`, and `status`. Update Project accepts project field codes such as `pname`.

Search Tasks and List Task Comments each return a page. Use `page_number` and `page_size` to retrieve subsequent pages. Enable the corresponding OpenAPI permissions for the actions you plan to use.

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

## Run the live smoke test

Set `WORKZAPPY_CLIENT_ID` and `WORKZAPPY_SECRET_KEY` with credentials that have **Get Project List** permission. From the repository root, run:

```sh
python -m pytest workzappy/tests/test_workzappy_integration.py -m integration
```

With credentials alone, the smoke test authenticates and lists projects. TeamCity maps both variables from the WorkZappy custom auth connection using `tests/teamcity.env`.

The full live suite covers all 16 actions. For all read tests, also set
`WORKZAPPY_PROJECT_ID`, `WORKZAPPY_TASK_TYPE_ID`, and `WORKZAPPY_TASK_ID` to
existing records in your test workspace. Grant the API key permissions for the
actions you plan to exercise.

To include writes, set `WORKZAPPY_RUN_WRITE_TESTS=1` and
`WORKZAPPY_PROJECT_TEMPLATE_CODE` in a disposable workspace, then run the same
command. The task test removes its own task. The project test leaves a uniquely
named project for manual cleanup.
