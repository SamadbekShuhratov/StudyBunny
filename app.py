from __future__ import annotations

import ast
import json
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from io import BytesIO
from typing import Any
from urllib.parse import quote

import streamlit as st
import litellm
from icalendar import Calendar, Event

DEFAULT_LANGUAGE = "Uzbek"


@dataclass
class ToolResult:
    ok: bool
    content: str


def init_state() -> None:
    if "events" not in st.session_state:
        st.session_state.events = []
    if "tasks" not in st.session_state:
        st.session_state.tasks = []
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "action_logs" not in st.session_state:
        st.session_state.action_logs = []


def parse_datetime(raw: str) -> datetime:
    return datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))


def urgency_for_date(target: datetime) -> str:
    days = (target.date() - datetime.now().date()).days
    if days <= 3:
        return "red"
    if days <= 7:
        return "yellow"
    return "green"


def calculator(expression: str) -> ToolResult:
    allowed_nodes = {
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Pow,
        ast.Mod,
        ast.USub,
        ast.UAdd,
        ast.FloorDiv,
    }

    def _check(node: ast.AST) -> None:
        if type(node) not in allowed_nodes:
            raise ValueError(f"Unsupported operation: {type(node).__name__}")
        for child in ast.iter_child_nodes(node):
            _check(child)

    try:
        parsed = ast.parse(expression, mode="eval")
        _check(parsed)
        value = eval(compile(parsed, "<calc>", "eval"), {"__builtins__": {}}, {})
        return ToolResult(True, str(value))
    except Exception as exc:
        return ToolResult(False, f"Calculator error: {exc}")


def add_event(
    title: str,
    event_type: str,
    start_iso: str,
    end_iso: str | None = None,
    repeat_weekly: bool = False,
    description: str = "",
) -> ToolResult:
    try:
        start_at = parse_datetime(start_iso)
        end_at = parse_datetime(end_iso) if end_iso else start_at + timedelta(hours=1)
        event = {
            "id": str(uuid.uuid4()),
            "title": title,
            "event_type": event_type,
            "start": start_at.isoformat(),
            "end": end_at.isoformat(),
            "repeat_weekly": bool(repeat_weekly),
            "description": description,
        }
        st.session_state.events.append(event)
        return ToolResult(True, f"Event added: {title} ({event_type})")
    except Exception as exc:
        return ToolResult(False, f"add_event error: {exc}")


def _occurrences_in_range(event: dict[str, Any], until: datetime) -> list[dict[str, Any]]:
    start = parse_datetime(event["start"])
    end = parse_datetime(event["end"])
    now = datetime.now(start.tzinfo)
    items = []

    if not event.get("repeat_weekly"):
        if now <= start <= until:
            items.append(event)
        return items

    cursor_start, cursor_end = start, end
    while cursor_start <= until:
        if cursor_start >= now:
            repeated = dict(event)
            repeated["start"] = cursor_start.isoformat()
            repeated["end"] = cursor_end.isoformat()
            items.append(repeated)
        cursor_start += timedelta(days=7)
        cursor_end += timedelta(days=7)

    return items


def get_upcoming(days: int = 7) -> ToolResult:
    try:
        now = datetime.now()
        until = now + timedelta(days=int(days))
        upcoming = []
        for event in st.session_state.events:
            upcoming.extend(_occurrences_in_range(event, until))
        upcoming.sort(key=lambda e: e["start"])
        return ToolResult(True, json.dumps(upcoming, ensure_ascii=False))
    except Exception as exc:
        return ToolResult(False, f"get_upcoming error: {exc}")


def add_tasks(event_title: str, tasks: list[str]) -> ToolResult:
    try:
        created = []
        for task_text in tasks:
            task = {
                "id": str(uuid.uuid4()),
                "event_title": event_title,
                "task": task_text,
                "done": False,
            }
            st.session_state.tasks.append(task)
            created.append(task_text)
        return ToolResult(True, f"Tasks added for {event_title}: {', '.join(created)}")
    except Exception as exc:
        return ToolResult(False, f"add_tasks error: {exc}")


