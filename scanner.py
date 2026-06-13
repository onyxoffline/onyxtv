#!/usr/bin/env python3
"""
ONYX TV — Channel Scanner
Varre fontes públicas de IPTV, testa cada URL e gera channels.json
para ser hospedado no GitHub e consumido pelo app Roku.

Uso:
    python scanner.py              # scan completo + gera JSON
    python scanner.py --test-only  # só testa canais já no JSON
    python scanner.py --sources    # lista as fontes configuradas
"""

import asyncio
import aiohttp
import json
import re
import sys
import time
import os
from datetime import datetime, timezone
from pathlib import Path

# ─────────────────────────────────────────
#  CONFIGURAÇÃO
# ─────────────────────────────────────────

OUTPUT_JSON = Path(__file__).parent / "channels.json"

# Timeout por canal (segundos)
TEST_TIMEOUT = 6

# Máximo de checagens paralelas
MAX_CONCURRENT = 40

# Fontes de canais a vasculhar
SOURCES = [
    # iptv-org — Brasil
    "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/br.m3u",
    # FTA Brasil (canais abertos verificados)
    "https://raw.githubusercontent.com/joaoguidugli/FTA-IPTV-Brasil/master/playlist.m3u8",
    # Free-TV global (filtra BR)
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",
    # Ramys Brasil 2026
    "https://raw.githubusercontent.com/Ramys/Iptv-Brasil-2026/master/CanaisBR01.m3u8",
    "https://raw.githubusercontent.com/Ramys/Iptv-Brasil-2026/master/CanaisBR03.m3u8",
]

