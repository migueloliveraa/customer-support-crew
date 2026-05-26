#!/usr/bin/env python
import os
import json
import warnings
from customer_support_crew.crew import SupportOrchestrationCrew

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

def run():
    """
    Run the customer support ticket execution crew.
    """
    # Create required output directory structures automatically [cite: 57]
    os.makedirs('output', exist_ok=True)

    # Runtime user inputs externalized from core code definitions [cite: 31, 49]
    inputs = {
        'ticket_id': 'SUP-125' # Replace with a valid target ticket key in your Jira Project
    }
    
    print(f"[*] Starting Support Crew Pipeline processing Jira ticket: {inputs['ticket_id']}...")
    
    try:
        # Kick off agent execution pipeline
        crew_output = SupportOrchestrationCrew().crew().kickoff(inputs=inputs)
        
        # Accessing the validated dictionary structure parsed via Pydantic 
        result_data = crew_output.pydantic
        
        print("\n" + "="*40)
        print("          PIPELINE EXECUTION SUCCESS          ")
        print("="*40)
        
        if result_data.resolution_status == "escalated_to_human":
            print(f"[ALERT] High Frustration Level detected ({result_data.frustration_score}/10)!")
            print(f"[STATUS] Ticket Escalated to Human Management Override Layer.")
            print(f"[NOTES] {result_data.internal_escalation_notes}")
        else:
            print(f"[STATUS] Ticket successfully drafted by Tier-2 Engine ({result_data.frustration_score}/10).")
            print(f"[RESPONSE TEMPLATE]:\n{result_data.email_response_template}")
            
    except Exception as e:
        print(f"[FATAL ERROR] Execution failed: {e}")

if __name__ == "__main__":
    run()