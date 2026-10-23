import json, re, sys, importlib.util
spec = importlib.util.spec_from_file_location("check", sys.argv[1]); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
tests = json.load(open(sys.argv[2], encoding="utf-8"))
for t in tests:
    reply = open(f"{sys.argv[3]}/{t['id']}.md", encoding="utf-8").read()
    blocks = re.findall(r"```json\s*(.*?)```", reply, re.S)
    tail = reply[reply.rfind("```")+3:].strip() if blocks else ""
    analysis_has_code = reply.count("```") > 2
    try:
        obj = json.loads(blocks[-1])
    except Exception as e:
        print(t["id"], "PARSE FAIL", e); continue
    errs = m.check(obj, t["review_text"])
    if tail: errs.append(f"text after json: {tail[:30]}")
    if analysis_has_code: errs.append("analysis area contains code block")
    print(t["id"], "OK  " if not errs else "FAIL", obj["category"], obj["other_reason"], obj["uncertainty"], [(i["type"], i["aspect"], i["problem"]) for i in obj["issues"]], errs or "")
