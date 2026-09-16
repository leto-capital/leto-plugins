@echo off
rem Prepara a maquina para usar os plugins da Leto.
rem Duplo clique aqui.

chcp 65001 > nul
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0configurar-ambiente.ps1"

if errorlevel 1 (
  echo.
  echo   Terminou com pendencias. Veja as mensagens acima.
  pause
)
