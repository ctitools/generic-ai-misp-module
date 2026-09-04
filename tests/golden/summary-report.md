{"model": "qwen3.8:latest", "digest": "22130167c4c2", "server": "ollama 0.33.2", "prompt_sha256": "22dc0a98abda8ed8cd1977ea2c1a4f1e910e0fa26a645414768a31002bd2fff1"}
---
## Threat
On 2 September 2026, ACME Bank customers received phishing emails from alerts@acme-bank-secure.example. The emails contained an Excel attachment, Invoice_2026.xlsm, which, upon enabling macros, contacted a malicious host to download a second-stage loader. The campaign aimed to steal credentials and one-time codes via a fake login portal. Twelve customers reported fraudulent transfers totaling approximately 40,000 EUR. The campaign is attributed with low confidence to the group responsible for the March 2026 attack on Beta Credit Union.

## Targets
ACME Bank customers were targeted. No employee accounts were compromised.

## Indicators
*   **Sender Email:** alerts@acme-bank-secure.example
*   **Phishing URL:** https://login-acme-bank.example/verify
*   **Domain:** login-acme-bank.example
*   **IP Address:** 203.0.113.42
*   **File Name:** Invoice_2026.xlsm
*   **MD5:** d41d8cd98f00b204e9800998ecf8427e
*   **SHA256:** e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

## Recommended actions
Block the domain login-acme-bank.example and IP address 203.0.113.42. Reset credentials for affected customers. Warn customers about the sender address alerts@acme-bank-secure.example. Report new URLs to the CSIRT.
