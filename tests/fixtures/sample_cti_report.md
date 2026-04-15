# Incident Report

Analysts observed a phishing campaign targeting finance staff with messages themed around invoice reviews. The lure delivered a password-protected archive containing a malicious JavaScript downloader. The downloader contacted `hxxps://updates-example[.]com/api/sync` and retrieved a second-stage payload that established persistence through a scheduled task. Investigators contained the affected workstation within thirty minutes and blocked the domain at the proxy. No evidence of lateral movement was found during the initial triage window.
