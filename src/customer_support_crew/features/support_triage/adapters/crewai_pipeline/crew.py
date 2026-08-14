"""The crew: two agents, sequential, prose in YAML and wiring in Python.

Note where the `LLM(...)` objects are built — inside the `@agent` methods, not in the
class body. That is the whole reason this module is now safe to import at module scope:
the environment is read when a crew is *constructed*, not when the file is imported.
"""

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from customer_support_crew.core.llm import build_llm
from customer_support_crew.core.settings import get_settings
from customer_support_crew.features.support_triage.adapters.crewai_pipeline.tools import (
    JiraTicketFetcherTool,
)
from customer_support_crew.features.support_triage.domain.models import (
    TechnicalResolutionResult,
    TicketTriageResult,
)
from customer_support_crew.features.support_triage.ports import TicketSource


@CrewBase
class SupportOrchestrationCrew:
    """Customer Support Sentiment Escalation and Resolution Crew"""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self, ticket_source: TicketSource) -> None:
        self._ticket_source = ticket_source

    @agent
    def triage_agent(self) -> Agent:
        settings = get_settings()
        return Agent(
            config=self.agents_config["triage_agent"],
            llm=build_llm(settings.triage_model, settings.triage_temperature),
            tools=[JiraTicketFetcherTool(source=self._ticket_source)],
            verbose=True,
        )

    @agent
    def technical_resolver(self) -> Agent:
        settings = get_settings()
        return Agent(
            config=self.agents_config["technical_resolver"],
            llm=build_llm(settings.resolver_model, settings.resolver_temperature),
            verbose=True,
        )

    @task
    def triage_task(self) -> Task:
        return Task(
            config=self.tasks_config["triage_task"],
            output_json=TicketTriageResult,
        )

    @task
    def resolution_task(self) -> Task:
        # No output_file= here on purpose: persistence is the FileResolutionStore's
        # job, so the path can be anchored to the repo root instead of the CWD.
        return Task(
            config=self.tasks_config["resolution_task"],
            output_json=TechnicalResolutionResult,
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Customer Support crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