def draft_email(recipient: str, subject: str, body: str) -> ToolResult:
    try:
        mailto_link = f"mailto:{quote(recipient)}?subject={quote(subject)}&body={quote(body)}"
        payload = {
            "recipient": recipient,
            "subject": subject,
            "body": body,
            "mailto": mailto_link,
            "notice": "Emails are never sent automatically.",
        }
        return ToolResult(True, json.dumps(payload, ensure_ascii=False))
    except Exception as exc:
        return ToolResult(False, f"draft_email error: {exc}")


def study_plan(subject: str, exam_date: str, hours_per_day: float = 2.0) -> ToolResult:
    try:
        exam = date.fromisoformat(exam_date)
        today = date.today()
        if exam <= today:
            return ToolResult(False, "study_plan error: exam_date must be in the future")

        days = (exam - today).days
        if days < 2:
            return ToolResult(False, "study_plan error: need at least 2 days before exam")

        plan = []
        for offset in range(days):
            current_day = today + timedelta(days=offset)
            if current_day == exam - timedelta(days=1):
                plan.append(
                    {
                        "date": current_day.isoformat(),
                        "subject": subject,
                        "task": "Revision day: summarize key formulas/concepts and solve mixed problems.",
                        "hours": hours_per_day,
                    }
                )
            elif current_day < exam:
                plan.append(
                    {
                        "date": current_day.isoformat(),
                        "subject": subject,
                        "task": "Focused study block + short self-test.",
                        "hours": hours_per_day,
                    }
                )
        return ToolResult(True, json.dumps(plan, ensure_ascii=False))
    except Exception as exc:
        return ToolResult(False, f"study_plan error: {exc}")


def web_search(query: str) -> ToolResult:
    return ToolResult(
        True,
        (
            f"Web search requested with query: {query}"
        ),
    )


def tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "name": "calculator",
            "description": "Safely evaluate arithmetic expressions.",
            "input_schema": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
        {
            "name": "add_event",
            "description": "Add a class, exam, assignment, or other calendar event.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "event_type": {"type": "string"},
                    "start_iso": {"type": "string", "description": "ISO datetime"},
                    "end_iso": {"type": "string", "description": "ISO datetime"},
                    "repeat_weekly": {"type": "boolean"},
                    "description": {"type": "string"},
                },
                "required": ["title", "event_type", "start_iso"],
            },
        },
        {
            "name": "get_upcoming",
            "description": "Get upcoming events in the next N days.",
            "input_schema": {
                "type": "object",
                "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 30}},
            },
        },
        {
            "name": "add_tasks",
            "description": "Add preparation tasks tied to an event.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "event_title": {"type": "string"},
                    "tasks": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["event_title", "tasks"],
            },
        },
        {
            "name": "draft_email",
            "description": "Create an email draft and mailto link. Never send automatically.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["recipient", "subject", "body"],
            },
        },
        {
            "name": "study_plan",
            "description": "Generate a day-by-day study plan until exam date with a revision day.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string"},
                    "exam_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "hours_per_day": {"type": "number", "minimum": 0.5, "maximum": 12},
                },
                "required": ["subject", "exam_date"],
            },
        },
        {
            "name": "web_search",
            "description": "Search the web for current information.",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    ]


