---
name: clawos-rag
description: Query ClawOS project documents with citations. Use when the user asks about
  documents, files, PDFs, reports, contracts, or anything that might be in a project.
  Call rag_query with the user's question to get an answer with page citations.
version: 1.0.0
requires:
  bins: ["python3"]
---

# ClawOS RAG — Document Retrieval

## When to use this skill
- User asks about contents of a document, PDF, report, or file
- User asks "what does the contract say", "find in the docs", "according to my notes"
- User asks about a project's details and project documents have been uploaded

## How to use

Run the query script:

```bash
python3 {baseDir}/rag_query.py "your question here"
```

The script returns a cited answer from indexed project documents.
The output includes source file names and page numbers in brackets like [budget.pdf p.4].

## Output format
Always include the citations in your response exactly as returned.
If no documents are indexed, inform the user they can upload documents with:
  nexus project upload <filename>
