FROM python:3.11-slim
RUN apt-get update && apt-get install -y tmux git curl
RUN curl -fsSL https://claude.ai/install.sh | sh
WORKDIR /workspace
CMD ["tmux", "new-session", "-s", "docker-agent", "-d", "claude", "--allow-dangerously-skip-permissions"]
