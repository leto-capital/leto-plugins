# Armadilhas de `cr_instrument_series`

Cada item aqui já está tratado no `scripts/puxar.py`. O texto existe para quando um
número parecer estranho ou alguém precisar mexer no script — todas foram encontradas
na prática, e todas produzem resultado plausível e errado, sem lançar erro.

## `id` é sequência global, não por instrumento

Pares (instrumento, data) se repetem porque a origem recarrega lotes. A linha
legítima é a **primeira gravação**, ou seja, o menor `id`.

Usar o maior `id` parece mais natural — "a versão mais recente" — e é justamente o
que quebra. Num caso real, o bucket de um instrumento tinha recebido um lote com
catorze séries alheias, inclusive uma constante em 0,002, e a regra do maior `id`
puxava esse lixo. A série do papel passou a terminar dois meses antes do que devia,
com mínimo de 0,00.

## Datas-lixo

A tabela tem linhas em `0001-01-01` e um bloco antigo de 2014. `MAX(target_date)` sem
filtro devolve lixo. O script descarta qualquer linha anterior a 2015.

## `anb_pu` zerado

A ANBIMA publica zero em algumas datas. Zero **não** é marcação: é ausência. Tratado
como número, vira 0% no gráfico e arrasta a média e o mínimo.

Num conjunto de quatro papéis havia 23 datas assim, e em todas a carteira do fundo
tinha preço real — ou seja, o dado existia, só não pela ANBIMA. O script descarta
essas datas em vez de plotá-las.

## `anb_yref` zerado — a taxa some antes do preço

A mesma lógica do `anb_pu`, com uma consequência própria: **em papel distressed a
ANBIMA para de publicar a taxa indicativa e continua publicando o PU.** O campo vem
zerado, não nulo, então uma leitura ingênua desenha uma linha descendo a 0%.

Medido num conjunto de oito papéis: 237 datas zeradas no BRKMA6, 236 no BRKMA8 e 430
no AERI11 — contra zero nos papéis saudáveis do mesmo conjunto. E a data em que a
taxa some é informativa: nos dois papéis da Braskem ela para em 25/09/2025, o mesmo
pregão do evento de crédito que derrubou o preço em 25 pontos.

Consequência prática para gráfico: um papel pode ter série de %par muito mais longa
que a de taxa. As duas curvas terminam em datas diferentes, e a caixinha de cada uma
tem de citar a última data **daquela** métrica — cruzar as duas produz um par que
nunca existiu junto. Quando a série termina antes do fim do gráfico, mostre a data
junto do número, senão o valor é lido como atual.

## A reserva: média dos administradores

Onde a ANBIMA não publica taxa, o script usa a média das colunas de administrador
preenchidas naquela data. São sete possíveis — mellon, bradesco, intrag, daycoval,
btg, xp, ot — e a família depende do indexador do papel (`cr_instrument.index_type_id`
→ `cr_index_type`):

| Indexador | Coluna |
|---|---|
| DI+, %DI, SELIC+, %SELIC | `<admin>_yld_di` |
| IPCA+ e demais indexados a inflação | `<admin>_yld_ipca` |
| PRE, sem índice, dólar, TR | `<admin>_yld` |

Ler a família errada dá número plausível na régua errada: spread sobre CDI não é taxa
real. Se a família do indexador vier vazia, o script tenta a taxa cheia antes de
desistir.

**A emenda é segura.** Onde as duas fontes coexistem os números batem na quarta casa:
num papel DI+, `anb_yref = 0,156603` contra média dos administradores `0,156614`. Não
há degrau visível na transição.

**Mas há um teto de 100% ao ano.** Num papel marcado muito abaixo do par o yield
implícito explode: o AERI11, marcado a 12% do par, devolve 419% a.a. pelos
administradores. É o preço quebrado voltando como taxa — aritmética correta,
informação nenhuma. A ANBIMA para de publicar exatamente nesses casos, e a reserva
não deve reintroduzir o número que a fonte primária decidiu não dar. Acima do teto o
ponto vira ausência, o script avisa, e a curva de %par continua completa.

O teto não vale para a ANBIMA: se ela publicar algo alto, é decisão editorial dela.

Vale olhar também a dispersão entre administradores. O script conta as datas em que
eles divergem mais de 0,5 pp entre si e avisa, porque a média esconde desacordo.

## `pupar` ausente ou zero

`%par = anb_pu / pupar`. Sem a guarda de `pupar > 0` o resultado é `Infinity`.

Existem também prints isolados de `pupar` corrompido: um papel marcou 336,84 entre
734,17 e 735,08, o que joga o %par de ~47% para ~103% num dia só. O script não pega
esse caso automaticamente — quando um salto grande aparecer, compare a variação do
`pupar` com a do numerador. Se o `pupar` andou sozinho, é o denominador que está
quebrado, não o preço.

A distinção que importa: um degrau no `pupar` acompanhado de amortização é real
(o papel amortizou); um degrau isolado que reverte no dia seguinte é print ruim.

## Carga parcial

A carga da base roda durante o dia. Uma data com bem menos linhas que as vizinhas
está incompleta, e qualquer número tirado dela é provisório.

Exemplo real: uma data com 6.219 linhas contra ~12.250 das anteriores. Nela, três
papéis do mesmo emissor caíam juntos e o `pupar` de dois recuava ~5% sem amortização
registrada. Parecia evento de crédito; era a carga pela metade.

O script compara cada uma das últimas doze datas contra a mediana e marca como
provisória qualquer uma abaixo de 60%. Essas linhas entram no CSV com
`provisorio = 1` e ficam fora dos gráficos.

## Como distinguir evento de crédito de erro de carga

Quando um degrau grande aparecer, três perguntas resolvem quase sempre:

1. **O `pupar` andou junto?** Se o numerador caiu e o denominador ficou parado, o
   movimento é de preço. Se os dois se mexeram na mesma proporção, foi amortização.
2. **Reverteu no dia seguinte?** Evento de crédito não reverte; print ruim reverte.
3. **Os papéis irmãos se moveram?** Dois papéis do mesmo emissor caindo juntos, com
   denominadores parados, é assinatura de evento do emissor. Um só caindo, sozinho,
   com os irmãos parados, é suspeito.

Num caso real duas debêntures do mesmo emissor caíram 25 e 26 pontos no mesmo
pregão, com `pupar` acretando normalmente e sem reversão: evento de crédito, série
mantida. Noutro, um papel isolado saltou 24 pontos num dia e voltou no seguinte
enquanto o irmão não se mexeu: print ruim, sinalizado.

## Limites da API

- Paginação recusada acima de offset 100.000. Quando a tabela é grande, filtre por
  `instrument_id` ou por `target_date` em vez de avançar páginas.
- `page_size` efetivo de 500 nos datasets de dados e 200 no catálogo.
- Mandar um parâmetro de filtro inválido devolve 422 **listando todos os filtros
  habilitados** daquele dataset. É o jeito mais rápido de descobrir por onde dá para
  filtrar.
- A chave só alcança `/api/v1/data`, `/api/v1/model` e `/api/v1/mail`. Rotas de
  aplicação devolvem 403.
