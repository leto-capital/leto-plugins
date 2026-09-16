# -*- coding: utf-8 -*-
"""Puxa taxa ANBIMA e %par de N papéis, aplicando as guardas conhecidas da base.

Uso:  python puxar.py TEPA11 TEPA12 TEPA13 --saida ./saida

Gera  <saida>/series.csv        uma linha por (ativo, data)
      <saida>/diagnostico.json  o que foi descartado e por quê

O script NÃO decide sozinho o que fazer com papel sem dado: ele reporta em
`bloqueios` e devolve código de saída 2. Quem chama decide — a ideia é que um
gráfico nunca saia pela metade sem alguém ter visto.
"""
import argparse
import csv
import datetime as dt
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datacontrol as dc

INSTRUMENTO = "/api/v1/data/jba-db/cr-instrument"
SERIE = "/api/v1/data/jba-db/cr-instrument-series"
EMISSORES = "/api/v1/data/jba-db/vw-cr-issuers"

ANO_MINIMO = 2015          # a tabela tem linhas em 0001-01-01 e um bloco antigo de 2014
PISO_CARGA = 0.60          # data com menos de 60% da mediana de linhas = carga parcial

ADMINISTRADORES = ["mellon", "bradesco", "intrag", "daycoval", "btg", "xp", "ot"]

# A taxa do administrador vem numa coluna por indexador. Ler a família errada dá
# número plausível na régua errada: `_yld_di` é spread sobre o CDI, `_yld_ipca` é
# taxa real. O id vem de cr_instrument.index_type_id (tabela cr_index_type).
SUFIXO_POR_INDEXADOR = {
    1: "_yld_di", 2: "_yld_di", 14: "_yld_di", 15: "_yld_di",          # DI+, %DI, SELIC
    3: "_yld_ipca", 6: "_yld_ipca", 11: "_yld_ipca", 12: "_yld_ipca",  # IPCA+ e demais
    13: "_yld_ipca", 16: "_yld_ipca", 17: "_yld_ipca", 18: "_yld_ipca",  # indexados a inflação
}
SUFIXO_PADRAO = "_yld"     # PRE, sem índice, dólar, TR: taxa cheia

# Teto para a taxa vinda dos administradores, em fração (1.0 = 100% a.a.).
# Num papel marcado a 12% do par o yield implícito passa de 400% a.a.: é aritmética
# correta e informação nenhuma — é o preço quebrado voltando como taxa. A ANBIMA
# para de publicar justamente nesses casos, então a reserva não deve reintroduzir o
# número que a fonte primária decidiu não dar. Acima do teto o ponto vira ausência.
# Não vale para a ANBIMA: se ela publicar algo alto, é decisão editorial dela.
TETO_TAXA_ADMIN = 1.0


def _f(v):
    """Campo numérico da API: vem como string, e vazio não é zero."""
    s = str(v).strip() if v is not None else ""
    return float(s) if s else None


def _d(v):
    return dt.datetime.fromisoformat(str(v).replace("Z", "")).date()


def resolve(ticker):
    r = dc.get(INSTRUMENTO, code=ticker, limit=5)
    n = r.get("total_rows", 0)
    if n == 0:
        return None, f"{ticker} não existe no cadastro (cr_instrument.code)"
    if n > 1:
        return None, f"{ticker} casa com {n} instrumentos; o código deveria ser único"
    x = r["rows"][0]
    iid = int(x["id"])
    emissor, setor = "", ""
    try:
        e = dc.get(EMISSORES, instrument_id=iid, limit=1).get("rows") or []
        if e:
            emissor, setor = e[0].get("issuer_name", ""), e[0].get("sector", "")
    except dc.ErroDaAPI:
        pass
    idx = x.get("index_type_id")
    idx = int(idx) if str(idx or "").strip() else None
    return {
        "ticker": ticker, "instrument_id": iid, "isin": x.get("isin", ""),
        "emissor": emissor, "setor": setor,
        "index_type_id": idx,
        "sufixo_admin": SUFIXO_POR_INDEXADOR.get(idx, SUFIXO_PADRAO),
        "emissao": str(x.get("issue_date", ""))[:10],
        "vencimento": str(x.get("maturity", ""))[:10],
    }, None


