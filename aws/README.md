# AWS Integration for Autohive

AWS security and monitoring integration covering Security Hub, GuardDuty, CloudWatch, and CloudTrail.

## Description

This integration provides access to core AWS security and monitoring services for investigating security findings, monitoring infrastructure metrics and logs, and auditing API activity. It uses boto3 directly with custom authentication (AWS access keys) and implements 20 actions across 5 service areas.

**Services covered:**
- **AWS Security Hub** -- Centralized security findings and compliance insights
- **Amazon GuardDuty** -- Threat detection and finding management
- **Amazon CloudWatch Metrics & Alarms** -- Infrastructure metrics, alarms, and alarm history
- **Amazon CloudWatch Logs** -- Log group discovery and log event search
- **AWS CloudTrail** -- API activity auditing and trail configuration

## Setup & Authentication

This integration uses **custom authentication** with AWS IAM credentials.

### Prerequisites

1. An AWS account with the services you plan to use enabled (Security Hub, GuardDuty, etc.)
2. An IAM user with programmatic access (access key ID and secret access key)

### Creating IAM Credentials

1. Sign in to the [AWS IAM Console](https://console.aws.amazon.com/iam/)
2. Go to **Users** and select or create a user for Autohive
3. Under the **Security credentials** tab, click **Create access key**
4. Select **Third-party service** as the use case
5. Copy the **Access Key ID** and **Secret Access Key** (the secret is only shown once)

### Setup Steps in Autohive

1. Add the AWS integration in Autohive
2. Enter your **AWS Access Key ID**
3. Enter your **AWS Secret Access Key**
4. Enter your **AWS Region** (e.g. `us-east-1`, `eu-west-1`, `ap-southeast-2`)
5. Save and start using the integration actions

### Required IAM Permissions

For read-only access to all services, attach the **SecurityAudit** AWS managed policy to the IAM user. This covers all read actions across Security Hub, GuardDuty, CloudWatch, CloudTrail, and CloudWatch Logs.

For the three write actions in this integration, add a custom inline policy with these additional permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "securityhub:BatchUpdateFindings",
                "guardduty:ArchiveFindings",
                "cloudwatch:SetAlarmState"
            ],
            "Resource": "*"
        }
    ]
}
```

**Summary of permissions:**

| Policy / Permission | Covers |
|---|---|
| `SecurityAudit` (managed policy) | All read actions across all 5 services |
| `securityhub:BatchUpdateFindings` | `update_finding_workflow` action |
| `guardduty:ArchiveFindings` | `archive_findings` action |
| `cloudwatch:SetAlarmState` | `set_alarm_state` action |

## Action Results

All actions return a standardized response structure:
- `result` (boolean): Indicates whether the action succeeded (true) or failed (false)
- `error` (string, optional): Contains error message if the action failed
- `error_code` (string, optional): AWS error code if the action failed
- Additional action-specific data fields

## Actions (20 Total)

### Security Hub (4 actions)

#### `get_findings`
List and filter security findings from AWS Security Hub.

**Inputs:**
- `filters` (optional): AWS Security Hub filter criteria in the GetFindings API format (e.g. SeverityLabel, ComplianceStatus, ResourceType filters)
- `max_results` (optional): Maximum number of findings to return (default: 20, max: 100)
- `next_token` (optional): Pagination token from a previous request

**Outputs:**
- `findings`: List of Security Hub findings
- `next_token`: Pagination token for the next page of results
- `result`: Success status

---

#### `get_finding_details`
Get detailed information about a specific Security Hub finding by its ARN.

**Inputs:**
- `finding_arn` (required): The ARN of the Security Hub finding to retrieve

**Outputs:**
- `finding`: The Security Hub finding details (or null if not found)
- `result`: Success status

---

#### `update_finding_workflow`
Update the workflow status of one or more Security Hub findings.

**Inputs:**
- `finding_arns` (required): List of finding ARNs to update
- `workflow_status` (required): The new workflow status to set. One of: `NEW`, `NOTIFIED`, `RESOLVED`, `SUPPRESSED`
- `note` (optional): Note to add to the findings

**Outputs:**
- `processed_findings`: List of findings that were successfully updated
- `unprocessed_findings`: List of findings that could not be updated
- `result`: Success status

---

#### `get_insights`
Get security insight results from AWS Security Hub.

**Inputs:**
- `insight_arns` (optional): List of insight ARNs to retrieve. If not specified, returns all insights.
- `max_results` (optional): Maximum number of insights to return (default: 20)
- `next_token` (optional): Pagination token from a previous request

**Outputs:**
- `insights`: List of Security Hub insights with name, filters, group_by_attribute, and results
- `next_token`: Pagination token for the next page of results
- `result`: Success status

---

### GuardDuty (4 actions)

#### `list_detectors`
List all GuardDuty detector IDs in the current AWS account and region.

**Inputs:**
- `max_results` (optional): Maximum number of detector IDs to return (default: 50)
- `next_token` (optional): Pagination token from a previous request

**Outputs:**
- `detector_ids`: List of GuardDuty detector IDs
- `next_token`: Pagination token for the next page of results
- `result`: Success status

---

#### `list_guardduty_findings`
List and filter GuardDuty findings for a specific detector.

**Inputs:**
- `detector_id` (required): The ID of the GuardDuty detector
- `finding_criteria` (optional): Criteria to filter findings (e.g. by severity, type, or resource)
- `sort_criteria` (optional): Criteria for sorting results (attribute name and order direction)
- `max_results` (optional): Maximum number of finding IDs to return (default: 50)
- `next_token` (optional): Pagination token from a previous request

**Outputs:**
- `finding_ids`: List of GuardDuty finding IDs
- `next_token`: Pagination token for the next page of results
- `result`: Success status

---

#### `get_guardduty_finding_details`
Get detailed information about one or more GuardDuty findings.

**Inputs:**
- `detector_id` (required): The ID of the GuardDuty detector
- `finding_ids` (required): List of finding IDs to retrieve details for

**Outputs:**
- `findings`: List of detailed GuardDuty findings
- `result`: Success status

---

#### `archive_findings`
Archive one or more GuardDuty findings by their IDs.

**Inputs:**
- `detector_id` (required): The ID of the GuardDuty detector
- `finding_ids` (required): List of finding IDs to archive

**Outputs:**
- `success`: Whether the findings were successfully archived
- `result`: Success status

---

### CloudWatch Metrics & Alarms (5 actions)

#### `list_metrics`
List available CloudWatch metrics, optionally filtered by namespace, name, or dimensions.

**Inputs:**
- `namespace` (optional): The namespace to filter metrics by (e.g. `AWS/EC2`, `AWS/RDS`, `AWS/Lambda`)
- `metric_name` (optional): The metric name to filter by (e.g. `CPUUtilization`, `NetworkIn`)
- `dimensions` (optional): List of dimension filters, each with Name and Value
- `next_token` (optional): Pagination token from a previous request

**Outputs:**
- `metrics`: List of CloudWatch metrics with namespace, name, and dimensions
- `next_token`: Pagination token for the next page of results
- `result`: Success status

---

#### `get_metric_data`
Retrieve CloudWatch metric statistics for one or more metrics over a specified time period.

**Inputs:**
- `metric_data_queries` (required): List of metric data queries. Each query requires an `id` and either a `metric_stat` (with metric, period, stat) or an `expression`.
- `start_time` (required): Start of the time range in ISO 8601 format (e.g. `2024-01-01T00:00:00Z`)
- `end_time` (required): End of the time range in ISO 8601 format (e.g. `2024-01-02T00:00:00Z`)

**Outputs:**
- `metric_data_results`: List of metric data results with timestamps and values
- `result`: Success status

---

#### `describe_alarms`
List and filter CloudWatch alarms by name, prefix, or state.

**Inputs:**
- `alarm_names` (optional): List of specific alarm names to retrieve
- `alarm_name_prefix` (optional): Prefix to filter alarm names by
- `state_value` (optional): Filter alarms by state. One of: `OK`, `ALARM`, `INSUFFICIENT_DATA`
- `max_records` (optional): Maximum number of alarm records to return (default: 50)
- `next_token` (optional): Pagination token from a previous request

**Outputs:**
- `metric_alarms`: List of metric alarms
- `composite_alarms`: List of composite alarms
- `next_token`: Pagination token for the next page of results
- `result`: Success status

---

#### `get_alarm_history`
Retrieve the history of state changes and actions for CloudWatch alarms.

**Inputs:**
- `alarm_name` (optional): The name of the alarm to get history for. If not specified, returns history for all alarms.
- `alarm_types` (optional): Filter by alarm type (`MetricAlarm`, `CompositeAlarm`)
- `history_item_type` (optional): Filter by history item type. One of: `ConfigurationUpdate`, `StateUpdate`, `Action`
- `start_date` (optional): Start of the date range in ISO 8601 format
- `end_date` (optional): End of the date range in ISO 8601 format
- `max_records` (optional): Maximum number of history items to return (default: 50)
- `next_token` (optional): Pagination token from a previous request

**Outputs:**
- `alarm_history_items`: List of alarm history items with timestamp, type, and summary
- `next_token`: Pagination token for the next page of results
- `result`: Success status

---

#### `set_alarm_state`
Temporarily set the state of a CloudWatch alarm for testing or maintenance purposes.

**Inputs:**
- `alarm_name` (required): The name of the alarm to set the state for
- `state_value` (required): The state value to set. One of: `OK`, `ALARM`, `INSUFFICIENT_DATA`
- `state_reason` (required): A human-readable reason for the state change

**Outputs:**
- `success`: Whether the alarm state was successfully set
- `result`: Success status

---

### CloudWatch Logs (3 actions)

#### `describe_log_groups`
List CloudWatch Logs log groups, optionally filtered by name prefix.

**Inputs:**
- `log_group_name_prefix` (optional): Prefix to filter log group names by
- `limit` (optional): Maximum number of log groups to return (default: 50, max: 50)
- `next_token` (optional): Pagination token from a previous request

**Outputs:**
- `log_groups`: List of log groups with name, ARN, creation time, and stored bytes
- `next_token`: Pagination token for the next page of results
- `result`: Success status

---

#### `filter_log_events`
Search and filter log events across one or more log streams within a log group.

**Inputs:**
- `log_group_name` (required): The name of the log group to search
- `log_stream_names` (optional): List of log stream names to search within
- `filter_pattern` (optional): CloudWatch Logs filter pattern to match events (e.g. `ERROR`, `{ $.statusCode = 500 }`)
- `start_time` (optional): Start of the time range in ISO 8601 format
- `end_time` (optional): End of the time range in ISO 8601 format
- `limit` (optional): Maximum number of events to return (default: 50, max: 10000)
- `next_token` (optional): Pagination token from a previous request

**Outputs:**
- `events`: List of matching log events with timestamp, message, and log stream name
- `searched_log_streams`: List of log streams that were searched
- `next_token`: Pagination token for the next page of results
- `result`: Success status

---

#### `get_log_events`
Get log events from a specific log stream in a log group.

**Inputs:**
- `log_group_name` (required): The name of the log group
- `log_stream_name` (required): The name of the log stream
- `start_time` (optional): Start of the time range in ISO 8601 format
- `end_time` (optional): End of the time range in ISO 8601 format
- `limit` (optional): Maximum number of events to return (default: 50, max: 10000)
- `start_from_head` (optional): If true, return events from the oldest first. If false, return from the newest first (default: true).
- `next_token` (optional): Pagination token from a previous request

**Outputs:**
- `events`: List of log events with timestamp and message
- `next_forward_token`: Token for fetching the next set of events going forward in time
- `next_backward_token`: Token for fetching the next set of events going backward in time
- `result`: Success status

---

### CloudTrail (4 actions)

#### `lookup_events`
Search CloudTrail management events by attributes such as event name, user, or resource.

**Inputs:**
- `lookup_attributes` (optional): List of lookup attributes to filter events. Each item has `attribute_key` (e.g. EventName, Username, ResourceType, ResourceName, EventSource) and `attribute_value`.
- `start_time` (optional): Start of the time range in ISO 8601 format
- `end_time` (optional): End of the time range in ISO 8601 format
- `max_results` (optional): Maximum number of events to return (default: 50, max: 50)
- `next_token` (optional): Pagination token from a previous request

**Outputs:**
- `events`: List of CloudTrail events with event name, time, user, and resources
- `next_token`: Pagination token for the next page of results
- `result`: Success status

---

#### `describe_trails`
List configured CloudTrail trails in the account.

**Inputs:**
- `trail_name_list` (optional): List of trail names or ARNs to describe. If not specified, returns all trails.
- `include_shadow_trails` (optional): Whether to include shadow trails (replications of trails in other regions). Default: true.

**Outputs:**
- `trails`: List of CloudTrail trail configurations
- `result`: Success status

---

#### `get_trail_status`
Get the current logging status and latest delivery information for a CloudTrail trail.

**Inputs:**
- `trail_name` (required): The trail name or ARN to get status for

**Outputs:**
- `trail_status`: Trail status including logging state, latest delivery time, and any delivery errors
- `result`: Success status

---

#### `get_event_selectors`
Get the event recording configuration for a CloudTrail trail, including management and data event selectors.

**Inputs:**
- `trail_name` (required): The trail name or ARN to get event selectors for

**Outputs:**
- `trail_arn`: The ARN of the trail
- `event_selectors`: List of event selectors configured on the trail
- `advanced_event_selectors`: List of advanced event selectors configured on the trail
- `result`: Success status

---

## Requirements

- `autohive-integrations-sdk` - The Autohive integrations SDK
- `boto3` - AWS SDK for Python

## API Information

- **AWS SDK**: boto3
- **Authentication**: IAM access keys (custom auth)
- **Region**: Configured per integration instance
- **Documentation**: https://docs.aws.amazon.com/

## Important Notes

- **Region-Scoped**: Each integration instance connects to a single AWS region. To monitor multiple regions, add separate integration instances.
- **Service Enablement**: Security Hub and GuardDuty must be enabled in your AWS account before their actions will work. CloudWatch and CloudTrail are enabled by default.
- **GuardDuty Workflow**: Use `list_detectors` first to get your detector ID, then pass it to `list_guardduty_findings`, `get_guardduty_finding_details`, and `archive_findings`.
- **Write Actions**: Only three actions perform writes: `update_finding_workflow` (Security Hub), `archive_findings` (GuardDuty), and `set_alarm_state` (CloudWatch). All other actions are read-only.
- **Pagination**: All list actions support pagination via `next_token`. When `next_token` is returned in a response, pass it to the next request to get the next page of results.
- **Time Formats**: All time-based inputs accept ISO 8601 format (e.g. `2024-01-15T00:00:00Z`).

## Common Use Cases

**Security Monitoring:**
- Review Security Hub findings filtered by severity or compliance status
- Investigate GuardDuty threat detections and archive resolved findings
- Update finding workflow status to track remediation progress

**Infrastructure Monitoring:**
- Query CloudWatch metrics for EC2, RDS, Lambda, and other services
- Check alarm states and review alarm history for incidents
- Temporarily set alarm state during maintenance windows

**Log Analysis:**
- Search CloudWatch Logs for errors or specific patterns across log groups
- Retrieve log events from specific streams for debugging
- Discover available log groups and their sizes

**Audit & Compliance:**
- Look up CloudTrail events to audit who made API calls and when
- Verify trail configurations and logging status
- Review event selectors to confirm what activity is being recorded

## Version History

- **1.0.0** - Initial release with 20 actions
  - Security Hub: get_findings, get_finding_details, update_finding_workflow, get_insights (4 actions)
  - GuardDuty: list_detectors, list_guardduty_findings, get_guardduty_finding_details, archive_findings (4 actions)
  - CloudWatch Metrics & Alarms: list_metrics, get_metric_data, describe_alarms, get_alarm_history, set_alarm_state (5 actions)
  - CloudWatch Logs: describe_log_groups, filter_log_events, get_log_events (3 actions)
  - CloudTrail: lookup_events, describe_trails, get_trail_status, get_event_selectors (4 actions)

## Sources

- [AWS Security Hub API Reference](https://docs.aws.amazon.com/securityhub/1.0/APIReference/)
- [Amazon GuardDuty API Reference](https://docs.aws.amazon.com/guardduty/latest/APIReference/)
- [Amazon CloudWatch API Reference](https://docs.aws.amazon.com/AmazonCloudWatch/latest/APIReference/)
- [Amazon CloudWatch Logs API Reference](https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/)
- [AWS CloudTrail API Reference](https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/)
- [boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
