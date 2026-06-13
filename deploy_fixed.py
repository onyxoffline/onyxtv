#!/usr/bin/env python3
"""
deploy.py — Publica channels.json no GitHub.
Filtra para manter só canais online e limita a 500 canais (limite API GitHub = 1MB).
"""

import os, json, sys
from pathlib import Path

try:
    from github import Github
except ImportError:
    print("❌ Instale: pip install PyGithub")
    sys.exit(1)

OUTPUT_JSON = Path(__file__).parent / "channels.json"
GITHUB_FILE = "channels.json"
MAX_CHANNELS = 500  # limite seguro para caber em 1MB

def deploy():
    token     = os.environ.get("GITHUB_TOKEN")
    repo_name = os.environ.get("GITHUB_REPO")

    if not token or not repo_name:
        print("❌ Defina GITHUB_TOKEN e GITHUB_REPO")
        sys.exit(1)

    if not OUTPUT_JSON.exists():
        print("❌ channels.json não encontrado. Rode scanner.py primeiro.")
        sys.exit(1)

    data = json.loads(OUTPUT_JSON.read_text())

    # Filtra só online e limita quantidade
    all_ch  = data["channels"]
    online  = [c for c in all_ch if all_ch.index(c) < data["stats"]["online"]][:MAX_CHANNELS]

    # Reconstrói JSON enxuto
    payload = {
        "version": data["version"],
        "updated": data["updated"],
        "stats": {
            "total":   len(online),
            "online":  len(online),
            "offline": 0,
        },
        "channels": online,
    }

    content = json.dumps(payload, ensure_ascii=False, indent=2)
    size_kb = len(content.encode()) / 1024
    print(f"📦 JSON: {len(online)} canais, {size_kb:.1f} KB")

    if size_kb > 900:
        print("⚠️  Ainda muito grande, reduzindo para 300 canais...")
        online  = online[:300]
        payload["channels"] = online
        payload["stats"]["total"] = len(online)
        payload["stats"]["online"] = len(online)
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        print(f"📦 JSON reduzido: {len(online)} canais, {len(content.encode())/1024:.1f} KB")

    version = payload["version"]
    print(f"📤 Publicando v{version} → {repo_name}...")

    g    = Github(token)
    repo = g.get_repo(repo_name)

    try:
        existing = repo.get_contents(GITHUB_FILE)
        repo.update_file(
            path=GITHUB_FILE,
            message=f"chore: update channels v{version} ({len(online)} online)",
            content=content,
            sha=existing.sha,
        )
        print(f"✅ Atualizado! {len(online)} canais publicados")
    except Exception as e:
        if "404" in str(e):
            repo.create_file(
                path=GITHUB_FILE,
                message=f"feat: initial channels v{version}",
                content=content,
            )
            print("✅ Arquivo criado no repo!")
        else:
            print(f"❌ Erro: {e}")
            sys.exit(1)

    print(f"\n🌐 URL: https://raw.githubusercontent.com/{repo_name}/main/{GITHUB_FILE}")

if __name__ == "__main__":
    deploy()
