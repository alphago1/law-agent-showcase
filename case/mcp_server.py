"""Expose only the fictional contract, local browser actions and draft submission."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
STRING = {"type": "string", "minLength": 1}
STRING_LIST = {"type": "array", "items": STRING, "minItems": 1}


def schema(properties, required):
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


def tool(name, description, properties, required):
    return {"name": name, "description": description, "inputSchema": schema(properties, required)}


TOOLS = [
    tool("read_contract", "读取本案虚构合同原文与条款编号。", {}, []),
    tool("browse", "操作临汀项目资料室的本地浏览器。home 打开工作台，search 输入查询企业并点击查询，open 点击工作台记录。返回页面可见文字并自动存截图。",
         {"action": {"type": "string", "enum": ["home", "search", "open"]},
          "query": STRING, "record": STRING}, ["action"]),
    tool("submit", "把完整审查答卷保存为待主办律师复核的草稿。evidenceIds 只能引用你已点开的记录。",
         {"summary": STRING, "edits": {"type": "array", "minItems": 1,
          "items": schema({"clause": {"type": "string", "enum": ["P01", "P02", "P03", "P04"]},
                           "severity": {"type": "string", "enum": ["重大", "重要", "提示"]},
                           "replacement": STRING, "comment": STRING,
                           "evidenceIds": STRING_LIST},
                          ["clause", "severity", "replacement", "comment", "evidenceIds"])},
          "client_note": STRING_LIST, "pending": STRING_LIST},
         ["summary", "edits", "client_note", "pending"]),
]


def call_tool(name, arguments):
    if name == "read_contract":
        return (ROOT / "contract.json").read_text(encoding="utf-8")
    if name == "browse":
        action = arguments["action"]
        if action not in {"home", "search", "open"}:
            raise ValueError("Unknown action.")
        parameters = {"search": "query", "open": "record"}
        value = [arguments[parameters[action]]] if action in parameters else []
        result = subprocess.run([sys.executable, str(ROOT / "browser.py"), action, *value],
                                capture_output=True, encoding="utf-8", errors="replace", timeout=35)
        if result.returncode:
            raise ValueError(result.stderr.strip() or "Browser action failed.")
        return result.stdout
    if name == "submit":
        edits = arguments["edits"]
        edit_ids = [edit["clause"] for edit in edits]
        if len(set(edit_ids)) != len(edit_ids):
            raise ValueError("Each clause may appear only once.")
        events = ROOT / "trace/browser.jsonl"
        opened = {event["record"] for line in events.read_text(encoding="utf-8").splitlines()
                  if (event := json.loads(line))["action"] == "open"} if events.exists() else set()
        citations = {item for edit in edits for item in edit["evidenceIds"]}
        if not citations or citations - opened:
            raise ValueError("Cite record IDs from completed open actions only.")
        (ROOT / "submission.json").write_text(
            json.dumps(arguments, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return "答卷草稿已保存，等待主办律师复核。"
    raise ValueError("Unknown tool.")


def dispatch(method, params):
    if method == "initialize":
        version = params.get("protocolVersion")
        if version not in {"2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"}:
            version = "2025-11-25"
        return {"protocolVersion": version, "capabilities": {"tools": {}},
                "serverInfo": {"name": "fictional-c06", "version": "1.0.0"}}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        try:
            text = call_tool(params["name"], params.get("arguments", {}))
            return {"content": [{"type": "text", "text": text}]}
        except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired) as error:
            return {"isError": True, "content": [{"type": "text", "text": str(error)}]}
    raise NotImplementedError(method)


def main():
    for line in sys.stdin.buffer:
        message = json.loads(line)
        if "id" not in message:
            continue
        response = {"jsonrpc": "2.0", "id": message["id"]}
        try:
            response["result"] = dispatch(message["method"], message.get("params", {}))
        except NotImplementedError:
            response["error"] = {"code": -32601, "message": "Method not found"}
        sys.stdout.buffer.write((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))
        sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()

