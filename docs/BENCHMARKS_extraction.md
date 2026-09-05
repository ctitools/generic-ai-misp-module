# Extraction benchmark: LLM vs classic regex extractor

Date: 2026-09-05. Sample: seed 42, n 100, reports with
results 100, reports with LLM errors 5.

- Model: `qwen3.8:latest` digest `22130167c4c2` server `ollama 0.33.2`
- Prompt: `cti-info-extraction/qwen3.8-v1` v3 sha256 `f25563e3df2eb6cf00ff93202af01fa5a344515236d866d553eff64348c98da2`
- Classic tool: `iocextract 1.16.1`

- Dates: 39 of 1411 stored indicators carry a first_seen/last_seen stated in the text;
  61 reports state a publication date
- Not actionable per the model (to_ids lowered): 35 indicators (listed under Deviations)

**Method.** Indicators are compared by normalised value only (lower-case, trailing `/` and `.`
stripped); types are ignored. The classic extractor is a deliberate *superset* reference (it also
catches defanged values), so an LLM "false positive" is a value the regexes missed and an LLM
"false negative" may be a correct omission (e.g. the reporting vendor's own site). Specificity and
accuracy need a wider universe than `llm ∪ classic` and are only meaningful in the gold view.

## LLM vs classic (95 reports)

### Confusion matrix (micro counts)

|  | classic yes | classic no | total |
|---|---|---|---|
| LLM yes | 743 | 668 | 1411 |
| LLM no | 480 | 0 | 480 |
| total | 1223 | 668 | 1891 |

### Metrics

| metric | micro | macro (mean per report) |
|---|---|---|
| precision | 0.527 | 0.409 |
| recall | 0.608 | 0.430 |
| specificity | 0.000 | 0.000 |
| accuracy | 0.393 | 0.288 |
| f1 | 0.564 | 0.385 |
| jaccard | 0.393 | 0.288 |
| cohen_kappa | -0.419 | -0.280 |

### Recall of classic values by type

| type | classic n | recall |
|---|---|---|
| domain | 216 | 0.083 |
| email | 14 | 0.429 |
| ip-dst | 127 | 0.622 |
| md5 | 131 | 0.954 |
| sha1 | 75 | 0.840 |
| sha256 | 317 | 0.984 |
| url | 344 | 0.407 |
```mermaid
xychart-beta
  title "Recall by type"
  x-axis ["ip-dst", "url", "domain", "email", "md5", "sha1", "sha256"]
  y-axis "recall" 0 --> 1.000
  bar [0.622, 0.407, 0.083, 0.429, 0.954, 0.840, 0.984]
```

### Agreement

```mermaid
pie title LLM-only / both / classic-only
  "LLM only" : 668
  "both" : 743
  "classic only" : 480
```

### Per-report F1 histogram

```mermaid
xychart-beta
  title "Per-report F1"
  x-axis ["0.0", "0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9"]
  y-axis "reports" 0 --> 31
  bar [31, 1, 4, 7, 9, 15, 12, 6, 7, 3]
```

### Reports by recall and precision

```mermaid
quadrantChart
  title Reports by recall (x) and precision (y)
  x-axis "low recall" --> "high recall"
  y-axis "low precision" --> "high precision"
  quadrant-1 agree
  quadrant-2 LLM strict
  quadrant-3 disagree
  quadrant-4 LLM generous
  8e804b2b: [0.000, 0.000]
  540efc3c: [0.771, 0.386]
  d27118be: [1.000, 0.200]
  8cb9ac5c: [0.556, 0.500]
  c9acfc88: [0.375, 0.429]
  d256214e: [0.706, 0.667]
  45f70928: [0.500, 0.600]
  662a629b: [0.455, 1.000]
  7d04b6ff: [0.765, 0.433]
  082d3389: [0.824, 0.318]
  f22ca523: [0.000, 0.000]
  0d759389: [0.000, 0.000]
  712ff0fc: [0.385, 0.714]
  0173351d: [0.833, 0.577]
  c191576a: [0.464, 0.565]
  93f7b554: [0.167, 1.000]
  6eeb84e3: [0.944, 0.586]
  fdb2627c: [0.000, 0.000]
  ea50871d: [0.857, 0.638]
  c143dbde: [0.000, 0.000]
  7d02b3fa: [0.000, 0.000]
  0e1ee8a9: [0.417, 0.385]
  405f54ff: [0.933, 0.509]
  1405a5dc: [0.000, 0.000]
  6cc03d12: [0.333, 0.333]
  78d08d87: [0.647, 0.524]
  68303cde: [0.000, 0.000]
  69b2b5d5: [0.000, 0.000]
  fbb37538: [0.000, 0.000]
  d740af4f: [0.000, 0.000]
  10524cc8: [0.967, 0.906]
  e0234eb8: [0.250, 0.200]
  b376f09a: [0.000, 0.000]
  9d745433: [0.692, 0.360]
  f9158c72: [0.588, 0.435]
  cc13367a: [0.444, 1.000]
  52cbaed5: [0.000, 0.000]
  4e697d2e: [0.500, 1.000]
  11def925: [0.811, 0.956]
  36f4a46a: [0.786, 0.786]
  53ecd031: [1.000, 1.000]
  53d99aad: [0.000, 0.000]
  59058517: [0.389, 0.538]
  5b6dbdb5: [0.815, 0.688]
  07e04656: [0.909, 0.909]
  be97537d: [0.864, 0.826]
  13edb894: [0.000, 0.000]
  731ff89d: [0.250, 0.667]
  5f36e25e: [0.000, 0.000]
  03e9e845: [0.538, 0.750]
  d1d74b29: [1.000, 0.375]
  536e5094: [0.667, 0.421]
  014c75a7: [0.000, 0.000]
  12b3fde8: [0.000, 0.000]
  40301ca4: [0.000, 0.000]
  d72a26f9: [0.950, 0.792]
  bd43481b: [0.800, 1.000]
  20649884: [0.611, 0.524]
  cc825515: [1.000, 0.500]
  b131f886: [0.920, 0.676]
```

### Indicator counts per extractor

```mermaid
xychart-beta
  title "Indicators per type"
  x-axis ["ip-dst", "url", "domain", "email", "md5", "sha1", "sha256"]
  y-axis "classic / llm" 0 --> 344
  bar [127, 344, 216, 14, 134, 75, 321]
  bar [60, 154, 126, 1, 123, 61, 312]
```

### Per report

| id | title | classic n | llm n | tp | fp | fn | precision | recall | f1 | kappa | seconds |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 8e804b2b-e84d-4eb4-b6ca-d4b0fdb21aee | With Upgrades in Delivery and Support In | 3 | 5 | 0 | 5 | 3 | 0.000 | 0.000 | 0.000 | -0.882 | 5.852 |
| 540efc3c-e3f9-437c-9684-eef5d0262a77 | 2020-05-21 - No “Game over” for the Winn | 35 | 70 | 27 | 43 | 8 | 0.386 | 0.771 | 0.514 | -0.209 | 60.751 |
| d27118be-8a8f-4660-994e-7450c6d80ab1 | A Pretty Dope Story About Bears: Early I | 1 | 5 | 1 | 4 | 0 | 0.200 | 1.000 | 0.333 | 0.000 | 5.931 |
| 8cb9ac5c-b5dd-45a5-80d9-56dbdacdbc5a | Operation Bleeding Bear | 9 | 10 | 5 | 5 | 4 | 0.500 | 0.556 | 0.526 | -0.465 | 13.469 |
| c9acfc88-6f0e-4ded-94f3-8e6985871d86 | 2021-11-02 - Underminer Exploit Kit- The | 16 | 14 | 6 | 8 | 10 | 0.429 | 0.375 | 0.400 | -0.588 | 18.203 |
| d256214e-8231-4909-91e7-e2dfbe7f31f4 | 2017-07-24 - Real News, Fake Flash- Mac  | 17 | 18 | 12 | 6 | 5 | 0.667 | 0.706 | 0.686 | -0.311 | 16.874 |
| 45f70928-55c0-4208-9f4e-75c1a1ba1d26 | 2010-03-07 - March 2010 Opachki Trojan u | 6 | 5 | 3 | 2 | 3 | 0.600 | 0.500 | 0.545 | -0.429 | 10.134 |
| 662a629b-5164-483c-acf3-7741fd42edb5 | IssueMakersLab - Cyber Warfare Research  | 22 | 10 | 10 | 0 | 12 | 1.000 | 0.455 | 0.625 | 0.000 | 15.445 |
| 7d04b6ff-183f-42d5-8508-8e52f1a00bbf | Rancor: Cyber Espionage Group Uses New C | 20 | 30 | 13 | 17 | 4 | 0.433 | 0.765 | 0.553 | -0.235 | 33.698 |
| 082d3389-8415-4dc9-8355-91a8ff03a6d7 | Cutting Edge, Part 3: Investigating Ivan | 17 | 44 | 14 | 30 | 3 | 0.318 | 0.824 | 0.459 | -0.131 | 43.755 |
| f22ca523-b736-4340-9ed2-bacc2a123910 | Secure Communications Blog | 2 | 0 | 0 | 0 | 2 | 0.000 | 0.000 | 0.000 | 0.000 | 1.920 |
| 0d759389-9c2f-45fc-9e94-7fe3617ce50b | 2017-10-13 - FIN7 Dissected- Hackers Acc | 0 | 2 | 0 | 2 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 2.117 |
| 712ff0fc-e931-40f9-bc34-299b70a12075 | Hagga of SectorH01 continues abusing Bit | 26 | 14 | 10 | 4 | 16 | 0.714 | 0.385 | 0.500 | -0.271 | 35.546 |
| 0173351d-ecc3-4815-a3ad-05720e6d7773 | Chafer: Latest Attacks Reveal Heightened | 18 | 26 | 15 | 11 | 3 | 0.577 | 0.833 | 0.682 | -0.194 | 19.929 |
| c191576a-2829-4fd3-9e06-d34390fac314 |  | 28 | 23 | 13 | 10 | 15 | 0.565 | 0.464 | 0.510 | -0.462 | 26.352 |
| 93f7b554-a14b-46a5-8c6a-612fec57668b | 2020-10-11 - Chimera, APT19 under the ra | 6 | 1 | 1 | 0 | 5 | 1.000 | 0.167 | 0.286 | 0.000 | 5.994 |
| 6eeb84e3-8986-48e4-9441-145d10cb8f02 | 2020-01-23 - German language malspam pus | 18 | 29 | 17 | 12 | 1 | 0.586 | 0.944 | 0.723 | -0.066 | 26.090 |
| fdb2627c-d5dc-4601-bfbe-bf446e27ba17 | Treasury Sanctions China-based Hacker In | 2 | 8 | 0 | 8 | 2 | 0.000 | 0.000 | 0.000 | -0.471 | 7.791 |
| ea50871d-6809-483c-8777-07924f8c9419 | COVID-19 and New Year greetings: an inve | 35 | 47 | 30 | 17 | 5 | 0.638 | 0.857 | 0.732 | -0.175 | 64.978 |
| c143dbde-a82b-46b6-9bfe-21c8c18905e7 | HP_Bromium_Threat_Insights_Report_Q4_202 | 31 | 4 | 0 | 4 | 31 | 0.000 | 0.000 | 0.000 | -0.254 | 5.900 |
| 7d02b3fa-342e-4857-b094-85c65c96779c | New threat actor, UAT-9921, leverages Vo | 2 | 4 | 0 | 4 | 2 | 0.000 | 0.000 | 0.000 | -0.800 | 8.250 |
| 0e1ee8a9-df19-40ed-b899-4e825353b0e6 | 2017-11-15 - New EMOTET Hijacks a Window | 12 | 13 | 5 | 8 | 7 | 0.385 | 0.417 | 0.400 | -0.596 | 15.692 |
| 405f54ff-1a60-4f56-a8ed-7a502e0445fc | MMD-0064-2019 - Linux/AirDropBot | 30 | 55 | 28 | 27 | 2 | 0.509 | 0.933 | 0.659 | -0.070 | 56.319 |
| 1405a5dc-c3f2-4f58-8c62-46c8367e62f0 | Authorities confirm RagnarLocker ransomw | 2 | 2 | 0 | 2 | 2 | 0.000 | 0.000 | 0.000 | -1.000 | 3.476 |
| 6cc03d12-f2bd-4227-aca9-882cf2deed9d | New Apple Mac Trojan Called OSX/Crisis D | 3 | 3 | 1 | 2 | 2 | 0.333 | 0.333 | 0.333 | -0.667 | 3.670 |
| 78d08d87-e069-48aa-bdf8-e0f677503ce2 | ZINC weaponizing open-source software |  | 17 | 21 | 11 | 10 | 6 | 0.524 | 0.647 | 0.579 | -0.385 | 30.614 |
| 68303cde-3001-483f-837d-4571efae2158 | 1,400 Pegasus spyware infections detaile | 2 | 2 | 0 | 2 | 2 | 0.000 | 0.000 | 0.000 | -1.000 | 5.684 |
| 69b2b5d5-53fd-46c9-95de-dd95527a8649 | 2020-12-02 - ‘Shadow Academy’ Targets 20 | 0 | 7 | 0 | 7 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 6.420 |
| fbb37538-3879-45ae-980e-a549a3f54d9b | Censys Blog | Cybersecurity Insights & T | 3 | 0 | 0 | 0 | 3 | 0.000 | 0.000 | 0.000 | 0.000 | 1.806 |
| d740af4f-cd35-4cc9-a33b-4cf450aaf816 | Enabling or disabling Lockdown mode on a | 2 | 0 | 0 | 0 | 2 | 0.000 | 0.000 | 0.000 | 0.000 | 1.553 |
| 10524cc8-bf09-47e5-bcc7-0f9e5ec1c061 | 2020-03-21 - On the Royal Road | 30 | 32 | 29 | 3 | 1 | 0.906 | 0.967 | 0.935 | -0.048 | 43.025 |
| e0234eb8-0ea8-4087-87e7-7aa11fcacd46 | Passive Income of Cyber Criminals: Disse | 5 | 5 | 1 | 4 | 3 | 0.200 | 0.250 | 0.222 | -0.750 | 8.381 |
| b376f09a-1824-4881-8847-35d66d236ba2 | Advisories are published, but are enough | 2 | 5 | 0 | 5 | 2 | 0.000 | 0.000 | 0.000 | -0.690 | 4.692 |
| 9d745433-260f-4b45-bc4c-372a71aa8b56 |  | 13 | 25 | 9 | 16 | 4 | 0.360 | 0.692 | 0.474 | -0.283 | 20.910 |
| f9158c72-03d6-4e82-a9fa-cf9680adbdcd | Medre.A - AutoCAD worm samples | 17 | 23 | 10 | 13 | 7 | 0.435 | 0.588 | 0.500 | -0.435 | 24.648 |
| cc13367a-315e-4d21-9ebf-184092d35371 | Enterprise Scale Threat Hunting: C2 Beac | 9 | 4 | 4 | 0 | 5 | 1.000 | 0.444 | 0.615 | 0.000 | 5.132 |
| 52cbaed5-b357-4ba4-949f-9b846045446a | 2020-04-08 - How Cyber Adversaries are A | 0 | 24 | 0 | 24 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 17.823 |
| 4e697d2e-8ecf-4947-b43e-2c18b8298aa8 | Adobe To Announce Source Code, Customer  | 2 | 1 | 1 | 0 | 1 | 1.000 | 0.500 | 0.667 | 0.000 | 2.753 |
| 11def925-953a-4785-af7e-27d88970460c | CryptoClippy is Evolving to Pilfer Even  | 54 | 45 | 43 | 2 | 10 | 0.956 | 0.811 | 0.878 | -0.065 | 59.182 |
| 36f4a46a-d4d6-49dd-89c0-0c7fac1356eb | 2020-09-17 - Complex obfuscation- Meh… ( | 14 | 14 | 11 | 3 | 3 | 0.786 | 0.786 | 0.786 | -0.214 | 19.508 |
| 53ecd031-d5cc-491f-93cb-6d516b242723 | 2022-11-15 - New RapperBot Campaign – We | 24 | 24 | 24 | 0 | 0 | 1.000 | 1.000 | 1.000 | 1.000 | 25.895 |
| 53d99aad-54d9-44f7-9161-f4346320da12 | CAPEC-163: Spear Phishing (Version 3.9) | 2 | 2 | 0 | 2 | 2 | 0.000 | 0.000 | 0.000 | -1.000 | 3.889 |
| 59058517-476f-42b7-a8ff-6b06b85e1c4d | 2021-06-17 - New TA402 Molerats Malware  | 18 | 13 | 7 | 6 | 11 | 0.538 | 0.389 | 0.452 | -0.478 | 21.351 |
| 5b6dbdb5-7232-4d88-b1cd-cda6e02c9d82 | 2016-11-08 - Analysis of iOSGuiInject Ad | 54 | 64 | 44 | 20 | 10 | 0.688 | 0.815 | 0.746 | -0.220 | 51.445 |
| 07e04656-9d85-45ee-9f71-ea6a4f787881 | 2022-03-11 - New Wiper Malware Attacking | 22 | 22 | 20 | 2 | 2 | 0.909 | 0.909 | 0.909 | -0.091 | 25.350 |
| be97537d-9a58-4756-af78-49314e7c10dc | 2023-01-26 - Welcome to Goot Camp- Track | 44 | 46 | 38 | 8 | 6 | 0.826 | 0.864 | 0.844 | -0.152 | 65.550 |
| 13edb894-84e6-4415-ba72-43c6d5cd4da9 | 2009-08-05 - PC Users Threatened by Conf | 0 | 8 | 0 | 8 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 7.782 |
| 731ff89d-2473-41f6-a29a-10a7b1a21221 | New “CleverSoar” Installer Targets Chine | 8 | 3 | 2 | 1 | 6 | 0.667 | 0.250 | 0.364 | -0.235 | 5.428 |
| 5f36e25e-4cfd-4cc8-8476-8a21405a80cc | Web skimmers found on the websites of In | 2 | 1 | 0 | 1 | 2 | 0.000 | 0.000 | 0.000 | -0.800 | 2.295 |
| 03e9e845-dd6f-41aa-ae06-0f700f8b6209 | ErrorFather's Cerberus: Amplifying Cyber | 39 | 28 | 21 | 7 | 18 | 0.750 | 0.538 | 0.627 | -0.281 | 33.254 |
| d1d74b29-dfae-465f-bde6-95e3789d35c5 | Nobelium Returns to the Political World  | 3 | 8 | 3 | 5 | 0 | 0.375 | 1.000 | 0.545 | 0.000 | 10.653 |
| 536e5094-0063-4752-8c4f-492ae30c636d | Gamaredon group grows its game | 12 | 19 | 8 | 11 | 4 | 0.421 | 0.667 | 0.516 | -0.342 | 18.932 |
| 014c75a7-0397-46b8-a722-f3cdca20a203 | US aerospace services provider breached  | 2 | 1 | 0 | 1 | 2 | 0.000 | 0.000 | 0.000 | -0.800 | 3.266 |
| 12b3fde8-4bca-4a69-a632-c4fbb17388ea | SonicALERT: CVE 2014-0322 Malware - Saku | 2 | 4 | 0 | 4 | 2 | 0.000 | 0.000 | 0.000 | -0.800 | 4.824 |
| 40301ca4-fed9-4b59-95ba-b668eb8eb7aa | 2018-11-27 - Meet CrowdStrike’s Adversar | 0 | 7 | 0 | 7 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 7.015 |
| d72a26f9-8c68-4211-9724-f56248338daa | 2023-01-24 - DragonSpark - Attacks Evade | 20 | 24 | 19 | 5 | 1 | 0.792 | 0.950 | 0.864 | -0.071 | 23.159 |
| bd43481b-2327-459f-b28d-2190e5c53c2e | LAPSUS$: Recent techniques, tactics and  | 5 | 4 | 4 | 0 | 1 | 1.000 | 0.800 | 0.889 | 0.000 | 5.784 |
| 20649884-ffe0-4fa6-aa3a-6e4e28d041c8 | North Korean hackers are skimming US and | 18 | 21 | 11 | 10 | 7 | 0.524 | 0.611 | 0.564 | -0.417 | 20.445 |
| cc825515-25a8-40ef-8eb0-fc8647a2a6fc | 2022-08-25 - New Golang Ransomware Agend | 4 | 8 | 4 | 4 | 0 | 0.500 | 1.000 | 0.667 | 0.000 | 13.701 |
| b131f886-5ffa-423f-a28e-d3bc0b9c094a | IcedID Campaign Spotted Being Spiced Wit | 25 | 34 | 23 | 11 | 2 | 0.676 | 0.920 | 0.780 | -0.104 | 39.229 |
| 6970d678-af35-45eb-a737-ae6dff7f95bb | Yokogawa announcement warns of counterfe | 3 | 1 | 1 | 0 | 2 | 1.000 | 0.333 | 0.500 | 0.000 | 2.616 |
| 97271a6a-85e2-4e34-afd8-4ef4fcea8001 | Probable Iranian Cyber Actors, Static Ki | 34 | 10 | 8 | 2 | 26 | 0.800 | 0.235 | 0.364 | -0.115 | 12.217 |
| 2ddc0184-fa5c-43d9-971f-2063eed1f473 | Latest Cyber Threat Intelligence & Secur | 53 | 34 | 0 | 34 | 53 | 0.000 | 0.000 | 0.000 | -0.909 | 27.106 |
| 88425055-d1e5-4ee5-99fc-9da64837161d | Equinix data center giant hit by Netwalk | 4 | 3 | 0 | 3 | 4 | 0.000 | 0.000 | 0.000 | -0.960 | 3.836 |
| 7d044e79-5cff-47b3-a06d-71ba997d3aa0 | 2022-01-21 - A deeper UEFI dive into Moo | 2 | 3 | 1 | 2 | 1 | 0.333 | 0.500 | 0.400 | -0.500 | 7.811 |
| 428fd94c-4beb-4216-9997-9b9aaf872b21 | Threat Analysis: Active C2 Discovery Usi | 5 | 6 | 3 | 3 | 2 | 0.500 | 0.600 | 0.545 | -0.429 | 6.848 |
| 43cd6667-c47f-4b9c-a2be-acc4d152d63d |  | 0 | 1 | 0 | 1 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 2.356 |
| ca2af944-50d1-451f-b2f1-07b599d43b73 | Waterbear Returns, Uses API Hooking to E | 21 | 22 | 19 | 3 | 2 | 0.864 | 0.905 | 0.884 | -0.111 | 30.135 |
| 881ef0cf-5e33-418f-96ce-f36b5e5525dd | 2021-04-12 - A chat with DarkSide | 0 | 6 | 0 | 6 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 6.753 |
| c266b9cf-17a6-4cfc-b6a2-c5544aa8bf9b | Daxin Backdoor: In-Depth Analysis, Part  | 7 | 0 | 0 | 0 | 7 | 0.000 | 0.000 | 0.000 | 0.000 | 6.954 |
| c58b4df0-ab21-460e-adbf-23c5c8b30ccd | FBI seize BreachForums hacking forum use | 3 | 8 | 1 | 7 | 2 | 0.125 | 0.333 | 0.182 | -0.452 | 11.303 |
| a5d54f81-2d95-4598-9ea7-8648c79c0e06 | 2019-05-02 - Detricking TrickBot Loader | 27 | 49 | 17 | 32 | 10 | 0.347 | 0.630 | 0.447 | -0.348 | 42.991 |
| 9fcc0e30-0309-40cc-be0e-424d0185f335 | Parrot TDS takes over web servers and th | 11 | 5 | 2 | 3 | 9 | 0.400 | 0.182 | 0.250 | -0.474 | 6.793 |
| 198f65d2-3283-460b-84bc-0394d7cbbb0e | DanaBot: A New Banking Trojan Targeting  | 24 | 19 | 13 | 6 | 11 | 0.684 | 0.542 | 0.605 | -0.349 | 25.900 |
| 37cabd68-a29c-4e5a-9020-9f8468a21fe4 | Rorschach – A New Sophisticated and Fast | 5 | 7 | 3 | 4 | 2 | 0.429 | 0.600 | 0.500 | -0.421 | 9.703 |
| 226d6c53-ef8e-455b-bb6f-48058bf96635 | 2014-05-13 - Cat Scratch Fever- CrowdStr | 3 | 9 | 2 | 7 | 1 | 0.222 | 0.667 | 0.333 | -0.212 | 8.776 |
| 5ffd1c8b-ea76-4a97-959a-8a6601dd0f73 | 2021-10-21 - Cobalt Strike- Using Known  | 0 | 2 | 0 | 2 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 2.806 |
| 64b77888-2d30-48e2-80c2-6b0b9a254db5 | 2020-12-15 - Removing Coordinated Inauth | 0 | 2 | 0 | 2 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 5.438 |
| e4fec4d0-8262-4692-9866-4c09652b652a | 2020-12-22 - Leftover Lunch- Finding, Hu | 19 | 46 | 13 | 33 | 6 | 0.283 | 0.684 | 0.400 | -0.243 | 38.991 |
| d43f68c1-fcde-4481-92f9-920a2509a249 | CVE-2022-23812 | RIAEvangelist/node-ipc  | 12 | 3 | 2 | 1 | 10 | 0.667 | 0.167 | 0.267 | -0.163 | 6.902 |
| 3b452297-cd55-4743-b1f7-741f558a30c8 | 2022-04-14 - Orion Threat Alert- Flight  | 15 | 32 | 12 | 20 | 3 | 0.375 | 0.800 | 0.511 | -0.175 | 31.993 |
| d0d69f14-ce3e-4069-a77a-c3f4661dc1df | VERMIN: Quasar RAT and Custom Malware Us | 59 | 64 | 41 | 23 | 18 | 0.641 | 0.695 | 0.667 | -0.327 | 67.143 |
| e0f1ad2e-49e3-4f62-8c33-9754426b1b27 | Blackhole Ramnit - samples and analysis | 37 | 18 | 10 | 8 | 24 | 0.556 | 0.294 | 0.385 | -0.400 | 18.672 |
| a9b8e5c7-a287-40f9-bf3a-1e188b94cee5 | Important Detection and Remediation Acti | 2 | 2 | 0 | 2 | 2 | 0.000 | 0.000 | 0.000 | -1.000 | 2.989 |
| 79a42502-2174-4138-9838-715426a8e449 | Some notes on IoCs | 2 | 1 | 1 | 0 | 1 | 1.000 | 0.500 | 0.667 | 0.000 | 2.091 |
| 09ce4b89-5222-457d-a887-4595d636644b | 2017-10-05 - FreeMilk- A Highly Targeted | 20 | 33 | 20 | 13 | 0 | 0.606 | 1.000 | 0.755 | 0.000 | 33.809 |
| c91d14a0-dd48-4b5c-92e5-c602bde66e1c | ZIP files, make it bigger to avoid EDR d | 3 | 2 | 1 | 1 | 2 | 0.500 | 0.333 | 0.400 | -0.500 | 3.316 |
| 94486493-db69-494a-9eba-157c17bc0127 | Research, News, and Perspectives | 2 | 4 | 0 | 4 | 2 | 0.000 | 0.000 | 0.000 | -0.800 | 4.283 |
| 4c375f8c-a405-4927-930c-97fdfd69e972 | 2021-11-18 - Two Iranian Nationals Charg | 0 | 4 | 0 | 4 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 4.807 |
| 2dd4dea5-a859-4ba4-b25c-ce158e084017 | 2020-11-18 - Business as usual- Criminal | 8 | 12 | 8 | 4 | 0 | 0.667 | 1.000 | 0.800 | 0.000 | 16.469 |
| 283b3f32-ea0a-4e05-b871-556307952612 | Cloud Security - Palo Alto Networks Blog | 2 | 0 | 0 | 0 | 2 | 0.000 | 0.000 | 0.000 | 0.000 | 3.168 |
| e60bcd10-a59d-4e73-8764-e5eb716bced7 | 2022-12-20 - Lazarus APT’s Operation Int | 1 | 5 | 1 | 4 | 0 | 0.200 | 1.000 | 0.333 | 0.000 | 6.145 |
| 114744a5-256d-45fc-b95c-bb0b68619145 | 2020-05-04 - ATM malware targets Wincor  | 4 | 2 | 2 | 0 | 2 | 1.000 | 0.500 | 0.667 | 0.000 | 4.239 |
| 00414a04-1453-42cd-ae50-42c2a761b837 | SoumniBot: the new Android banker’s uniq | 6 | 4 | 4 | 0 | 2 | 1.000 | 0.667 | 0.800 | 0.000 | 6.835 |
| eda4d990-63ba-47a8-90fc-1cbcea0f8d06 | Windows PWDUMP tools | 2 | 1 | 0 | 1 | 2 | 0.000 | 0.000 | 0.000 | -0.800 | 3.005 |

## Deviations

### LLM-only values (what the regexes missed), top 50

| id | type | value |
|---|---|---|
| 8e804b2b | domain | blogspot.com |
| 8e804b2b | filename | 29.html |
| 8e804b2b | filename | blog-page.html |
| 8e804b2b | filename | urGHE2PF |
| 8e804b2b | malware-type | Revenge RAT |
| 540efc3c | domain | client.gnisoft.com |
| 540efc3c | domain | n8.ahnlabinc.com |
| 540efc3c | domain | nmn.nhndesk.com |
| 540efc3c | domain | owa.ahnlabinc.com |
| 540efc3c | domain | ssl.lcrest.com |
| 540efc3c | domain | ssl2.ahnlabinc.com |
| 540efc3c | domain | ssl2.dyn-tracker.com |
| 540efc3c | domain | www2.dyn.tracker.com |
| 540efc3c | filename | %SYSTEM32%\spool\prtprocs\x64\B0SDFUWEkNCj.log |
| 540efc3c | filename | %SYSTEM32%\spool\prtprocs\x64\D8JNCKS0DJE |
| 540efc3c | filename | %SYSTEM32%\spool\prtprocs\x64\DEment.dll |
| 540efc3c | filename | %SYSTEM32%\spool\prtprocs\x64\EntAppsvc.dll |
| 540efc3c | filename | %SYSTEM32%\spool\prtprocs\x64\Interactive.dll |
| 540efc3c | filename | %SYSTEM32%\spool\prtprocs\x64\JSONDIU7c9djE |
| 540efc3c | filename | %SYSTEM32%\spool\prtprocs\x64\K9ds0fhNCisdjf |
| 540efc3c | filename | %SYSTEM32%\spool\prtprocs\x64\License.hwp |
| 540efc3c | filename | %SYSTEM32%\spool\prtprocs\x64\NTFSSSE.log |
| 540efc3c | filename | %SYSTEM32%\spool\prtprocs\x64\banner.bmp |
| 540efc3c | filename | %SYSTEM32%\spool\prtprocs\x64\certificate.cert |
| 540efc3c | filename | 100.exe |
| 540efc3c | filename | 103.exe |
| 540efc3c | filename | AceHash64.exe |
| 540efc3c | filename | Slack.exe |
| 540efc3c | filename | mz64x.exe |
| 540efc3c | filename | setup.exe |
| 540efc3c | malware-type | PipeMon |
| 540efc3c | named pipe | \\.\pipe\CMDPipeRead |
| 540efc3c | named pipe | \\.\pipe\CMDPipeWrite |
| 540efc3c | named pipe | \\.\pipe\ComHeatPipeRead%B64_TIMESTAMP% |
| 540efc3c | named pipe | \\.\pipe\FilePipeRead%B64_TIMESTAMP% |
| 540efc3c | named pipe | \\.\pipe\FilePipeWrite%B64_TIMESTAMP% |
| 540efc3c | named pipe | \\.\pipe\InCmdPipeRead%B64_TIMESTAMP% |
| 540efc3c | named pipe | \\.\pipe\InCmdPipeWrite%B64_TIMESTAMP% |
| 540efc3c | named pipe | \\.\pipe\MainHeatPipeRead%B64_TIMESTAMP% |
| 540efc3c | named pipe | \\.\pipe\MainPipeRead%B64_TIMESTAMP% |
| 540efc3c | named pipe | \\.\pipe\MainPipeWrite%B64_TIMESTAMP% |
| 540efc3c | named pipe | \\.\pipe\RoutePipeWriite%B64_TIMESTAMP% |
| 540efc3c | named pipe | \\.\pipe\ScreenPipeRead%CNC_DEFINED% |
| 540efc3c | named pipe | \\.\pipe\ScreenPipeWrite%CNC_DEFINED% |
| 540efc3c | regkey | HKLM\SOFTWARE\Microsoft\Print\Components\A66F35-4164-45FF-9CB4-69ACAA10E52D |
| 540efc3c | regkey | HKLM\SOFTWARE\Microsoft\Print\Components\DC20FD7E-4B1B-4B88-8172-61F0BED7D9E8 |
| 540efc3c | regkey | HKLM\SYSTEM\ControlSet001\Control\Print\Environments\Windows x64\Print Processors\PrintFiiterPipelineSvc\Driver |
| 540efc3c | regkey | HKLM\SYSTEM\CurrentControlSet\Control\Print\Environments\Windows x64\Print Processors\lltdsvc1\Driver |
| d27118be | domain | dopingagency.com |
| d27118be | domain | mail.dopingagency.com |

### Classic-only values (what the LLM left out), first 10 per type

reporter-domain: 112, other: 369 (of 481 classic-only values)

| id | type | value | flag |
|---|---|---|---|
| 8e804b2b | domain | web.archive.org | reporter-domain |
| 8cb9ac5c | domain | www.elastic.co | reporter-domain |
| c9acfc88 | domain | intel471.com |  |
| c9acfc88 | domain | socprime.com |  |
| c9acfc88 | domain | www.aldeid.com |  |
| c9acfc88 | domain | www.bleepingcomputer.com |  |
| c9acfc88 | domain | www.trendmicro.com |  |
| d256214e | domain | get.adobe.com |  |
| 45f70928 | domain | www.threatexpert.com |  |
| 45f70928 | domain | www.virustotal.com |  |
| 540efc3c | email | threatintel@eset.com |  |
| 8cb9ac5c | email | report@ncscc.gov.ua |  |
| 6eeb84e3 | email | malware-traffic-analysis.net |  |
| fbb37538 | email | connect@censys.com | reporter-domain |
| e0234eb8 | email | 183.9.25.156 |  |
| 226d6c53 | email | intelligence@crowdstrike.com |  |
| d0d69f14 | email | jcortes@paloaltonetworks.com |  |
| e0f1ad2e | email | contact@privacyprotect.org |  |
| 540efc3c | ip-dst | 0.0.0.0 |  |
| 540efc3c | ip-dst | 1.1.1.4 |  |
| 540efc3c | ip-dst | 1.1.1.5 |  |
| 8cb9ac5c | ip-dst | 111.111.111.111 |  |
| d256214e | ip-dst | 176.9.0.0 |  |
| d256214e | ip-dst | 213.200.0.0 |  |
| d256214e | ip-dst | 45.77.52.0 |  |
| 082d3389 | ip-dst | 112.0.0.0 |  |
| c191576a | ip-dst | 192.168.3.201 |  |
| 93f7b554 | ip-dst | 112.213.98.44 |  |
| 78d08d87 | md5 | 0CE1241A44557AA438F27BC6D4ACA246 |  |
| 78d08d87 | md5 | C3A9B30B6A313F289297C9A36730DB6D |  |
| 10524cc8 | md5 | 5e31d16d6bf35ea117d6d2c4d42ea879 |  |
| be97537d | md5 | 2567a2bca964504709820de7052d3486 |  |
| d43f68c1 | md5 | ae511e1627824a968aaaa758a5309154 |  |
| d43f68c1 | md5 | f7ae3457420af78a54b38a31cc0c809c |  |
| 540efc3c | sha1 | 6c97039605f93ccf1afccbab8174d26a43f91b20 |  |
| 540efc3c | sha1 | 7ca43f3612db0891b2c4c8ccab1543f581d0d10c |  |
| 540efc3c | sha1 | 97da4f938166007ce365c29e1d685a1b850c5bb0 |  |
| 540efc3c | sha1 | b02ad3e8b1cf0b78ad9239374d535a0ac57bf27e |  |
| f9158c72 | sha1 | 023e6c7730445db2b4c777b5d9b612e902dc7f72 |  |
| f9158c72 | sha1 | 43ea33bedadc9bfc92c570b316b78b6fd9787f09 |  |
| f9158c72 | sha1 | 44561e474bda129379d87750f49fd57a5d378f91 |  |
| f9158c72 | sha1 | f46c445f912c6d1224e22f9e6a76020d594888b9 |  |
| f9158c72 | sha1 | ffadbc944a2976982e1daf0b715478e6062c9488 |  |
| d72a26f9 | sha1 | 6920f726d74efb7836a03d3acfc0f23af196765e |  |
| 59058517 | sha256 | 0db46fea5a0be8624069f978f115e4270833df29ed776c712182327a758fd639 |  |
| 59058517 | sha256 | 6d65804ca8f71e21b18de08176a53d8f203bc23629dd822ef3c0da217f95f119 |  |
| e0f1ad2e | sha256 | a40aacca731c142148733786cae64d45df2e740e3fb744ffc513d251ec121cf7 |  |
| e0f1ad2e | sha256 | c1293f8dd8a243391d087742fc22c99b8263f70c6937f784c15e9e20252b38ae |  |
| e0f1ad2e | sha256 | f52bfac9637aea189ec918d05113c36f5bcf580f3c0de8a934fe3438107d3f0c |  |
| 8e804b2b | url | https://web.archive.org/web/20200428173819/https://cofense.com/upgrades-delivery-support-infrastructure-revenge-rat-malware-bigg | reporter-domain |

### Not actionable per the model (to_ids lowered; for human review)

| id | type | value |
|---|---|---|
| 45f70928 | url | http://www.threatexpert.com/report.aspx?md5=2ded7ee112cea2db509ba95dc09fded6 |
| cc13367a | url | https://blog.fox-it.com/2020/01/15/hunting-for-beacons/ |
| cc13367a | url | https://en.wikipedia.org/wiki/Standard_deviation |
| cc13367a | url | https://mergene.medium.com/enterprise-scale-threat-hunting-network-beacon-detection-with-unsupervised-machine-learning-and-277c4c30304f |
| cc13367a | url | https://www.activecountermeasures.com/threat-hunting-simplifying-the-beacon-analysis-process/ |
| 4e697d2e | url | https://krebsonsecurity.com/2013/10/adobe-to-announce-source-code-customer-data-breach/ |
| 53d99aad | domain | www.paypal.com |
| 6970d678 | email-dst | support@us.yokogawa.com |
| a5d54f81 | filename | ALMon.exe |
| a5d54f81 | filename | ALsvc.exe |
| a5d54f81 | filename | Clean.exe |
| a5d54f81 | filename | MSASCui.exe |
| a5d54f81 | filename | MSASCuiL.exe |
| a5d54f81 | filename | MsMpEng.exe |
| a5d54f81 | filename | SAVAdminService.exe |
| a5d54f81 | filename | SavService.exe |
| a5d54f81 | filename | SbieDll.dll |
| a5d54f81 | filename | Sf2.dll |
| a5d54f81 | filename | SophosFS.exe |
| a5d54f81 | filename | SxIn.dll |
| a5d54f81 | filename | api_log.dll |
| a5d54f81 | filename | cmdvrt32.dll |
| a5d54f81 | filename | dbghelp.dll |
| a5d54f81 | filename | dir_watch.dll |
| a5d54f81 | filename | pstorec.dll |
| a5d54f81 | filename | snxhk.dll |
| a5d54f81 | filename | vmcheck.dll |
| a5d54f81 | filename | wpespy.dll |
| 9fcc0e30 | email | ti@avast.com |
| 9fcc0e30 | url | https://github.com/avast/ioc/tree/master/ParrotTDS |
| 5ffd1c8b | filename | 1768.py |
| e0f1ad2e | domain | amberfreda.com |
| e0f1ad2e | hostname | p3nlhg49c090.shr.prod.phx3.secureserver.net |
| e0f1ad2e | ip-dst | 173.201.97.1 |
| 79a42502 | url | https://blog.erratasec.com/2016/12/some-notes-on-iocs.html |

### LLM rejection reasons (summed over reports)

| reason | count |
|---|---|
| format | 56 |
| confidence | 26 |
| free-text-type | 23 |
| not-in-source | 17 |
| duplicate | 11 |
| quote-mismatch | 1 |

## Gold view (3 hand-labelled reports)

Universe = classic ∪ llm ∪ gold per report, so tn, specificity and accuracy are meaningful.

| report | pair | tp | fp | fn | tn | precision | recall | specificity | accuracy | f1 | jaccard | kappa |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 10a94632 | llm vs gold | 0 | 0 | 0 | 4 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| 10a94632 | classic vs gold | 0 | 4 | 0 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 59ed4725 | llm vs gold | 17 | 0 | 2 | 52 | 1.000 | 0.895 | 1.000 | 0.972 | 0.944 | 0.895 | 0.926 |
| 59ed4725 | classic vs gold | 6 | 52 | 13 | 0 | 0.103 | 0.316 | 0.000 | 0.085 | 0.156 | 0.085 | -0.414 |
| orkl-sam | llm vs gold | 16 | 0 | 1 | 3 | 1.000 | 0.941 | 1.000 | 0.950 | 0.970 | 0.941 | 0.828 |
| orkl-sam | classic vs gold | 12 | 3 | 5 | 0 | 0.800 | 0.706 | 0.000 | 0.600 | 0.750 | 0.600 | -0.231 |
| micro | llm vs gold | 33 | 0 | 3 | 59 | 1.000 | 0.917 | 1.000 | 0.968 | 0.957 | 0.917 | 0.932 |
| micro | classic vs gold | 18 | 59 | 18 | 0 | 0.234 | 0.500 | 0.000 | 0.189 | 0.319 | 0.189 | -0.409 |

### Cohen's kappa

| report | LLM–gold | classic–gold | LLM–classic |
|---|---|---|---|
| 10a94632 | 1.000 | 0.000 | 0.000 |
| 59ed4725 | 0.926 | -0.414 | -0.376 |
| orkl-sam | 0.828 | -0.231 | 0.000 |

## Reproduce

```bash
python -m benchmarks.orkl --n 100 --seed 42
python -m genai.classic benchmarks/data/orkl/*.json -o benchmarks/results
python -m benchmarks.run_llm
python -m benchmarks.compare --data-dir benchmarks/data/orkl --results-dir benchmarks/results-v4 --out docs/BENCHMARKS_extraction.md --csv benchmarks/results/extraction.csv
```
