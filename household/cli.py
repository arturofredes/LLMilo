from __future__ import annotations

import sys
from datetime import time

from household.db import (
    add_chore,
    create_element,
    create_person,
    delete_chore,
    delete_element,
    delete_person,
    get_household_by_name,
    get_session,
    init_db,
    list_chores,
    list_elements,
    list_households,
    list_people,
)


def _pick_household(session, quiet: bool = False) -> int:
    households = list_households(session)
    if not households:
        print("No households found. Run load_yaml first.")
        sys.exit(1)
    if len(households) == 1:
        if not quiet:
            print(f"Household: {households[0].name}")
        return households[0].id
    print("Households:")
    for i, h in enumerate(households, 1):
        print(f"  {i}. {h.name}")
    choice = int(input("Select household #: ")) - 1
    return households[choice].id


def _pick_element(session, household_id: int) -> int:
    elements = list_elements(session, household_id)
    if not elements:
        print("No elements found.")
        sys.exit(1)
    if len(elements) == 1:
        print(f"Element: {elements[0].name}")
        return elements[0].id
    print("Elements:")
    for i, e in enumerate(elements, 1):
        print(f"  {i}. {e.name}")
    choice = int(input("Select element #: ")) - 1
    return elements[choice].id


def cmd_add_element(args: list[str]) -> None:
    with get_session() as session:
        hid = _pick_household(session)
        name = args[0] if args else input("Element name: ")
        existing = [e for e in list_elements(session, hid) if e.name == name]
        if existing:
            print(f"Element '{name}' already exists.")
            return
        create_element(session, name, hid)
        session.commit()
        print(f"Added element '{name}'.")


def cmd_add_chore(args: list[str]) -> None:
    valid_freq = {"daily", "weekly", "biweekly", "monthly", "yearly"}
    with get_session() as session:
        hid = _pick_household(session)
        eid = _pick_element(session, hid)
        name = args[0] if args else input("Chore name: ")
        frequency = args[1] if len(args) > 1 else input(f"Frequency ({', '.join(sorted(valid_freq))}): ")
        if frequency not in valid_freq:
            print(f"Invalid frequency '{frequency}'.")
            return
        description = input("Description (optional, press Enter to skip): ") or None
        due_time_str = input("Due time HH:MM (optional, press Enter to skip): ") or None
        parsed_time = None
        if due_time_str:
            parts = due_time_str.split(":")
            parsed_time = time(hour=int(parts[0]), minute=int(parts[1]))
        add_chore(session, name=name, frequency=frequency, element_id=eid, description=description, due_time=parsed_time)
        session.commit()
        print(f"Added chore '{name}' ({frequency}).")


def cmd_add_person(args: list[str]) -> None:
    with get_session() as session:
        hid = _pick_household(session)
        name = args[0] if args else input("Person name: ")
        existing = [p for p in list_people(session, hid) if p.name == name]
        if existing:
            print(f"Person '{name}' already exists.")
            return
        telegram_id = input("Telegram ID (optional, press Enter to skip): ") or None
        create_person(session, name=name, household_id=hid, telegram_id=telegram_id)
        session.commit()
        print(f"Added person '{name}'.")


def cmd_remove_element(args: list[str]) -> None:
    with get_session() as session:
        hid = _pick_household(session)
        elements = list_elements(session, hid)
        if not elements:
            print("No elements to remove.")
            return
        name = args[0] if args else input("Element name to remove: ")
        target = [e for e in elements if e.name == name]
        if not target:
            print(f"Element '{name}' not found.")
            return
        delete_element(session, target[0].id)
        session.commit()
        print(f"Removed element '{name}' and its chores.")


def cmd_remove_chore(args: list[str]) -> None:
    with get_session() as session:
        hid = _pick_household(session)
        eid = _pick_element(session, hid)
        chores = list_chores(session, eid)
        if not chores:
            print("No chores to remove.")
            return
        name = args[0] if args else input("Chore name to remove: ")
        target = [c for c in chores if c.name == name]
        if not target:
            print(f"Chore '{name}' not found.")
            return
        delete_chore(session, target[0].id)
        session.commit()
        print(f"Removed chore '{name}'.")


def cmd_remove_person(args: list[str]) -> None:
    with get_session() as session:
        hid = _pick_household(session)
        people = list_people(session, hid)
        if not people:
            print("No people to remove.")
            return
        name = args[0] if args else input("Person name to remove: ")
        target = [p for p in people if p.name == name]
        if not target:
            print(f"Person '{name}' not found.")
            return
        delete_person(session, target[0].id)
        session.commit()
        print(f"Removed person '{name}'.")


def cmd_list(args: list[str]) -> None:
    with get_session() as session:
        hid = _pick_household(session, quiet=True)
        household = next(h for h in list_households(session) if h.id == hid)

        print(f"\nHousehold: {household.name}")
        people = list_people(session, hid)
        if people:
            print("People:")
            for p in people:
                tg = f" (telegram: {p.telegram_id})" if p.telegram_id else ""
                print(f"  - {p.name}{tg}")

        elements = list_elements(session, hid)
        for e in elements:
            print(f"\n  [{e.name}]")
            chores = list_chores(session, e.id)
            for c in chores:
                due = f" due {c.due_time}" if c.due_time else ""
                desc = f" — {c.description}" if c.description else ""
                status = "done" if c.is_done else "pending"
                print(f"    - {c.name} ({c.frequency}{due}) [{status}]{desc}")


COMMANDS = {
    "add-element": cmd_add_element,
    "add-chore": cmd_add_chore,
    "add-person": cmd_add_person,
    "remove-element": cmd_remove_element,
    "remove-chore": cmd_remove_chore,
    "remove-person": cmd_remove_person,
    "list": cmd_list,
}


def main() -> None:
    init_db()
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Usage: python -m household.cli <command> [args]")
        print("\nCommands:")
        for cmd in sorted(COMMANDS):
            print(f"  {cmd}")
        print("\nExamples:")
        print("  python -m household.cli add-element kitchen")
        print("  python -m household.cli add-chore")
        print("  python -m household.cli add-person Arturo")
        print("  python -m household.cli list")
        return

    command = sys.argv[1]
    if command not in COMMANDS:
        print(f"Unknown command '{command}'. Available: {', '.join(sorted(COMMANDS))}")
        sys.exit(1)

    COMMANDS[command](sys.argv[2:])


if __name__ == "__main__":
    main()