def execute_tool(name: str, payload: dict[str, Any]) -> ToolResult:
    try:
        if name == "calculator":
            return calculator(payload["expression"])
        if name == "add_event":
            return add_event(
                title=payload["title"],
                event_type=payload["event_type"],
                start_iso=payload["start_iso"],
                end_iso=payload.get("end_iso"),
                repeat_weekly=payload.get("repeat_weekly", False),
                description=payload.get("description", ""),
            )
        if name == "get_upcoming":
            return get_upcoming(int(payload.get("days", 7)))
        if name == "add_tasks":
            return add_tasks(event_title=payload["event_title"], tasks=payload["tasks"])
        if name == "draft_email":
            return draft_email(
                recipient=payload["recipient"],
                subject=payload["subject"],
                body=payload["body"],
            )
        if name == "study_plan":
            return study_plan(
                subject=payload["subject"],
                exam_date=payload["exam_date"],
                hours_per_day=float(payload.get("hours_per_day", 2.0)),
            )
        if name == "web_search":
            return web_search(payload["query"])
        return ToolResult(False, f"Unknown tool: {name}")
    except Exception as exc:
        return ToolResult(False, f"Tool execution error ({name}): {exc}")


def build_system_prompt(language: str) -> str:
    today = date.today().isoformat()
    return f"""
You are StudyBuddy+, a personal AI assistant for university students in Uzbekistan.
Today's date is {today}.
Primary response language is {language} unless user asks otherwise.

Rules:
1) Never guess dates or calculations; use tools.
2) Ask at most one short clarifying question if essential details are missing.
3) Always draft emails only; never claim an email was sent.
4) Be concise, clear, and encouraging.
5) For preparation requests, inspect upcoming events (next 7 days), generate concrete tasks, and prioritize by urgency.
""".strip()


def run_agent(user_input: str, api_key: str, model_name: str, language: str) -> tuple[str, list[dict[str, Any]]]:
    # LiteLLM yordamida universal kalit va modelni o'rnatish
    import os
    if "claude" in model_name.lower():
        os.environ["ANTHROPIC_API_KEY"] = api_key
    elif "gpt" in model_name.lower() or "o1" in model_name.lower() or "o3" in model_name.lower():
        os.environ["OPENAI_API_KEY"] = api_key
    elif "gemini" in model_name.lower():
        os.environ["GEMINI_API_KEY"] = api_key
    else:
        # Standart holatda universal tarzda uzatamiz
        os.environ["GEMINI_API_KEY"] = api_key
        os.environ["OPENAI_API_KEY"] = api_key
        os.environ["ANTHROPIC_API_KEY"] = api_key

    messages = [
        {"role": msg.get("role", "assistant"), "content": msg.get("content", "")}
        for msg in st.session_state.chat_messages
    ]
    messages.append({"role": "user", "content": user_input})
    action_log: list[dict[str, Any]] = []

    formatted_tools = [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"]
            }
        }
        for t in tool_schemas() if t.get("name")
    ]

    for iteration in range(10):
        response = litellm.completion(
            model=model_name,
            max_tokens=1200,
            messages=[{"role": "system", "content": build_system_prompt(language)}] + messages,
            tools=formatted_tools,
        )

        assistant_message = response.choices[0].message
        assistant_content = assistant_message.content or ""
        tool_calls = getattr(assistant_message, "tool_calls", None)

        messages.append({"role": "assistant", "content": assistant_content, "tool_calls": tool_calls})

        if tool_calls:
            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_input = json.loads(tool_call.function.arguments)
                except Exception:
                    tool_input = {}
                
                result = execute_tool(tool_name, tool_input)
                action_log.append(
                    {
                        "iteration": iteration + 1,
                        "type": "tool_use",
                        "tool": tool_name,
                        "input": tool_input,
                        "ok": result.ok,
                        "output": result.content,
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result.content,
                    }
                )
            continue

        return assistant_content or "No response generated.", action_log

    fallback = "Reached iteration limit. Please rephrase or try a smaller request."
    return fallback, action_log


