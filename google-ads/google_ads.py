import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Setup environment variables
from dotenv import load_dotenv
load_dotenv()

try:
    DEVELOPER_TOKEN = os.environ["ADWORDS_DEVELOPER_TOKEN"]
    CLIENT_ID = os.environ["ADWORDS_CLIENT_ID"]
    CLIENT_SECRET = os.environ["ADWORDS_CLIENT_SECRET"]
except KeyError as e:
    logger.error(f"Error loading environment variables: {str(e)}")
    raise

from enum import Enum
import proto
from autohive_integrations_sdk import ActionHandler, ExecutionContext, Integration, ActionResult
from google.ads.googleads.client import GoogleAdsClient
from google.api_core import protobuf_helpers

# Load integration configuration
_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
google_ads = Integration.load(_config_path)


# ---- Utility Functions ----

class AdType(Enum):
    RESPONSIVE_SEARCH_AD = 'RESPONSIVE_SEARCH_AD'
    EXPANDED_TEXT_AD = 'EXPANDED_TEXT_AD'


def micros_to_currency(micros):
    """Convert Google Ads API micros (millionths) to standard currency format."""
    return float(micros) / 1000000 if micros is not None else 'N/A'


def _get_google_ads_client(refresh_token: str, login_customer_id: Optional[str] = None) -> GoogleAdsClient:
    """Initialize and return a Google Ads API client."""
    credentials = {
        "developer_token": DEVELOPER_TOKEN,
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
        "use_proto_plus": True
    }
    if login_customer_id:
        credentials["login_customer_id"] = login_customer_id
        
    return GoogleAdsClient.load_from_dict(credentials)


def _validate_auth_and_inputs(inputs: Dict[str, Any], context: ExecutionContext) -> tuple:
    """Validate authentication and extract common inputs."""
    refresh_token = context.auth.get("credentials", {}).get("refresh_token")
    if not refresh_token:
        raise Exception("Refresh token is required for authentication with Google Ads API")
    
    login_customer_id = inputs.get('login_customer_id')
    customer_id = inputs.get('customer_id')
    
    if not login_customer_id:
        raise Exception("Manager Account ID (login_customer_id) is required")
    if not customer_id:
        raise Exception("Customer ID is required")
    
    return refresh_token, login_customer_id, customer_id


def _get_ad_text_assets(ad_data_from_row: Dict[str, Any]) -> Dict[str, list]:
    """Extracts headlines and descriptions from the ad_data part of a Google Ads API row."""
    headlines = []
    descriptions = []
    ad_type = ad_data_from_row.get('type', 'N/A')

    if ad_type == AdType.RESPONSIVE_SEARCH_AD.value:
        rsa_info = ad_data_from_row.get('responsive_search_ad', {})
        headlines.extend([h.get('text', '') for h in rsa_info.get('headlines', []) if h.get('text')])
        descriptions.extend([d.get('text', '') for d in rsa_info.get('descriptions', []) if d.get('text')])
    elif ad_type == AdType.EXPANDED_TEXT_AD.value:
        eta_info = ad_data_from_row.get('expanded_text_ad', {})
        for part in ['headline_part1', 'headline_part2', 'headline_part3']:
            if eta_info.get(part):
                headlines.append(eta_info.get(part))
        for part in ['description', 'description2']:
            if eta_info.get(part):
                descriptions.append(eta_info.get(part))

    return {"headlines": headlines, "descriptions": descriptions}


def _calculate_safe_rate(numerator_raw, denominator_raw, default_numerator=0.0, default_denominator=0.0):
    """Safely calculates a rate, handling potential non-numeric inputs."""
    try:
        numerator = float(numerator_raw)
    except (ValueError, TypeError):
        numerator = default_numerator
    try:
        denominator = float(denominator_raw)
    except (ValueError, TypeError):
        denominator = default_denominator
    
    if denominator > 0:
        return numerator / denominator
    return 0.0


def parse_date_range(range_name_str: str) -> Dict[str, str]:
    """Parses a date range string into start and end dates."""
    if range_name_str.lower() in ["last 7 days", "last_7_days"]:
        today = datetime.now().date()
        end_date = today - timedelta(days=1)
        start_date = end_date - timedelta(days=6)
        return {
            "start_date": start_date.strftime('%Y-%m-%d'),
            "end_date": end_date.strftime('%Y-%m-%d')
        }
    
    if '/' in range_name_str and '_' not in range_name_str:
        try:
            parsed_date = datetime.strptime(range_name_str, '%d/%m/%Y').date()
            formatted_date = parsed_date.strftime('%Y-%m-%d')
            return {"start_date": formatted_date, "end_date": formatted_date}
        except ValueError:
            pass
    
    if '_' in range_name_str:
        try:
            start_str, end_str = range_name_str.split('_')
            datetime.strptime(start_str, '%Y-%m-%d')
            datetime.strptime(end_str, '%Y-%m-%d')
            return {"start_date": start_str, "end_date": end_str}
        except ValueError:
            pass
    
    raise ValueError(f"Invalid date range format: '{range_name_str}'")


# ---- Data Fetching Functions ----

def fetch_campaign_data(client, customer_id, date_ranges_input, campaign_type=None):
    """Fetches campaign performance data from Google Ads API.
    
    Args:
        client: GoogleAdsClient instance.
        customer_id: The Google Ads customer ID.
        date_ranges_input: Date ranges to query.
        campaign_type: Optional campaign type filter. 
            'VIDEO' includes video-specific metrics (average_cpv).
            'SEARCH', 'DISPLAY', 'PERFORMANCE_MAX', or 'ALL' use universal metrics only.
            Defaults to 'ALL' (universal metrics safe for all campaign types).
    """
    ga_service = client.get_service("GoogleAdsService")

    # Base fields that work for all campaign types
    base_fields = """
        campaign.id, campaign.status, campaign.name, campaign_budget.amount_micros,
        customer.currency_code, campaign.bidding_strategy_system_status,
        campaign.optimization_score, customer.descriptive_name,
        campaign.advertising_channel_type, metrics.interactions,
        metrics.interaction_rate, metrics.average_cost, metrics.cost_micros,
        metrics.impressions, campaign.bidding_strategy_type, metrics.clicks,
        metrics.conversions_value, metrics.cost_per_all_conversions,
        metrics.all_conversions, metrics.average_cpc, metrics.cost_per_conversion"""

    # Video-specific metrics (only valid for VIDEO campaigns)
    video_fields = ", metrics.average_cpv"

    # Build query based on campaign type
    include_video_metrics = campaign_type and campaign_type.upper() == 'VIDEO'
    
    select_fields = base_fields
    if include_video_metrics:
        select_fields += video_fields

    query_template = f"""
    SELECT{select_fields}
    FROM campaign
    WHERE segments.date BETWEEN '{{start_date}}' AND '{{end_date}}'
        AND campaign.status = 'ENABLED'
        AND campaign.bidding_strategy_system_status != 'PAUSED'
    """
    
    # Add campaign type filter if specified (and not 'ALL')
    if campaign_type and campaign_type.upper() not in ['ALL', 'VIDEO']:
        query_template += f"\n        AND campaign.advertising_channel_type = '{campaign_type.upper()}'"
    elif campaign_type and campaign_type.upper() == 'VIDEO':
        query_template += "\n        AND campaign.advertising_channel_type = 'VIDEO'"

    all_results = []
    parsed_date_ranges = []
    
    if isinstance(date_ranges_input, str):
        date_ranges_input = [date_ranges_input]
    
    for dr_input in date_ranges_input:
        parsed_date_ranges.append(parse_date_range(dr_input))

    for date_range in parsed_date_ranges:
        query = query_template.format(start_date=date_range['start_date'], end_date=date_range['end_date'])
        
        try:
            response = ga_service.search(customer_id=customer_id, query=query)
        except Exception as e:
            logger.error(f"Error during API call for date range {date_range}: {str(e)}")
            all_results.append({
                'date_range': f"{date_range['start_date']} to {date_range['end_date']}",
                'error': f"Failed to retrieve data: {str(e)}",
                'data': []
            })
            continue

        date_range_result = {
            'date_range': f"{date_range['start_date']} to {date_range['end_date']}",
            'data': []
        }

        for row in response:
            row_dict = proto.Message.to_dict(row, use_integers_for_enums=False)
            campaign = row_dict.get('campaign', {})
            metrics = row_dict.get('metrics', {})
            customer = row_dict.get('customer', {})
            budget = row_dict.get('campaign_budget', {})

            conversions_value = metrics.get('conversions_value', 0.0)
            cost_micros = metrics.get('cost_micros', 1)
            cost = micros_to_currency(cost_micros)
            
            roas = 0
            if isinstance(cost, (int, float)) and cost != 0:
                roas = conversions_value / cost

            all_conversions_rate = _calculate_safe_rate(
                metrics.get('all_conversions'),
                metrics.get('interactions')
            )

            data = {
                "Campaign ID": campaign.get('id', 'N/A'),
                "Campaign status": campaign.get('status', 'N/A'),
                "Campaign": campaign.get('name', 'N/A'),
                "Currency code": customer.get('currency_code', 'N/A'),
                "Budget": micros_to_currency(budget.get('amount_micros')),
                "Status": campaign.get('bidding_strategy_system_status', 'N/A'),
                "Optimization score": campaign.get('optimization_score', 'N/A'),
                "Account": customer.get('descriptive_name', 'N/A'),
                "Campaign type": campaign.get('advertising_channel_type', 'N/A'),
                "Interactions": metrics.get('interactions', 'N/A'),
                "Interaction rate": metrics.get('interaction_rate', 'N/A'),
                "Avg. cost": micros_to_currency(metrics.get('average_cost')),
                "Cost": cost,
                "Impr.": metrics.get('impressions', 'N/A'),
                "Bid strategy type": campaign.get('bidding_strategy_type', 'N/A'),
                "Clicks": metrics.get('clicks', 'N/A'),
                "Conv. value": conversions_value,
                "Conv. value / cost": roas,
                "Conversions": metrics.get('all_conversions', 'N/A'),
                "Avg. CPC": micros_to_currency(metrics.get('average_cpc')),
                "Cost / conv.": micros_to_currency(metrics.get('cost_per_conversion')),
                "All Conversions Rate": all_conversions_rate
            }
            
            # Only include video-specific metrics when querying VIDEO campaigns
            if include_video_metrics:
                data["Avg. CPV"] = micros_to_currency(metrics.get('average_cpv'))
            date_range_result['data'].append(data)
        all_results.append(date_range_result)
    return all_results