# Canais curados manualmente (sempre incluídos, independente das fontes)
MANUAL_CHANNELS = [
    # Cinema FAST
    {"name": "RunTime",            "cat": "Cinema",   "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=2153"},
    {"name": "RunTime Ação",       "cat": "Cinema",   "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=2552"},
    {"name": "RunTime Suspense",   "cat": "Cinema",   "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=4865"},
    {"name": "RunTime Comédia",    "cat": "Cinema",   "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=2553"},
    {"name": "RunTime Crime",      "cat": "Cinema",   "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=4864"},
    {"name": "RunTime Família",    "cat": "Cinema",   "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=4866"},
    {"name": "RunTime Romance",    "cat": "Cinema",   "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=4867"},
    {"name": "MovieSphere BR",     "cat": "Cinema",   "url": "https://cdn-uw2-prod.tsv2.amagi.tv/linear/amg00353-lionsgatestudio-moviespherebrazil-runtimelatam/playlist.m3u8"},
    {"name": "MyTime Movie BR",    "cat": "Cinema",   "url": "https://appletree-mytime-samsungbrazil.amagi.tv/playlist.m3u8"},
    {"name": "CineMonde",          "cat": "Cinema",   "url": "https://video01.soultv.com.br/cinemonde/cinemonde/playlist.m3u8"},
    {"name": "DarkFlix HD",        "cat": "Cinema",   "url": "https://video01.soultv.com.br/darkflix/darkflix/playlist.m3u8"},
    {"name": "Soul Cine Clube",    "cat": "Cinema",   "url": "https://video01.soultv.com.br/soulcine/soulcine/playlist.m3u8"},
    {"name": "Cine Brasil TV",     "cat": "Cinema",   "url": "https://cinebrasiltv.brasilstream.com.br/hls/cinebrasiltv/index.m3u8"},
    {"name": "Plex Movies",        "cat": "Cinema",   "url": "https://epix-plexmovies-1-us.plex.wurl.tv/playlist.m3u8"},
    {"name": "Shout Factory",      "cat": "Cinema",   "url": "https://shoutfactory-1-us.plex.wurl.tv/playlist.m3u8"},
    {"name": "Canela Cinema",      "cat": "Cinema",   "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=2011"},
    {"name": "Crackle",            "cat": "Cinema",   "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=163"},
    # Séries
    {"name": "Sony Novelas",       "cat": "Series",   "url": "https://spt-novelas-1-us.lg.wurl.tv/playlist.m3u8"},
    {"name": "Canela Telenovelas", "cat": "Series",   "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=1152"},
    {"name": "MasterChef BR",      "cat": "Series",   "url": "https://amg00627-amg00627c9-runtime-latam-2613.playouts.now.amagi.tv/playlist/amg00627-banijayfast-masterchefbrazil-runtimelatam/playlist.m3u8"},
    {"name": "Trace Brazuca",      "cat": "Series",   "url": "https://cdn-uw2-prod.tsv2.amagi.tv/linear/amg01131-tracetv-tracebrazuca-xiaomi/playlist.m3u8"},
    {"name": "Plex TV Shows",      "cat": "Series",   "url": "https://epix-plextvshows-1-us.plex.wurl.tv/playlist.m3u8"},
    {"name": "Classic Reruns TV",  "cat": "Series",   "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=1097"},
    {"name": "Electric Now 1",     "cat": "Series",   "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=32"},
    {"name": "Electric Now 2",     "cat": "Series",   "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=53"},
    {"name": "Popcornflix",        "cat": "Series",   "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=161"},
    # Futebol
    {"name": "CazeTV",             "cat": "Futebol",  "url": "https://dfr80qz435crc.cloudfront.net/MNOP/Amagi/Caze/Caze_TV_BR/Caze_TV.m3u8"},
    {"name": "ge Fast",            "cat": "Futebol",  "url": "https://dfr80qz435crc.cloudfront.net/EFGH/Amagi/Globo/GE_Fast_BR/GE_Fast.m3u8"},
    {"name": "Premiere FC 1",      "cat": "Futebol",  "url": "https://megaott-live-1.akamaized.net/PREMIERE_FC/index.m3u8"},
    {"name": "Premiere FC 2",      "cat": "Futebol",  "url": "https://megaott-live-2.akamaized.net/PREMIERE_FC2/index.m3u8"},
    {"name": "Gol TV",             "cat": "Futebol",  "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=1090"},
    {"name": "TyC Sports AR",      "cat": "Futebol",  "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=1115"},
    {"name": "beIN Sports Xtra",   "cat": "Futebol",  "url": "http://linear-256.frequency.stream/256/hls/master/playlist.m3u8"},
    # Esportes
    {"name": "Red Bull TV",        "cat": "Esportes", "url": "https://rbmn-live.akamaized.net/hls/live/590964/BoRB-AT/master.m3u8"},
    {"name": "Edge Sport",         "cat": "Esportes", "url": "https://edgesports-plex.amagi.tv/hls/amagi_hls_data_plexAAAAA-edgesports-plex/CDN/playlist.m3u8"},
    {"name": "Fight Network 1",    "cat": "Esportes", "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=566"},
    {"name": "MMA TV",             "cat": "Esportes", "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=802"},
    {"name": "Tennis Channel",     "cat": "Esportes", "url": "https://tennischannel-intl-samsung-uk.amagi.tv/playlist.m3u8"},
    {"name": "Motorvision PT-BR",  "cat": "Esportes", "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=758"},
    {"name": "FloRacing 24/7",     "cat": "Esportes", "url": "https://d35j504z0x2vu2.cloudfront.net/v1/master/0bc8e8376bd8417a1b6761138aa41c26c7309312/floracing-247/playlist.m3u8"},
    # Notícias
    {"name": "Record News",        "cat": "Noticias", "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=5431"},
    {"name": "Canal Gov",          "cat": "Noticias", "url": "https://canalgov-stream.ebc.com.br/index.m3u8"},
    {"name": "TV Camara 1",        "cat": "Noticias", "url": "https://stream3.camara.gov.br/tv1/manifest.m3u8"},
    {"name": "TV Camara 2",        "cat": "Noticias", "url": "https://stream3.camara.gov.br/tv2/manifest.m3u8"},
    {"name": "TV ALMG MG",         "cat": "Noticias", "url": "https://streaming.almg.gov.br/live/tvalmg.m3u8"},
    {"name": "RTP 3 Portugal",     "cat": "Noticias", "url": "https://streaming-live.rtp.pt/livetvhlsDVR/rtpnHDdvr.smil/playlist.m3u8"},
    # Variedades
    {"name": "RecordTV",           "cat": "Variedades","url": "https://cdn.jmvstream.com/w/LVW-10842/LVW10842_513N26MDBL/chunklist.m3u8"},
    {"name": "TV Brasil Web",      "cat": "Variedades","url": "https://tvbrasil-stream.ebc.com.br/index.m3u8"},
    {"name": "Canal Rural",        "cat": "Variedades","url": "https://607d2a1a47b1f.streamlock.net/crur/smil:canalrural.smil/playlist.m3u8"},
    {"name": "Amazon Sat",         "cat": "Variedades","url": "https://amazonsat.brasilstream.com.br/hls/amazonsat/index.m3u8"},
    {"name": "TV Arapuan",         "cat": "Variedades","url": "https://5b7f3c45ab7c2.streamlock.net/tvarapuan/tvarapuan/playlist.m3u8"},
    {"name": "CNT Nacional",       "cat": "Variedades","url": "https://d1s664t39qub1o.cloudfront.net/live/cnt-manaus.m3u8"},
    # Infantil
    {"name": "NickToons Brasil",   "cat": "Infantil", "url": "https://stmv2.srvif.com/nicktoons/nicktoons/playlist.m3u8"},
    {"name": "Kuriakos Kids",      "cat": "Infantil", "url": "https://w2.manasat.com/kkids/smil:kkids.smil/playlist.m3u8"},
    {"name": "Toon Googles 1",     "cat": "Infantil", "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=274"},
    {"name": "Toon Googles 2",     "cat": "Infantil", "url": "https://stream.ads.ottera.tv/playlist.m3u8?network_id=465"},
    # Educação
    {"name": "TV Cultura SP",      "cat": "Educacao", "url": "https://player-tvcultura.stream.uol.com.br/live/tvcultura_lsd.m3u8"},
    {"name": "Canal Educacao",     "cat": "Educacao", "url": "https://canaleducacao-stream.ebc.com.br/index.m3u8"},
    {"name": "Rede Minas",         "cat": "Educacao", "url": "https://8hzcavccys.zoeweb.tv/redeminas/ngrp:redeminas_all/playlist.m3u8"},
    {"name": "SESC TV",            "cat": "Educacao", "url": "https://slbps-ml-sambatech.akamaized.net/samba-live/2472/7424/8a00fe7cc36ac263b2c3e9324497d5ff/video/93a9920d-1b24-4c5e-a7d2-63d5489f59b5_index.m3u8"},
    # Religioso
    {"name": "TV Aparecida",       "cat": "Religioso","url": "https://cdn.jmvstream.com/w/LVW-9716/LVW9716_HbtQtezcaw/master.m3u8"},
    {"name": "Novo Tempo",         "cat": "Religioso","url": "https://stream.live.novotempo.com/tv/smil:tvnovotempo.smil/playlist.m3u8"},
    {"name": "TV Cancao Nova",     "cat": "Religioso","url": "https://cdn.jmvstream.com/w/LVW-9365/LVW9365_3mBCe4DHnQ/playlist.m3u8"},
    {"name": "Rede Vida",          "cat": "Religioso","url": "https://d12e4o88jd8gex.cloudfront.net/out/v1/cea3de0b76ac4e82ab8ee0fd3f17ce12/index.m3u8"},
    # Música
    {"name": "Stingray Hits BR",   "cat": "Musica",   "url": "https://d20xuwbyc4yoag.cloudfront.net/v1/master/9d062541f2ff39b5c0f48b743c6411d25f62fc25/DistroTV-MuxIP-STHBR/388.m3u8"},
    {"name": "KpopTV Play",        "cat": "Musica",   "url": "https://giatv.bozztv.com/giatv/giatv-kpoptvplay/kpoptvplay/playlist.m3u8"},
]

