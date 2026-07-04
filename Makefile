install:
	agents-cli install

playground:
	agents-cli playground

run:
	uv run uvicorn app.fast_api_app:app --host 127.0.0.1 --port 8000
