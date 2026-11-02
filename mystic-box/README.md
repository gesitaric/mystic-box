# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.

## Configuracao (AWS Cognito + API)

1. Copie `.env.example` para `.env`.
2. Preencha com os valores exibidos nos outputs do stack `mystic-box-back`:
   - `VITE_API_URL`: `OpenBoxApi` sem o sufixo `/box/open` (ex.: `https://xxxx.execute-api.us-east-1.amazonaws.com/Prod`)
   - `VITE_COGNITO_USER_POOL_ID`: output `UserPoolId`
   - `VITE_COGNITO_CLIENT_ID`: output `UserPoolClientId`
3. Rode `npm run dev`.

### Rodar contra a API local (testes)

Use `npm run dev:local` com o `.env.localapi` (copie de `.env.localapi.example`).
O passo a passo completo (Docker, banco e API) está em `../mystic-box-back/local/README.md`.

Fluxo: qualquer pessoa pode puxar cartas sem login. O sorteio e feito no servidor, que devolve as cartas e um `summonToken` assinado. Apos a revelacao, se nao estiver autenticada, aparece a opcao de entrar/criar conta para guardar as cartas na colecao (o token vale por 30 minutos). Usuarios autenticados tem as cartas guardadas automaticamente. Na colecao, cada carta pode ser vendida pelo preco informado pela API.

**Importante:** o frontend nao define NENHUMA regra do jogo (precos, raridades, sorteio, saldo, tempo de espera). Ele so exibe o que a API devolve e envia intencoes (ex.: o `summonToken`, o `ownedCardId` da carta a vender). Veja o `CLAUDE.md` na raiz do repositorio.