def import_ics(uploaded_file: BytesIO) -> tuple[int, int]:
    ok_count = 0
    skipped = 0
    cal = Calendar.from_ical(uploaded_file.read())
    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        try:
            title = str(component.get("summary", "Untitled"))
            dt_start = component.decoded("dtstart")
            dt_end = component.decoded("dtend", None)
            if isinstance(dt_start, date) and not isinstance(dt_start, datetime):
                dt_start = datetime.combine(dt_start, time(hour=9, minute=0))
            if isinstance(dt_end, date) and not isinstance(dt_end, datetime):
                dt_end = datetime.combine(dt_end, time(hour=10, minute=0))
            if dt_end is None:
                dt_end = dt_start + timedelta(hours=1)

            repeat_weekly = False
            rrule = component.get("rrule")
            if rrule and "FREQ" in rrule and "WEEKLY" in [str(v) for v in rrule["FREQ"]]:
                repeat_weekly = True

            st.session_state.events.append(
                {
                    "id": str(uuid.uuid4()),
                    "title": title,
                    "event_type": "class",
                    "start": dt_start.isoformat(),
                    "end": dt_end.isoformat(),
                    "repeat_weekly": repeat_weekly,
                    "description": str(component.get("description", "")),
                }
            )
            ok_count += 1
        except Exception:
            skipped += 1

    return ok_count, skipped


def export_ics(events: list[dict[str, Any]]) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//StudyBuddy+//study planner//")
    cal.add("version", "2.0")

    for item in events:
        ev = Event()
        ev.add("uid", item.get("id", str(uuid.uuid4())))
        ev.add("summary", item.get("title", "Untitled"))
        ev.add("description", item.get("description", ""))
        ev.add("dtstart", parse_datetime(item["start"]))
        ev.add("dtend", parse_datetime(item["end"]))
        if item.get("repeat_weekly"):
            ev.add("rrule", {"freq": "weekly"})
        cal.add_component(ev)

    return cal.to_ical()


def render_dashboard() -> None:
    st.subheader("Dashboard")

    exams = [e for e in st.session_state.events if str(e.get("event_type", "")).lower() == "exam"]
    if exams:
        next_exam = min(exams, key=lambda e: e["start"])
        exam_date = parse_datetime(next_exam["start"]).date()
        countdown = (exam_date - date.today()).days
        st.metric("Next exam countdown", f"{countdown} day(s)", next_exam["title"])
    else:
        st.info("No exams yet.")

    st.markdown("### Upcoming events")
    upcoming_raw = get_upcoming(7)
    upcoming = json.loads(upcoming_raw.content) if upcoming_raw.ok else []
    if not upcoming:
        st.write("No events in next 7 days.")
    for event in upcoming:
        start_at = parse_datetime(event["start"])
        urgency = urgency_for_date(start_at)
        color = {"red": "🔴", "yellow": "🟡", "green": "🟢"}.get(urgency, "🟢")
        st.write(f"{color} **{event['title']}** ({event['event_type']}) — {start_at.strftime('%Y-%m-%d %H:%M')}")

    st.markdown("### Task checklist")
    completed = 0
    for i, task in enumerate(st.session_state.tasks):
        checked = st.checkbox(
            f"{task['event_title']}: {task['task']}",
            value=task.get("done", False),
            key=f"task_{task['id']}_{i}",
        )
        task["done"] = checked
        completed += int(checked)

    total = len(st.session_state.tasks)
    progress = (completed / total) if total else 0.0
    st.progress(progress)
    st.caption(f"Progress: {completed}/{total}")


