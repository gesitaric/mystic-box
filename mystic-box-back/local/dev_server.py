"""Servidor local para testes: roda as Lambdas do template.yaml sem Docker por Lambda.

Só o DynamoDB roda em Docker (DynamoDB Local, ver docker-compose.yml). As Lambdas
são carregadas direto deste processo, chamadas com eventos no formato do API
Gateway (REST). Rotas, variáveis de ambiente e tabelas são lidas do
`template.yaml`; nenhuma regra do jogo é copiada para cá.

Diferenças em relação à AWS (só para uso local):
- O token do Cognito NÃO tem a assinatura verificada: o `sub` é lido do payload
  do JWT (checando só `exp` e `token_use`). Por isso o servidor escuta só em
  127.0.0.1.
- A chave do summon token é fixa (LOCAL_SUMMON_SECRET), sem Secrets Manager.
- Credenciais da AWS são falsas e todo endpoint aponta para o DynamoDB Local,
  então nada aqui acessa a conta real.

Uso (a partir de mystic-box-back/):
    python local/dev_server.py
"""

import argparse
import base64
import importlib.util
import json
import os
import re
import sys
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import yaml

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = BACKEND_DIR / "template.yaml"

DEFAULT_DYNAMODB_URL = "http://localhost:8000"
DEFAULT_SECRET = "local-dev-summon-secret"

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


# ---------------------------------------------------------------- template ---

class _CfnLoader(yaml.SafeLoader):
    """SafeLoader que aceita as tags do CloudFormation (!Ref, !GetAtt, !Sub...)."""


