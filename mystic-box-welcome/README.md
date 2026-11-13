# Mystic Box: landing page

Página pública de apresentação do jogo em **https://mystic-box-welcome.geskee.com.br**
(React + Vite, mesmo tema "Grimório Celestial" do jogo).

## O que tem

- Hero com a caixa 3D animada e personagens saindo dela.
- Boato da semana com contagem regressiva.
- Como jogar (seis pilares), galeria de campeões com filtro, mapa de Aethra
  clicável, crônica do mundo, chances do sorteio e roda dos elementos.
- **Notas de lançamento** (`src/releases.js`).

## Regras do jogo continuam no backend

A landing só lê as rotas públicas `GET /world` e `GET /rules` (sem login). Todo
número exibido (chances, tempo de espera, quantidade de cartas, multiplicadores do
boato, vantagem de elemento...) vem dessas respostas. Se a API não responder, as
seções que dependem dela simplesmente não aparecem.

As ilustrações das cartas e o mapa são lidos de `../mystic-box/src/assets`
(sem cópia); o build já os inclui.

## Notas de lançamento

`src/releases.js` é o histórico de novidades mostrado na página. **Todo PR que muda
algo que o jogador vê ganha uma nota lá**, em inglês e sem números de regra:

- mesmo dia do lançamento mais recente: nota nova nele;
- senão: lançamento novo no topo, com a próxima versão.

`src/releases.test.js` confere ordem, versões e campos.

## Rodar localmente

```powershell
cp .env.example .env     # preencha VITE_API_URL (a API de produção serve, as rotas são públicas)
npm install
npm run dev              # http://localhost:5174
```

Com a API local (`mystic-box-back/local/dev_server.py`): copie `.env.localapi.example`
para `.env.localapi` e rode `npm run dev:local`.

## Testes

```powershell
npx eslint src
npm test
npx vite build
```

## Publicar

Infra (uma vez, e quando `infra/template.yaml` mudar), em `infra/`:

```powershell
sam validate --lint
sam deploy
```

A stack `mystic-box-welcome` cria o bucket (privado), o CloudFront com o certificado
`*.geskee.com.br` que já existe e os registros A/AAAA na hosted zone do
`geskee.com.br`. É independente da stack do jogo (`mystic-box-frontend`).

Conteúdo, em `mystic-box-welcome/` com o `.env` de produção:

```powershell
npm run deploy
```

Mesmo script do jogo: assets com hash com cache de 1 ano, `index.html` com
`no-cache` e invalidação só do que não tem hash.