# Mapeamento de palavras-chave do M3U para categorias do app
CATEGORY_MAP = {
    "futebol": "Futebol", "soccer": "Futebol", "football": "Futebol",
    "sport": "Esportes",  "esporte": "Esportes", "auto": "Esportes",
    "racing": "Esportes", "mma": "Esportes", "fight": "Esportes",
    "cinema": "Cinema",   "movie": "Cinema", "filme": "Cinema", "cine": "Cinema",
    "serie": "Series",    "novela": "Series", "tv show": "Series",
    "notic": "Noticias",  "news": "Noticias", "jornal": "Noticias",
    "infan": "Infantil",  "kids": "Infantil", "cartoon": "Infantil",
    "educa": "Educacao",  "cultur": "Educacao", "universit": "Educacao",
    "religi": "Religioso","gospel": "Religioso", "catol": "Religioso",
    "music": "Musica",    "musica": "Musica",
    "agro": "Variedades", "rural": "Variedades",
}

# ─────────────────────────────────────────
#  PARSE M3U
# ─────────────────────────────────────────

def parse_m3u(content: str) -> list[dict]:
    """Extrai canais de uma playlist M3U."""
    channels = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            # Extrai nome
            name_match = re.search(r',(.+)$', line)
            name = name_match.group(1).strip() if name_match else "Canal"

            # Extrai group-title
            group_match = re.search(r'group-title="([^"]*)"', line)
            group = group_match.group(1).lower() if group_match else ""

            # Determina categoria
            cat = guess_category(name.lower() + " " + group)

            # Próxima linha = URL
            if i + 1 < len(lines):
                url = lines[i + 1].strip()
                if url and not url.startswith("#") and ("m3u8" in url or "http" in url):
                    # Ignora YouTube (não funciona no Roku)
                    if "youtube.com" not in url and "youtu.be" not in url:
                        channels.append({
                            "name": clean_name(name),
                            "cat": cat,
                            "url": url,
                        })
            i += 2
        else:
            i += 1
    return channels


