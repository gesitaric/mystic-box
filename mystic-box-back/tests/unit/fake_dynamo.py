"""DynamoDB em memória para testes, com as expressões que as Lambdas usam.

Entende condições simples (`a = :v`, `<>`, `<=`, `<`, `>=`, `>`,
`attribute_exists`, `attribute_not_exists`, ligadas por AND/OR sem
parênteses), atualizações `SET a = :v, ...` e `ADD a :v, ...`, consultas por
igualdade da chave (tabela ou índice) com FilterExpression e transações
(Put, Delete, Update e ConditionCheck) com CancellationReasons.
"""

import copy
import re

from botocore.exceptions import ClientError

COMPARISON = re.compile(r"^(#?\w+)\s*(=|<>|<=|>=|<|>)\s*(:\w+)$")
FUNCTION = re.compile(r"^(attribute_exists|attribute_not_exists)\((#?\w+)\)$")


def _value(attribute):
    if "N" in attribute:
        return float(attribute["N"])
    return attribute.get("S")


class FakeDynamo:
    def __init__(self, keys):
        """`keys`: {tabela: (chave de partição, chave de ordenação ou None)}."""
        self.keys = keys
        self.tables = {name: {} for name in keys}
        self.calls = []

    # ------------------------------------------------------------ apoio ---

    def _key(self, table, item):
        hash_key, range_key = self.keys[table]
        return (item[hash_key]["S"], item[range_key]["S"] if range_key else None)

    def _check(self, item, expression, names, values):
        if not expression:
            return True
        names = names or {}
        values = values or {}

        def resolve(name):
            return names.get(name, name)

        def term(text):
            text = text.strip()
            match = FUNCTION.match(text)
            if match:
                exists = item is not None and resolve(match.group(2)) in item
                return exists if match.group(1) == "attribute_exists" else not exists
            match = COMPARISON.match(text)
            if not match:
                raise ValueError(f"Unsupported condition: {text}")
            if item is None or resolve(match.group(1)) not in item:
                return False
            left = _value(item[resolve(match.group(1))])
            right = _value(values[match.group(3)])
            op = match.group(2)
            return {
                "=": left == right,
                "<>": left != right,
                "<=": left <= right,
                "<": left < right,
                ">=": left >= right,
                ">": left > right,
            }[op]

        return any(
            all(term(part) for part in clause.split(" AND "))
            for clause in expression.split(" OR ")
        )

    def _fail(self, operation):
        raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, operation)

    def _apply_update(self, item, expression, names, values):
        names = names or {}
        sections = re.split(r"\b(SET|ADD)\b", expression)
        mode = None
        for part in sections:
            part = part.strip()
            if part in ("SET", "ADD"):
                mode = part
                continue
            if not part:
                continue
            for assignment in part.split(","):
                assignment = assignment.strip()
                if mode == "SET":
                    name, value = [x.strip() for x in assignment.split("=")]
                    item[names.get(name, name)] = copy.deepcopy(values[value])
                else:
                    name, value = assignment.split()
                    name = names.get(name, name)
                    old = float(item.get(name, {"N": "0"})["N"])
                    total = old + float(values[value]["N"])
                    item[name] = {"N": str(int(total))}

    # ---------------------------------------------------------- leitura ---

    def get_item(self, TableName, Key, **_):
        self.calls.append(("get_item", TableName))
        item = self.tables[TableName].get(self._key(TableName, Key))
        return {"Item": copy.deepcopy(item)} if item else {}

    def batch_get_item(self, RequestItems):
        responses = {}
        for table, request in RequestItems.items():
            responses[table] = [
                copy.deepcopy(self.tables[table][self._key(table, key)])
                for key in request["Keys"]
                if self._key(table, key) in self.tables[table]
            ]
        return {"Responses": responses}

    def query(self, TableName, KeyConditionExpression, ExpressionAttributeValues,
              FilterExpression=None, ExpressionAttributeNames=None, **_):
        match = re.match(r"^(\w+)\s*=\s*(:\w+)", KeyConditionExpression)
        attribute, placeholder = match.groups()
        wanted = ExpressionAttributeValues[placeholder]["S"]
        items = [
            copy.deepcopy(item)
            for item in self.tables[TableName].values()
            if item.get(attribute, {}).get("S") == wanted
            and self._check(item, FilterExpression, ExpressionAttributeNames,
                            ExpressionAttributeValues)
        ]
        return {"Items": items}

    # ---------------------------------------------------------- escrita ---

    def _put(self, put):
        table = put["TableName"]
        current = self.tables[table].get(self._key(table, put["Item"]))
        if not self._check(current, put.get("ConditionExpression"),
                           put.get("ExpressionAttributeNames"),
                           put.get("ExpressionAttributeValues")):
            return False
        return lambda: self.tables[table].__setitem__(
            self._key(table, put["Item"]), copy.deepcopy(put["Item"])
        )

    def _delete(self, delete):
        table = delete["TableName"]
        key = self._key(table, delete["Key"])
        current = self.tables[table].get(key)
        if not self._check(current, delete.get("ConditionExpression"),
                           delete.get("ExpressionAttributeNames"),
                           delete.get("ExpressionAttributeValues")):
            return False
        return lambda: self.tables[table].pop(key, None)

    def _update(self, update):
        table = update["TableName"]
        key = self._key(table, update["Key"])
        current = self.tables[table].get(key)
        if not self._check(current, update.get("ConditionExpression"),
                           update.get("ExpressionAttributeNames"),
                           update.get("ExpressionAttributeValues")):
            return False

        def apply():
            item = self.tables[table].setdefault(key, copy.deepcopy(update["Key"]))
            self._apply_update(item, update["UpdateExpression"],
                               update.get("ExpressionAttributeNames"),
                               update.get("ExpressionAttributeValues"))

        return apply

    def _condition_check(self, check):
        table = check["TableName"]
        current = self.tables[table].get(self._key(table, check["Key"]))
        if not self._check(current, check.get("ConditionExpression"),
                           check.get("ExpressionAttributeNames"),
                           check.get("ExpressionAttributeValues")):
            return False
        return lambda: None

    def put_item(self, **put):
        apply = self._put(put)
        if not apply:
            self._fail("PutItem")
        apply()

    def delete_item(self, **delete):
        apply = self._delete(delete)
        if not apply:
            self._fail("DeleteItem")
        apply()

    def update_item(self, **update):
        apply = self._update(update)
        if not apply:
            self._fail("UpdateItem")
        apply()

    def transact_write_items(self, TransactItems):
        self.calls.append(("transact_write_items", len(TransactItems)))
        handlers = {"Put": self._put, "Delete": self._delete, "Update": self._update,
                    "ConditionCheck": self._condition_check}
        applies = []
        reasons = []
        for entry in TransactItems:
            (kind, request), = entry.items()
            apply = handlers[kind](request)
            applies.append(apply)
            reasons.append({"Code": "None" if apply else "ConditionalCheckFailed"})
        if not all(applies):
            raise ClientError(
                {"Error": {"Code": "TransactionCanceledException"},
                 "CancellationReasons": reasons},
                "TransactWriteItems",
            )
        for apply in applies:
            apply()
