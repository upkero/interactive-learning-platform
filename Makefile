.PHONY: gen-api

gen-api:
	cd backend && AUTH_JWT_SECRET="$${AUTH_JWT_SECRET:-openapi-schema-only-secret-not-for-production}" uv run python -m src.cli export-openapi
