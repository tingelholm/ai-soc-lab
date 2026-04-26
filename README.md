```markdown
# AI-Augmented SOC on a Raspberry Pi 5

> Most home labs detect attacks. This one **understands** them.

A self-hosted Security Operations Center running on a Raspberry Pi 5 in this case catches SSH brute-force attacks, then hands them to **Claude AI** for instant Tier 2 triage — threat level, MITRE ATT&CK mapping, and remediation actions in seconds.

![SOC Architecture](docs/architecture.png)

## Why I built this

I love working in my home lab and decided spontaneously to turn my Raspberry Pi 5 into an AI-powered SOC. The goal was to see if I could get it running with the ELK Stack, then simulate attacks against it and have AI parse the resulting logs into something actionable.

The Pi was the perfect excuse to build this on real hardware instead of cloud VMs. The AI integration came naturally , SOC analysts spend significant time triaging alerts (assessing severity, mapping to MITRE ATT&CK, recommending actions), and I wanted to explore how an LLM like Claude could augment that workflow with instant structured analysis.

## What it does

Collects logs from Kali Linux and the Pi itself via Filebeat. Detects SSH brute-force attempts via custom Kibana detection rules. Sends each alert to Claude Sonnet 4.5 for AI triage threat level (and re-classification when the rule under-rates it), MITRE ATT&CK technique mapping, false positive likelihood with confidence score, and concrete remediation steps. Saves structured incident reports as JSON for downstream automation.

## Architecture

```
   [Kali VM]  ──┐
                ├──► Filebeat ──► Logstash ──► Elasticsearch ──► Kibana
[Raspberry Pi] ─┘                                    │
                                                     ▼
                                             Python + Claude AI
                                                     │
                                                     ▼
                                          JSON incident report
```

## Tech Stack

| Component       | Choice                                      |
| --------------- | ------------------------------------------- |
| Hardware        | Raspberry Pi 5 (4GB RAM)                    |
| SIEM            | ELK Stack 8.19 (Elasticsearch + Kibana)     |
| Log pipeline    | Filebeat to Logstash                        |
| Attack lab      | Kali Linux (Nmap, Hydra)                    |
| AI engine       | Anthropic Claude Sonnet 4.5                 |
| Glue language   | Python 3.13                                 |
| Defense layers  | UFW, Quad9 DNS, Bastion-style SSH           |

## Quick Start

### Prerequisites

Raspberry Pi 5 with Raspberry Pi OS (64-bit). Static IP and SSH configured. ELK Stack 8.x running. An Anthropic API key.

### Install

```bash
git clone https://github.com/YOUR_USERNAME/ai-soc.git
cd ai-soc

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your credentials
```

### Run

```bash
python analyze_alerts.py
```

## Sample Output

```
==================================================
Rule: SSH Brute Force Attempt - Multiple Failed Logins
Severity: low

Asking Claude...

Threat Level: Medium
Attack Type: SSH Brute Force Attack
MITRE: T1110.001
False Positive: False
Confidence: 0.75

Summary: Multiple failed SSH login attempts detected,
indicating a potential brute force attack against SSH
services. Pattern is consistent with automated credential
guessing.

Actions:
  Review SSH logs to identify source IPs
  Implement rate limiting via fail2ban
  Verify SSH key-based authentication is enforced
  Saved to output/alert_2026-04-25T20-45-47.152Z.json
```

## Key Insight

Kibana flagged this alert as **low** severity using static thresholds. Claude correctly **elevated it to Medium** based on attack pattern context, the exact judgment call a human Tier 2 analyst would make manually.

> Cost per analysis: ~$0.002 USD. Time saved per analysis: ~15 minutes of human triage.

## Lessons Learned

ELK on 4GB RAM is tight but workable. Careful JVM heap tuning is mandatory (1GB Elasticsearch, 512MB Logstash).

The SIEM server itself is also a target. Install Filebeat there too.

Self-signed certs and HTTPS toggling cause silent pipeline failures. Explicit `verify_certs=False` saves hours of debugging.

## Roadmap

Streamlit dashboard for visual alert browsing. Slack webhook for AI analysis push notifications. Multi-rule support (port scanning, privilege escalation, lateral movement). Winlogbeat agent on Windows endpoints. Prompt fine-tuning based on past alert outcomes.

## License

MIT — Use freely, attribution appreciated.
```
