# Cortex-HQ

## Project overview

This project builds and explores a HydraDB knowledge graph from the EnterpriseRAG-Bench datasets. The main interactive entry point is the Streamlit explorer at `explorer/knowledge_explorer.py`.

## Running on Replit

The `Knowledge Explorer` workflow starts the Streamlit app on port 5000. It requires these Replit Secrets:

- `HYDRADB_API_KEY` — HydraDB access
- `GROQ_API_KEY` — LLM extraction

The extraction pipeline uses Groq model `llama-3.1-8b-instant` by default through `DEFAULT_GROQ_MODEL`. To run extraction manually:

```bash
python extraction/extract.py --provider groq
```

Use `schema/create_collection.py --collection <name>` to ensure a HydraDB collection exists before ingesting data. The explorer defaults to the `benchmark-eval` collection and lets you select another collection from the sidebar.

## User preferences

- Use the provided Groq API key for LLM work.
- Keep the default Groq model set to `llama-3.1-8b-instant`.