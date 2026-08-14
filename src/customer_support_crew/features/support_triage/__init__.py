"""Support triage: score a customer's frustration, then draft a reply or escalate.

Layout inside the slice:

    domain/       the schemas and the escalation policy — no I/O, no crewAI
    ports.py      the Protocols the application layer depends on
    application/  the use case, which is what the API, the web console and the CLI call
    adapters/     Jira, the filesystem, and the crewAI implementation of the pipeline
    api/          the HTTP wire contract and its router
"""
