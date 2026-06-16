# Benchmarks

Benchmarks exist per use-case and per community profile.

**Note well**: there are different MISPs out there which focus on different aspects. Such as law enforcement, classical CERTs, drones, etc.
We will call this "community profile".

Within a community profile, we have at least three dimensions for evaluation:
- model
- prompt
- use-case


## Models
Make sure that we support a few different models (on-prem, SaaS) are supported and documented.
Initially we could focus on:

* qwen3.6
* gemma4
* DeepSeek-V4
* gpt-oss:120b (?)
* nemotron (nvidia)
* kimi k2.x
* mistral models (mixtral 8x22b, -large)


## Prompts

Depend on the use-case. 

Combined with prompts's parameters (temp., seed, etc.)

## Use-case 

See [USE-CASES.md](USE-CASES.md). 
We initially focus on these use-cases fore the benchmark:

1. story-telling based on the contents of the events (i.e on the graph). The task here is to generate a CTI report (in natural language) based on the attributes, event, objects
2. summarization of the CTI report
3. info extraction
4. NER / tagging
5. Quality review (which tags are missing, etc.) --> recommendation engine on what other *similar* events have w.r.t tags, attributes, etc.

