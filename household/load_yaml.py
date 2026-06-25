from __future__ import annotations

from datetime import time
from pathlib import Path

import yaml

from household.db import (
    add_chore,
    create_element,
    create_household,
    create_person,
    get_household_by_name,
    get_person_by_name,
    get_session,
    init_db,
)

DEFAULT_YAML_PATH = Path(__file__).resolve().parent / "household.yaml"
DEFAULT_PEOPLE_YAML_PATH = Path(__file__).resolve().parent / "people.yaml"


def _parse_due_time(value: str | None) -> time | None:
    if value is None:
        return None
    parts = value.split(":")
    return time(hour=int(parts[0]), minute=int(parts[1]))


def load_household_from_yaml(path: Path | str | None = None) -> None:
    yaml_path = Path(path) if path else DEFAULT_YAML_PATH

    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    if not data or "household" not in data:
        raise ValueError(f"Invalid YAML: missing top-level 'household' key in {yaml_path}")

    init_db()

    with get_session() as session:
        household_data = data["household"]
        household_name = household_data["name"]

        household = get_household_by_name(session, household_name)
        if household is None:
            household = create_household(session, household_name)

        for element_data in household_data.get("elements", []):
            element_name = element_data["name"]
            existing = (
                session.query(type(household).elements.property.mapper.class_)
                .filter_by(household_id=household.id, name=element_name)
                .first()
            )
            if existing is not None:
                element = existing
            else:
                element = create_element(session, element_name, household.id)

            for chore_data in element_data.get("chores", []):
                chore_name = chore_data["name"]
                from household.db import ChoreModel

                existing_chore = (
                    session.query(ChoreModel)
                    .filter_by(element_id=element.id, name=chore_name)
                    .first()
                )
                if existing_chore is not None:
                    continue

                add_chore(
                    session,
                    name=chore_name,
                    frequency=chore_data["frequency"],
                    element_id=element.id,
                    description=chore_data.get("description"),
                    due_time=_parse_due_time(chore_data.get("due_time")),
                )

        session.commit()


def load_people_from_yaml(path: Path | str | None = None) -> None:
    yaml_path = Path(path) if path else DEFAULT_PEOPLE_YAML_PATH

    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    if not data or "household" not in data or "people" not in data:
        raise ValueError(f"Invalid YAML: missing 'household' and/or 'people' keys in {yaml_path}")

    init_db()

    with get_session() as session:
        household_name = data["household"]

        household = get_household_by_name(session, household_name)
        if household is None:
            raise ValueError(f"Household '{household_name}' not found. Load household YAML first.")

        for person_data in data["people"]:
            person_name = person_data["name"]
            telegram_id = person_data.get("telegram_id")

            existing = get_person_by_name(session, person_name, household.id)
            if existing is not None:
                continue

            create_person(session, name=person_name, household_id=household.id, telegram_id=telegram_id)

        session.commit()
