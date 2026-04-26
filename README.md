# AI Augmented SOC on a Raspberry Pi 5

> A self hosted Security Operations Center running on a Raspberry Pi 5.

It catches simulated SSH brute force attacks against the Pi, then hands each alert to **Claude** to analyze. The result comes back as structured JSON in seconds: threat level, MITRE ATT&CK mapping, false positive likelihood, and concrete remediation actions.

![SOC Architecture](docs/architecture.svg)

---

## Why I built this

I love working in my home lab, and I decided to see how far I could push my new Raspberry Pi 5. The plan was simple. Get the ELK Stack running on it, simulate attacks from a Kali Linux machine, and see whether an LLM could turn the resulting noise into something actually actionable. The Pi was the perfect excuse to build this on real hardware instead of cloud VMs. Limited memory, real network constraints, real consequences if I misconfigured something.

The AI part came naturally. Security analysts spend a significant chunk of their day on the same handful of tasks: judging how serious an alert is, mapping it to known attack patterns, and deciding what is real signal versus background noise. I wanted to see whether Claude could do that part of the job in seconds.

This project sits at the intersection of two things I enjoy: cybersecurity and making LLMs do useful work.

---

## What it does

Both the Kali attacker and the Pi itself run **Filebeat**, a small agent that ships every system log line into the **ELK Stack**. ELK is the open source trio at the heart of the pipeline: Elasticsearch stores and indexes the logs, Logstash parses them on the way in, and Kibana provides the search interface and detection engine on top. A custom rule in Kibana fires whenever 3 or more failed SSH logins happen within 5 minutes from the same source. A Python script then pulls those fresh alerts out of Elasticsearch through its HTTP API and hands each one to Claude with a "senior SOC analyst" prompt.

Claude returns a structured response. It gives a threat level, and reclassifies it when the static rule underrates the event. It maps the alert to a known attack technique, scores how likely the alert is a false alarm, writes a short human readable summary, and proposes concrete remediation steps. Every analysis is printed to the terminal and written to disk as a JSON incident report ready for downstream automation.

---

## Tech Stack

| Component        | Choice                                              |
| ---------------- | --------------------------------------------------- |
| Hardware         | Raspberry Pi 5 (4 GB RAM)                           |
| Log monitoring   | ELK Stack 8.19 (Elasticsearch + Logstash + Kibana)  |
| Log shipping     | Filebeat (on Kali **and** on the Pi)                |
| Attack lab       | Kali Linux in VMware (Nmap, Hydra)                  |
| AI engine        | Anthropic Claude Sonnet 4.5 via API                 |
| Glue language    | Python 3.13                                         |
| Defense layers   | UFW firewall, Quad9 DNS, hardened SSH               |

---

## Pipeline in Action

A walkthrough from start to finish, ending with a finished incident report analyzed by AI.

### 1. The Pi, hardened

Before anything else, the Pi gets locked down. A firewall (UFW) that blocks all incoming traffic by default, a fixed IP on the lab network, a custom hostname, and SSH locked to key only authentication. The monitoring server itself is a target, and that mindset shapes every later decision.

![Pi hardening: UFW status, hostname, static IP](docs/screenshots/01-pi-hardening.png)

### 2. ELK up and running

Elasticsearch, Logstash, and Kibana all running as background services on a 4 GB Pi. Memory limits are tuned conservatively (1 GB for Elasticsearch, 512 MB for Logstash) so the box doesn't crash under load.

![ELK services running under systemd](docs/screenshots/02-elk-services.png)

### 3. Logs streaming into Kibana

With Filebeat shipping from both Kali and the Pi, Kibana fills up with structured events in real time. This is the raw nervous system of the SOC, and everything else is built on top of this stream.

![Kibana Discover view with logs streaming in](docs/screenshots/03-kibana-logs.png)

### 4. Simulated attack from Kali

Hydra, a tool that automates password guessing, runs an SSH brute force attempt from the Kali VM against the Pi. Within seconds, the failed login events show up in Kibana. This is the signal the detection rule is built around.

