---
source: https://docs.getsemantica.ai/learning-more
title: Learning More - Semantica
---

# Learning More - Semantica

Whether you’re running your first pipeline or deploying Semantica in production, this page gives you a structured path forward: from beginner to enterprise-grade usage.

##  Learning Paths

* **Beginner (1–2 hrs)**: new to Semantica and knowledge graphs. [Start with Installation →](/installation)
* **Intermediate (4–6 hrs)**: comfortable with basics, building real applications. [Start with Modules →](/modules)
* **Advanced (8+ hrs)**: enterprise deployments, customization, and extension. [Start with Architecture →](/architecture)

* Beginner (1–2 hrs)
* Intermediate (4–6 hrs)
* Advanced (8+ hrs)

New to Semantica and knowledge graphs. No prior graph database experience required.

1

Set up your environment

[Installation Guide](/installation): virtual environments, optional extras, platform-specific fixes.

2

Understand the core ideas

[Core Concepts](/concepts): what knowledge graphs are, how embeddings work, what extraction does.

3

Run your first example

[Getting Started](/getting-started): 5-minute code walkthrough with pattern-based extraction (no API key needed).

4

Build your first knowledge graph

[Quickstart Tutorial](/quickstart): full 6-step pipeline from ingestion to visualization.

5

Explore interactively