def clean_name(name: str) -> str:
    """Remove lixo de nomes de canais M3U."""
    name = re.sub(r'\[.*?\]', '', name)   # remove [HD], [BR] etc
    name = re.sub(r'\(.*?\)', '', name)   # remove (...)
    name = re.sub(r'\s+', ' ', name)
    return name.strip()[:60]


def guess_category(text: str) -> str:
    for kw, cat in CATEGORY_MAP.items():
        if kw in text:
            return cat
    return "Variedades"


# ─────────────────────────────────────────
#  TESTE DE DISPONIBILIDADE (ASYNC)
# ─────────────────────────────────────────

async def check_url(session: aiohttp.ClientSession, channel: dict, semaphore: asyncio.Semaphore) -> dict:
    """Testa se uma URL HLS responde. Retorna canal com campo 'online'."""
    url = channel["url"]
    async with semaphore:
        try:
            async with session.head(url, timeout=aiohttp.ClientTimeout(total=TEST_TIMEOUT),
                                    allow_redirects=True, ssl=False) as resp:
                online = resp.status in range(200, 410)  # 405 = método não permitido = servidor ok
        except Exception:
            # Tenta GET com range mínimo se HEAD falhar
            try:
                headers = {"Range": "bytes=0-0"}
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=TEST_TIMEOUT),
                                       headers=headers, allow_redirects=True, ssl=False) as resp:
                    online = resp.status in range(200, 410)
            except Exception:
                online = False

    return {**channel, "online": online}


