# Plugins da Leto Capital

Marketplace interno de plugins do Claude Code para a mesa de crédito.

## Plugins disponíveis

| Plugin | O que faz |
|---|---|
| `leto-curvas` | A pessoa informa os tickers e recebe dois gráficos no padrão visual da casa: taxa indicativa e marcação em % do PU par. Quantos papéis quiser, de qualquer emissor. |

---

## Como usar (para quem vai só usar)

São dois passos, e a ordem importa pouco.

### 1. Preparar a máquina

Baixe este repositório e **dê duplo clique em `CONFIGURAR.bat`**.

Ele confere se você tem Python, instala a biblioteca de gráficos, pergunta pela sua
chave da API e testa a conexão. Leva menos de um minuto.

> **A chave é pessoal.** Peça a sua a quem administra o DataControl em vez de
> reaproveitar a de outra pessoa. Nenhum plugin daqui traz chave embutida.

### 2. Instalar o plugin no Claude

**Pelo aplicativo:** Diretório → Plugins → botão **+** → cole o endereço deste
repositório → Sincronizar. Depois instale `leto-curvas` na aba Pessoal.

**Pelo terminal:**

```
/plugin marketplace add <owner>/leto-plugins
/plugin install leto-curvas@leto
```

Abra uma sessão nova e peça, em português mesmo:

> faz o gráfico de TEPA11, TEPA12 e TEPA13

---

## Como publicar (para quem mantém)

Este diretório já é o repositório. Suba para o GitHub da empresa:

```bash
git remote add origin https://github.com/<owner>/leto-plugins.git
git push -u origin main
```

Depois disso, todo mundo usa `<owner>/leto-plugins` no passo 2 acima.

### Para atualizar um plugin

Edite os arquivos em `plugins/<nome>/`, **suba o `version`** no
`plugins/<nome>/.claude-plugin/plugin.json` e no `.claude-plugin/marketplace.json`,
e faça push. Quem já instalou recebe a atualização — sem bump de versão, não recebe.

### Para acrescentar um plugin novo

Crie `plugins/<novo>/` com o próprio `.claude-plugin/plugin.json` e acrescente uma
entrada em `.claude-plugin/marketplace.json` apontando para `./plugins/<novo>`.

### Repositório privado

Funciona normalmente, desde que quem for instalar tenha acesso de leitura e o `git`
autenticado na máquina.

---

## Estrutura

```
leto-plugins/
├── .claude-plugin/
│   └── marketplace.json          catálogo lido pelo Claude
├── plugins/
│   └── leto-curvas/
│       ├── .claude-plugin/plugin.json
│       └── skills/curvas-credito/
│           ├── SKILL.md           instruções que o Claude segue
│           ├── scripts/           extração e desenho
│           ├── assets/            fontes e logo da marca
│           └── references/        as armadilhas da base, documentadas
├── CONFIGURAR.bat                 prepara a máquina (Python, lib, chave)
└── configurar-ambiente.ps1
```

As fontes PP Neue Montreal e o logo vão dentro do plugin, então o gráfico sai no
padrão da marca mesmo em máquina onde nada esteja instalado.
