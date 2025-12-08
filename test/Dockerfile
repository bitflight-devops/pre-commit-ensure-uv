FROM python:3.12-slim

# Build argument to select which runner invokes hooks (prek or pre-commit)
ARG RUNNER=prek

# Install git and curl (needed for uv installer)
RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*

# Install both runners to test runner detection
RUN pip install prek pre-commit

WORKDIR /app

# Copy the hook package
COPY . /hook

# Install the hook package
RUN pip install /hook

# Create a test project
RUN git init && \
    git config user.email "test@test.com" && \
    git config user.name "Test"

# Create pre-commit config that uses the installed hook
RUN cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: local
    hooks:
      - id: ensure-uv
        name: Ensure uv is installed
        entry: ensure-uv
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

# Use the selected runner
CMD ${RUNNER} run --all-files
