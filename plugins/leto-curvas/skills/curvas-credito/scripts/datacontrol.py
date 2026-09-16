# -*- coding: utf-8 -*-
"""Cliente do barramento DataControl. Só biblioteca padrão, sem dependências."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("DATA_CONTROL_BASE_URL", "https://data.creditapps.com.br")

_ONDE_PROCURAMOS = [
    "variável de ambiente DATA_CONTROL_API_KEY",
    r"C:\ProgramData\DataControl\api_key.txt",
    "~/.datacontrol/api_key.txt",
]


class SemChave(RuntimeError):
    pass


class ErroDaAPI(RuntimeError):
    def __init__(self, status, url, corpo):
        self.status, self.url, self.corpo = status, url, corpo
        super().__init__(f"HTTP {status} em {url}\n{corpo}")


def _chave():
    v = os.environ.get("DATA_CONTROL_API_KEY", "").strip()
    if v:
        return v
    for caminho in (r"C:\ProgramData\DataControl\api_key.txt",
                    os.path.expanduser("~/.datacontrol/api_key.txt")):
        try:
            with open(caminho, encoding="utf-8") as f:
                v = f.read().strip()
            if v:
                return v
        except OSError:
            pass
    raise SemChave(
        "Não encontrei a chave da API do DataControl.\n"
        "Procurei em: " + "; ".join(_ONDE_PROCURAMOS) + "\n\n"
        "Para configurar, no PowerShell:\n"
        '  [Environment]::SetEnvironmentVariable("DATA_CONTROL_API_KEY", "<sua chave>", "User")\n'
        "e abra um terminal novo. A chave é pessoal: peça a sua a quem administra o DataControl, "
        "não reaproveite a de outra pessoa."
    )


def get(path, **query):
    """Uma requisição. Devolve o JSON já decodificado."""
    url = BASE + path
    if query:
        url += "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
    req = urllib.request.Request(url, headers={"X-API-Key": _chave(), "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", "replace")
        if e.code == 403:
            corpo += ("\n\nDica: a chave só alcança /api/v1/data. As rotas de aplicação "
                      "(offshoremonitor e afins) exigem o portal.")
        raise ErroDaAPI(e.code, url, corpo) from None


def linhas(path, **query):
    """Todas as linhas de um dataset, paginando.

    A API recusa offset acima de 100.000 ("paginação profunda demais"). Quando isso
    acontece a saída é filtrar mais — tipicamente por instrument_id ou target_date —
    em vez de continuar avançando páginas.
    """
    acc, pagina = [], 1
    while True:
        r = get(path, page=pagina, page_size=500, **query)
        acc.extend(r.get("rows", []))
        if pagina >= r.get("total_pages", 1):
            return acc
        pagina += 1


def contagem(path, **query):
    """Só o total_rows, sem trazer as linhas."""
    return get(path, page_size=1, **query).get("total_rows", 0)
