{"model": "qwen3.8:latest", "digest": "22130167c4c2", "server": "ollama 0.33.2", "prompt_sha256": "b5ed5d27d94e2336aa4a5633f2b6f9e1168d101d9a636b03c843cd0e714098df"}
---
## What happened
On 2026-09-02, a phishing campaign targeted ACME Bank customers using fake hotel invoices. The operation, labeled "ACME hotel-invoice phishing 2026," resulted in approximately 40,000 EUR in losses across twelve victims. The attack leveraged the MITRE ATT&CK technique T1566 (Phishing) to deliver malicious payloads.

## Key indicators
The event includes the following network and file indicators:
- **Domain:** login-acme-bank.example
- **IP Address:** 203.0.113.42 (identified as the phishing host)
- **URL:** https://login-acme-bank.example/verify
- **Email Source:** alerts@acme-bank-secure.example
- **File Object:** `0a1b2c3d-4e5f-4607-8192-a3b4c5d6e7f8`
  - Filename: Invoice_2026.xlsm
  - MD5: d41d8cd98f00b204e9800998ecf8427e
  - SHA256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

## Context and attribution
The campaign is attributed to the "ACME hotel-invoice phishing 2026" operation. It is tagged with `misp-galaxy:mitre-attack-pattern="Phishing - T1566"` and marked `tlp:amber`. No specific threat actor or galaxy attribution beyond the campaign name and technique is provided in the event data.

## Related events
One related event is linked:
- `1b2c3d4e-5f60-4718-8293-a4b5c6d7e8f9`: March 2026 phishing campaign against Beta Credit Union
