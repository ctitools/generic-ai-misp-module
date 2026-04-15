# AIPITCH Kaplan 



## Usecases

There are different types of use-cases: those which use the AI MISP module (similar to enrichment modules), those that use MISP externally + AI features (such as RAG, MCP).

The following is a dump of use-case ideas we collected during the hackathon2026. 

Of course, this is just a start. We could re-visit the possible use-cases as well by going through the typical use-case categories of NLP:

* Text classification: spam detection, topic labeling, intent detection, sentiment analysis
* Named Entity Recognition (NER): finding people, companies, dates, locations, products
* Information extraction: pulling structured facts, relations, events, key fields from text
* Summarization: condensing documents, emails, articles, or meetings
* Question answering: answering questions from documents, FAQs, or knowledge bases
* Machine translation: translating between languages
* Text generation: drafting replies, reports, product descriptions, or creative text
* Semantic search / retrieval: Vector search, RAG, finding relevant documents by meaning, not just keywords
* Text similarity / matching: deduplication, paraphrase detection, semantic matching
* Topic modeling / clustering: grouping documents by theme
* Keyword / keyphrase extraction: finding the main concepts in text
* (probably less relevant) Sentiment and emotion analysis: detecting polarity, tone, or affect
* (probably less relevant) Intent detection: classifying what a user wants in chatbots or support flows
* Dialogue systems / chatbots: conversational assistants, support bots, virtual agents
* (probably less relevant) Natural language parsing: syntax, dependency parsing, grammatical structure
* (probably less relevant) Coreference resolution: linking pronouns and mentions to the same entity
* (probably less relevant) Text normalization / preprocessing: spelling correction, tokenization, lemmatization, cleanup
* (probably less relevant) Toxicity / moderation: detecting abusive, unsafe, or policy-violating content
* (probably less relevant) Document understanding: combining NLP with layout/forms/invoices/contracts
* (probably less relevant) Recommendation and personalization from text: using reviews, profiles, or queries to rank content

#### Long job 
**Video with QwenVL3.5 or similar analysis**
File size: large, could be 30GB video from HD security feed of large event

## Async/Sync 
- Sync: Requests from misp-core to misp-modules
- Sync: option 1 - Requests from misp-module to monolith AI service
- Sync: option 2 - Requests from misp-module to task manager of load balanced efereral container management 
- Requests from Task Manager to load balancer and container should 


### MISP tag proposal ML model

Idea: you have an event and you ask the AI Module to propose the best matching tags

### ML checker

The ML model can check pre-publishing of an event if all suggested best current practices were followed.
It can make proposals on what should still happen.

--> can be complicated and is highly dependent on the MISP community (what they use. For example disinformation versus GSMA community - totally different user groups).

We can however do it like this: 
- we do a checker module
- it comes with a user-prompt as *example*
- the example should be overwritten by the rules of the particular MISP community
- the prompt + rendered MISP event gets sent to the LLM



### summarization

There are different sub- use-cases for summarization

#### summary of the content of the incident (report)

summary of PDFs, reports etc. attached.

#### summary of the whole event for management / user
Testing the idea to have basic event info read to a user - either totally client-based using a template 
or supporting a locally running LLM. 
https://github.com/christianteuschel/MISP

### CTI info extraction
attributes/event metadata and tags extraction



### chatbot Marty Mc Fly (--> Merjouan)
Mattermost chat (username, channel_name, text, response_url)
Tools:
  - misp search

Uses fastMCP

### new idea: T-codes / TA clustering

An interesting experiment might be to cluster TAs (and all possible TA names associated with one event) by T-Codes as well as by other attributes. Pick one representative of the cluster as "canonical" TA name for the cluster.
New event + attributes comes in -> propose the most likely canoncical TA name which would fit this pattern.

Why? Because MARTI currently manually selects the TA name for every new report.

This might be helped by the existing TA canonical name mapping that CIRCL has: [link](https://misp-galaxy.org/threat-actor/) -> synonyms.


### Periodic/Quartelry reports improvements

We have MISP input data (+knowledge base + PDFs/text) for quarterly reports.
These will be pre-filtered/tagged in MISP so that we know which reports should go into the next stage.
We want to summarize the input data for a quarterly report. This then will be reviewed by analysts.
Add links to the knowledge base / MISP event so that the analyst can review the correctness of the summary.
(possibly make the summarization an agentic system which can check things for correctness).


### MISP MCP server

Install Andras' [MISP-mcp](https://github.com/MISP/MISP-mcp) and let it run against a local model.
Uses FastMCP.
Document it, make a tutorial on how run it with local LLMs

### MISP Search MCP server

Maybe the easiest is to do an "AI assisted search" on top of MISP is to use https://github.com/MISP/misp-workbench. 
(talk to Luciano). There are no issues with ACLs there. Also has opensearch for now.tlang

### Prompt template library

Collect and document
```
Use-case <-> model <-> prompt combinations which work.
```
