{"model": "qwen3.8:latest", "digest": "22130167c4c2", "server": "ollama 0.33.2", "prompt_sha256": "702a911fb51766663251ce3bd008f0e8eb8e07d112f1189a0290d87c4bd4dc7d"}
---
## Threat
Phishing campaign targeting ACME Bank customers. Attackers use spoofed emails and malicious Excel attachments to steal credentials and one-time codes. Low-confidence attribution links this to a March 2026 campaign against Beta Credit Union.

## Targets
ACME Bank customers. Twelve customers reported fraudulent transfers. No employee accounts were compromised.

## Indicators
alerts@acme-bank-secure.example
https://login-acme-bank.example/verify
203.0.113.42
login-acme-bank.example
Invoice_2026.xlsm
and 2 more in the report

## Recommended actions
Block the domain and IP. Reset credentials of affected customers. Warn customers about the sender address. Report new URLs to the CSIRT.