async def test_all(channels: list[dict]) -> list[dict]:
    """Testa todos os canais em paralelo com limite de concorrência."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT, ssl=False)

    total = len(channels)
    done = 0
    results = []

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_url(session, ch, semaphore) for ch in channels]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            done += 1
            status = "✓" if result["online"] else "✗"
            print(f"\r  [{done:3d}/{total}] {status} {result['name'][:40]:<40}", end="", flush=True)
            results.append(result)

    print()  # nova linha após progress
    return results


# ─────────────────────────────────────────
#  FETCH DE FONTES
# ─────────────────────────────────────────

async def fetch_source(session: aiohttp.ClientSession, url: str) -> list[dict]:
    """Baixa e parseia uma fonte M3U."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                print(f"  ⚠ Fonte indisponível ({resp.status}): {url}")
                return []
            content = await resp.text(errors="replace")
            channels = parse_m3u(content)
            print(f"  ✓ {len(channels):3d} canais — {url.split('/')[-1]}")
            return channels
    except Exception as e:
        print(f"  ✗ Erro ao buscar fonte: {url}\n    {e}")
        return []


async def fetch_all_sources() -> list[dict]:
    """Busca todas as fontes e mescla os canais."""
    print(f"\n📡 Buscando {len(SOURCES)} fontes M3U...")
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_source(session, src) for src in SOURCES]
        results = await asyncio.gather(*tasks)

    all_channels = []
    seen_urls = set()

    # Canais manuais primeiro (prioridade)
    for ch in MANUAL_CHANNELS:
        if ch["url"] not in seen_urls:
            all_channels.append(ch)
            seen_urls.add(ch["url"])

    # Canais das fontes
    for batch in results:
        for ch in batch:
            if ch["url"] not in seen_urls:
                all_channels.append(ch)
                seen_urls.add(ch["url"])

    print(f"\n  Total de canais únicos: {len(all_channels)}")
    return all_channels


# ─────────────────────────────────────────
#  GERAÇÃO DO JSON
# ─────────────────────────────────────────

def generate_json(channels_with_status: list[dict]) -> dict:
    """Gera o JSON final que o app Roku irá consumir."""
    online  = [ch for ch in channels_with_status if ch.get("online")]
    offline = [ch for ch in channels_with_status if not ch.get("online")]

    # Remove campo 'online' do JSON final (o app vai usar a ordem)
    def clean(ch):
        return {"name": ch["name"], "cat": ch["cat"], "url": ch["url"]}

    return {
        "version": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M"),
        "updated": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "total": len(channels_with_status),
            "online": len(online),
            "offline": len(offline),
        },
        # Online primeiro, depois offline
        "channels": [clean(ch) for ch in online] + [clean(ch) for ch in offline],
    }


# ─────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────

async def main():
    test_only = "--test-only" in sys.argv
    list_sources = "--sources" in sys.argv

    if list_sources:
        print("Fontes configuradas:")
        for s in SOURCES:
            print(f"  {s}")
        return

    start = time.time()
    print("=" * 60)
    print("  ONYX TV — Channel Scanner")
    print("=" * 60)

    if test_only and OUTPUT_JSON.exists():
        print("\n🔄 Modo: apenas re-testar JSON existente")
        data = json.loads(OUTPUT_JSON.read_text())
        channels = data["channels"]
    else:
        channels = await fetch_all_sources()

    print(f"\n🔍 Testando {len(channels)} canais ({MAX_CONCURRENT} em paralelo)...")
    tested = await test_all(channels)

    online_count = sum(1 for ch in tested if ch.get("online"))
    print(f"\n  ✅ Online:  {online_count}")
    print(f"  ❌ Offline: {len(tested) - online_count}")

    data = generate_json(tested)
    OUTPUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    elapsed = time.time() - start
    print(f"\n✨ channels.json gerado — {online_count}/{len(tested)} canais online")
    print(f"   Arquivo: {OUTPUT_JSON}")
    print(f"   Tempo:   {elapsed:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
