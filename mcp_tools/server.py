from __future__ import annotations

from datetime import datetime, time

from mcp.server.fastmcp import FastMCP

from household.db import (
    add_chore as _add_chore,
    create_element as _create_element,
    create_person as _create_person,
    delete_chore as _delete_chore,
    delete_element as _delete_element,
    delete_person as _delete_person,
    get_chore,
    get_household_by_name,
    get_pending_chores,
    get_session,
    init_db,
    list_actions,
    list_chores,
    list_elements,
    list_households,
    list_people,
    mark_chore_done,
)

mcp = FastMCP("llmilo-tools")

init_db()


def _serialize_household_state(household_name: str | None = None, household_id: int | None = None) -> str:
    with get_session() as session:
        if household_name:
            household = get_household_by_name(session, household_name)
        elif household_id:
            from household.db import get_household
            household = get_household(session, household_id)
        else:
            households = list_households(session)
            if not households:
                return "No households found."
            household = households[0]

        if household is None:
            return f"Household '{household_name}' not found."

        lines = [f"Household: {household.name}"]

        people = list_people(session, household.id)
        if people:
            lines.append("People:")
            for p in people:
                tg = f" (telegram: {p.telegram_id})" if p.telegram_id else ""
                lines.append(f"  - {p.name}{tg}")

        pending = get_pending_chores(session, household.id)
        lines.append(f"Pending chores ({len(pending)}):")
        for c in pending:
            element_name = c.element.name if c.element else "unknown"
            due = f" due {c.due_time}" if c.due_time else ""
            desc = f" — {c.description}" if c.description else ""
            lines.append(f"  - [{element_name}] {c.name} ({c.frequency}{due}){desc}")

        elements = list_elements(session, household.id)
        all_chores = []
        for e in elements:
            all_chores.extend(list_chores(session, e.id))
        done_chores = [c for c in all_chores if c.is_done]
        lines.append(f"Done chores ({len(done_chores)}):")
        for c in done_chores:
            element_name = c.element.name if c.element else "unknown"
            last = c.last_action
            by = f" by {last.done_by}" if last else ""
            lines.append(f"  - [{element_name}] {c.name}{by}")

        return "\n".join(lines)


@mcp.tool(description="Get the current state of a household: people, pending chores, and done chores. If no household name is given, returns the first household.")
def get_household_state(household_name: str | None = None) -> str:
    return _serialize_household_state(household_name=household_name)


@mcp.tool(description="Record that a chore was completed by someone. Provide the chore name, who did it, and optionally which household and element it belongs to.")
def write_action(chore_name: str, done_by: str, household_name: str | None = None, element_name: str | None = None) -> str:
    with get_session() as session:
        if household_name:
            household = get_household_by_name(session, household_name)
        else:
            households = list_households(session)
            household = households[0] if households else None

        if household is None:
            return f"Household '{household_name}' not found."

        elements = list_elements(session, household.id)
        matching_chores = []
        for e in elements:
            if element_name and e.name != element_name:
                continue
            for c in list_chores(session, e.id):
                if c.name == chore_name:
                    matching_chores.append(c)

        if not matching_chores:
            return f"Chore '{chore_name}' not found in household '{household.name}'."
        if len(matching_chores) > 1:
            options = ", ".join(f"{c.element.name}/{c.name}" for c in matching_chores)
            return f"Multiple chores named '{chore_name}' found. Specify element_name. Options: {options}"

        chore = matching_chores[0]
        action = mark_chore_done(session, chore.id, done_by)
        session.commit()

        return f"Recorded: '{chore.name}' done by {done_by} at {action.done_at.strftime('%Y-%m-%d %H:%M')}"