def main() -> None:
    st.set_page_config(page_title="StudyBuddy+", page_icon="📚", layout="wide")
    init_state()

    st.title("📚 StudyBuddy+")
    st.caption("Personal AI assistant for students — Uzbek / English / Russian")
    st.warning("Emails are never sent automatically.")

    with st.sidebar:
        st.header("Settings")
        api_key = st.text_input("AI API Key", type="password", help="Enter your API key (Anthropic, OpenAI, Gemini, etc.)")
        model_name = st.text_input("Model Name", value="claude-3-5-sonnet-20241022", help="LiteLLM format model name (e.g., gpt-4o, claude-3-5-sonnet-20241022, gemini/gemini-1.5-pro)")
        language = st.selectbox("Interface language", ["Uzbek", "English", "Russian"], index=0)

        st.markdown("### Student profile")
        st.text_input("Student name", value="Your name", key="student_name")
        st.text_input("University / faculty", value="TUIT, Computer Engineering", key="faculty")
        st.text_input("Main subjects", value="Python, Mathematics, Physics", key="subjects")
        st.text_input("Extra feature", value="none", key="extra_feature")

        st.markdown("### Calendar (.ics)")
        uploaded = st.file_uploader("Import .ics", type=["ics"])
        if uploaded is not None and st.button("Import calendar"):
            imported, skipped = import_ics(uploaded)
            st.success(f"Imported {imported} events, skipped {skipped}.")

        ics_data = export_ics(st.session_state.events)
        st.download_button(
            "Export .ics",
            data=ics_data,
            file_name="studybuddy_schedule.ics",
            mime="text/calendar",
            use_container_width=True,
        )

        if st.button("Daily briefing (next 7 days)", use_container_width=True):
            if not api_key:
                st.error("Please provide your API key first.")
            else:
                summary_prompt = "Give me a full daily briefing for the next 7 days based on my schedule and tasks."
                try:
                    with st.spinner("Generating daily briefing..."):
                        answer, actions = run_agent(summary_prompt, api_key, model_name, language)
                    st.session_state.action_logs.append(actions)
                    st.session_state.chat_messages.extend(
                        [
                            {"role": "user", "content": summary_prompt},
                            {"role": "assistant", "content": answer},
                        ]
                    )
                    st.success("Briefing ready in Chat tab.")
                except Exception as e:
                    st.error(f"❌ Xatolik yuz berdi: {e}")

    tab_chat, tab_dashboard = st.tabs(["Chat", "Dashboard"])

    with tab_chat:
        st.subheader("Agent chat")
        for msg in st.session_state.chat_messages:
            role = msg.get("role", "assistant")
            if role == "user":
                st.chat_message("user").write(msg.get("content", ""))
            else:
                content = msg.get("content", "")
                if isinstance(content, str):
                    st.chat_message("assistant").write(content)

        prompt = st.chat_input("Write your request (Uzbek is supported)")
        if prompt:
            if not api_key:
                st.error("Please enter your API key in the sidebar.")
            else:
                st.chat_message("user").write(prompt)
                try:
                    with st.spinner("Thinking..."):
                        answer, actions = run_agent(prompt, api_key, model_name, language)
                    st.chat_message("assistant").write(answer)
                    st.session_state.action_logs.append(actions)
                    st.session_state.chat_messages.extend(
                        [
                            {"role": "user", "content": prompt},
                            {"role": "assistant", "content": answer},
                        ]
                    )
                except Exception as e:
                    st.error(f"❌ Xatolik yuz berdi: {e}")

        with st.expander("Agent actions log", expanded=False):
            if not st.session_state.action_logs:
                st.write("No actions yet.")
            for batch_id, actions in enumerate(st.session_state.action_logs, start=1):
                st.markdown(f"**Run {batch_id}**")
                if not actions:
                    st.write("No tool calls.")
                    continue
                for action in actions:
                    st.json(action)

    with tab_dashboard:
        render_dashboard()
        st.markdown("### Testing checklist (example commands)")
        st.markdown(
            """
1. `Dushanba 09:00 da Python darsi qo'sh (har hafta takrorlansin).`
2. `Matematika imtihonim 2026-11-20. Nima tayyorlashim kerak?`
3. `Menga Professor Karimovga uzr so‘rab email draft yozib ber.`
4. `Fizika imtihoni uchun bugundan boshlab o‘qish rejasini tuz.`
5. `Kelasi 7 kun uchun daily briefing ber.`
            """
        )


if __name__ == "__main__":
    main()
