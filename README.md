# Sporting Risk Data Widget Prototype

Prototype of a football data widget built with a Tornado backend, vanilla JavaScript frontend, and a standalone configurator for theme overrides. The project is structured so the backend can later swap mock JSON for live data sources without changing the widget contract.

## Prerequisites

- Docker with Docker Compose support
- Python 3.11
- `uv` for local Python workflow

## Quickstart

### Docker Compose

From the project root:

```bash
docker compose up --build
```

If your WSL user does not yet have Docker socket access, you may need:

```bash
sudo docker compose up --build
```

The app will be available on port `8080`.

### Local `uv` workflow

Create or refresh the environment:

```bash
uv sync --all-groups
```

Run the backend locally:

```bash
uv run python backend/server.py
```

Run backend smoke tests:

```bash
uv run python -m unittest discover -s tests -p 'test_api_smoke.py'
```

## URL Index

- `/example` - example operator page with the embedded widget and dev phase toggles
- `/config` - standalone configurator with live preview and generated CSS overrides
- `/api/health` - health endpoint for local checks and container health probes

## Project Layout

- `backend/` - Tornado application, request handlers, mock data, and container image
- `frontend/` - embeddable widget loader, container shell, renderers, styles, and example page
- `configurator/` - theming tool for generating CSS variable overrides
- `tests/` - API smoke tests and browser smoke scaffolding

## Architecture Summary

### Why Tornado

Tornado fits the widget backend well because the API is I/O-oriented, small, and phase-aware. Its async request handling keeps the server responsive while we simulate or later replace mock JSON reads with real upstream calls, caches, or data services.

### Why vanilla JavaScript

The widget is intended to be embedded into third-party pages with minimal integration cost. Vanilla JavaScript keeps the payload simple, avoids framework coupling, and makes the widget easier to drop into operator environments that may already have their own frontend stack.

### Why CSS variables instead of Shadow DOM

CSS custom properties let the widget stay themeable from the host page and from the configurator without needing a compile step. That is a better fit for an embeddable betting/media widget than strict style isolation, because operators usually want branding control more than hard encapsulation.

## Development Notes

- The example page at `/example` includes force-phase buttons for local demo behavior.
- The backend serves frontend assets from `/static/*`.
- The current API uses mock JSON under `backend/mock_data/`, loaded through async handlers so the contract stays stable while the data source evolves.

## AWS Deployment Note

For a production-shaped deployment, the API layer maps cleanly to ECS Fargate, static widget assets can be distributed through CloudFront, and a Redis cache layer on ElastiCache would be the natural place to absorb hot reads and short-lived match state lookups.
