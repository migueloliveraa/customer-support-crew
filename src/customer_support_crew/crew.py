import os
from crewai import Agent, Crew, Process, Task, LLM
from crewai.project import CrewBase, agent, crew, task
from customer_support_crew.tools.jira_tool import JiraTicketFetcherTool
from customer_support_crew.config.schemas import TicketTriageResult, TechnicalResolutionResult

@CrewBase
class SupportOrchestrationCrew():
    """Customer Support Sentiment Escalation and Resolution Crew"""

    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    # Externalizing the LLMs dynamically from .env [cite: 37, 53]
    # We use a fast, cost-efficient model for triage, and a smart reasoning model for resolution [cite: 59]
    triage_llm = LLM(model=os.getenv("TRIAGE_MODEL", "openai/gpt-4o-mini"), temperature=0.2)
    resolver_llm = LLM(model=os.getenv("RESOLVER_MODEL", "gemini/gemini-2.0-flash"), temperature=0.5)

    @agent
    def triage_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['triage_agent'],
            llm=self.triage_llm,
            tools=[JiraTicketFetcherTool()], # Bind the custom fetcher tool [cite: 54]
            verbose=True
        )

    @agent
    def technical_resolver(self) -> Agent:
        return Agent(
            config=self.agents_config['technical_resolver'],
            llm=self.resolver_llm,
            verbose=True
        )

    @task
    def triage_task(self) -> Task:
        return Task(
            config=self.tasks_config['triage_task'],
            output_json=TicketTriageResult # Enforces strict output validation schema 
        )

    @task
    def resolution_task(self) -> Task:
        return Task(
            config=self.tasks_config['resolution_task'],
            output_json=TechnicalResolutionResult, # Enforces strict output validation schema 
            output_file='output/final_resolution_report.json'
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Customer Support crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True
        )