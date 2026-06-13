#!/usr/bin/env python3
"""
deploy.py — Publica channels.json no GitHub automaticamente após o scan.

Pré-requisitos:
  pip install aiohttp PyGithub

Configuração (uma vez só):
  export GITHUB_TOKEN=ghp_seutoken
  export GITHUB_REPO=seunome/onyxtv-channels   # repo que você criar

O repo precisa ter um arquivo channels.json inicial (pode ser vazio: {}).
"""

import os
import json
import sys
from pathlib import Path

try:
    from github import Github
except ImportError:
    print("❌ Instale: pip install PyGithub")
    sys.exit(1)

OUTPUT_JSON = Path(__file__).parent / "channels.json"
GITHUB_FILE = "channels.json"  # caminho dentro do repo


def deploy():
    token = os.environ.get("GITHUB_TOKEN")
    repo_name = os.environ.get("GITHUB_REPO")

    if not token:
        print("❌ Defina a variável GITHUB_TOKEN")
        print("   export GITHUB_TOKEN=ghp_seutoken")
        sys.exit(1)

    if not repo_name:
        print("❌ Defina a variável GITHUB_REPO")
        print("   export GITHUB_REPO=seunome/onyxtv-channels")
        sys.exit(1)

    if not OUTPUT_JSON.exists():
        print("❌ channels.json não encontrado. Rode scanner.py primeiro.")
        sys.exit(1)

    content = OUTPUT_JSON.read_text()
    data = json.loads(content)
    version = data.get("version", "?")

    print(f"📤 Publicando channels.json v{version} → {repo_name}...")

    g = Github(token)
    repo = g.get_repo(repo_name)

    try:
        existing = repo.get_contents(GITHUB_FILE)
        repo.update_file(
            path=GITHUB_FILE,
            message=f"chore: update channels v{version} ({data['stats']['online']} online)",
            content=content,
            sha=existing.sha,
        )
        print(f"✅ Atualizado! {data['stats']['online']}/{data['stats']['total']} canais online")
    except Exception as e:
        if "404" in str(e):
            repo.create_file(
                path=GITHUB_FILE,
                message=f"feat: initial channels v{version}",
                content=content,
            )
            print("✅ Arquivo criado no repo!")
        else:
            print(f"❌ Erro ao publicar: {e}")
            sys.exit(1)

    raw_url = f"https://raw.githubusercontent.com/{repo_name}/main/{GITHUB_FILE}"
    print(f"\n🌐 URL do JSON (para o app Roku):")
    print(f"   {raw_url}")


if __name__ == "__main__":
    deploy()