def taxa_administradores(linha, sufixo):
    """Média das taxas dos administradores que publicaram naquela data.

    Onde ANBIMA e administradores coexistem os números batem na quarta casa, então
    a emenda entre as duas fontes não produz degrau. Devolve (media, quantos, spread).
    """
    for suf in (sufixo, SUFIXO_PADRAO):        # se a família do indexador estiver
        vals = []                              # vazia, tenta a taxa cheia
        for a in ADMINISTRADORES:
            v = _f(linha.get(a + suf))
            if v is not None and v > 0:
                vals.append(v)
        if vals:
            return sum(vals) / len(vals), len(vals), max(vals) - min(vals)
    return None, 0, None


def serie(iid, sufixo):
    """Uma linha por data, já com as guardas aplicadas."""
    brutas = dc.linhas(SERIE, instrument_id=iid, sort_by="id", sort_dir="asc")
    diag = {"cru": len(brutas), "lixo": 0, "duplicadas": 0,
            "sem_pupar": 0, "anb_nulo": 0, "anb_zero": 0}
    vistas, pontos = set(), []

    # `id` é sequência global na origem e pares (instrumento, data) se repetem em
    # recargas; a primeira gravação é a boa. Por isso percorremos em ordem de id.
    for x in sorted(brutas, key=lambda r: int(r["id"])):
        d = _d(x["target_date"])
        if d.year < ANO_MINIMO:
            diag["lixo"] += 1
            continue
        if d in vistas:
            diag["duplicadas"] += 1
            continue
        vistas.add(d)

        pupar = _f(x.get("pupar"))
        if not pupar or pupar <= 0:          # dividir por zero vira Infinity
            diag["sem_pupar"] += 1
            continue
        anb = _f(x.get("anb_pu"))
        if anb is None:
            diag["anb_nulo"] += 1
            continue
        if anb == 0:                          # zero publicado nunca é marcação válida
            diag["anb_zero"] += 1
            continue

        # anb_yref zerado não é taxa, é ausência — mesmo raciocínio do anb_pu.
        # Acontece em papel distressed: a ANBIMA segue publicando o PU mas para de
        # publicar a taxa indicativa. Tratado como número, vira uma linha em 0%.
        yref = _f(x.get("anb_yref"))
        if yref is not None and yref <= 0:
            yref = None
            diag["yref_zero"] = diag.get("yref_zero", 0) + 1

        fonte, n_adm, disp = "ANBIMA", None, None
        if yref is None:
            yref, n_adm, disp = taxa_administradores(x, sufixo)
            if yref is not None and yref > TETO_TAXA_ADMIN:
                yref, n_adm = None, None
                diag["admin_absurdo"] = diag.get("admin_absurdo", 0) + 1
            fonte = "administradores" if yref is not None else None
            if yref is not None:
                diag["taxa_admin"] = diag.get("taxa_admin", 0) + 1
                if disp is not None and disp > 0.005:     # meio ponto percentual
                    diag["admin_divergente"] = diag.get("admin_divergente", 0) + 1
        elif yref is not None:
            diag["taxa_anbima"] = diag.get("taxa_anbima", 0) + 1

        pontos.append({
            "data": d, "pct_par": round(100 * anb / pupar, 4),
            "taxa": round(100 * yref, 4) if yref is not None else None,
            "fonte_taxa": fonte, "n_admin": n_adm,
            "anb_pu": round(anb, 6), "pupar": round(pupar, 6),
            "duration": _f(x.get("anb_dur")),
        })
    pontos.sort(key=lambda p: p["data"])
    diag["usadas"] = len(pontos)
    return pontos, diag


