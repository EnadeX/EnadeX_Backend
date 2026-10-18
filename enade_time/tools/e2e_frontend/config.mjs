// Configuração comum das verificações. Tudo pode ser trocado por variável de ambiente.
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const aqui = path.dirname(fileURLToPath(import.meta.url))

export const BASE = process.env.BASE_URL ?? 'http://localhost:3000' // EnadeX_Frontend (pnpm start/dev -p 3000)
export const API = process.env.API_URL ?? 'http://localhost:8002/api/enade-time'
export const RAIZ_ENADEX = process.env.ENADEX_DIR ?? path.resolve(aqui, '..', '..', '..')
export const CONTAINER_PG = process.env.PG_CONTAINER ?? 'enade_postgres'
export const OUT = path.join(aqui, 'out')
fs.mkdirSync(OUT, { recursive: true })

const candidatosChrome = [
  process.env.CHROME_PATH,
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  '/usr/bin/google-chrome',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
].filter(Boolean)

export const CHROME = candidatosChrome.find((c) => fs.existsSync(c))
if (!CHROME) throw new Error('Chrome/Edge não encontrado: defina CHROME_PATH.')

// Recursos que o layout raiz do grupo pede e não existem (sem public/ e fora da Vercel).
export const RUIDO_CONHECIDO = [/\/icon/i, /apple-icon/i, /_vercel\/insights/i, /favicon/i]

export function criarVerificador() {
  const resultados = []
  return {
    check(nome, ok, detalhe = '') {
      resultados.push({ nome, ok })
      console.log(`${ok ? 'PASS' : 'FAIL'}  ${nome}${detalhe ? '  — ' + detalhe : ''}`)
    },
    encerrar() {
      const falhas = resultados.filter((r) => !r.ok)
      console.log(`\n${resultados.length - falhas.length}/${resultados.length} verificações OK`)
      if (falhas.length) console.log('FALHAS:\n - ' + falhas.map((f) => f.nome).join('\n - '))
      process.exit(falhas.length ? 1 : 0)
    },
  }
}