def _cfn_tag(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    else:
        value = loader.construct_mapping(node, deep=True)
    return {tag_suffix: value}


_CfnLoader.add_multi_constructor("!", _cfn_tag)


def load_template():
    with TEMPLATE_PATH.open(encoding="utf-8") as handle:
        return yaml.load(handle, Loader=_CfnLoader)


def resolve_env_value(value):
    # Localmente o nome de cada tabela/recurso é o próprio ID lógico.
    if isinstance(value, dict) and "Ref" in value:
        return value["Ref"]
    return str(value)


def read_tables(template):
    return {
        name: resource["Properties"]
        for name, resource in template["Resources"].items()
        if resource["Type"] == "AWS::DynamoDB::Table"
    }


def read_functions(template):
    global_env = (
        template.get("Globals", {}).get("Function", {}).get("Environment", {}).get("Variables", {})
    )
    functions = []
    for name, resource in template["Resources"].items():
        if resource["Type"] != "AWS::Serverless::Function":
            continue
        props = resource["Properties"]
        env = {**global_env, **props.get("Environment", {}).get("Variables", {})}
        routes = []
        for event in props.get("Events", {}).values():
            if event["Type"] != "Api":
                continue
            event_props = event["Properties"]
            routes.append(
                {
                    "method": event_props["Method"].upper(),
                    "path": event_props["Path"],
                    "auth": bool(event_props.get("Auth", {}).get("Authorizer")),
                }
            )
        functions.append(
            {
                "name": name,
                "code_dir": BACKEND_DIR / props["CodeUri"],
                "handler": props["Handler"],
                "env": {key: resolve_env_value(value) for key, value in env.items()},
                "routes": routes,
            }
        )
    return functions


# --------------------------------------------------------------- ambiente ---

def configure_aws_env(dynamodb_url):
    # Credenciais falsas e endpoint local para TODOS os serviços: nada chega na AWS real.
    for key in ("AWS_PROFILE", "AWS_SESSION_TOKEN", "AWS_SECURITY_TOKEN"):
        os.environ.pop(key, None)
    os.environ["AWS_ACCESS_KEY_ID"] = "local"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "local"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    os.environ["AWS_REGION"] = "us-east-1"
    os.environ["AWS_ENDPOINT_URL"] = dynamodb_url


def apply_function_env(functions):
    """As Lambdas leem o ambiente ao importar; todas rodam no mesmo processo."""
    merged = {}
    for function in functions:
        for key, value in function["env"].items():
            if key in merged and merged[key] != value:
                raise SystemExit(
                    f"Variável {key} tem valores diferentes entre Lambdas "
                    f"({merged[key]!r} x {value!r}); o servidor local não suporta isso."
                )
            merged[key] = value
    for key, value in merged.items():
        # Permite sobrescrever no terminal, ex.: SUMMON_COOLDOWN_SECONDS=10.
        os.environ.setdefault(key, value)


def add_missing_indexes(client, name, props):
    """Índice novo no template numa tabela que já existe no banco local."""
    wanted = props.get("GlobalSecondaryIndexes") or []
    if not wanted:
        return
    table = client.describe_table(TableName=name)["Table"]
    existing = {index["IndexName"] for index in table.get("GlobalSecondaryIndexes", [])}
    for index in wanted:
        if index["IndexName"] in existing:
            continue
        used = {key["AttributeName"] for key in index["KeySchema"]}
        client.update_table(
            TableName=name,
            AttributeDefinitions=[
                definition
                for definition in props["AttributeDefinitions"]
                if definition["AttributeName"] in used
            ],
            GlobalSecondaryIndexUpdates=[{"Create": index}],
        )
        print(f"  indice criado: {name}.{index['IndexName']}")


def ensure_tables(tables):
    import boto3

    client = boto3.client("dynamodb")
    existing = set(client.list_tables()["TableNames"])
    for name, props in tables.items():
        if name in existing:
            add_missing_indexes(client, name, props)
            continue
        options = {}
        if props.get("GlobalSecondaryIndexes"):
            options["GlobalSecondaryIndexes"] = props["GlobalSecondaryIndexes"]
        client.create_table(
            TableName=name,
            AttributeDefinitions=props["AttributeDefinitions"],
            KeySchema=props["KeySchema"],
            BillingMode=props.get("BillingMode", "PAY_PER_REQUEST"),
            **options,
        )
        print(f"  tabela criada: {name}")


def load_handlers(functions, secret):
    sys.path.insert(0, str(BACKEND_DIR / "shared"))
    from mystic_shared import summon_token

    summon_token._secret = secret.encode()

    for function in functions:
        module_name, handler_name = function["handler"].rsplit(".", 1)
        spec = importlib.util.spec_from_file_location(
            f"local_lambda_{function['name']}",
            function["code_dir"] / f"{module_name}.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        function["callable"] = getattr(module, handler_name)


def build_routes(functions):
    routes = []
    for function in functions:
        for route in function["routes"]:
            pattern = re.sub(r"\\\{(\w+)\\\}", r"(?P<\1>[^/]+)", re.escape(route["path"]))
            routes.append({**route, "regex": re.compile(f"^{pattern}$"), "function": function})
    return routes


# ------------------------------------------------------------------- auth ---

def decode_claims(authorization):
    """Lê o payload do ID token do Cognito. Sem verificar assinatura (só local)."""
    if not authorization:
        return None
    token = authorization.split(" ", 1)[1] if authorization.lower().startswith("bearer ") else authorization
    try:
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError):
        return None
    if claims.get("token_use") != "id" or claims.get("exp", 0) < time.time() or not claims.get("sub"):
        return None
    return claims


# ------------------------------------------------------------------- http ---

class LambdaContext:
    def __init__(self, function_name):
        self.function_name = function_name
        self.aws_request_id = str(uuid.uuid4())
        self.memory_limit_in_mb = 512
        self.invoked_function_arn = f"arn:aws:lambda:us-east-1:000000000000:function:{function_name}"
        self._deadline = time.time() + 10

    def get_remaining_time_in_millis(self):
        return max(0, int((self._deadline - time.time()) * 1000))


def make_handler_class(routes):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _send(self, status, headers, body):
            data = body.encode() if isinstance(body, str) else (body or b"")
            self.send_response(status)
            for key, value in {**CORS_HEADERS, **(headers or {})}.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _dispatch(self):
            url = urlsplit(self.path)
            method = self.command
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length).decode() if length else None

            path_matches = [(r, r["regex"].match(url.path)) for r in routes]
            path_matches = [(r, m) for r, m in path_matches if m]
            if not path_matches:
                return self._send(404, {"Content-Type": "application/json"}, '{"message":"Not Found"}')

            route, match = next(((r, m) for r, m in path_matches if r["method"] == method), (None, None))
            if route is None:
                if method == "OPTIONS":
                    return self._send(200, {}, "")
                return self._send(403, {"Content-Type": "application/json"}, '{"message":"Missing Authentication Token"}')

            request_context = {
                "httpMethod": method,
                "resourcePath": route["path"],
                "path": f"/Prod{url.path}",
                "stage": "Prod",
                "requestId": str(uuid.uuid4()),
                "identity": {"sourceIp": self.client_address[0]},
            }
            if route["auth"]:
                claims = decode_claims(self.headers.get("Authorization"))
                if claims is None:
                    return self._send(401, {"Content-Type": "application/json"}, '{"message":"Unauthorized"}')
                request_context["authorizer"] = {"claims": claims}

            query = parse_qs(url.query, keep_blank_values=True)
            headers = dict(self.headers.items())
            event = {
                "resource": route["path"],
                "path": url.path,
                "httpMethod": method,
                "headers": headers,
                "multiValueHeaders": {k: [v] for k, v in headers.items()},
                "queryStringParameters": {k: v[-1] for k, v in query.items()} or None,
                "multiValueQueryStringParameters": query or None,
                "pathParameters": match.groupdict() or None,
                "stageVariables": None,
                "requestContext": request_context,
                "body": body,
                "isBase64Encoded": False,
            }

            function = route["function"]
            started = time.time()
            try:
                result = function["callable"](event, LambdaContext(function["name"]))
            except Exception:
                traceback.print_exc()
                return self._send(502, {"Content-Type": "application/json"}, '{"message":"Internal server error"}')

            elapsed = (time.time() - started) * 1000
            print(f"  -> {function['name']} {result.get('statusCode')} ({elapsed:.0f} ms)")
            out_headers = dict(result.get("headers") or {})
            out_headers.setdefault("Content-Type", "application/json")
            self._send(result.get("statusCode", 200), out_headers, result.get("body") or "")

        do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _dispatch

        def log_message(self, fmt, *args):
            print(f"{self.command} {self.path}")

    return Handler


