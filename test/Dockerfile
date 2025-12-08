FROM python:3.12-slim

# Install git and curl (needed for uv installer)
RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*

# Install prek
RUN pip install prek

WORKDIR /app

# Copy the hook package
COPY . /hook

# Create a test project
RUN git init && \
    git config user.email "test@test.com" && \
    git config user.name "Test"

# Create pre-commit config that uses the local hook
RUN cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: local
    hooks:
      - id: ensure-uv
        name: Ensure uv is installed
        entry: python /hook/packages/ensure_uv/main.py
        language: system
        always_run: true
        pass_filenames: false

      - id: test-uv
        name: Test uv is available
        entry: uv --version
        language: system
        always_run: true
        pass_filenames: false
EOF

# Create a dummy file to commit
RUN echo "test" > test.txt && git add .

CMD ["prek", "run", "--all-files"]
