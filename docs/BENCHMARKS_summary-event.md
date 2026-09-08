# Summarization benchmark: summary_kind=event

Date: 2026-09-05. Reports: 100, summaries: 99, errors: 1.

- Model: `qwen3.8:latest` digest `22130167c4c2` server `ollama 0.33.2`
- Prompt: `summary-event/qwen3.8-v2` v2 sha256 `7194f5dff1341991f59bd1caa2926bf82ed8d115868e04cf8da1ec4a5280cda4`; headings ['## What happened', '## Key indicators', '## Context and attribution', '## Related events']; max words 200

**Method.** No reference summaries exist, so this measures the module's own gate (headings, length, no indicator that is not in the input), length, how much of the event's own hashes/IPs/URLs the summary mentions (coverage, informational: a good summary need not list every hash), timing, and determinism between two passes with the same seed (byte-identical, and word-level similarity otherwise).

## Gate

| outcome / gate problem (one error can carry several) | count |
|---|---|
| summary produced | 99 |
| LLM answer was truncated (max_tokens too | 1 |

```mermaid
pie title Gate outcome
  "ok" : 99
  "LLM answer was truncated (max_tokens too" : 1
```

## Length (words, headings excluded by the gate; limit 200)

| min | median | p90 | max |
|---|---|---|---|
| 46 | 93 | 147 | 182 |

```mermaid
xychart-beta
  title "Words per summary"
  x-axis ["0", "25", "50", "75", "100", "125", "150", "175", "200", "225"]
  y-axis "summaries" 0 --> 46
  bar [0, 1, 13, 46, 18, 12, 7, 2, 0, 0]
```

## Headings present

| heading | summaries |
|---|---|
| ## What happened | 99 |
| ## Key indicators | 99 |
| ## Context and attribution | 99 |
| ## Related events | 99 |

## Indicator coverage (share of the reference md5/sha1/sha256/ip-dst/url mentioned)

| reports with indicators | mean coverage | median |
|---|---|---|
| 80 | 0.542 | 0.500 |

## Timing

| median s | p90 s | max s | total min |
|---|---|---|---|
| 5.130 | 7.588 | 13.401 | 8.906 |

## Determinism (second pass, same seed and temperature 0)

| paired | byte-identical | mean word similarity | min similarity |
|---|---|---|---|
| 99 | 97 | 0.994 | 0.538 |

## Per report

| id | title | status | words | coverage | seconds | identical | similarity |
|---|---|---|---|---|---|---|---|
| 03488f3d | DigitalSide Malware report: MD5: af5e5b2 | ok | 109 | 0.231 | 5.264 | True | 1.000 |
| 0c4cb36b | Malware collection | ok | 62 | 0.750 | 3.225 | True | 1.000 |
| 0d2fc4a8 | Redis bruteforce Attackers [2024-07-17] | ok | 81 |  | 4.925 | True | 1.000 |
| 0ef83690 | DigitalSide Malware report: MD5: fe34555 | ok | 100 | 0.800 | 6.660 | True | 1.000 |
| 0fe4fcd5 | DigitalSide Malware report: MD5: 15ca693 | ok | 126 | 0.800 | 6.197 | True | 1.000 |
| 1557a21b | Agent Tesla - javascript dropper - SMTP  | ok | 121 | 0.333 | 4.964 | True | 1.000 |
| 1699737c | AlienVault | Backdoored PHP Software | ok | 68 | 0.102 | 3.704 | True | 1.000 |
| 21d28baf | Honeytrap | ok | 74 |  | 4.837 | True | 1.000 |
| 229a6cc8 | Remcos host indicators [2023-09-12] | ok | 97 | 0.278 | 5.344 | True | 1.000 |
| 264575d2 | ThreatFox IOCs for 2024-04-12 | ok | 118 | 0.000 | 11.519 | True | 1.000 |
| 26d4048d | Dionaea | ok | 81 |  | 3.625 | True | 1.000 |
| 2a330185 | AlienVault | New modular downloaders fin | ok | 138 | 0.263 | 7.289 | True | 1.000 |
| 2cfaae22 | AlienVault | Carbanak attacks against Ch | ok | 96 | 0.556 | 4.348 | True | 1.000 |
| 2d6a7f33 | AgentTesla downloaded from a .js file (S | ok | 147 | 0.364 | 5.918 | True | 1.000 |
| 2eef230e | Cowrie | ok | 55 |  | 2.415 | True | 1.000 |
| 30dbf7d0 | Unveiling the Weaponized Web Shell Encys | ok | 91 |  | 3.778 | True | 1.000 |
| 317f3edc | Storm-1175 focuses gaze on vulnerable we | ok | 179 | 0.556 | 6.812 | True | 1.000 |
| 31a5a558 | Telnet bruteforce Attackers [2024-01-25] | ok | 82 |  | 6.914 | True | 1.000 |
| 361b5b3e | Formbook host indicators [2024-07-02] | ok | 89 | 0.278 | 5.171 | False | 0.538 |
| 3cc0969a | Telnet bruteforce Attackers [2024-03-07] | ok | 75 |  | 6.079 | True | 1.000 |
| 44146c5a | RDP bruteforce Attackers [2022-08-10] | ok | 80 |  | 6.913 | True | 1.000 |
| 4bf84caa | DigitalSide Malware report: MD5: ac06141 | ok | 99 | 0.286 | 4.590 | True | 1.000 |
| 4e1b163a | "Subject: [REDACTED] will be Disabled ,  | ok | 96 | 1.000 | 4.134 | True | 1.000 |
| 4f937fac | "Subject: RE: SHIPPING DOC - From: chenh | ok | 79 |  | 3.738 | True | 1.000 |
| 4ff7ce39 | Nuevo Backdoor en Outlook Atribuido a AP | ok | 108 | 1.000 | 5.310 | True | 1.000 |
| 5302ad3a | Detecting Linux Variants of Interlock Ra | ok | 104 | 1.000 | 5.126 | True | 1.000 |
| 56e1af4c | 0076e384e324fbb55fcb9d42b0ce281c | ok | 96 | 1.000 | 3.629 | True | 1.000 |
| 56e1b16a | 01ada39c547ab3b4c5bc811203caa493 | ok | 79 | 1.000 | 3.607 | True | 1.000 |
| 57615970 | Targeted attack against DNC | ok | 121 | 0.263 | 4.315 | True | 1.000 |
| 580f6d79 | Locky 2016-10-25 : Affid=3, DGA=88822 -  | ok | 143 | 0.064 | 8.437 | True | 1.000 |
| 587940d2 | Lokibot host indicators [2024-12-09] | ok | 79 | 0.556 | 4.135 | True | 1.000 |
| 589a41fb | Cerber delivered via malicious Office do | ok | 84 | 1.000 | 3.899 | True | 1.000 |
| 58b8193a | Reversing malware in a custom format_ Hi | ok | 63 | 1.000 | 3.086 | True | 1.000 |
| 591b7178 | Formbook host indicators [2024-05-22] | ok | 114 | 0.098 | 7.750 | True | 1.000 |
| 59aaa45d | Active ransomware attack uses impersonat | ok | 73 | 1.000 | 3.746 | True | 1.000 |
| 5a24041c | OSINT - Android Malware Appears Linked t | ok | 144 | 0.176 | 5.135 | True | 1.000 |
| 5a26b608 | M2M - "..doc" 2017-11-30 : "FL-123456 11 | ok | 138 | 0.172 | 7.588 | True | 1.000 |
| 5b6952a8 | DigitalSide Malware report: MD5: d90b513 | ok | 91 | 1.000 | 4.361 | True | 1.000 |
| 5b6ab2dc | "Zestawieni VAT-08/ZUS-08" Campaign | ok | 80 | 1.000 | 4.049 | True | 1.000 |
| 5c4970b2 | emotet IOC update | ok | 99 | 0.625 | 5.078 | True | 1.000 |
| 5c51a54e | OSINT: Excel 4.0 Macro Utilized by TA505 | ok | 182 | 0.056 | 10.664 | True | 1.000 |
| 5c55ff39 | emotet IOC update | ok | 106 | 0.444 | 5.571 | True | 1.000 |
| 5c65d32b | emotet IOC update | ok | 82 | 0.500 | 4.846 | True | 1.000 |
| 5c6d7d5f | c2 endpoint delta | ok | 68 | 1.000 | 3.961 | True | 1.000 |
| 5c6db438 | emotet IOC update | ok | 88 | 1.000 | 4.483 | True | 1.000 |
| 5c6dfe96 | c2 endpoint delta | ok | 76 | 0.104 | 4.511 | True | 1.000 |
| 5c974ce1 | emotet IOC update | ok | 108 | 0.122 | 6.231 | True | 1.000 |
| 5ca43fed | emotet IOC update | ok | 87 | 0.023 | 10.896 | True | 1.000 |
| 5d8f6b9e | emotet IOC update | ok | 83 | 0.104 | 6.684 | True | 1.000 |
| 5dc46103 | emotet IOC update | ok | 87 | 0.063 | 7.020 | True | 1.000 |
| 5dd58352 | emotet IOC update | ok | 95 | 0.060 | 6.833 | True | 1.000 |
| 5dea53aa | c2 endpoint delta | ok | 71 | 1.000 | 3.809 | True | 1.000 |
| 5e207470 | emotet IOC update | ok | 81 | 0.417 | 5.107 | True | 1.000 |
| 5e2890cc | emotet exe 5-tuple | ok | 71 | 1.000 | 3.855 | True | 1.000 |
| 5e3008c1 | Nice Try: 501 (Ransomware) Not Implement | ok | 116 | 0.250 | 3.839 | True | 1.000 |
| 5e37c8d1 | emotet IOC update | ok | 79 | 1.000 | 4.646 | True | 1.000 |
| 5e65434b | UPDATE binary C2 additions | ok | 97 |  | 5.213 | True | 1.000 |
| 5f0ee937 | UPDATE binary C2 additions | ok | 93 |  | 4.445 | True | 1.000 |
| 5f13849e | DigitalSide Malware report: MD5: b1a1bcb | ok | 127 | 0.800 | 6.236 | True | 1.000 |
| 5f15a68b | emotet IOC update | ok | 65 | 0.179 | 4.758 | True | 1.000 |
| 5f15caee | emotet exe 5-tuple | ok | 71 | 1.000 | 4.050 | True | 1.000 |
| 7082388a | SSH bruteforce Attackers [2026-08-14] | ok | 87 |  | 5.436 | True | 1.000 |
| 719d64ec | ATR_82599 | ok | 80 | 0.667 | 3.354 | True | 1.000 |
| 71ee28a1 | DigitalSide Malware report: MD5: 22faf22 | ok | 118 | 1.000 | 5.727 | True | 1.000 |
| 7ef5c2f6 | SSH bruteforce Attackers [2025-03-09] | ok | 80 |  | 13.401 | True | 1.000 |
| 813bc4df | Tibet Lurk | ok | 88 | 0.750 | 3.142 | True | 1.000 |
| 84248423 | AlienVault | ChinaZ Updates Toolkit by I | ok | 95 | 0.500 | 5.252 | True | 1.000 |
| 85b11f6b | njRAT host indicators [2024-02-21] | ok | 100 | 0.333 | 4.555 | True | 1.000 |
| 9a50d10e | AgentTesla in ISO mail attachment (SMTP  | ok | 61 | 0.333 | 3.282 | True | 1.000 |
| a8e25d5c | AlienVault | Parallax RAT sample CoronaV | ok | 134 | 1.000 | 4.786 | True | 1.000 |
| a9e1a395 | "Subject: Zapytanie ofertowe 7100519 - F | ok | 74 | 1.000 | 4.945 | True | 1.000 |
| ae108754 | AgentTesla in .tar email attachment (SMT | ok | 97 | 0.143 | 5.151 | True | 1.000 |
| ae41bec2 | Урядовою командою реагування на комп'юте | error | 0 |  | 9.286 |  |  |
| b201e6c4 | Telnet bruteforce Attackers [2024-05-15] | ok | 82 |  | 7.295 | True | 1.000 |
| b447f959 | AlienVault | Footprints of Fin7 | ok | 171 | 0.043 | 7.479 | True | 1.000 |
| b62ed471 | AlienVault | Zero-day exploit (CVE-2018- | ok | 168 |  | 5.240 | True | 1.000 |
| be0db1ab | Smoke Loader host indicators [2023-09-26 | ok | 100 | 0.217 | 5.521 | True | 1.000 |
| c426d9d8 | A recent campaign exploiting the Oman Mi | ok | 152 | 0.103 | 8.103 | True | 1.000 |
| c4bb38ee | Phishing URL Finding | urlabuse.com | ok | 89 | 1.000 | 2.655 | True | 1.000 |
| ca70216a | CACTUS: Analyzing a Coordinated Ransomwa | ok | 153 | 0.200 | 6.168 | True | 1.000 |
| cb2e2bb7 | VNC bruteforce Attackers [2025-11-09] | ok | 84 |  | 5.204 | True | 1.000 |
| ce05e941 | Daily Incremental ThreatFox Import - 202 | ok | 151 | 0.015 | 8.404 | True | 1.000 |
| d266f5a6 | Phishing URL Finding | ok | 130 | 1.000 | 4.889 | True | 1.000 |
| d729922e | BazaFlix: BazaLoader Fakes Movie Streami | ok | 154 | 0.200 | 5.322 | True | 1.000 |
| da2397a3 | Scam URL findings | ok | 75 | 1.000 | 2.642 | True | 1.000 |
| da61d35d | AlienVault | Goblin Panda continues to t | ok | 136 | 1.000 | 5.224 | True | 1.000 |
| dc0f8ebf | AlienVault | OilRig Targets Technology S | ok | 151 | 0.833 | 5.983 | False | 0.839 |
| dc58b05e | Redis bruteforce Attackers [2026-01-13] | ok | 85 |  | 5.346 | True | 1.000 |
| e05c2b5c | Scam URL findings | ok | 78 | 1.000 | 2.438 | True | 1.000 |
| e126ff7c | Formbook in email (.zip) attachment | ok | 125 | 0.333 | 7.113 | True | 1.000 |
| e6a2c4ae | VNC bruteforce Attackers [2022-05-22] | ok | 81 |  | 6.229 | True | 1.000 |
| eaab8d40 | NPM debug and chalk packages compromised | ok | 78 | 1.000 | 3.190 | True | 1.000 |
| ede6b753 | Command and Control in the Fifth Domain | ok | 139 | 0.057 | 5.727 | True | 1.000 |
| f178f6aa | DigitalSide Malware report: MD5: 2e091d7 | ok | 109 | 0.800 | 5.291 | True | 1.000 |
| f1e3923a | Lokibot host indicators [2023-08-22] | ok | 92 | 0.333 | 5.036 | True | 1.000 |
| f394628d | DigitalSide Malware report: MD5: d118057 | ok | 110 | 0.136 | 6.131 | True | 1.000 |
| f85b39fa | DDoSPot | ok | 46 |  | 2.057 | True | 1.000 |
| f9d71002 | Campaign Tracked as STAC6405  Organizati | ok | 100 | 1.000 | 2.779 | True | 1.000 |
| fa2d17b5 | Agent Tesla downloader via email attachm | ok | 91 | 0.154 | 5.228 | True | 1.000 |
| fbac52a7 | AlienVault | Nice Try: 501 (Ransomware)  | ok | 105 | 0.500 | 4.097 | True | 1.000 |

## Reproduce

```bash
GENERIC_AI_REQUEST_TIMEOUT=900 python -m benchmarks.run_llm --use-case summarization --kind event
GENERIC_AI_REQUEST_TIMEOUT=900 python -m benchmarks.run_llm --use-case summarization --kind event --results-dir benchmarks/results-pass2
python -m benchmarks.compare_summary --kind event --second-dir benchmarks/results-pass2
```
