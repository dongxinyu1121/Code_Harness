"""受限子 Agent 委派。"""


def delegate(args, create_child_agent, history_text, clip):
    task = str(args.get("task", "")).strip()
    if not task:
        raise ValueError("task must not be empty")
    child = create_child_agent(args)
    child.session["memory"]["task"] = task
    child.session["memory"]["notes"] = [clip(history_text(), 300)]
    return "delegate_result:\n" + child.ask(task)
