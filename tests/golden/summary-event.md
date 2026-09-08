{"model": "qwen3.8:latest", "digest": "22130167c4c2", "server": "ollama 0.33.2", "prompt_sha256": "7194f5dff1341991f59bd1caa2926bf82ed8d115868e04cf8da1ec4a5280cda4"}
---
## What happened
A phishing campaign targeted ACME Bank customers. Attackers sent emails from a spoofed address containing a malicious Excel attachment. The campaign resulted in approximately 40,000 EUR in losses for twelve victims.

## Key indicators
- domain: login-acme-bank.example
- ip-dst: 203.0.113.42
- url: https://login-acme-bank.example/verify
- email-src: alerts@acme-bank-secure.example
- sha256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

## Context and attribution
The event is tagged with MITRE ATT&CK pattern T1566 (Phishing). The campaign is named "ACME hotel-invoice phishing 2026". The malicious file object (0a1b2c3d-4e5f-4607-8192-a3b4c5d6e7f8) contains the payload. TLP:Amber applies.

## Related events
- 1b2c3d4e-5f60-4718-8293-a4b5c6d7e8f9: March 2026 phishing campaign against Beta Credit Union
