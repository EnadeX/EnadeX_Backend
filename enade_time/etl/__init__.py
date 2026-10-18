"""
Módulo `etl` — funções puras reutilizáveis pelo benchmark sequencial/paralelo.

O conteúdo aqui deve ser importável de processos workers do
ProcessPoolExecutor (no Windows, via spawn). Por isso nada de I/O em disco
nem de estado global mutável.
"""
