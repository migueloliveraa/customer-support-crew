#!/usr/bin/env python
import os
import json  # <-- Moved to the top to fix your local variable scoping error
import warnings
from types import SimpleNamespace
from customer_support_crew.crew import SupportOrchestrationCrew

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

def run():
    os.makedirs('output', exist_ok=True)

    inputs = {
        'ticket_id': 'CREWAISUP-1' # Replace with your active test key
    }
    
    print(f"[*] Starting Support Crew Pipeline processing Jira ticket: {inputs['ticket_id']}...")
    
    try:
        # Kick off agent execution pipeline
        crew_output = SupportOrchestrationCrew().crew().kickoff(inputs=inputs)
        
        # --- SAFE OUTPUT PARSING LAYER ---
        result_data = None
        
        # 1. Try extracting directly from memory if available
        if hasattr(crew_output, 'pydantic') and crew_output.pydantic is not None:
            print("Try extracting the output directly from memory if available")
            result_data = crew_output.pydantic
        # 2. Fallback: Parse the raw string response or JSON dictionary
        elif hasattr(crew_output, 'json_dict') and crew_output.json_dict is not None:
            # Converts the raw output dictionary back into an accessible object wrapper
            print("Parse the raw string response or JSON dictionary")
            result_data = json.loads(json.dumps(crew_output.json_dict), object_hook=lambda d: SimpleNamespace(**d))
        else:
            # 3. Final Fallback: Read directly from the raw string output
            print("Read directly from the raw string output")
            raw_json = json.loads(crew_output.raw)
            result_data = SimpleNamespace(**raw_json)
        # ---------------------------------

        print("\n" + "="*40)
        print("          PIPELINE EXECUTION SUCCESS          ")
        print("="*40)
        
        # Now result_data will never be NoneType
        if result_data.resolution_status == "escalated_to_human":
            print(f"[ALERT] High Frustration Level detected ({result_data.frustration_score}/10)!")
            print(f"[STATUS] Ticket Escalated to Human Management Override Layer.")
            print(f"[NOTES] {getattr(result_data, 'internal_escalation_notes', 'No notes provided.')}")
        else:
            print(f"[STATUS] Ticket successfully drafted by Tier-2 Engine ({result_data.frustration_score}/10).")
            print(f"[RESPONSE TEMPLATE]:\n{getattr(result_data, 'email_response_template', 'No template generated.')}")
            
    except Exception as e:
        print(f"[FATAL ERROR] Execution failed: {e}")

if __name__ == "__main__":
    run()