![Failed password events from the Kali attacker](docs/screenshots/04-failed-passwords.png)
# ADD NMAP SCAN
![Failed password events from the Kali attacker](docs/screenshots/04-failed-passwords.png)

# ADD KALI ATTACK
![Failed password events from the Kali attacker](docs/screenshots/04-failed-passwords.png)


### 5. Detection rule fires

The custom Kibana rule (3 or more failed SSH logins from the same source within 5 minutes) promotes the raw events into a proper alert. This is where a traditional security pipeline would either page a human analyst or get ignored as noise.

![Triggered alerts in the Kibana Security app](docs/screenshots/05-alerts.png)

### 6. Claude takes the alert

The Python script pulls the alert from Elasticsearch and sends it to Claude with a senior analyst prompt. Claude returns a structured verdict: threat level, attack type, MITRE technique, false alarm assessment with a confidence score, a written summary, and remediation steps. The whole round trip takes a couple of seconds.

![Terminal output of analyze_alerts.py showing Claude's structured analysis](docs/screenshots/06-ai-analysis.png)

### 7. Persisted as a JSON incident report

Each analysis is saved to disk as a timestamped JSON file containing both the original alert and the AI verdict. This is the format I would hand to downstream automation, whether that means alerting the team, opening a ticket, or kicking off an automated response.

![JSON output file showing alert and ai_analysis fields](docs/screenshots/07-json-report.png)

---

## Quick Start

### Prerequisites

A Raspberry Pi 5 (or any Linux box) running 64 bit Raspberry Pi OS, with a static IP and SSH configured. ELK Stack 8.x up and running. An Anthropic API key.

### Install

```bash
git clone https://github.com/tingelholm/ai-soc-lab.git
cd ai-soc-lab

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY, ES_HOST, ES_USER, ES_PASSWORD
```

### Run

```bash
python analyze_alerts.py
```

---

## Sample Output

```
==================================================
Rule: SSH Brute Force Attempt: Multiple Failed Logins
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
  Verify SSH key based authentication is enforced

  Saved to output/alert_2026-04-25T20-45-47.152Z.json
```

---

## Key Insight

Kibana flagged this alert as **low** severity using its static thresholds. Claude correctly **elevated it to Medium** based on the attack pattern. That is the same judgment call a human analyst would make manually after eyeballing the data, and it is the whole thesis of the project in one example. Static rules are great at catching things, but bad at understanding them. An LLM in the loop bridges that gap cheaply.

> Cost per analysis: about $0.002. Time saved: around 15 minutes of analyst work per alert.

---

## Lessons Learned

**Running a full ELK Stack on 4 GB of RAM is tight but workable.** Java memory limits have to be tuned by hand (1 GB for Elasticsearch, 512 MB for Logstash) or the whole system silently starts swapping and grinding to a halt.

**The monitoring server itself is also a target.** I run Filebeat on the Pi, not just on the things being monitored. If the SOC gets compromised and is not shipping its own logs, you will never see the attack that took it down.

**Silent pipeline failures often come from encryption mismatches between components.** Filebeat will happily pretend everything is fine while quietly dropping log lines on the floor. An explicit `verify_certs=False` setting during lab work saves hours of debugging. Just don't ship that into anything resembling production.

**AI excels at the contextual reasoning that static rules can't encode.** Rules are good at "this happened N times in M minutes." LLMs are good at "this matters because…", and the second half is where most of the analyst work actually lives.

---

## Roadmap

A web dashboard (probably Streamlit) for browsing alerts visually is the next step, followed by Slack notifications so AI analyses get pushed to my phone instead of sitting in a JSON file. Beyond that: support for additional attack types like port scanning, privilege escalation, and lateral movement, Windows endpoint coverage via Winlogbeat, and prompt tuning based on the outcomes of past alerts so the system gets sharper over time.

---

## License

MIT. Use freely, attribution appreciated.
