---
name: curvas-credito
description: Gera dois gráficos no padrão visual da Leto Capital — taxa indicativa ANBIMA e marcação em % do PU par — para qualquer conjunto de papéis de crédito, a partir dos tickers. Use sempre que alguém citar códigos de debênture, CRA, CRI ou letra financeira e pedir gráfico, curva, histórico, evolução, marcação, taxa, %par, "como está o papel", "manda a curva disso", "faz um gráfico desses ativos" ou quiser comparar papéis entre si — mesmo que não diga "Leto", "ANBIMA" nem "gráfico" com todas as letras. Também vale quando pedirem a imagem para colar em apresentação, e-mail ou comitê.
---

# Curvas de crédito — padrão Leto Capital

Transforma uma lista de tickers em duas imagens prontas para apresentação: a taxa
indicativa ANBIMA e a marcação em % do PU par, ambas no padrão visual da casa.

Quantos papéis a pessoa quiser. A marcação em %par vem sempre da ANBIMA — `anb_pu`
sobre `pupar`, em `cr_instrument_series`.

A taxa também começa na ANBIMA (`anb_yref`) e, **onde ela falta, cai para a média
das taxas dos administradores** que publicaram naquela data. A coluna certa depende
do indexador do papel: `_yld_di` para DI+ e %DI, `_yld_ipca` para os indexados a
inflação, `_yld` para pré e sem índice. Ler a família errada dá número plausível na
régua errada — spread sobre CDI não é taxa real.

A emenda entre as duas fontes é segura: onde ANBIMA e administradores coexistem os
números batem na quarta casa decimal. O gráfico diz no rodapé quais papéis usaram a
média, e o `series.csv` traz a coluna `fonte_taxa` linha a linha.

## Como rodar

Dois passos. O primeiro puxa e valida, o segundo desenha.

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/curvas-credito/scripts/puxar.py" TEPA11 TEPA12 TEPA13 --saida ./curvas
python "${CLAUDE_PLUGIN_ROOT}/skills/curvas-credito/scripts/graficos.py" --entrada ./curvas --saida ./curvas
```

Saem `taxa_anbima.png`, `pct_par.png`, mais `series.csv` e `diagnostico.json` para
auditoria. Entregue as duas imagens e diga onde ficou o CSV.

O `puxar.py` aceita `--desde AAAA-MM-DD` para recortar o período. Sem isso ele traz
o histórico completo de cada papel, que é o padrão: papéis de emissões diferentes
começam em datas diferentes e isso é informação, não defeito.

## Quando o script para

`puxar.py` devolve código de saída 2 e uma lista em `bloqueios` quando algum ticker
não dá para usar — não existe no cadastro, casa com mais de um instrumento, ou não
tem nenhuma taxa ANBIMA no período.

**Não contorne isso sozinho.** Mostre à pessoa quais papéis ficaram de fora e o
motivo exato que está no `diagnostico.json`, e pergunte se ela quer seguir sem eles
ou ajustar a lista. A razão é concreta: papel sem preço ANBIMA costuma ser emissão
nova, papel vencido ou código digitado errado, e cada um desses casos pede uma
decisão diferente de quem está pedindo o gráfico. Um gráfico que sai calado com dois
papéis quando a pessoa pediu três é pior que um erro, porque ninguém percebe.

Se ela confirmar, rode de novo só com os tickers que passaram.

## O que o script já resolve

A base tem armadilhas que geram número errado sem dar erro. O `puxar.py` já trata
todas; `references/armadilhas.md` explica cada uma em detalhe, e vale ler antes de
mexer no script ou de explicar um número estranho:

- `id` é sequência global, não por instrumento — pares (instrumento, data) se repetem
- datas-lixo em `0001-01-01` e um bloco antigo de 2014
- `anb_pu` zerado, que não é marcação e viraria 0% no gráfico
- `anb_yref` zerado, idem: em papel distressed a ANBIMA para de publicar a taxa e
  continua publicando o preço, então a curva de taxa termina antes da de %par
- `pupar` ausente ou zero, que geraria divisão por zero
- carga parcial do dia corrente, marcada como provisória e excluída dos gráficos

Por causa do `anb_yref`, papel em estresse costuma ter curva de taxa mais curta que a
de %par. A média dos administradores cobre boa parte desse vão, mas não todo: há um
**teto de 100% ao ano** na reserva, porque num papel marcado muito abaixo do par o
yield implícito explode — o AERI11 chega a 419% a.a. marcado a 12% do par. É aritmética
correta e informação nenhuma, e é justamente por isso que a ANBIMA para de publicar;
a reserva não deve reintroduzir o número que a fonte primária decidiu não dar.

Quando isso acontece o script avisa, e a caixinha do gráfico mostra a data em que a
série daquele papel parou, para o número não ser lido como atual. A curva de %par
segue completa — é ela que continua dizendo alguma coisa sobre papel quebrado.

Quando houver carga parcial o script avisa. Repasse o aviso: a pessoa precisa saber
que o último ponto do gráfico é de ontem, não de hoje.

## Padrão visual

As duas imagens saem 2400×1350 px, proporção 16:9, prontas para slide. Fontes
PP Neue Montreal e logo vêm em `assets/`, então não dependem de nada instalado.

A paleta é a categórica da marca, na ordem do manual, filtrada por contraste: sobre
branco, metade dos slots fica abaixo de 3:1 e uma linha fina desaparece. O script
calcula o contraste e usa só os que passam, preservando a ordem entre eles. Acima de
seis papéis a cor repete e o traço passa a diferenciar.

Cada curva termina com uma caixinha trazendo a outra métrica: no gráfico de taxa, o
%par daquele papel; no de %par, a taxa. Assim cada imagem se sustenta sozinha quando
alguém colar só uma no e-mail.

## Chave de acesso

O script lê a chave do DataControl da variável `DATA_CONTROL_API_KEY`, e se não achar
procura em `C:\ProgramData\DataControl\api_key.txt` e `~/.datacontrol/api_key.txt`.
A chave é pessoal. Se faltar, o erro já traz o comando de configuração — repasse para
a pessoa e não tente contornar com a chave de outro usuário.

## Dependências

`matplotlib` para desenhar. O acesso à API usa só biblioteca padrão. Se faltar:

```bash
python -m pip install matplotlib
```