@mcp.tool(description="Get the action history for a household. Can filter by person name, chore name, or date range (ISO format: YYYY-MM-DD).")
def get_history(
    household_name: str | None = None,
    done_by: str | None = None,
    chore_name: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> str:
    with get_session() as session:
        if household_name:
            household = get_household_by_name(session, household_name)
        else:
            households = list_households(session)
            household = households[0] if households else None

        if household is None:
            return f"Household '{household_name}' not found."

        elements = list_elements(session, household.id)
        all_chore_ids = []
        chore_lookup = {}
        for e in elements:
            for c in list_chores(session, e.id):
                all_chore_ids.append(c.id)
                chore_lookup[c.id] = c

        if not all_chore_ids:
            return "No chores found."

        from household.db import ActionModel
        query = session.query(ActionModel).filter(ActionModel.chore_id.in_(all_chore_ids))

        if done_by:
            query = query.filter(ActionModel.done_by == done_by)

        if chore_name:
            matching_ids = [cid for cid, c in chore_lookup.items() if c.name == chore_name]
            if not matching_ids:
                return f"No chores named '{chore_name}' found."
            query = query.filter(ActionModel.chore_id.in_(matching_ids))

        if from_date:
            try:
                from_dt = datetime.fromisoformat(from_date)
            except ValueError:
                return f"Invalid from_date format. Use YYYY-MM-DD."
            query = query.filter(ActionModel.done_at >= from_dt)

        if to_date:
            try:
                to_dt = datetime.fromisoformat(to_date)
            except ValueError:
                return f"Invalid to_date format. Use YYYY-MM-DD."
            query = query.filter(ActionModel.done_at <= to_dt)

        actions = query.order_by(ActionModel.done_at.desc()).all()

        if not actions:
            return "No actions found matching the filters."

        lines = [f"History ({len(actions)} actions):"]
        for a in actions:
            chore = chore_lookup.get(a.chore_id)
            chore_label = f"{chore.element.name}/{chore.name}" if chore else f"chore#{a.chore_id}"
            lines.append(f"  {a.done_at.strftime('%Y-%m-%d %H:%M')} | {chore_label} | by {a.done_by}")

        return "\n".join(lines)


@mcp.tool(description="Add a new element (room/area) to a household. Returns the created element.")
def add_element(name: str, household_name: str | None = None) -> str:
    with get_session() as session:
        if household_name:
            household = get_household_by_name(session, household_name)
        else:
            households = list_households(session)
            household = households[0] if households else None

        if household is None:
            return f"Household '{household_name}' not found."

        existing = [e for e in list_elements(session, household.id) if e.name == name]
        if existing:
            return f"Element '{name}' already exists in household '{household.name}'."

        element = _create_element(session, name, household.id)
        session.commit()
        return f"Added element '{element.name}' to household '{household.name}'."


@mcp.tool(description="Add a new chore to an element. frequency must be one of: daily, weekly, biweekly, monthly, yearly. due_time is optional (format HH:MM).")
def add_chore(
    name: str,
    frequency: str,
    element_name: str,
    household_name: str | None = None,
    description: str | None = None,
    due_time: str | None = None,
) -> str:
    with get_session() as session:
        if household_name:
            household = get_household_by_name(session, household_name)
        else:
            households = list_households(session)
            household = households[0] if households else None

        if household is None:
            return f"Household '{household_name}' not found."

        elements = list_elements(session, household.id)
        target = [e for e in elements if e.name == element_name]
        if not target:
            return f"Element '{element_name}' not found in household '{household.name}'."
        element = target[0]

        existing = [c for c in list_chores(session, element.id) if c.name == name]
        if existing:
            return f"Chore '{name}' already exists in element '{element_name}'."

        valid_frequencies = {"daily", "weekly", "biweekly", "monthly", "yearly"}
        if frequency not in valid_frequencies:
            return f"Invalid frequency '{frequency}'. Must be one of: {', '.join(sorted(valid_frequencies))}."

        parsed_time = None
        if due_time:
            try:
                parts = due_time.split(":")
                parsed_time = time(hour=int(parts[0]), minute=int(parts[1]))
            except (ValueError, IndexError):
                return f"Invalid due_time '{due_time}'. Use HH:MM format."

        chore = _add_chore(
            session,
            name=name,
            frequency=frequency,
            element_id=element.id,
            description=description,
            due_time=parsed_time,
        )
        session.commit()
        due_str = f" due {due_time}" if due_time else ""
        desc_str = f" — {description}" if description else ""
        return f"Added chore '{chore.name}' ({frequency}{due_str}){desc_str} to element '{element_name}'."


@mcp.tool(description="Add a new person to a household. telegram_id is optional.")
def add_person(name: str, household_name: str | None = None, telegram_id: str | None = None) -> str:
    with get_session() as session:
        if household_name:
            household = get_household_by_name(session, household_name)
        else:
            households = list_households(session)
            household = households[0] if households else None

        if household is None:
            return f"Household '{household_name}' not found."

        existing = [p for p in list_people(session, household.id) if p.name == name]
        if existing:
            return f"Person '{name}' already exists in household '{household.name}'."

        person = _create_person(session, name=name, household_id=household.id, telegram_id=telegram_id)
        session.commit()
        tg = f" (telegram: {telegram_id})" if telegram_id else ""
        return f"Added person '{person.name}'{tg} to household '{household.name}'."


@mcp.tool(description="Remove an element (and all its chores) from a household.")
def remove_element(name: str, household_name: str | None = None) -> str:
    with get_session() as session:
        if household_name:
            household = get_household_by_name(session, household_name)
        else:
            households = list_households(session)
            household = households[0] if households else None

        if household is None:
            return f"Household '{household_name}' not found."

        target = [e for e in list_elements(session, household.id) if e.name == name]
        if not target:
            return f"Element '{name}' not found in household '{household.name}'."

        _delete_element(session, target[0].id)
        session.commit()
        return f"Removed element '{name}' (and its chores) from household '{household.name}'."


@mcp.tool(description="Remove a chore from an element.")
def remove_chore(name: str, element_name: str, household_name: str | None = None) -> str:
    with get_session() as session:
        if household_name:
            household = get_household_by_name(session, household_name)
        else:
            households = list_households(session)
            household = households[0] if households else None

        if household is None:
            return f"Household '{household_name}' not found."

        elements = list_elements(session, household.id)
        target_elem = [e for e in elements if e.name == element_name]
        if not target_elem:
            return f"Element '{element_name}' not found in household '{household.name}'."

        target_chore = [c for c in list_chores(session, target_elem[0].id) if c.name == name]
        if not target_chore:
            return f"Chore '{name}' not found in element '{element_name}'."

        _delete_chore(session, target_chore[0].id)
        session.commit()
        return f"Removed chore '{name}' from element '{element_name}'."


@mcp.tool(description="Remove a person from a household.")
def remove_person(name: str, household_name: str | None = None) -> str:
    with get_session() as session:
        if household_name:
            household = get_household_by_name(session, household_name)
        else:
            households = list_households(session)
            household = households[0] if households else None

        if household is None:
            return f"Household '{household_name}' not found."

        target = [p for p in list_people(session, household.id) if p.name == name]
        if not target:
            return f"Person '{name}' not found in household '{household.name}'."

        _delete_person(session, target[0].id)
        session.commit()
        return f"Removed person '{name}' from household '{household.name}'."


@mcp.tool(description="Search the web for information about a topic")
async def web_search(query: str) -> str:
    return f"[web_search placeholder] Results for: {query}"


@mcp.tool(description="Get the current date and time")
async def get_current_time() -> str:
    from datetime import timezone
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    mcp.run()