def fetch_keyword_data(client, customer_id, date_ranges_input, campaign_ids=None, ad_group_ids=None):
    """Fetches keyword performance data from Google Ads API."""
    ga_service = client.get_service("GoogleAdsService")
    all_results = []

    parsed_date_ranges = []
    if isinstance(date_ranges_input, str):
        date_ranges_input = [date_ranges_input]
    for dr_input in date_ranges_input:
        parsed_date_ranges.append(parse_date_range(dr_input))

    query_template = """
        SELECT
        ad_group_criterion.keyword.text, metrics.impressions,
        metrics.clicks, metrics.cost_micros
        FROM keyword_view
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
        AND ad_group_criterion.status != 'REMOVED'
    """

    if campaign_ids and len(campaign_ids) > 0:
        campaign_filter = ", ".join([f"'{cid}'" for cid in campaign_ids])
        query_template += f" AND campaign.id IN ({campaign_filter})"

    if ad_group_ids and len(ad_group_ids) > 0:
        ad_group_filter = ", ".join([f"'{agid}'" for agid in ad_group_ids])
        query_template += f" AND ad_group.id IN ({ad_group_filter})"

    for date_range in parsed_date_ranges:
        query = query_template.format(start_date=date_range['start_date'], end_date=date_range['end_date'])

        current_range_results = {
            'date_range': f"{date_range['start_date']} to {date_range['end_date']}",
            'error': None,
            'data': []
        }

        try:
            response = ga_service.search(customer_id=customer_id, query=query)
            
            for row in response:
                row_dict = proto.Message.to_dict(row, use_integers_for_enums=False)
                campaign = row_dict.get('campaign', {})
                ad_group = row_dict.get('ad_group', {})
                criterion = row_dict.get('ad_group_criterion', {})
                keyword = criterion.get('keyword', {})
                metrics = row_dict.get('metrics', {})
                quality_info = criterion.get('quality_info', {})
                
                keyword_data = {
                    "Campaign ID": campaign.get('id', 'N/A'),
                    "Campaign": campaign.get('name', 'N/A'),
                    "Ad Group ID": ad_group.get('id', 'N/A'),
                    "Ad Group": ad_group.get('name', 'N/A'),
                    "Keyword ID": criterion.get('criterion_id', 'N/A'),
                    "Keyword": keyword.get('text', 'N/A'),
                    "Match Type": keyword.get('match_type', 'N/A'),
                    "Status": criterion.get('status', 'N/A'),
                    "Quality Score": quality_info.get('quality_score', 'N/A'),
                    "Impressions": metrics.get('impressions', 'N/A'),
                    "Clicks": metrics.get('clicks', 'N/A'),
                    "Cost": micros_to_currency(metrics.get('cost_micros')),
                    "Conversions": metrics.get('all_conversions', 'N/A'),
                    "Conversion Rate": metrics.get('conversion_rate', 0.0),
                    "Interaction Rate": metrics.get('interaction_rate', 'N/A'),
                    "Avg. CPC": micros_to_currency(metrics.get('average_cpc'))
                }
                current_range_results['data'].append(keyword_data)

        except Exception as e:
            logger.error(f"Error during keyword data retrieval: {str(e)}")
            current_range_results['error'] = f"Failed to retrieve keyword data: {str(e)}"
        
        all_results.append(current_range_results)

    return all_results