def main():
    parser = argparse.ArgumentParser(description="API local do Mystic Box")
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--dynamodb-url", default=os.environ.get("LOCAL_DYNAMODB_URL", DEFAULT_DYNAMODB_URL))
    args = parser.parse_args()

    template = load_template()
    functions = read_functions(template)

    configure_aws_env(args.dynamodb_url)
    apply_function_env(functions)

    print(f"DynamoDB Local: {args.dynamodb_url}")
    try:
        ensure_tables(read_tables(template))
    except Exception as error:  # noqa: BLE001
        raise SystemExit(
            f"Não consegui acessar o DynamoDB Local em {args.dynamodb_url}: {error}\n"
            "Ele está rodando? (no Ubuntu/WSL: docker compose -f local/docker-compose.yml up -d)"
        )

    load_handlers(functions, os.environ.get("LOCAL_SUMMON_SECRET", DEFAULT_SECRET))
    routes = build_routes(functions)

    print("Rotas:")
    for route in routes:
        if route["method"] != "OPTIONS":
            lock = " (auth)" if route["auth"] else ""
            print(f"  {route['method']:5} {route['path']}{lock} -> {route['function']['name']}")
    print(f"SUMMON_COOLDOWN_SECONDS={os.environ.get('SUMMON_COOLDOWN_SECONDS')}")
    print(f"\nAPI local em http://localhost:{args.port}  (Ctrl+C para parar)")

    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler_class(routes))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
