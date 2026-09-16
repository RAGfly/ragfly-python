"""Basic RAGfly SDK example."""
from ragfly import RAGfly

client = RAGfly(api_key="rf_your_api_key")

print(client.ask("What are the Q1 sales figures?").answer)

results = client.search("maintenance contracts", limit=5)
print(f"\n{results.total_documents} documents found")
for doc in results.documents:
    print(f"  · {doc.name} (score: {doc.rrf_score or 0:.3f})")
    for chunk in doc.chunks[:1]:
        print(f'      "{chunk.text[:120]}…"')

for op in client.list_operations()["operations"][:5]:
    print(op["code"], op["kind"])
