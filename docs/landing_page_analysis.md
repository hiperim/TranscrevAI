# Landing Page — Análise e Plano de Adequação

**Data:** 2026-04-27
**Arquivo alvo:** `static/Transcrev.ai Landing.html`
**Referência visual do app real:** `static/TranscrevAI_preview.png`

---

## 1. Mudanças sugeridas (waveform — revertidas, documentadas para referência)

A proposta era inserir uma waveform animada em Canvas vanilla JS no bloco de status de processamento do app (`index.html` + `app.js`).

### Arquivos que seriam alterados

| Arquivo | Mudança |
|---|---|
| `static/waveform.js` | Arquivo novo. `WaveformPlayer` com 48 barras, dois senos sobrepostos por barra, `requestAnimationFrame`. API: `WaveformPlayer.show()` / `WaveformPlayer.hide()` |
| `templates/index.html` | Canvas + container inseridos dentro de `#status`, antes do spinner. Tag `<script src="/static/waveform.js">` antes de `app.js` |
| `static/app.js` | `showStatus()`: aciona `show()` quando `progress < 100`, `hide()` quando `>= 100`. `clearResults()`: `hide()` ao resetar a UI |

### Por que foi revertido
A pedido do usuário — não há registro de motivo técnico. As mudanças eram não-destrutivas e reversíveis.

### Para reimplementar
Aplicar os três trechos acima. Nenhuma dependência externa — Canvas API puro.

---

## 2. Análise da landing page atual vs. app real

### Contexto visual observado
- **Landing page:** fundo branco, estilo Apple (Inter, Bento Box, cores `mist`/`fog`/`ink`), React + Framer Motion via CDN, Babel standalone no browser.
- **App real (`TranscrevAI_preview.png`):** fundo `#0A0A0A`/`#1C1C1C`, tema dark utilitário, labels em caps (`SPEAKER_01`), botões coloridos por ação (verde/amarelo/vermelho), fonte system-ui. Sem framework JS.

---

## 3. Problemas e dificuldades identificados

### 3.1 Babel Standalone — compilação em runtime

**O que é:** A landing usa `<script type="text/babel">` com Babel carregado via CDN (~300KB). O browser compila JSX para JS na primeira visita.

**Impacto prático:**
- Carregamento inicial lento (~1–2s extras em conexões médias).
- Inconsistente com a filosofia do backend (CPU otimizado, INT8, <5s startup).

**Opções de solução, por custo:**
1. **Mínimo esforço:** Pré-compilar o JSX uma vez com `npx babel` e substituir o `<script type="text/babel">` pelo JS gerado. Sem bundler, sem build pipeline.
2. **Esforço médio:** Migrar para Vite (dev server + build em segundos). Gera um bundle minificado.
3. **Máximo controle:** Reescrever em Vanilla JS/Canvas (como o `waveform.js` proposto). Elimina React e Framer Motion da landing.

**Recomendação:** Opção 1 enquanto o projeto está em portfólio/demo. Opção 3 se a landing for para produção real.

---

### 3.2 Dados mockados no componente WaveToText

**O que é:** O componente interativo usa `TRANSCRIPT_LINES` estático com nomes fictícios ("Ana", "Léo") e texto de reunião corporativa genérica.

**Inconsistência com o app real:**
- O preview mostra `SPEAKER_01` com o texto real da fala gravada ("Bem-vindo! Este é o TranscrevAI...").
- A landing simula diarização com 2 speakers nomeados; o app detecta N speakers sem nome prévio.

**Solução recomendada:**
Substituir `TRANSCRIPT_LINES` pelo conteúdo real do `TranscrevAI_preview.png`:

```js
const TRANSCRIPT_LINES = [
  { speaker: "SPEAKER_01", text: "Bem-vindo! Este é o TranscrevAI, meu aplicativo de transcrição de áudio com processamento 100% local," },
  { speaker: "SPEAKER_01", text: "em conformidade com a Lei Geral de Proteção de Dados Brasileira." },
  { speaker: "SPEAKER_01", text: "Por meio de inteligência artificial, o aplicativo identifica quem disse o quê e quando em uma gravação," },
  { speaker: "SPEAKER_01", text: "seja por envio de arquivo ou gravação ao vivo feita pelo usuário," },
  { speaker: "SPEAKER_01", text: "sem enviar nenhum dado para servidores externos." },
];
```

Isso torna a demo autentica — é o output real do próprio app.