def cargas_parciais(datas):
    """A carga da base roda durante o dia. Uma data com bem menos linhas que as
    vizinhas está incompleta, e qualquer número tirado dela é provisório."""
    ultimas = sorted(datas)[-12:]
    if len(ultimas) < 4:
        return {}, None
    tam = {d: dc.contagem(SERIE, target_date=d.isoformat()) for d in ultimas}
    mediana = statistics.median(tam.values())
    return {d: n for d, n in tam.items() if n < PISO_CARGA * mediana}, mediana


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--saida", default="saida")
    ap.add_argument("--desde", help="AAAA-MM-DD; padrão é o histórico completo")
    a = ap.parse_args()

    os.makedirs(a.saida, exist_ok=True)
    tickers = [t.strip().upper() for t in a.tickers if t.strip()]
    corte = dt.date.fromisoformat(a.desde) if a.desde else None

    ativos, linhas_csv, bloqueios, avisos = [], [], [], []

    for t in tickers:
        meta, erro = resolve(t)
        if erro:
            bloqueios.append({"ticker": t, "motivo": erro})
            print(f"  {t:<8} BLOQUEIO — {erro}")
            continue
        pontos, diag = serie(meta["instrument_id"], meta["sufixo_admin"])
        com_taxa = [p for p in pontos if p["taxa"] is not None]
        if corte:
            pontos = [p for p in pontos if p["data"] >= corte]
            com_taxa = [p for p in com_taxa if p["data"] >= corte]

        meta["diagnostico"] = diag
        meta["obs_taxa"] = len(com_taxa)
        meta["obs_par"] = len(pontos)
        if com_taxa:
            meta["inicio"] = com_taxa[0]["data"].isoformat()
            meta["fim"] = com_taxa[-1]["data"].isoformat()

        if not com_taxa:
            faixa = f" no recorte a partir de {corte}" if corte else ""
            bloqueios.append({
                "ticker": t,
                "motivo": (f"{t} não tem taxa nem pela ANBIMA nem pela média dos "
                           f"administradores{faixa}. De {diag['cru']} linhas brutas, "
                           f"{diag['anb_nulo']} estão sem anb_pu, {diag['anb_zero']} vieram com "
                           f"anb_pu zerado e {diag.get('yref_zero', 0)} com anb_yref zerado; "
                           f"as colunas de administrador também estão vazias."),
                "diagnostico": diag,
            })
            print(f"  {t:<8} BLOQUEIO — sem taxa ANBIMA utilizável")
            continue

        ativos.append(meta)
        for p in pontos:
            linhas_csv.append({
                "ativo": t, "emissor": meta["emissor"], "data": p["data"].isoformat(),
                "taxa": p["taxa"], "fonte_taxa": p["fonte_taxa"], "n_admin": p["n_admin"],
                "pct_par": p["pct_par"],
                "anb_pu": p["anb_pu"], "pupar": p["pupar"], "duration": p["duration"],
                "provisorio": 0,
            })
        n_adm = sum(1 for p in com_taxa if p["fonte_taxa"] == "administradores")
        extra = f" · {n_adm} pela média dos administradores" if n_adm else ""
        print(f"  {t:<8} {len(com_taxa):>5} obs de taxa · {meta.get('inicio')} a {meta.get('fim')}"
              f"  ({meta['emissor']}){extra}")
        if diag.get("admin_divergente"):
            avisos.append(f"{t}: em {diag['admin_divergente']} datas os administradores divergem "
                          f"mais de 0,5 pp entre si; a média esconde essa dispersão.")
        if diag.get("admin_absurdo"):
            avisos.append(
                f"{t}: em {diag['admin_absurdo']} datas a média dos administradores passou de "
                f"{TETO_TAXA_ADMIN * 100:.0f}% a.a. e foi descartada. Num papel marcado muito abaixo "
                f"do par o yield implícito explode — é o preço quebrado voltando como taxa, e é por "
                f"isso que a ANBIMA deixa de publicar. A curva de %par continua completa.")

    if not linhas_csv:
        print("\nNenhum papel utilizável. Nada foi gerado.")
        json.dump({"ativos": [], "bloqueios": bloqueios, "avisos": []},
                  open(os.path.join(a.saida, "diagnostico.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        return 2

    # carga parcial: marca em vez de apagar, para quem lê decidir
    todas = {dt.date.fromisoformat(r["data"]) for r in linhas_csv}
    parciais, mediana = cargas_parciais(todas)
    for r in linhas_csv:
        if dt.date.fromisoformat(r["data"]) in parciais:
            r["provisorio"] = 1
    for d, n in sorted(parciais.items()):
        msg = (f"{d.isoformat()} tem {n:,} linhas em cr_instrument_series contra uma mediana de "
               f"{mediana:,.0f} nas datas vizinhas: carga ainda rodando. As linhas dessa data "
               f"estão marcadas como provisórias e ficam fora dos gráficos.")
        avisos.append(msg)
        print(f"\n  AVISO {msg}")

    with open(os.path.join(a.saida, "series.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ativo", "emissor", "data", "taxa", "fonte_taxa",
                                          "n_admin", "pct_par", "anb_pu", "pupar",
                                          "duration", "provisorio"])
        w.writeheader()
        w.writerows(linhas_csv)

    json.dump({"ativos": ativos, "bloqueios": bloqueios, "avisos": avisos,
               "gerado_em": dt.date.today().isoformat()},
              open(os.path.join(a.saida, "diagnostico.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2, default=str)

    print(f"\n{len(linhas_csv)} linhas · {len(ativos)} papéis -> {a.saida}/series.csv")
    if bloqueios:
        print(f"{len(bloqueios)} papel(is) bloqueado(s) — veja diagnostico.json")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
