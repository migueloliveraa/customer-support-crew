import os
from typing import Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from jira import JIRA

class JiraTicketFetcherInput(BaseModel):
    """Input schema for fetching a Jira ticket."""
    ticket_key: str = Field(..., description="The explicit Jira issue key to pull (e.g., 'SUP-101').")

class JiraTicketFetcherTool(BaseTool):
    name: str = "Jira Ticket Fetcher Tool"
    description: str = "Connects to a Jira instance and retrieves the summary and description of an issue key."
    args_schema: Type[BaseModel] = JiraTicketFetcherInput

    def _run(self, ticket_key: str) -> str:
        # Retrieve credentials externalized via environment variables
        jira_url = os.getenv("JIRA_SERVER_URL") # e.g., https://your-domain.atlassian.net
        jira_email = os.getenv("JIRA_EMAIL")
        jira_token = os.getenv("JIRA_API_TOKEN") # Generated in Atlassian Account Security settings

        if not all([jira_url, jira_email, jira_token]):
            return "Error: Missing Jira configuration environment variables."

        try:
            # Initialize connection to Atlassian Jira Cloud
            jira_client = JIRA(server=jira_url, basic_auth=(jira_email, jira_token))
            issue = jira_client.issue(ticket_key)
            
            summary = issue.fields.summary
            description = issue.fields.description or "No description provided."
            
            return f"Ticket Key: {ticket_key}\nSummary: {summary}\nDescription: {description}"
        except Exception as e:
            return f"Failed to fetch ticket {ticket_key} from Jira. Error: {str(e)}"