---

### 3.3 Conflito de identidade visual (Apple-esque vs. dark utilitário)

**Divergências concretas observadas:**

| Token | Landing page | App real |
|---|---|---|
| Background | `#FFFFFF` / `#F5F5F7` | `#0A0A0A` / `#1C1C1C` |
| Texto principal | `#000000` | `#E8E8E8` |
| Fonte | Inter 800, letter-spacing -0.055em | system-ui, peso 400–600 |
| Border-radius | 28px (cards grandes) | 8–12px |
| Labels de speaker | "Ana", "Léo" (nomes) | `SPEAKER_01` (caps técnico) |
| Botões | Preto arredondado, minimalista | Verde/amarelo/vermelho por estado |

**Risco:** Usuário chega pela landing esperando interface clean/branca e encontra app dark/técnico. Quebra de expectativa.

**Opções:**
- A) Manter landing white como "vitrine de marketing" e aceitar a diferença (válido para portfólio).
- B) Escurecer a landing para `#0A0A0A` com texto `#E8E8E8` — alinha com o app e mantém coerência. Custo: trocar as classes Tailwind de cor (`bg-paper`→`bg-ink`, `text-black`→`text-white`, `bg-mist`→`bg-[#1C1C1C]`).
- C) Criar uma seção na landing que exiba o screenshot real (`TranscrevAI_preview.png`) como prova de funcionamento — ancoragem na realidade sem redesign.

**Recomendação para portfólio:** Opção C de imediato (mais rápido), depois B se quiser consistência total.

---

### 3.4 Fragmentação / manutenibilidade

**Situação atual:**
- App: lógica em `app.js` + estilos em `styles.css` (separados, versionados).
- Landing: tudo embutido num HTML de ~30KB — CSS inline via Tailwind CDN, JSX dentro de `<script>`, componentes React definidos no mesmo arquivo.

**Riscos concretos:**
- Editar a animação da waveform requer navegar ~400 linhas de HTML misturado com CSS e JS.
- Sem source map, erros no console apontam para linhas do Babel compilado, não do fonte original.
- Se `styles.css` do app for atualizado, a landing não herda — duplicação de estilos é inevitável.

**Solução mínima:** Não há urgência de refatorar enquanto é portfólio. Documentar aqui que os dois sistemas de estilo são **independentes por design**.

---

### 3.5 SEO e Acessibilidade

**SEO:**
- Tudo renderizado via `ReactDOM.createRoot(#root)` — bots que não executam JS verão uma página vazia.
- Para portfólio não é crítico (recrutador acessa via link direto, não por busca orgânica).
- Se virar produto: usar SSR (Next.js) ou pré-render estático.

**Acessibilidade — gaps concretos:**
- O scrubber `<input type="range">` tem `aria-label="Alternar"` no botão adjacente, mas o range em si não tem `aria-label` nem `aria-valuetext`.
- Os chips flutuantes no `PrivacyVisual` são `<motion.span>` sem role — invisíveis para leitores de tela.
- Correção mínima: adicionar `aria-label="Progresso da transcrição"` no range e `role="img" aria-label="Recursos de segurança"` no container de chips.

---

## 4. Priorização sugerida

| # | Mudança | Esforço | Impacto |
|---|---|---|---|
| 1 | Substituir `TRANSCRIPT_LINES` pelo texto real do app | 5 min | Alto — autenticidade imediata |
| 2 | Adicionar screenshot real (`TranscrevAI_preview.png`) na landing | 15 min | Alto — prova concreta do produto |
| 3 | Ajustar labels de speaker para `SPEAKER_01` no componente | 5 min | Médio — consistência técnica |
| 4 | Adicionar `aria-label` no scrubber e chips | 10 min | Médio — acessibilidade básica |
| 5 | Escurecer paleta da landing para dark (opção B) | 1–2h | Médio — coerência visual |
| 6 | Pré-compilar Babel offline e remover CDN | 30 min | Médio — performance de carregamento |
| 7 | Extrair JS/CSS para arquivos separados | 2–4h | Baixo agora, alto se virar produto |

---

## 5. O que NÃO mudar

- Esquema de cores da landing pode permanecer white (decisão do usuário).
- Estrutura de seções (Hero, Bento, CTA, Footer) está bem organizada.
- Animações Framer Motion funcionam bem e agregam valor visual para portfólio.
- `app.js` e `styles.css` do app não devem ser tocados para adequar a landing.
