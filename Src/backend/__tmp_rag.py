from app.ports.retriever import rag_search
from app.config import settings


def main() -> None:
	payload = rag_search(
		settings.tenant_id,
		{"accessible_projects": ["PX", "PB", "global"], "tenant_id": settings.tenant_id},
		query="pricing strategy",
	)
	print(payload)


if __name__ == "__main__":
	main()