# ---- Action Handlers: READ Operations ----
@google_ads.action("get_accessible_accounts")
class GetAccessibleAccountsAction(ActionHandler):
    """Action handler for listing accessible Google Ads accounts."""
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        refresh_token = context.auth.get("credentials", {}).get("refresh_token")
        if not refresh_token:
            raise Exception("Refresh token is required for authentication with Google Ads API")
            
        try:
            # 1. List accessible customers (no login_customer_id needed)
            client = _get_google_ads_client(refresh_token, None)
            customer_service = client.get_service("CustomerService")
            
            try:
                response = customer_service.list_accessible_customers()
            except Exception as e:
                 logger.error(f"Failed to list accessible customers: {e}")
                 raise

            accounts = []
            for resource_name in response.resource_names:
                # Format: customers/{customer_id}
                customer_id = resource_name.split("/")[-1]
                accounts.append({
                    "resource_name": resource_name,
                    "customer_id": customer_id,
                    "descriptive_name": "Unknown",
                    "currency_code": "N/A"
                })

            # 2. Try to fetch details for each account
            final_accounts = []
            
            for account in accounts:
                try:
                    # Re-initialize client specifically for this customer
                    sub_client = _get_google_ads_client(refresh_token, account['customer_id'])
                    google_ads_service = sub_client.get_service("GoogleAdsService")
                    
                    query = """
                        SELECT customer.id, customer.descriptive_name, customer.currency_code 
                        FROM customer 
                        LIMIT 1
                    """
                    
                    stream = google_ads_service.search(customer_id=account['customer_id'], query=query)
                    
                    found = False
                    for row in stream:
                        account['descriptive_name'] = row.customer.descriptive_name
                        account['currency_code'] = row.customer.currency_code
                        found = True
                        break
                    
                    final_accounts.append(account)
                    
                except Exception as e:
                    logger.warning(f"Could not fetch details for {account['customer_id']}: {str(e)}")
                    final_accounts.append(account)

            return ActionResult(data={"accounts": final_accounts}, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Failed to get accessible accounts: {str(e)}")
            raise


@google_ads.action("retrieve_campaign_metrics")
class RetrieveCampaignMetricsAction(ActionHandler):
    """Action handler for retrieving campaign performance metrics."""
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        date_ranges_input = inputs.get('date_ranges')
        if not date_ranges_input:
            raise Exception("'date_ranges' is required.")
        
        campaign_type = inputs.get('campaign_type', 'ALL')

        try:
            results = fetch_campaign_data(client, customer_id, date_ranges_input, campaign_type)
            logger.info("Successfully retrieved campaign data.")
            return ActionResult(data=results, cost_usd=0.00)
        except Exception as e:
            logger.exception(f"Exception during campaign data retrieval: {str(e)}")
            raise


@google_ads.action("retrieve_keyword_metrics")
class RetrieveKeywordMetricsAction(ActionHandler):
    """Action handler for retrieving keyword performance metrics."""
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        date_ranges_input = inputs.get('date_ranges')
        campaign_ids = inputs.get('campaign_ids', [])
        ad_group_ids = inputs.get('ad_group_ids', [])

        if not date_ranges_input:
            raise Exception("'date_ranges' is required.")

        try:
            results = fetch_keyword_data(client, customer_id, date_ranges_input, campaign_ids, ad_group_ids)
            logger.info("Successfully retrieved keyword data.")
            return ActionResult(data=results, cost_usd=0.00)
        except Exception as e:
            logger.exception(f"Exception during keyword data retrieval: {str(e)}")
            raise


# ---- Action Handlers: CAMPAIGN CRUD Operations ----

@google_ads.action("create_campaign")
class CreateCampaignAction(ActionHandler):
    """Action handler for creating a new campaign with budget."""
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        campaign_name = inputs.get('campaign_name')
        budget_amount_micros = inputs.get('budget_amount_micros')

        # Validate required inputs
        if not campaign_name:
            raise Exception("campaign_name is required")
        if not budget_amount_micros:
            raise Exception("budget_amount_micros is required")

        budget_name = inputs.get('budget_name', f"Budget for {campaign_name}")
        bidding_strategy = inputs.get('bidding_strategy', 'MANUAL_CPC')
        
        start_date = inputs.get('start_date')
        end_date = inputs.get('end_date')
        
        if not start_date:
            start_date = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d')
        if not end_date:
            end_date = (datetime.now() + timedelta(days=365)).strftime('%Y%m%d')

        try:
            # Create campaign budget
            campaign_budget_service = client.get_service("CampaignBudgetService")
            campaign_budget_operation = client.get_type("CampaignBudgetOperation")
            campaign_budget = campaign_budget_operation.create
            campaign_budget.name = budget_name
            campaign_budget.amount_micros = budget_amount_micros
            campaign_budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD

            budget_response = campaign_budget_service.mutate_campaign_budgets(
                customer_id=customer_id,
                operations=[campaign_budget_operation]
            )
            budget_resource_name = budget_response.results[0].resource_name
            logger.info(f"Created budget: {budget_resource_name}")

            # Create campaign
            campaign_service = client.get_service("CampaignService")
            campaign_operation = client.get_type("CampaignOperation")
            campaign = campaign_operation.create
            campaign.name = campaign_name
            campaign.campaign_budget = budget_resource_name
            campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.SEARCH
            campaign.status = client.enums.CampaignStatusEnum.PAUSED
            campaign.start_date = start_date
            campaign.end_date = end_date

            # Set bidding strategy
            # Note: For smart bidding strategies, we only set optional constraints if provided
            # Setting values to 0 can cause API errors; omitting them lets Google optimize automatically
            # Uses client.copy_from() as per Google Ads Python library best practices
            if bidding_strategy == 'MANUAL_CPC':
                campaign.manual_cpc.enhanced_cpc_enabled = inputs.get('enhanced_cpc_enabled', False)
            elif bidding_strategy == 'TARGET_SPEND':
                # TARGET_SPEND = Maximize clicks within budget
                target_spend_micros = inputs.get('target_spend_micros')
                if target_spend_micros is not None:
                    campaign.target_spend.target_spend_micros = target_spend_micros
                else:
                    # Enable strategy without specific target (Google optimizes automatically)
                    client.copy_from(campaign.target_spend, client.get_type("TargetSpend")())
            elif bidding_strategy == 'MAXIMIZE_CONVERSIONS':
                # MAXIMIZE_CONVERSIONS with optional target CPA
                target_cpa_micros = inputs.get('target_cpa_micros')
                if target_cpa_micros is not None:
                    campaign.maximize_conversions.target_cpa_micros = target_cpa_micros
                else:
                    # Enable strategy without specific target CPA
                    client.copy_from(campaign.maximize_conversions, client.get_type("MaximizeConversions")())
            elif bidding_strategy == 'MAXIMIZE_CLICKS':
                # MAXIMIZE_CLICKS with optional bid ceiling
                cpc_bid_ceiling_micros = inputs.get('cpc_bid_ceiling_micros')
                if cpc_bid_ceiling_micros is not None:
                    campaign.maximize_clicks.cpc_bid_ceiling_micros = cpc_bid_ceiling_micros
                else:
                    # Enable strategy without bid ceiling
                    client.copy_from(campaign.maximize_clicks, client.get_type("MaximizeClicks")())

            # Network settings
            campaign.network_settings.target_google_search = True
            campaign.network_settings.target_search_network = True
            campaign.network_settings.target_content_network = False
            campaign.network_settings.target_partner_search_network = False

            # EU Political Advertising compliance (required field as of API v19.2+)
            # Convert boolean input to Google Ads API enum value
            is_political = inputs.get('contains_eu_political_advertising', False)
            if is_political:
                campaign.contains_eu_political_advertising = client.enums.EuPoliticalAdvertisingStatusEnum.CONTAINS_EU_POLITICAL_ADVERTISING
            else:
                campaign.contains_eu_political_advertising = client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING

            campaign_response = campaign_service.mutate_campaigns(
                customer_id=customer_id,
                operations=[campaign_operation]
            )
            campaign_resource_name = campaign_response.results[0].resource_name
            campaign_id = campaign_resource_name.split('/')[-1]

            logger.info(f"Created campaign: {campaign_resource_name}")

            return ActionResult(data={
                "campaign_resource_name": campaign_resource_name,
                "budget_resource_name": budget_resource_name,
                "campaign_id": campaign_id,
                "status": "PAUSED"
            }, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Failed to create campaign: {str(e)}")
            raise


@google_ads.action("update_campaign")
class UpdateCampaignAction(ActionHandler):
    """Action handler for updating an existing campaign."""
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        campaign_id = inputs.get('campaign_id')
        new_status = inputs.get('status')
        new_name = inputs.get('name')

        if not campaign_id:
            raise Exception("campaign_id is required")

        try:
            campaign_service = client.get_service("CampaignService")
            campaign_operation = client.get_type("CampaignOperation")
            campaign = campaign_operation.update
            
            campaign.resource_name = campaign_service.campaign_path(customer_id, campaign_id)

            if new_status:
                if new_status == 'ENABLED':
                    campaign.status = client.enums.CampaignStatusEnum.ENABLED
                elif new_status == 'PAUSED':
                    campaign.status = client.enums.CampaignStatusEnum.PAUSED

            if new_name:
                campaign.name = new_name

            # Create field mask
            client.copy_from(
                campaign_operation.update_mask,
                protobuf_helpers.field_mask(None, campaign._pb)
            )

            response = campaign_service.mutate_campaigns(
                customer_id=customer_id,
                operations=[campaign_operation]
            )

            result_resource_name = response.results[0].resource_name
            logger.info(f"Updated campaign: {result_resource_name}")

            return ActionResult(data={
                "campaign_resource_name": result_resource_name,
                "status": new_status or "unchanged"
            }, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Failed to update campaign: {str(e)}")
            raise


@google_ads.action("remove_campaign")
class RemoveCampaignAction(ActionHandler):
    """Action handler for removing a campaign."""
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        campaign_id = inputs.get('campaign_id')
        if not campaign_id:
            raise Exception("campaign_id is required")

        try:
            campaign_service = client.get_service("CampaignService")
            campaign_operation = client.get_type("CampaignOperation")
            
            resource_name = campaign_service.campaign_path(customer_id, campaign_id)
            campaign_operation.remove = resource_name

            response = campaign_service.mutate_campaigns(
                customer_id=customer_id,
                operations=[campaign_operation]
            )

            removed_resource_name = response.results[0].resource_name
            logger.info(f"Removed campaign: {removed_resource_name}")

            return ActionResult(data={
                "removed_campaign_resource_name": removed_resource_name,
                "status": "REMOVED"
            }, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Failed to remove campaign: {str(e)}")
            raise


# ---- Action Handlers: AD GROUP Operations ----

@google_ads.action("create_ad_group")
class CreateAdGroupAction(ActionHandler):
    """Action handler for creating a new ad group."""
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        campaign_id = inputs.get('campaign_id')
        ad_group_name = inputs.get('ad_group_name')
        cpc_bid_micros = inputs.get('cpc_bid_micros', 1000000)
        status = inputs.get('status', 'PAUSED')

        if not campaign_id or not ad_group_name:
            raise Exception("campaign_id and ad_group_name are required")

        try:
            ad_group_service = client.get_service("AdGroupService")
            campaign_service = client.get_service("CampaignService")
            ad_group_operation = client.get_type("AdGroupOperation")
            
            ad_group = ad_group_operation.create
            ad_group.name = ad_group_name
            ad_group.campaign = campaign_service.campaign_path(customer_id, campaign_id)
            ad_group.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD
            ad_group.cpc_bid_micros = cpc_bid_micros
            
            if status == 'ENABLED':
                ad_group.status = client.enums.AdGroupStatusEnum.ENABLED
            else:
                ad_group.status = client.enums.AdGroupStatusEnum.PAUSED

            response = ad_group_service.mutate_ad_groups(
                customer_id=customer_id,
                operations=[ad_group_operation]
            )

            ad_group_resource_name = response.results[0].resource_name
            ad_group_id = ad_group_resource_name.split('/')[-1]
            logger.info(f"Created ad group: {ad_group_resource_name}")

            return ActionResult(data={
                "ad_group_resource_name": ad_group_resource_name,
                "ad_group_id": ad_group_id,
                "status": status
            }, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Failed to create ad group: {str(e)}")
            raise


# ---- Action Handlers: AD Operations ----

@google_ads.action("create_responsive_search_ad")
class CreateResponsiveSearchAdAction(ActionHandler):
    """Action handler for creating a Responsive Search Ad."""
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        ad_group_id = inputs.get('ad_group_id')
        headlines = inputs.get('headlines', [])
        descriptions = inputs.get('descriptions', [])
        final_url = inputs.get('final_url')
        path1 = inputs.get('path1', '')
        path2 = inputs.get('path2', '')
        status = inputs.get('status', 'PAUSED')

        if not ad_group_id or not headlines or not descriptions or not final_url:
            raise Exception("ad_group_id, headlines, descriptions, and final_url are required")

        if len(headlines) < 3:
            raise Exception("At least 3 headlines are required for RSA")
        if len(descriptions) < 2:
            raise Exception("At least 2 descriptions are required for RSA")

        try:
            ad_group_ad_service = client.get_service("AdGroupAdService")
            ad_group_service = client.get_service("AdGroupService")
            ad_group_ad_operation = client.get_type("AdGroupAdOperation")
            
            ad_group_ad = ad_group_ad_operation.create
            ad_group_ad.ad_group = ad_group_service.ad_group_path(customer_id, ad_group_id)
            
            if status == 'ENABLED':
                ad_group_ad.status = client.enums.AdGroupAdStatusEnum.ENABLED
            else:
                ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED

            # Set final URL
            ad_group_ad.ad.final_urls.append(final_url)

            # Add headlines
            for headline_text in headlines[:15]:
                ad_text_asset = client.get_type("AdTextAsset")
                ad_text_asset.text = headline_text[:30]
                ad_group_ad.ad.responsive_search_ad.headlines.append(ad_text_asset)

            # Add descriptions
            for desc_text in descriptions[:4]:
                ad_text_asset = client.get_type("AdTextAsset")
                ad_text_asset.text = desc_text[:90]
                ad_group_ad.ad.responsive_search_ad.descriptions.append(ad_text_asset)

            # Add path
            if path1:
                ad_group_ad.ad.responsive_search_ad.path1 = path1[:15]
            if path2:
                ad_group_ad.ad.responsive_search_ad.path2 = path2[:15]

            response = ad_group_ad_service.mutate_ad_group_ads(
                customer_id=customer_id,
                operations=[ad_group_ad_operation]
            )

            ad_resource_name = response.results[0].resource_name
            ad_id = ad_resource_name.split('~')[-1] if '~' in ad_resource_name else ad_resource_name.split('/')[-1]
            logger.info(f"Created RSA: {ad_resource_name}")

            return ActionResult(data={
                "ad_resource_name": ad_resource_name,
                "ad_id": ad_id,
                "status": status
            }, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Failed to create RSA: {str(e)}")
            raise


# ---- Action Handlers: KEYWORD Operations ----

@google_ads.action("add_keywords")
class AddKeywordsAction(ActionHandler):
    """Action handler for adding keywords to an ad group."""
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        ad_group_id = inputs.get('ad_group_id')
        keywords = inputs.get('keywords', [])

        if not ad_group_id or not keywords:
            raise Exception("ad_group_id and keywords are required")

        try:
            ad_group_criterion_service = client.get_service("AdGroupCriterionService")
            ad_group_service = client.get_service("AdGroupService")
            
            operations = []
            added_keywords = []

            for kw in keywords:
                keyword_text = kw.get('text')
                match_type_str = kw.get('match_type', 'BROAD').upper()
                
                if not keyword_text:
                    continue

                operation = client.get_type("AdGroupCriterionOperation")
                criterion = operation.create
                criterion.ad_group = ad_group_service.ad_group_path(customer_id, ad_group_id)
                criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
                criterion.keyword.text = keyword_text
                
                if match_type_str == 'EXACT':
                    criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.EXACT
                elif match_type_str == 'PHRASE':
                    criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.PHRASE
                else:
                    criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.BROAD

                operations.append(operation)
                added_keywords.append({
                    "keyword_text": keyword_text,
                    "match_type": match_type_str
                })

            if operations:
                response = ad_group_criterion_service.mutate_ad_group_criteria(
                    customer_id=customer_id,
                    operations=operations
                )

                for i, result in enumerate(response.results):
                    if i < len(added_keywords):
                        added_keywords[i]["resource_name"] = result.resource_name

                logger.info(f"Added {len(response.results)} keywords")

            return ActionResult(data={
                "added_keywords": added_keywords,
                "status": "success"
            }, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Failed to add keywords: {str(e)}")
            raise


# ---- Action Handlers: KEYWORD PLANNER Operations ----

@google_ads.action("generate_keyword_ideas")
class GenerateKeywordIdeasAction(ActionHandler):
    """Action handler for generating keyword ideas using Keyword Planner."""
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        seed_keywords = inputs.get('seed_keywords', [])
        page_url = inputs.get('page_url')
        language_id = inputs.get('language_id', '1000')
        location_ids = inputs.get('location_ids', ['2840'])
        include_adult_keywords = inputs.get('include_adult_keywords', False)

        if not seed_keywords and not page_url:
            raise Exception("At least one of seed_keywords or page_url is required")

        try:
            keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")
            
            request = client.get_type("GenerateKeywordIdeasRequest")
            request.customer_id = customer_id
            request.language = client.get_service("GoogleAdsService").language_constant_path(language_id)
            request.include_adult_keywords = include_adult_keywords
            request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH

            # Add geo target constants
            for loc_id in location_ids:
                request.geo_target_constants.append(
                    client.get_service("GoogleAdsService").geo_target_constant_path(loc_id)
                )

            # Set seeds
            if seed_keywords and page_url:
                request.keyword_and_url_seed.url = page_url
                request.keyword_and_url_seed.keywords.extend(seed_keywords)
            elif seed_keywords:
                request.keyword_seed.keywords.extend(seed_keywords)
            elif page_url:
                request.url_seed.url = page_url

            response = keyword_plan_idea_service.generate_keyword_ideas(request=request)

            keyword_ideas = []
            for result in response:
                metrics = result.keyword_idea_metrics
                keyword_ideas.append({
                    "keyword": result.text,
                    "avg_monthly_searches": metrics.avg_monthly_searches if metrics.avg_monthly_searches else 0,
                    "competition": str(metrics.competition.name) if metrics.competition else "UNKNOWN",
                    "competition_index": metrics.competition_index if metrics.competition_index else 0,
                    "low_top_of_page_bid_micros": metrics.low_top_of_page_bid_micros if metrics.low_top_of_page_bid_micros else 0,
                    "high_top_of_page_bid_micros": metrics.high_top_of_page_bid_micros if metrics.high_top_of_page_bid_micros else 0
                })

            logger.info(f"Generated {len(keyword_ideas)} keyword ideas")

            return ActionResult(data={
                "keyword_ideas": keyword_ideas,
                "total_results": len(keyword_ideas)
            }, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Failed to generate keyword ideas: {str(e)}")
            raise


@google_ads.action("generate_keyword_historical_metrics")
class GenerateKeywordHistoricalMetricsAction(ActionHandler):
    """Action handler for getting historical metrics for keywords."""
    
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        keywords = inputs.get('keywords', [])
        language_id = inputs.get('language_id', '1000')
        location_ids = inputs.get('location_ids', ['2840'])

        if not keywords:
            raise Exception("keywords list is required")

        try:
            keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")
            
            request = client.get_type("GenerateKeywordHistoricalMetricsRequest")
            request.customer_id = customer_id
            request.keywords.extend(keywords)
            request.language = client.get_service("GoogleAdsService").language_constant_path(language_id)
            request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH

            for loc_id in location_ids:
                request.geo_target_constants.append(
                    client.get_service("GoogleAdsService").geo_target_constant_path(loc_id)
                )

            response = keyword_plan_idea_service.generate_keyword_historical_metrics(request=request)

            keyword_metrics = []
            for result in response.results:
                metrics = result.keyword_metrics
                
                monthly_volumes = []
                if metrics.monthly_search_volumes:
                    for vol in metrics.monthly_search_volumes:
                        monthly_volumes.append({
                            "month": str(vol.month.name) if vol.month else "UNKNOWN",
                            "year": vol.year if vol.year else 0,
                            "monthly_searches": vol.monthly_searches if vol.monthly_searches else 0
                        })

                keyword_metrics.append({
                    "keyword": result.text,
                    "avg_monthly_searches": metrics.avg_monthly_searches if metrics.avg_monthly_searches else 0,
                    "competition": str(metrics.competition.name) if metrics.competition else "UNKNOWN",
                    "competition_index": metrics.competition_index if metrics.competition_index else 0,
                    "low_top_of_page_bid_micros": metrics.low_top_of_page_bid_micros if metrics.low_top_of_page_bid_micros else 0,
                    "high_top_of_page_bid_micros": metrics.high_top_of_page_bid_micros if metrics.high_top_of_page_bid_micros else 0,
                    "monthly_search_volumes": monthly_volumes
                })

            logger.info(f"Retrieved historical metrics for {len(keyword_metrics)} keywords")

            return ActionResult(data={
                "keyword_metrics": keyword_metrics
            }, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Failed to get keyword historical metrics: {str(e)}")
            raise


# ---- NEW Action Handlers: Additional READ Operations ----

@google_ads.action("retrieve_ad_group_metrics")
class RetrieveAdGroupMetricsAction(ActionHandler):
    """Action handler for retrieving ad group performance metrics."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        date_ranges_input = inputs.get('date_ranges')
        campaign_ids = inputs.get('campaign_ids', [])

        if not date_ranges_input:
            raise Exception("'date_ranges' is required.")

        ga_service = client.get_service("GoogleAdsService")
        all_results = []

        parsed_date_ranges = []
        if isinstance(date_ranges_input, str):
            date_ranges_input = [date_ranges_input]
        for dr_input in date_ranges_input:
            parsed_date_ranges.append(parse_date_range(dr_input))

        query_template = """
            SELECT
                ad_group.id,
                ad_group.name,
                ad_group.status,
                ad_group.type,
                ad_group.cpc_bid_micros,
                campaign.id,
                campaign.name,
                campaign.status,
                metrics.impressions,
                metrics.clicks,
                metrics.ctr,
                metrics.average_cpc,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value,
                metrics.cost_per_conversion,
                metrics.all_conversions,
                metrics.interaction_rate
            FROM ad_group
            WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
                AND ad_group.status != 'REMOVED'
        """

        if campaign_ids and len(campaign_ids) > 0:
            campaign_filter = ", ".join([str(cid) for cid in campaign_ids])
            query_template += f" AND campaign.id IN ({campaign_filter})"

        try:
            for date_range in parsed_date_ranges:
                query = query_template.format(
                    start_date=date_range['start_date'],
                    end_date=date_range['end_date']
                )

                current_range_results = {
                    'date_range': f"{date_range['start_date']} to {date_range['end_date']}",
                    'data': []
                }

                response = ga_service.search(customer_id=customer_id, query=query)

                for row in response:
                    row_dict = proto.Message.to_dict(row, use_integers_for_enums=False)
                    ad_group = row_dict.get('ad_group', {})
                    campaign = row_dict.get('campaign', {})
                    metrics = row_dict.get('metrics', {})

                    ad_group_data = {
                        "ad_group_id": ad_group.get('id', 'N/A'),
                        "ad_group_name": ad_group.get('name', 'N/A'),
                        "ad_group_status": ad_group.get('status', 'N/A'),
                        "ad_group_type": ad_group.get('type', 'N/A'),
                        "cpc_bid": micros_to_currency(ad_group.get('cpc_bid_micros')),
                        "campaign_id": campaign.get('id', 'N/A'),
                        "campaign_name": campaign.get('name', 'N/A'),
                        "campaign_status": campaign.get('status', 'N/A'),
                        "impressions": metrics.get('impressions', 0),
                        "clicks": metrics.get('clicks', 0),
                        "ctr": metrics.get('ctr', 0),
                        "average_cpc": micros_to_currency(metrics.get('average_cpc')),
                        "cost": micros_to_currency(metrics.get('cost_micros')),
                        "conversions": metrics.get('conversions', 0),
                        "conversion_value": metrics.get('conversions_value', 0),
                        "cost_per_conversion": micros_to_currency(metrics.get('cost_per_conversion')),
                        "all_conversions": metrics.get('all_conversions', 0),
                        "interaction_rate": metrics.get('interaction_rate', 0)
                    }
                    current_range_results['data'].append(ad_group_data)

                all_results.append(current_range_results)

            logger.info("Successfully retrieved ad group metrics.")
            return ActionResult(data={"results": all_results}, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Exception during ad group metrics retrieval: {str(e)}")
            raise


@google_ads.action("retrieve_ad_metrics")
class RetrieveAdMetricsAction(ActionHandler):
    """Action handler for retrieving ad performance metrics."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        date_ranges_input = inputs.get('date_ranges')
        campaign_ids = inputs.get('campaign_ids', [])
        ad_group_ids = inputs.get('ad_group_ids', [])

        if not date_ranges_input:
            raise Exception("'date_ranges' is required.")

        ga_service = client.get_service("GoogleAdsService")
        all_results = []

        parsed_date_ranges = []
        if isinstance(date_ranges_input, str):
            date_ranges_input = [date_ranges_input]
        for dr_input in date_ranges_input:
            parsed_date_ranges.append(parse_date_range(dr_input))

        query_template = """
            SELECT
                ad_group_ad.ad.id,
                ad_group_ad.ad.name,
                ad_group_ad.status,
                ad_group_ad.ad.type,
                ad_group_ad.ad.final_urls,
                ad_group_ad.ad.responsive_search_ad.headlines,
                ad_group_ad.ad.responsive_search_ad.descriptions,
                ad_group.id,
                ad_group.name,
                campaign.id,
                campaign.name,
                metrics.impressions,
                metrics.clicks,
                metrics.ctr,
                metrics.average_cpc,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value,
                metrics.cost_per_conversion
            FROM ad_group_ad
            WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
                AND ad_group_ad.status != 'REMOVED'
        """

        if campaign_ids and len(campaign_ids) > 0:
            campaign_filter = ", ".join([str(cid) for cid in campaign_ids])
            query_template += f" AND campaign.id IN ({campaign_filter})"

        if ad_group_ids and len(ad_group_ids) > 0:
            ad_group_filter = ", ".join([str(agid) for agid in ad_group_ids])
            query_template += f" AND ad_group.id IN ({ad_group_filter})"

        try:
            for date_range in parsed_date_ranges:
                query = query_template.format(
                    start_date=date_range['start_date'],
                    end_date=date_range['end_date']
                )

                current_range_results = {
                    'date_range': f"{date_range['start_date']} to {date_range['end_date']}",
                    'data': []
                }

                response = ga_service.search(customer_id=customer_id, query=query)

                for row in response:
                    row_dict = proto.Message.to_dict(row, use_integers_for_enums=False)
                    ad_group_ad = row_dict.get('ad_group_ad', {})
                    ad = ad_group_ad.get('ad', {})
                    ad_group = row_dict.get('ad_group', {})
                    campaign = row_dict.get('campaign', {})
                    metrics = row_dict.get('metrics', {})

                    # Extract headlines and descriptions for RSA
                    text_assets = _get_ad_text_assets(ad)

                    ad_data = {
                        "ad_id": ad.get('id', 'N/A'),
                        "ad_name": ad.get('name', 'N/A'),
                        "ad_status": ad_group_ad.get('status', 'N/A'),
                        "ad_type": ad.get('type', 'N/A'),
                        "final_urls": ad.get('final_urls', []),
                        "headlines": text_assets.get('headlines', []),
                        "descriptions": text_assets.get('descriptions', []),
                        "ad_group_id": ad_group.get('id', 'N/A'),
                        "ad_group_name": ad_group.get('name', 'N/A'),
                        "campaign_id": campaign.get('id', 'N/A'),
                        "campaign_name": campaign.get('name', 'N/A'),
                        "impressions": metrics.get('impressions', 0),
                        "clicks": metrics.get('clicks', 0),
                        "ctr": metrics.get('ctr', 0),
                        "average_cpc": micros_to_currency(metrics.get('average_cpc')),
                        "cost": micros_to_currency(metrics.get('cost_micros')),
                        "conversions": metrics.get('conversions', 0),
                        "conversion_value": metrics.get('conversions_value', 0),
                        "cost_per_conversion": micros_to_currency(metrics.get('cost_per_conversion'))
                    }
                    current_range_results['data'].append(ad_data)

                all_results.append(current_range_results)

            logger.info("Successfully retrieved ad metrics.")
            return ActionResult(data={"results": all_results}, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Exception during ad metrics retrieval: {str(e)}")
            raise


@google_ads.action("retrieve_search_terms")
class RetrieveSearchTermsAction(ActionHandler):
    """Action handler for retrieving search term report."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        date_ranges_input = inputs.get('date_ranges')
        campaign_ids = inputs.get('campaign_ids', [])
        ad_group_ids = inputs.get('ad_group_ids', [])

        if not date_ranges_input:
            raise Exception("'date_ranges' is required.")

        ga_service = client.get_service("GoogleAdsService")
        all_results = []

        parsed_date_ranges = []
        if isinstance(date_ranges_input, str):
            date_ranges_input = [date_ranges_input]
        for dr_input in date_ranges_input:
            parsed_date_ranges.append(parse_date_range(dr_input))

        query_template = """
            SELECT
                search_term_view.search_term,
                search_term_view.status,
                segments.keyword.info.text,
                segments.keyword.info.match_type,
                ad_group.id,
                ad_group.name,
                campaign.id,
                campaign.name,
                metrics.impressions,
                metrics.clicks,
                metrics.ctr,
                metrics.average_cpc,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value
            FROM search_term_view
            WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
        """

        if campaign_ids and len(campaign_ids) > 0:
            campaign_filter = ", ".join([str(cid) for cid in campaign_ids])
            query_template += f" AND campaign.id IN ({campaign_filter})"

        if ad_group_ids and len(ad_group_ids) > 0:
            ad_group_filter = ", ".join([str(agid) for agid in ad_group_ids])
            query_template += f" AND ad_group.id IN ({ad_group_filter})"

        query_template += " ORDER BY metrics.impressions DESC"

        try:
            for date_range in parsed_date_ranges:
                query = query_template.format(
                    start_date=date_range['start_date'],
                    end_date=date_range['end_date']
                )

                current_range_results = {
                    'date_range': f"{date_range['start_date']} to {date_range['end_date']}",
                    'data': []
                }

                response = ga_service.search(customer_id=customer_id, query=query)

                for row in response:
                    row_dict = proto.Message.to_dict(row, use_integers_for_enums=False)
                    search_term_view = row_dict.get('search_term_view', {})
                    segments = row_dict.get('segments', {})
                    keyword_info = segments.get('keyword', {}).get('info', {})
                    ad_group = row_dict.get('ad_group', {})
                    campaign = row_dict.get('campaign', {})
                    metrics = row_dict.get('metrics', {})

                    search_term_data = {
                        "search_term": search_term_view.get('search_term', 'N/A'),
                        "status": search_term_view.get('status', 'N/A'),
                        "matched_keyword": keyword_info.get('text', 'N/A'),
                        "match_type": keyword_info.get('match_type', 'N/A'),
                        "ad_group_id": ad_group.get('id', 'N/A'),
                        "ad_group_name": ad_group.get('name', 'N/A'),
                        "campaign_id": campaign.get('id', 'N/A'),
                        "campaign_name": campaign.get('name', 'N/A'),
                        "impressions": metrics.get('impressions', 0),
                        "clicks": metrics.get('clicks', 0),
                        "ctr": metrics.get('ctr', 0),
                        "average_cpc": micros_to_currency(metrics.get('average_cpc')),
                        "cost": micros_to_currency(metrics.get('cost_micros')),
                        "conversions": metrics.get('conversions', 0),
                        "conversion_value": metrics.get('conversions_value', 0)
                    }
                    current_range_results['data'].append(search_term_data)

                all_results.append(current_range_results)

            logger.info("Successfully retrieved search terms.")
            return ActionResult(data={"results": all_results}, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Exception during search terms retrieval: {str(e)}")
            raise


@google_ads.action("get_active_ad_urls")
class GetActiveAdUrlsAction(ActionHandler):
    """Action handler for getting all active ads with their destination URLs."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        url_filter = inputs.get('url_filter')  # Optional: filter by specific URL

        ga_service = client.get_service("GoogleAdsService")

        query = """
            SELECT
                campaign.id,
                campaign.name,
                campaign.status,
                ad_group.id,
                ad_group.name,
                ad_group.status,
                ad_group_ad.ad.id,
                ad_group_ad.ad.name,
                ad_group_ad.status,
                ad_group_ad.ad.type,
                ad_group_ad.ad.final_urls,
                ad_group_ad.ad.final_mobile_urls,
                ad_group_ad.ad.tracking_url_template
            FROM ad_group_ad
            WHERE campaign.status = 'ENABLED'
                AND ad_group.status = 'ENABLED'
                AND ad_group_ad.status = 'ENABLED'
        """

        try:
            response = ga_service.search(customer_id=customer_id, query=query)

            results = []
            for row in response:
                row_dict = proto.Message.to_dict(row, use_integers_for_enums=False)
                campaign = row_dict.get('campaign', {})
                ad_group = row_dict.get('ad_group', {})
                ad_group_ad = row_dict.get('ad_group_ad', {})
                ad = ad_group_ad.get('ad', {})

                final_urls = ad.get('final_urls', [])

                # If url_filter is provided, only include ads matching that URL
                if url_filter:
                    if not any(url_filter in url for url in final_urls):
                        continue

                ad_url_data = {
                    "campaign_id": campaign.get('id', 'N/A'),
                    "campaign_name": campaign.get('name', 'N/A'),
                    "campaign_status": campaign.get('status', 'N/A'),
                    "ad_group_id": ad_group.get('id', 'N/A'),
                    "ad_group_name": ad_group.get('name', 'N/A'),
                    "ad_group_status": ad_group.get('status', 'N/A'),
                    "ad_id": ad.get('id', 'N/A'),
                    "ad_name": ad.get('name', 'N/A'),
                    "ad_status": ad_group_ad.get('status', 'N/A'),
                    "ad_type": ad.get('type', 'N/A'),
                    "final_urls": final_urls,
                    "final_mobile_urls": ad.get('final_mobile_urls', []),
                    "tracking_url_template": ad.get('tracking_url_template', '')
                }
                results.append(ad_url_data)

            logger.info(f"Successfully retrieved {len(results)} active ad URLs.")
            return ActionResult(data={
                "active_ads": results,
                "total_count": len(results)
            }, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Exception during active ad URLs retrieval: {str(e)}")
            raise


# ---- NEW Action Handlers: Negative Keywords ----

@google_ads.action("add_negative_keywords_to_campaign")
class AddNegativeKeywordsToCampaignAction(ActionHandler):
    """Action handler for adding negative keywords to a campaign."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        campaign_id = inputs.get('campaign_id')
        keywords = inputs.get('keywords', [])

        if not campaign_id or not keywords:
            raise Exception("campaign_id and keywords are required")

        try:
            campaign_criterion_service = client.get_service("CampaignCriterionService")
            campaign_service = client.get_service("CampaignService")

            operations = []
            added_keywords = []

            for kw in keywords:
                keyword_text = kw.get('text') if isinstance(kw, dict) else kw
                match_type_str = kw.get('match_type', 'BROAD').upper() if isinstance(kw, dict) else 'BROAD'

                if not keyword_text:
                    continue

                operation = client.get_type("CampaignCriterionOperation")
                criterion = operation.create
                criterion.campaign = campaign_service.campaign_path(customer_id, campaign_id)
                criterion.negative = True
                criterion.keyword.text = keyword_text

                if match_type_str == 'EXACT':
                    criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.EXACT
                elif match_type_str == 'PHRASE':
                    criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.PHRASE
                else:
                    criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.BROAD

                operations.append(operation)
                added_keywords.append({
                    "keyword_text": keyword_text,
                    "match_type": match_type_str
                })

            if operations:
                response = campaign_criterion_service.mutate_campaign_criteria(
                    customer_id=customer_id,
                    operations=operations
                )

                for i, result in enumerate(response.results):
                    if i < len(added_keywords):
                        added_keywords[i]["resource_name"] = result.resource_name

                logger.info(f"Added {len(response.results)} negative keywords to campaign")

            return ActionResult(data={
                "added_negative_keywords": added_keywords,
                "campaign_id": campaign_id,
                "status": "success"
            }, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Failed to add negative keywords to campaign: {str(e)}")
            raise


@google_ads.action("add_negative_keywords_to_ad_group")
class AddNegativeKeywordsToAdGroupAction(ActionHandler):
    """Action handler for adding negative keywords to an ad group."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        ad_group_id = inputs.get('ad_group_id')
        keywords = inputs.get('keywords', [])

        if not ad_group_id or not keywords:
            raise Exception("ad_group_id and keywords are required")

        try:
            ad_group_criterion_service = client.get_service("AdGroupCriterionService")
            ad_group_service = client.get_service("AdGroupService")

            operations = []
            added_keywords = []

            for kw in keywords:
                keyword_text = kw.get('text') if isinstance(kw, dict) else kw
                match_type_str = kw.get('match_type', 'BROAD').upper() if isinstance(kw, dict) else 'BROAD'

                if not keyword_text:
                    continue

                operation = client.get_type("AdGroupCriterionOperation")
                criterion = operation.create
                criterion.ad_group = ad_group_service.ad_group_path(customer_id, ad_group_id)
                criterion.negative = True
                criterion.keyword.text = keyword_text

                if match_type_str == 'EXACT':
                    criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.EXACT
                elif match_type_str == 'PHRASE':
                    criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.PHRASE
                else:
                    criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.BROAD

                operations.append(operation)
                added_keywords.append({
                    "keyword_text": keyword_text,
                    "match_type": match_type_str
                })

            if operations:
                response = ad_group_criterion_service.mutate_ad_group_criteria(
                    customer_id=customer_id,
                    operations=operations
                )

                for i, result in enumerate(response.results):
                    if i < len(added_keywords):
                        added_keywords[i]["resource_name"] = result.resource_name

                logger.info(f"Added {len(response.results)} negative keywords to ad group")

            return ActionResult(data={
                "added_negative_keywords": added_keywords,
                "ad_group_id": ad_group_id,
                "status": "success"
            }, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Failed to add negative keywords to ad group: {str(e)}")
            raise


# ---- NEW Action Handlers: Ad Group CRUD ----

@google_ads.action("update_ad_group")
class UpdateAdGroupAction(ActionHandler):
    """Action handler for updating an existing ad group."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        ad_group_id = inputs.get('ad_group_id')
        new_status = inputs.get('status')
        new_name = inputs.get('name')
        new_cpc_bid_micros = inputs.get('cpc_bid_micros')

        if not ad_group_id:
            raise Exception("ad_group_id is required")

        try:
            ad_group_service = client.get_service("AdGroupService")
            ad_group_operation = client.get_type("AdGroupOperation")
            ad_group = ad_group_operation.update

            ad_group.resource_name = ad_group_service.ad_group_path(customer_id, ad_group_id)

            if new_status:
                if new_status == 'ENABLED':
                    ad_group.status = client.enums.AdGroupStatusEnum.ENABLED
                elif new_status == 'PAUSED':
                    ad_group.status = client.enums.AdGroupStatusEnum.PAUSED

            if new_name:
                ad_group.name = new_name

            if new_cpc_bid_micros:
                ad_group.cpc_bid_micros = new_cpc_bid_micros

            # Create field mask
            client.copy_from(
                ad_group_operation.update_mask,
                protobuf_helpers.field_mask(None, ad_group._pb)
            )

            response = ad_group_service.mutate_ad_groups(
                customer_id=customer_id,
                operations=[ad_group_operation]
            )

            result_resource_name = response.results[0].resource_name
            logger.info(f"Updated ad group: {result_resource_name}")

            return ActionResult(data={
                "ad_group_resource_name": result_resource_name,
                "ad_group_id": ad_group_id,
                "status": new_status or "unchanged"
            }, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Failed to update ad group: {str(e)}")
            raise


@google_ads.action("remove_ad_group")
class RemoveAdGroupAction(ActionHandler):
    """Action handler for removing an ad group."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        ad_group_id = inputs.get('ad_group_id')
        if not ad_group_id:
            raise Exception("ad_group_id is required")

        try:
            ad_group_service = client.get_service("AdGroupService")
            ad_group_operation = client.get_type("AdGroupOperation")

            resource_name = ad_group_service.ad_group_path(customer_id, ad_group_id)
            ad_group_operation.remove = resource_name

            response = ad_group_service.mutate_ad_groups(
                customer_id=customer_id,
                operations=[ad_group_operation]
            )

            removed_resource_name = response.results[0].resource_name
            logger.info(f"Removed ad group: {removed_resource_name}")

            return ActionResult(data={
                "removed_ad_group_resource_name": removed_resource_name,
                "ad_group_id": ad_group_id,
                "status": "REMOVED"
            }, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Failed to remove ad group: {str(e)}")
            raise


# ---- NEW Action Handlers: Keyword CRUD ----

@google_ads.action("update_keyword")
class UpdateKeywordAction(ActionHandler):
    """Action handler for updating a keyword's status or bid."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        ad_group_id = inputs.get('ad_group_id')
        criterion_id = inputs.get('criterion_id')
        new_status = inputs.get('status')
        new_cpc_bid_micros = inputs.get('cpc_bid_micros')

        if not ad_group_id or not criterion_id:
            raise Exception("ad_group_id and criterion_id are required")

        try:
            ad_group_criterion_service = client.get_service("AdGroupCriterionService")
            operation = client.get_type("AdGroupCriterionOperation")
            criterion = operation.update

            criterion.resource_name = ad_group_criterion_service.ad_group_criterion_path(
                customer_id, ad_group_id, criterion_id
            )

            if new_status:
                if new_status == 'ENABLED':
                    criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
                elif new_status == 'PAUSED':
                    criterion.status = client.enums.AdGroupCriterionStatusEnum.PAUSED

            if new_cpc_bid_micros is not None:
                criterion.cpc_bid_micros = new_cpc_bid_micros

            # Create field mask
            client.copy_from(
                operation.update_mask,
                protobuf_helpers.field_mask(None, criterion._pb)
            )

            response = ad_group_criterion_service.mutate_ad_group_criteria(
                customer_id=customer_id,
                operations=[operation]
            )

            result_resource_name = response.results[0].resource_name
            logger.info(f"Updated keyword: {result_resource_name}")

            return ActionResult(data={
                "keyword_resource_name": result_resource_name,
                "criterion_id": criterion_id,
                "status": new_status or "unchanged"
            }, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Failed to update keyword: {str(e)}")
            raise


@google_ads.action("remove_keyword")
class RemoveKeywordAction(ActionHandler):
    """Action handler for removing a keyword."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        ad_group_id = inputs.get('ad_group_id')
        criterion_id = inputs.get('criterion_id')

        if not ad_group_id or not criterion_id:
            raise Exception("ad_group_id and criterion_id are required")

        try:
            ad_group_criterion_service = client.get_service("AdGroupCriterionService")
            operation = client.get_type("AdGroupCriterionOperation")

            resource_name = ad_group_criterion_service.ad_group_criterion_path(
                customer_id, ad_group_id, criterion_id
            )
            operation.remove = resource_name

            response = ad_group_criterion_service.mutate_ad_group_criteria(
                customer_id=customer_id,
                operations=[operation]
            )

            removed_resource_name = response.results[0].resource_name
            logger.info(f"Removed keyword: {removed_resource_name}")

            return ActionResult(data={
                "removed_keyword_resource_name": removed_resource_name,
                "criterion_id": criterion_id,
                "status": "REMOVED"
            }, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Failed to remove keyword: {str(e)}")
            raise


# ---- NEW Action Handlers: Ad CRUD ----

@google_ads.action("update_ad")
class UpdateAdAction(ActionHandler):
    """Action handler for updating an ad's status."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        ad_group_id = inputs.get('ad_group_id')
        ad_id = inputs.get('ad_id')
        new_status = inputs.get('status')

        if not ad_group_id or not ad_id:
            raise Exception("ad_group_id and ad_id are required")

        try:
            ad_group_ad_service = client.get_service("AdGroupAdService")
            operation = client.get_type("AdGroupAdOperation")
            ad_group_ad = operation.update

            ad_group_ad.resource_name = ad_group_ad_service.ad_group_ad_path(
                customer_id, ad_group_id, ad_id
            )

            if new_status:
                if new_status == 'ENABLED':
                    ad_group_ad.status = client.enums.AdGroupAdStatusEnum.ENABLED
                elif new_status == 'PAUSED':
                    ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED

            # Create field mask
            client.copy_from(
                operation.update_mask,
                protobuf_helpers.field_mask(None, ad_group_ad._pb)
            )

            response = ad_group_ad_service.mutate_ad_group_ads(
                customer_id=customer_id,
                operations=[operation]
            )

            result_resource_name = response.results[0].resource_name
            logger.info(f"Updated ad: {result_resource_name}")

            return ActionResult(data={
                "ad_resource_name": result_resource_name,
                "ad_id": ad_id,
                "status": new_status or "unchanged"
            }, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Failed to update ad: {str(e)}")
            raise


@google_ads.action("remove_ad")
class RemoveAdAction(ActionHandler):
    """Action handler for removing an ad."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        ad_group_id = inputs.get('ad_group_id')
        ad_id = inputs.get('ad_id')

        if not ad_group_id or not ad_id:
            raise Exception("ad_group_id and ad_id are required")

        try:
            ad_group_ad_service = client.get_service("AdGroupAdService")
            operation = client.get_type("AdGroupAdOperation")

            resource_name = ad_group_ad_service.ad_group_ad_path(
                customer_id, ad_group_id, ad_id
            )
            operation.remove = resource_name

            response = ad_group_ad_service.mutate_ad_group_ads(
                customer_id=customer_id,
                operations=[operation]
            )

            removed_resource_name = response.results[0].resource_name
            logger.info(f"Removed ad: {removed_resource_name}")

            return ActionResult(data={
                "removed_ad_resource_name": removed_resource_name,
                "ad_id": ad_id,
                "status": "REMOVED"
            }, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Failed to remove ad: {str(e)}")
            raise


# ---- NEW Action Handler: Keyword Forecast ----

@google_ads.action("generate_keyword_forecast")
class GenerateKeywordForecastAction(ActionHandler):
    """Action handler for generating keyword forecast metrics."""

    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            refresh_token, login_customer_id, customer_id = _validate_auth_and_inputs(inputs, context)
            client = _get_google_ads_client(refresh_token, login_customer_id)
        except Exception as e:
            logger.exception(f"Failed to initialize GoogleAdsClient: {str(e)}")
            raise

        keywords = inputs.get('keywords', [])
        daily_budget_micros = inputs.get('daily_budget_micros')
        max_cpc_bid_micros = inputs.get('max_cpc_bid_micros', 1000000)
        language_id = inputs.get('language_id', '1000')
        location_ids = inputs.get('location_ids', ['2840'])
        forecast_days = inputs.get('forecast_days', 30)

        if not keywords:
            raise Exception("keywords list is required")

        try:
            keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")
            googleads_service = client.get_service("GoogleAdsService")

            request = client.get_type("GenerateKeywordForecastMetricsRequest")
            request.customer_id = customer_id

            # Configure campaign to forecast
            campaign = request.campaign
            campaign.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH

            # Set bidding strategy
            if daily_budget_micros:
                campaign.bidding_strategy.target_spend_bidding_strategy.daily_target_spend_micros = daily_budget_micros
            else:
                campaign.bidding_strategy.manual_cpc_bidding_strategy.max_cpc_bid_micros = max_cpc_bid_micros

            # Add geo modifiers
            for loc_id in location_ids:
                geo_modifier = client.get_type("CriterionBidModifier")
                geo_modifier.geo_target_constant = googleads_service.geo_target_constant_path(loc_id)
                campaign.geo_modifiers.append(geo_modifier)

            # Add language
            campaign.language_constants.append(
                googleads_service.language_constant_path(language_id)
            )

            # Create ad group with keywords
            forecast_ad_group = client.get_type("ForecastAdGroup")

            for kw in keywords:
                keyword_text = kw.get('text') if isinstance(kw, dict) else kw
                match_type_str = kw.get('match_type', 'BROAD').upper() if isinstance(kw, dict) else 'BROAD'
                kw_bid_micros = kw.get('cpc_bid_micros', max_cpc_bid_micros) if isinstance(kw, dict) else max_cpc_bid_micros

                biddable_keyword = client.get_type("BiddableKeyword")
                biddable_keyword.keyword.text = keyword_text
                biddable_keyword.max_cpc_bid_micros = kw_bid_micros

                if match_type_str == 'EXACT':
                    biddable_keyword.keyword.match_type = client.enums.KeywordMatchTypeEnum.EXACT
                elif match_type_str == 'PHRASE':
                    biddable_keyword.keyword.match_type = client.enums.KeywordMatchTypeEnum.PHRASE
                else:
                    biddable_keyword.keyword.match_type = client.enums.KeywordMatchTypeEnum.BROAD

                forecast_ad_group.biddable_keywords.append(biddable_keyword)

            campaign.ad_groups.append(forecast_ad_group)

            # Set forecast period
            tomorrow = datetime.now() + timedelta(days=1)
            end_date = datetime.now() + timedelta(days=forecast_days)
            request.forecast_period.start_date = tomorrow.strftime("%Y-%m-%d")
            request.forecast_period.end_date = end_date.strftime("%Y-%m-%d")

            # Execute forecast
            response = keyword_plan_idea_service.generate_keyword_forecast_metrics(request=request)

            metrics = response.campaign_forecast_metrics

            forecast_result = {
                "forecast_period": {
                    "start_date": request.forecast_period.start_date,
                    "end_date": request.forecast_period.end_date,
                    "days": forecast_days
                },
                "campaign_metrics": {
                    "impressions": metrics.impressions if metrics.impressions else 0,
                    "clicks": metrics.clicks if metrics.clicks else 0,
                    "cost_micros": metrics.cost_micros if metrics.cost_micros else 0,
                    "cost": micros_to_currency(metrics.cost_micros) if metrics.cost_micros else 0,
                    "average_cpc_micros": metrics.average_cpc_micros if metrics.average_cpc_micros else 0,
                    "average_cpc": micros_to_currency(metrics.average_cpc_micros) if metrics.average_cpc_micros else 0
                },
                "keywords_count": len(keywords)
            }

            logger.info(f"Generated forecast for {len(keywords)} keywords")

            return ActionResult(data=forecast_result, cost_usd=0.00)

        except Exception as e:
            logger.exception(f"Failed to generate keyword forecast: {str(e)}")
            raise
