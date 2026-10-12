// Degradação do módulo /enade-time: API parada, banco parado (503 com CORS) e benchmark vazio.
// ATENÇÃO: este roteiro derruba e religa a API na porta 8002 e o container do Postgres
// (docker stop/start). Rode só em ambiente de desenvolvimento.
import { execSync, spawn } from 'node:child_process'
import { chromium } from 'playwright-core'

import { API, BASE, CHROME, CONTAINER_PG, OUT, RAIZ_ENADEX, criarVerificador } from './config.mjs'

const { check, encerrar } = criarVerificador()
const HEALTH = `${API}/health`
const dorme = (ms) => new Promise((r) => setTimeout(r, ms))

function pidsDaPorta(porta) {
  try {
    const saida = execSync(`netstat -ano | findstr :${porta} | findstr LISTENING`, { encoding: 'utf8' })
    return [...new Set(saida.split('\n').map((l) => l.trim().split(/\s+/).pop()).filter(Boolean))]
  } catch {
    return []
  }
}
const pararApi = () => {
  for (const pid of pidsDaPorta(8002)) {
    try {
      execSync(`taskkill /PID ${pid} /F`, { stdio: 'ignore' })
    } catch {
      /* já encerrado */
    }
  }
}
async function subirApi() {
  const processo = spawn('python', ['enade_time/enade_time_rotas.py'], {
    cwd: RAIZ_ENADEX,
    env: { ...process.env, PYTHONPATH: '.' },
    detached: true,
    stdio: 'ignore',
  })
  processo.unref()
  for (let i = 0; i < 40; i++) {
    try {
      const r = await fetch(HEALTH)
      if (r.status === 200 || r.status === 503) return
    } catch {
      /* ainda subindo */
    }
    await dorme(500)
  }
  throw new Error('API não subiu')
}
async function esperarHealth200() {
  for (let i = 0; i < 40; i++) {
    try {
      if ((await fetch(HEALTH)).status === 200) return true
    } catch {
      /* ainda indisponível */
    }
    await dorme(1000)
  }
  return false
}

const browser = await chromium.launch({ executablePath: CHROME, headless: true })
const page = await (await browser.newContext({ viewport: { width: 1280, height: 800 } })).newPage()
const texto = () => page.locator('body').innerText()

await page.goto(`${BASE}/enade-time/enade/anual`)
await page.locator('.recharts-surface').first().waitFor({ timeout: 15000 })
check('Base: dados carregados', true)

// 1) API parada
pararApi()
await dorme(1500)
await page.reload()
await page.getByText('API offline').waitFor({ timeout: 20000 }).catch(() => {})
check('API parada: pill "API offline"', (await texto()).includes('API offline'))
await page.getByText('Erro ao carregar dados').first().waitFor({ timeout: 20000 }).catch(() => {})
const t = await texto()
check('API parada: ErrorState com a URL da API', t.includes('API do ENADE-Time indisponível em'))
check('API parada: ErrorState com o comando para subir (porta 8002)', t.includes('enade_time_rotas.py'))
await page.screenshot({ path: `${OUT}/degradacao-api-offline.png` })

// 2) API volta e "Tentar novamente" funciona sem recarregar a página
await subirApi()
await esperarHealth200()
await page.getByRole('button', { name: 'Tentar novamente' }).first().click()
await page.locator('.recharts-surface').first().waitFor({ timeout: 20000 }).catch(() => {})
check('API voltou: "Tentar novamente" recarrega os dados', (await page.locator('.recharts-surface').count()) >= 1)

// 3) Postgres parado => 503 tratado (não vira "API offline")
execSync(`docker stop ${CONTAINER_PG}`, { stdio: 'ignore' })
await dorme(2000)
await page.reload()
await page.getByText('Banco indisponível').waitFor({ timeout: 20000 }).catch(() => {})
check('Banco parado: pill "Banco indisponível" (503)', (await texto()).includes('Banco indisponível') && !(await texto()).includes('API offline'))
await page.getByText('Erro ao carregar dados').first().waitFor({ timeout: 20000 }).catch(() => {})
check('Banco parado: ErrorState "Banco do ENADE-Time indisponível"', (await texto()).includes('Banco do ENADE-Time indisponível'))
await page.screenshot({ path: `${OUT}/degradacao-banco-503.png` })

// 4) Postgres volta sem reiniciar a API
execSync(`docker start ${CONTAINER_PG}`, { stdio: 'ignore' })
for (let i = 0; i < 40; i++) {
  const s = execSync(`docker inspect -f "{{.State.Health.Status}}" ${CONTAINER_PG}`, { encoding: 'utf8' }).trim()
  if (s === 'healthy') break
  await dorme(2000)
}
await dorme(6500) // fim do cooldown da API
await esperarHealth200()
await page.getByRole('button', { name: 'Tentar novamente' }).first().click()
await page.locator('.recharts-surface').first().waitFor({ timeout: 20000 }).catch(() => {})
check('Banco voltou: dados reaparecem sem reiniciar a API', (await page.locator('.recharts-surface').count()) >= 1)
await page.reload()
await page.getByText('API conectada').waitFor({ timeout: 20000 }).catch(() => {})
check('Banco voltou: pill volta a "API conectada"', (await texto()).includes('API conectada'))

// 5) Benchmark vazio => estado vazio explicativo
await page.route('**/api/enade-time/benchmark/comparativo*', (r) =>
  r.fulfill({
    status: 200,
    contentType: 'application/json',
    headers: { 'access-control-allow-origin': '*' },
    body: JSON.stringify({
      baseline_sequencial_id: null,
      tempo_baseline_seg: null,
      throughput_baseline_lps: null,
      cpu_count_maquina: null,
      itens: [],
      resumo: [],
    }),
  }),
)
await page.goto(`${BASE}/enade-time/spd/comparativo`)
await page.getByText('Nenhuma execução de benchmark carregada').waitFor({ timeout: 15000 }).catch(() => {})
check('Benchmark vazio: EmptyState explicativo', (await texto()).includes('Nenhuma execução de benchmark carregada'))
await page.screenshot({ path: `${OUT}/degradacao-benchmark-vazio.png` })

await browser.close()
encerrar()
