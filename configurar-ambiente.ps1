# Prepara a máquina para usar os plugins da Leto.
#
# NÃO instala o plugin: quem faz isso é o próprio Claude, pelo marketplace.
# Este script cuida só do que o Claude não resolve sozinho — Python, a
# biblioteca de gráficos e a chave da API — e testa a conexão no fim.
#
# Uso: duplo clique em CONFIGURAR.bat

param([switch]$NaoInterativo)

$ErrorActionPreference = "Stop"
$problemas = @()

function Titulo($t) { Write-Host ""; Write-Host "  $t" -ForegroundColor White }
function Ok($t)     { Write-Host "  [ok]   $t" -ForegroundColor Green }
function Aviso($t)  { Write-Host "  [!]    $t" -ForegroundColor Yellow }
function Erro($t)   { Write-Host "  [erro] $t" -ForegroundColor Red }

Write-Host ""
Write-Host "  ============================================================"
Write-Host "   Leto Capital - preparar ambiente para os plugins"
Write-Host "  ============================================================"

Titulo "1/4  Python"
$py = $null
foreach ($cmd in @("python", "python3", "py")) {
    $g = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($g) {
        $v = & $cmd -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $v) { $py = $cmd; break }
    }
}
if ($py) { Ok "$py $v encontrado" }
else {
    Erro "Python nao encontrado."
    Write-Host "         Instale em https://python.org/downloads (marque 'Add to PATH')."
    $problemas += "python"
}

Titulo "2/4  Biblioteca de graficos (matplotlib)"
if ($py) {
    & $py -c "import matplotlib" 2>$null
    if ($LASTEXITCODE -eq 0) {
        Ok "matplotlib $(& $py -c 'import matplotlib; print(matplotlib.__version__)') ja instalado"
    } else {
        Write-Host "         instalando, pode demorar um minuto..."
        & $py -m pip install --quiet --disable-pip-version-check matplotlib
        & $py -c "import matplotlib" 2>$null
        if ($LASTEXITCODE -eq 0) { Ok "matplotlib instalado" }
        else { Erro "nao consegui instalar"; $problemas += "matplotlib" }
    }
} else { Aviso "pulado, sem Python" }

Titulo "3/4  Chave da API do DataControl"
$chave = $env:DATA_CONTROL_API_KEY
if (-not $chave) { $chave = [Environment]::GetEnvironmentVariable("DATA_CONTROL_API_KEY", "User") }
if (-not $chave) {
    foreach ($c in @("C:\ProgramData\DataControl\api_key.txt",
                     (Join-Path $env:USERPROFILE ".datacontrol\api_key.txt"))) {
        if (Test-Path $c) { $chave = (Get-Content $c -Raw).Trim(); if ($chave) { break } }
    }
}
if ($chave) {
    Ok "chave encontrada (termina em ...$($chave.Substring([Math]::Max(0,$chave.Length-4))))"
} elseif ($NaoInterativo) {
    Aviso "nenhuma chave configurada"; $problemas += "chave"
} else {
    Aviso "nenhuma chave configurada."
    Write-Host "         A chave e pessoal: peca a sua a quem administra o DataControl."
    Write-Host "         Nao reaproveite a de outra pessoa."
    Write-Host ""
    $r = Read-Host "         Quer configurar agora? (s/N)"
    if ($r -match '^[sSyY]') {
        $sec = Read-Host "         Cole a chave (nao aparece na tela)" -AsSecureString
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
        try { $txt = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr).Trim() }
        finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
        if ($txt) {
            [Environment]::SetEnvironmentVariable("DATA_CONTROL_API_KEY", $txt, "User")
            $env:DATA_CONTROL_API_KEY = $txt
            $chave = $txt
            Ok "chave gravada na sua conta de usuario"
        } else { Aviso "nada digitado"; $problemas += "chave" }
    } else {
        Write-Host ""
        Write-Host "         Para configurar depois:" -ForegroundColor Gray
        Write-Host '         [Environment]::SetEnvironmentVariable("DATA_CONTROL_API_KEY", "<sua chave>", "User")' -ForegroundColor Gray
        $problemas += "chave"
    }
}

Titulo "4/4  Teste de conexao"
if (-not $py -or -not $chave) {
    Aviso "pulado - resolva os itens acima primeiro"
} else {
    $mod = Join-Path $PSScriptRoot "plugins\leto-curvas\skills\curvas-credito\scripts"
    $teste = @"
import sys; sys.path.insert(0, r'$mod')
import datacontrol as dc
print('OK %d datasets visiveis' % dc.get('/api/v1/data', page_size=1).get('count', 0))
"@
    $out = & $py -c $teste 2>&1
    if ($LASTEXITCODE -eq 0) { Ok "API respondeu - $out" }
    else {
        Erro "a API nao respondeu como esperado:"
        $out | ForEach-Object { Write-Host "         $_" -ForegroundColor Red }
        $problemas += "api"
    }
    Get-ChildItem $mod -Directory -ErrorAction SilentlyContinue |
        Where-Object Name -eq "__pycache__" |
        ForEach-Object { try { [IO.Directory]::Delete($_.FullName, $true) } catch { } }
}

Write-Host ""
Write-Host "  ------------------------------------------------------------"
if ($problemas.Count -eq 0) {
    Write-Host "   Ambiente pronto." -ForegroundColor Green
    Write-Host ""
    Write-Host "   Agora instale o plugin pelo Claude. No app:"
    Write-Host "     Diretorio > Plugins > + > cole o repositorio" -ForegroundColor Cyan
    Write-Host "   Ou no terminal:"
    Write-Host "     /plugin marketplace add <owner>/leto-plugins" -ForegroundColor Cyan
    Write-Host "     /plugin install leto-curvas@leto" -ForegroundColor Cyan
} else {
    Write-Host "   Pendencias: $($problemas -join ', ')" -ForegroundColor Yellow
}
Write-Host "  ------------------------------------------------------------"
Write-Host ""
if (-not $NaoInterativo) { try { Read-Host "  Pressione Enter para fechar" | Out-Null } catch { } }
exit $(if ($problemas.Count -eq 0) { 0 } else { 1 })
