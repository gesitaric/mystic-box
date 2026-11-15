"""Painel do Grafana local (local/monitoring): confere que ele acompanha o template."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "template.yaml"
DASHBOARD = ROOT / "local" / "monitoring" / "grafana" / "dashboards" / "mystic-box-producao.json"
DATASOURCE = ROOT / "local" / "monitoring" / "grafana" / "provisioning" / "datasources" / "cloudwatch.yml"


def _all_panels(dashboard):
    for panel in dashboard["panels"]:
        yield panel
        yield from panel.get("panels", [])


def _template_log_groups():
    text = TEMPLATE.read_text(encoding="utf-8")
    names = re.findall(r'LogGroupName: !Sub "/aws/lambda/\$\{AWS::StackName\}/(\w+)"', text)
    assert names, "nenhum grupo de log encontrado no template.yaml"
    return {f"/aws/lambda/mystic-box-back/{name}" for name in names}


def test_logs_panel_reads_every_lambda_log_group():
    """Lambda nova no template: o grupo de log dela precisa entrar no painel de logs."""
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    log_targets = [t for p in _all_panels(dashboard) for t in p.get("targets", []) if t.get("queryMode") == "Logs"]
    assert log_targets, "o painel não tem consulta de logs"
    for target in log_targets:
        in_panel = {group["name"] for group in target["logGroups"]}
        assert in_panel == _template_log_groups()
        # O Logs Insights aceita no máximo 50 grupos por consulta.
        assert len(in_panel) <= 50


def test_every_query_uses_the_provisioned_datasource():
    uid = re.search(r"^\s*uid:\s*(\S+)", DATASOURCE.read_text(encoding="utf-8"), re.M).group(1)
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    panels = [p for p in _all_panels(dashboard) if p["type"] != "row"]
    assert panels
    for panel in panels:
        assert panel["datasource"]["uid"] == uid, panel["title"]
        for target in panel["targets"]:
            assert target["datasource"]["uid"] == uid, panel["title"]
