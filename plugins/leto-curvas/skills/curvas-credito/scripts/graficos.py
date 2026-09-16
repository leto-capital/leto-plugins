# -*- coding: utf-8 -*-
"""Dois gráficos no padrão Leto Capital a partir de series.csv: taxa e %par.

Uso:  python graficos.py --entrada ./saida --saida ./saida

Gera  <saida>/taxa_anbima.png
      <saida>/pct_par.png
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.offsetbox import AnnotationBbox, OffsetImage

AQUI = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(AQUI), "assets")

BRANCO, PRETO, VERDE = "#FFFFFF", "#000000", "#D8EEA9"
N700, N500, N100 = "#505050", "#7D7D7D", "#E8E5DD"
N300 = "#BDB7A7"

# Paleta categórica da marca, na ordem do manual.
LETO = ["#000000", "#7B776C", "#BDB7A7", "#7F9657", "#A7C878", "#D8EEA9",
        "#956A49", "#C08B63", "#65798F", "#94A6BA", "#8C89A7", "#CFCBDA"]
TRACOS = ["-", "--", ":", "-."]


def contraste(hex_cor, fundo="#FFFFFF"):
    """WCAG. Uma linha fina precisa de ~3:1 para ser legível."""
    def lum(h):
        c = [int(h.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        c = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    a, b = sorted([lum(hex_cor), lum(fundo)], reverse=True)
    return (a + 0.05) / (b + 0.05)


# O manual manda usar a paleta na ordem definida E garantir contraste suficiente.
# Sobre branco, metade dos slots fica abaixo de 3:1 e some como linha, então
# ficamos com os que passam, preservando a ordem original entre eles.
PALETA = [c for c in LETO if contraste(c) >= 3.0]


def estilo(i):
    """Além de 6 papéis a cor repete; o traço passa a diferenciar."""
    return PALETA[i % len(PALETA)], TRACOS[(i // len(PALETA)) % len(TRACOS)]


def _br(v):
    """Número no formato brasileiro: milhar com ponto, decimal com vírgula."""
    return f"{v:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def fonte():
    d = os.path.join(ASSETS, "fontes")
    if os.path.isdir(d):
        for f in os.listdir(d):
            if f.lower().endswith((".otf", ".ttf")):
                try:
                    fm.fontManager.addfont(os.path.join(d, f))
                except Exception:
                    pass
    nomes = {f.name for f in fm.fontManager.ttflist}
    for cand in ("PP Neue Montreal", "Google Sans Flex"):
        if cand in nomes:
            return cand
    return "Arial"       # nunca serifada, conforme o manual


def eixo_trimestres(ax, ini, fim):
    qs = []
    for ano in range(ini.year, fim.year + 1):
        for m in (1, 4, 7, 10):
            q = dt.date(ano, m, 1)
            if ini <= q <= fim:
                qs.append(q)
    # com histórico longo o eixo entope; rareia mantendo sempre o 1Q de cada ano
    if len(qs) > 14:
        qs = [q for q in qs if q.month == 1] or qs[::4]
    ax.set_xticks(qs)
    ax.set_xticklabels([f"{(q.month - 1) // 3 + 1}Q{q:%y}" for q in qs])
    return qs


def desenha(series, campo, titulo, subtitulo, sufixo_y, caixa_campo, caixa_sufixo,
            destino, fam, nota_rodape, rotulo_y):
    fig = plt.figure(figsize=(12, 6.75), dpi=200, facecolor=BRANCO)
    ax = fig.add_axes([0.095, 0.145, 0.765, 0.59])
    ax.set_facecolor(BRANCO)

    ini = min(p["data"] for s in series for p in s["pontos"])
    fim = max(p["data"] for s in series for p in s["pontos"])

    for i, s in enumerate(series):
        cor, traco = estilo(i)
        validos = [p for p in s["pontos"] if p[campo] is not None]
        s["_cor"], s["_ultimo"], s["_linha"] = cor, None, None
        if not validos:
            continue
        ax.plot([p["data"] for p in validos], [p[campo] for p in validos],
                color=cor, linewidth=2.0, linestyle=traco,
                solid_capstyle="round", zorder=3)
        # a caixinha tem de citar a ÚLTIMA data com valor desta métrica, não a
        # última da série: em papel distressed a taxa some antes do preço, e
        # cruzar as duas datas produziria um par que nunca existiu junto
        s["_ultimo"] = (validos[-1]["data"], validos[-1][campo])
        s["_linha"] = validos[-1]

    eixo_trimestres(ax, ini, fim)
    folga = max(1, int((fim - ini).days * 0.14))
    ax.set_xlim(ini, fim + dt.timedelta(days=folga))
    ax.yaxis.set_major_formatter(lambda v, p: f"{v:,.0f}{sufixo_y}".replace(",", "."))
    ax.grid(axis="y", color=N100, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(N300)
    ax.tick_params(colors=N500, labelsize=9.5, length=0)
    for t in ax.get_xticklabels() + ax.get_yticklabels():
        t.set_fontfamily(fam)
    ax.set_ylabel(rotulo_y, fontsize=9.5, fontfamily=fam, color=N700, labelpad=10)
    ax.set_xlabel("Trimestre", fontsize=9.5, fontfamily=fam, color=N700, labelpad=8)

    # Caixinhas no último ponto. Papéis do mesmo emissor fecham perto um do outro,
    # então as caixas precisam ser empilhadas com espaço mínimo e ligadas ao ponto
    # por uma linha-guia — senão viram um bolo ilegível justamente no que interessa.
    com_ponto = [s for s in series if s.get("_ultimo")]
    com_ponto.sort(key=lambda s: -s["_ultimo"][1])
    lo, hi = ax.get_ylim()

    # O espaçamento mínimo entre caixas tem de sair da altura REAL da caixa, não de
    # uma fração chutada da escala: com poucos papéis a escala é curta e uma fração
    # pequena ainda deixa as caixas por cima uma da outra.
    FONTE_PT, ENTRELINHA, PAD = 8.5, 1.35, 0.45
    linhas_caixa = 1 if all(s["_linha"].get(caixa_campo) is None for s in com_ponto) else 2
    altura_pt = linhas_caixa * FONTE_PT * ENTRELINHA + 2 * PAD * FONTE_PT
    altura_eixo_pt = ax.get_position().height * fig.get_figheight() * 72
    passo = (hi - lo) * (altura_pt * 1.12) / altura_eixo_pt

    meia = passo * 0.55
    alvos = []
    for s in com_ponto:
        y = s["_ultimo"][1]
        alvos.append(y if not alvos else min(y, alvos[-1] - passo))

    # A pilha gulosa preserva a distância entre pontos afastados, e com isso pode
    # ocupar mais que a altura do eixo — aí deslocar o conjunto só joga a caixa de
    # cima para fora do gráfico. Quando não cabe, distribui por igual: a caixa perde
    # a proximidade com a própria linha, mas a linha-guia continua ligando as duas.
    topo, base = hi - meia, lo + meia
    if alvos and (alvos[0] - alvos[-1]) > (topo - base):
        n = len(alvos)
        alvos = [topo] if n == 1 else [topo - i * (topo - base) / (n - 1) for i in range(n)]
    elif alvos:
        if alvos[0] > topo:
            alvos = [v - (alvos[0] - topo) for v in alvos]
        if alvos[-1] < base:
            alvos = [v + (base - alvos[-1]) for v in alvos]

    dx = dt.timedelta(days=max(1, int((fim - ini).days * 0.022)))
    for s, alvo in zip(com_ponto, alvos):
        x, y = s["_ultimo"]
        ax.plot([x], [y], marker="o", markersize=5, color=s["_cor"],
                markeredgecolor=BRANCO, markeredgewidth=1.4, zorder=4)
        u = s["_linha"]
        txt = f"{s['ativo']}   {_br(u[campo])}{sufixo_y}"
        # papel cuja série parou antes do fim do gráfico precisa dizer quando parou,
        # senão o número é lido como atual — acontece muito: a ANBIMA deixa de
        # publicar a taxa de papel distressed e continua publicando o preço
        if u["data"] != fim:
            txt += f"   ({u['data']:%d/%m/%y})"
        if u.get(caixa_campo) is not None:
            txt += f"\n{_br(u[caixa_campo])}{caixa_sufixo}"
        ax.annotate(txt, xy=(x, y), xytext=(x + dx, alvo), textcoords="data",
                    va="center", ha="left", fontsize=8.5, fontfamily=fam, color=PRETO,
                    linespacing=1.35, zorder=5, annotation_clip=False,
                    arrowprops=dict(arrowstyle="-", color=s["_cor"],
                                    linewidth=0.8, shrinkA=0, shrinkB=3),
                    bbox=dict(boxstyle="square,pad=0.45", facecolor=BRANCO,
                              edgecolor=s["_cor"], linewidth=1.1))

    fig.text(0.065, 0.905, titulo, fontsize=21, fontfamily=fam, fontweight="bold", color=PRETO)
    fig.text(0.065, 0.852, subtitulo, fontsize=10.5, fontfamily=fam, color=N700)
    fig.add_artist(plt.Line2D([0.065, 0.935], [0.828, 0.828], color=VERDE, linewidth=2.5))
    fig.text(0.065, 0.045, nota_rodape, fontsize=8.5, fontfamily=fam, color=N500)
    fig.text(0.935, 0.045, "Capital com propósito", fontsize=8.5, fontfamily=fam,
             color=N500, ha="right")

    logo = os.path.join(ASSETS, "logos", "logo_gradiente_fundo_branco.png")
    if os.path.exists(logo):
        img = mpimg.imread(logo)
        # zoom do OffsetImage é em pontos: a 200 dpi cada ponto vale 200/72 px.
        # O manual pede no mínimo 250 px de largura para o logo completo.
        z = 320 / (img.shape[1] * 200 / 72)
        fig.add_artist(AnnotationBbox(OffsetImage(img, zoom=z), (0.935, 0.895),
                                      xycoords="figure fraction",
                                      box_alignment=(1.0, 0.5), frameon=False))
    fig.savefig(destino, facecolor=BRANCO, dpi=200)
    plt.close(fig)
    return destino


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entrada", default="saida")
    ap.add_argument("--saida", default="saida")
    a = ap.parse_args()
    os.makedirs(a.saida, exist_ok=True)

    dados = {}
    with open(os.path.join(a.entrada, "series.csv"), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if int(r["provisorio"]):       # carga parcial não entra em gráfico
                continue
            dados.setdefault(r["ativo"], []).append({
                "data": dt.date.fromisoformat(r["data"]),
                "taxa": float(r["taxa"]) if r["taxa"] else None,
                "pct_par": float(r["pct_par"]) if r["pct_par"] else None,
                "fonte_taxa": r.get("fonte_taxa") or None,
            })

    diag = {}
    p = os.path.join(a.entrada, "diagnostico.json")
    if os.path.exists(p):
        diag = json.load(open(p, encoding="utf-8"))
    ordem = [x["ticker"] for x in diag.get("ativos", [])] or sorted(dados)
    series = [{"ativo": t, "pontos": sorted(dados[t], key=lambda x: x["data"])}
              for t in ordem if t in dados]
    if not series:
        print("series.csv não tem nenhum ponto utilizável.")
        return 1

    fam = fonte()
    emissores = sorted({x["emissor"] for x in diag.get("ativos", []) if x.get("emissor")})
    quem = ", ".join(emissores) if 0 < len(emissores) <= 3 else f"{len(series)} papéis"
    fim = max(p["data"] for s in series for p in s["pontos"])
    ini = min(p["data"] for s in series for p in s["pontos"])
    MES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
           "agosto", "setembro", "outubro", "novembro", "dezembro"]
    periodo = f"{MES[ini.month - 1]} de {ini.year} a {MES[fim.month - 1]} de {fim.year}"
    lista = " · ".join(s["ativo"] for s in series)
    rodape = f"Fonte: ANBIMA, taxa indicativa. Posição de {fim.day} de {MES[fim.month - 1]} de {fim.year}."

    # papéis cuja taxa veio, em alguma data, da média dos administradores em vez da
    # ANBIMA — quem lê o gráfico precisa saber, porque são fontes diferentes
    com_admin = sorted({s["ativo"] for s in series
                        for p in s["pontos"] if p.get("fonte_taxa") == "administradores"})
    rodape_taxa = rodape
    if com_admin:
        rodape_taxa = (rodape.replace("Fonte: ANBIMA, taxa indicativa.",
                                      "Fonte: ANBIMA, taxa indicativa; onde ela falta, média das "
                                      "taxas dos administradores.")
                       + f"  Usaram a média: {', '.join(com_admin)}.")

    titulo_taxa = "Taxa indicativa" if com_admin else "Taxa ANBIMA"
    saidas = []
    saidas.append(desenha(
        series, "taxa", f"{titulo_taxa} — {quem}",
        f"Taxa ao ano · {lista} · {periodo}",
        "%", "pct_par", "% do par",
        os.path.join(a.saida, "taxa_anbima.png"), fam, rodape_taxa,
        "Taxa ao ano (%)"))
    saidas.append(desenha(
        series, "pct_par", f"Marcação em % do par — {quem}",
        f"Preço indicativo ANBIMA sobre o PU par · {lista} · {periodo}",
        "%", "taxa", "% de taxa",
        os.path.join(a.saida, "pct_par.png"), fam, rodape,
        "Preço em % do PU par"))

    print(f"fonte: {fam}")
    print(f"papéis: {len(series)} · paleta com {len(PALETA)} cores acima de 3:1 sobre branco")
    for s in saidas:
        print(f"gerado: {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
