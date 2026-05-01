FROM node:20-bookworm-slim AS web-build

WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci
COPY web ./
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PORT=10000

COPY pyproject.toml README.md LICENSE requirements-web.txt ./
COPY aerosim6dof ./aerosim6dof
COPY examples ./examples
COPY docs ./docs
COPY scripts ./scripts
COPY --from=web-build /app/web/dist ./web/dist

RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -e ".[web]" \
  && mkdir -p outputs/web_runs

CMD ["sh", "-c", "python -m uvicorn aerosim6dof.web.api:app --host 0.0.0.0 --port ${PORT}"]