[Welcome to Semantica notebook](https://github.com/semantica-agi/semantica/blob/main/cookbook/introduction/01_Welcome_to_Semantica.ipynb): Jupyter walkthrough of every module.

Comfortable with the basics, building real applications. Assumes you’ve completed the Beginner path.

1

Learn every module

[Modules Guide](/modules): all 27 modules with code examples and common pipeline chains.

2

Build production knowledge graphs

[Building Knowledge Graphs notebook](https://github.com/semantica-agi/semantica/blob/main/cookbook/introduction/07_Building_Knowledge_Graphs.ipynb): multi-source, deduplication, conflict resolution.

3

Add semantic search

[Embedding Generation notebook](https://github.com/semantica-agi/semantica/blob/main/cookbook/introduction/12_Embedding_Generation.ipynb): generating embeddings, provider and model switching, dimensions. Then [Vector Store notebook](https://github.com/semantica-agi/semantica/blob/main/cookbook/introduction/13_Vector_Store.ipynb): storing and searching vectors for retrieval.

4

Multi-source integration

[Multi-Source Data Integration notebook](https://github.com/semantica-agi/semantica/blob/main/cookbook/advanced/06_Multi_Source_Data_Integration.ipynb) for multi-source patterns.

Enterprise deployments, customization, and extension. Assumes production usage experience.

1

Understand the architecture

[Architecture Guide](/architecture): four-layer design, extension points, and design decisions.

2

Temporal intelligence

[Temporal Graphs notebook](https://github.com/semantica-agi/semantica/blob/main/cookbook/advanced/10_Temporal_Knowledge_Graphs.ipynb): `valid_from`/`valid_until`, Allen interval algebra, point-in-time queries.

3

Ontology-driven knowledge bases

[Ontology notebook](https://github.com/semantica-agi/semantica/blob/main/cookbook/introduction/14_Ontology.ipynb): auto-generation, SHACL validation, Ontology Hub.

4

Advanced visualization

[Complete Visualization Suite notebook](https://github.com/semantica-agi/semantica/blob/main/cookbook/advanced/03_Complete_Visualization_Suite.ipynb): UMAP, t-SNE, community layouts, embedding projections.

5

Enterprise export

[Multi-Format Export notebook](https://github.com/semantica-agi/semantica/blob/main/cookbook/advanced/05_Multi_Format_Export.ipynb): RDF with PROV-O, Parquet, Neo4j Cypher, Arrow, OWL.

##  Configuration Reference

All settings can be overridden with environment variables: no code changes needed.

| Setting | Environment Variable | Default |
| --- | --- | --- |
| OpenAI API Key | `OPENAI_API_KEY` | `None` |
| Groq API Key | `GROQ_API_KEY` | `None` |
| Anthropic API Key | `ANTHROPIC_API_KEY` | `None` |
| Graph Store Backend | `GRAPH_STORE_DEFAULT_BACKEND` | `"neo4j"` |
| Vector Store Backend | `VECTOR_STORE_DEFAULT_BACKEND` | `"faiss"` |
| Server Host | `SEMANTICA_HOST` | `"127.0.0.1"` |
| Server API Key | `SEMANTICA_API_KEY` | `None` |

##  Troubleshooting

ModuleNotFoundError: No module named 'semantica'

Verify installation and that the correct Python environment is active:

```
pip list | grep semantica
pip install --upgrade semantica
```

For optional features, install the relevant extra:

```
pip install "semantica[llm-openai]"   # OpenAI provider
pip install "semantica[gpu]"          # GPU acceleration
```

AuthenticationError

Set your API key as an environment variable (never hardcode keys in source files):

```
export OPENAI_API_KEY="sk-..."
export GROQ_API_KEY="gsk_..."
```

MemoryError or OOM crashes

Switch from the default in-memory NetworkX backend to a persistent graph database:

```
from semantica.graph_store import FalkorDBStore
from semantica.kg import GraphBuilder

store   = FalkorDBStore(host="localhost", port=6379)
builder = GraphBuilder(merge_entities=True, graph_store=store)
```

Also reduce batch sizes and enable streaming ingestion for large corpora.

Slow processing on large datasets

Enable parallel execution and GPU acceleration:

```
from semantica.pipeline import ParallelismManager, Task

# Run pipeline tasks concurrently across worker threads
manager = ParallelismManager(max_workers=8)
tasks = [
    Task("task_1", lambda: "process part 1"),
    Task("task_2", lambda: "process part 2"),
]
results = manager.execute_parallel(tasks)
```

```
pip install "semantica[gpu]"  # CUDA-backed embeddings
```

Windows [all] installation fails

Upgrade to the latest release:

```
pip install --upgrade semantica
```

Or install extras individually: `pip install semantica`, then add `[llm-openai]`, `[gpu]`, etc. as needed.

cp1252 encoding crash on Windows

Set the encoding environment variable:

```
set PYTHONIOENCODING=utf-8
```

##  Performance Optimization

Backend selection: development vs. production

| Operation | NetworkX (default) | Neo4j / FalkorDB |
| --- | --- | --- |
| Graph construction | Fast | Moderate |
| Query performance | Moderate | Fast |
| Scalability | In-memory only | Persistent, production-scale |
| Recommended for | Development, small graphs | Production, large corpora |

Use NetworkX for local development and prototyping. Switch to a persistent backend before deploying to production.

Batch processing for large corpora

Process documents in batches rather than one at a time. Split large texts into chunks and extract entities in batches:

```
from semantica.split import TextSplitter
from semantica.semantic_extract import NERExtractor

document_text = "Acme Corp announced record revenue in Seattle. CEO Jane Doe presented results."
splitter = TextSplitter(chunk_size=1000, chunk_overlap=100)
chunks = splitter.split(document_text)

extractor = NERExtractor()
batch_entities = extractor.extract_entities_batch([c.text for c in chunks])
```

Deduplication v2: up to 7× faster

If deduplication is a bottleneck, use candidate blocking to reduce O(n²) comparisons before similarity scoring:

```
from semantica.deduplication import DuplicateDetector, EntityMerger

entities = [
    {"id": "1", "name": "Acme Corp", "type": "Company"},
    {"id": "2", "name": "Acme Corporation", "type": "Company"},
    {"id": "3", "name": "Globex", "type": "Company"},
]

# Fast candidate blocking for large entity sets
detector = DuplicateDetector(similarity_threshold=0.8)
duplicates = detector.detect_duplicates(entities, candidate_strategy="blocking_v2")

merger = EntityMerger()
merged = merger.merge_duplicates(entities, strategy="keep_most_complete")
```

The `blocking_v2` and `hybrid_v2` candidate strategies filter candidate pairs before calculating fine-grained similarity.

##  Security Best Practices

* **API keys**: store in environment variables or a secrets manager; never commit them to version control; rotate on a schedule
* **Sensitive data**: use local embedding models (Ollama, HuggingFace) for PII or classified content; avoid sending sensitive data to external APIs without data handling agreements
* **Graph exports**: encrypt sensitive exports at rest; use SSRF-safe `base_url` validation when configuring custom LLM gateways
* **XML ingestion**: always use `XMLIngestor`, which uses the XXE-safe lxml backend; never parse untrusted XML with the standard library parser
* [Cookbook](/cookbook): interactive Jupyter notebooks from beginner to advanced.
* [FAQ](/faq): common questions answered.
* [API Reference](/reference/core): complete technical documentation.
