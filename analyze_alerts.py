import os
import json
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from anthropic import Anthropic
import urllib3

# Suppress warnings about self-signed certificates (acceptable in lab environment)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load credentials from .env file
load_dotenv()

# Ensure the output directory exists for saving incident reports
os.makedirs("output", exist_ok=True)

# ----------------------------------------------------------------------
# Elasticsearch client setup
# ----------------------------------------------------------------------
# Connects to the local ELK stack using credentials from .env.
# verify_certs=False is acceptable here because we use a self-signed
# certificate in the home lab. In production, use a valid CA cert.
es = Elasticsearch(
    os.getenv("ES_HOST"),
    basic_auth=(os.getenv("ES_USER"), os.getenv("ES_PASSWORD")),
    verify_certs=False,
    ssl_show_warn=False
)

# ----------------------------------------------------------------------
# Anthropic Claude client setup
# ----------------------------------------------------------------------
# The Anthropic SDK reads ANTHROPIC_API_KEY automatically from env vars.
claude = Anthropic()

# ----------------------------------------------------------------------
# Fetch the latest alerts from Kibana's detection engine index
# ----------------------------------------------------------------------
# Kibana stores triggered detection rule alerts in a dedicated system
# index. We grab the 3 most recent alerts to keep API costs low.
result = es.search(
    index=".internal.alerts-security.alerts-default-*",
    size=3,
    sort=[{"@timestamp": {"order": "desc"}}],
    query={"match_all": {}}
)

hits = result["hits"]["hits"]
print(f"Found {len(hits)} alerts to analyze\n")

# ----------------------------------------------------------------------
# Process each alert: print summary, ask Claude for analysis, save result
# ----------------------------------------------------------------------
for hit in hits:
    alert = hit["_source"]

    # Print basic alert info to the terminal
    print("=" * 50)
    print(f"Rule: {alert.get('kibana.alert.rule.name')}")
    print(f"Time: {alert.get('@timestamp')}")
    print(f"Severity: {alert.get('kibana.alert.severity')}")
    print()

    # Build the structured prompt for Claude. We ask for JSON output
    # so we can parse the response programmatically.
    prompt = f"""You are a senior SOC analyst. Analyze this security alert and respond ONLY with valid JSON.

Alert data:
- Rule: {alert.get('kibana.alert.rule.name')}
- Severity: {alert.get('kibana.alert.severity')}
- Reason: {alert.get('kibana.alert.reason', 'N/A')}
- Timestamp: {alert.get('@timestamp')}

Respond with this exact JSON schema (no markdown, no explanation, just JSON):
{{
  "threat_level": "Critical|High|Medium|Low",
  "attack_type": "short description",
  "mitre_technique": "MITRE ATT&CK ID like T1110.001",
  "is_false_positive": true|false,
  "confidence": 0.0-1.0,
  "summary": "2-3 sentence explanation",
  "recommended_actions": ["action 1", "action 2", "action 3"]
}}"""

    print("Asking Claude...")

    # Send the prompt to Claude Sonnet 4.5 and get the response
    response = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )

    # Extract the raw text and strip any markdown code blocks Claude
    # might add despite our instructions (LLMs are not deterministic).
    raw_text = response.content[0].text
    cleaned = raw_text.replace("```json", "").replace("```", "").strip()

    try:
        # Parse Claude's JSON response into a Python dict
        analysis = json.loads(cleaned)

        # Print a human-readable summary in the terminal
        print(f"\nThreat Level: {analysis['threat_level']}")
        print(f"Attack Type: {analysis['attack_type']}")
        print(f"MITRE: {analysis['mitre_technique']}")
        print(f"False Positive: {analysis['is_false_positive']}")
        print(f"Confidence: {analysis['confidence']}")
        print(f"\nSummary: {analysis['summary']}")
        print("\nActions:")
        for action in analysis['recommended_actions']:
            print(f"  - {action}")

        # Save the full incident report (alert + AI analysis) as JSON.
        # Filename uses the alert timestamp so filenames are unique
        # and chronologically sortable.
        timestamp = alert.get('@timestamp', 'unknown').replace(':', '-')
        filename = f"output/alert_{timestamp}.json"

        full_record = {
            "alert": {
                "rule": alert.get('kibana.alert.rule.name'),
                "timestamp": alert.get('@timestamp'),
                "severity": alert.get('kibana.alert.severity'),
                "reason": alert.get('kibana.alert.reason')
            },
            "ai_analysis": analysis
        }

        with open(filename, "w") as f:
            json.dump(full_record, f, indent=2)

        print(f"  Saved to {filename}")

    except json.JSONDecodeError:
        # Fallback: if Claude returns something we can't parse,
        # show the raw response so we can debug the prompt.
        print("Could not parse JSON, raw response:")
        print(raw_text)
    print()
