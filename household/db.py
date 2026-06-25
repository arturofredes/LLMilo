from __future__ import annotations

import os
from datetime import datetime, time, timedelta
from pathlib import Path

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Time, create_engine
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

Base = declarative_base()

DB_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DB_DIR / "llmilo.sqlite"

FREQUENCY_MAP = {
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
    "biweekly": timedelta(weeks=2),
    "monthly": timedelta(days=30),
    "yearly": timedelta(days=365),
}


class HouseholdModel(Base):
    __tablename__ = "households"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    elements = relationship("ElementModel", back_populates="household", cascade="all, delete-orphan")
    people = relationship("PersonModel", back_populates="household", cascade="all, delete-orphan")


class ElementModel(Base):
    __tablename__ = "elements"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    household_id = Column(Integer, ForeignKey("households.id"), nullable=False)

    household = relationship("HouseholdModel", back_populates="elements")
    chores = relationship("ChoreModel", back_populates="element", cascade="all, delete-orphan")


class PersonModel(Base):
    __tablename__ = "people"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    telegram_id = Column(String, nullable=True, unique=True)
    household_id = Column(Integer, ForeignKey("households.id"), nullable=False)

    household = relationship("HouseholdModel", back_populates="people")


class ChoreModel(Base):
    __tablename__ = "chores"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    frequency = Column(String, nullable=False)
    description = Column(String, nullable=True)
    due_time = Column(Time, nullable=True)
    element_id = Column(Integer, ForeignKey("elements.id"), nullable=False)

    element = relationship("ElementModel", back_populates="chores")
    actions = relationship("ActionModel", back_populates="chore", cascade="all, delete-orphan")

    @property
    def is_done(self) -> bool:
        last_action = self.last_action
        if last_action is None:
            return False
        delta = FREQUENCY_MAP.get(self.frequency)
        if delta is None:
            return False
        now = datetime.now()
        if self.frequency == "daily" and self.due_time is not None:
            due_today = datetime.combine(now.date(), self.due_time)
            if now < due_today:
                due_today -= timedelta(days=1)
            return last_action.done_at >= due_today
        return now < last_action.done_at + delta

    @property
    def last_action(self) -> ActionModel | None:
        if not self.actions:
            return None
        return max(self.actions, key=lambda a: a.done_at)


class ActionModel(Base):
    __tablename__ = "actions"

    id = Column(Integer, primary_key=True)
    chore_id = Column(Integer, ForeignKey("chores.id"), nullable=False)
    done_by = Column(String, nullable=False)
    done_at = Column(DateTime, nullable=False, default=datetime.now)

    chore = relationship("ChoreModel", back_populates="actions")


_SessionFactory: sessionmaker | None = None


def _get_session_factory() -> sessionmaker:
    global _SessionFactory
    if _SessionFactory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _SessionFactory


def get_session() -> Session:
    return _get_session_factory()()


def init_db(db_path: Path | str | None = None) -> sessionmaker:
    global _SessionFactory

    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)

    _SessionFactory = sessionmaker(bind=engine)
    return _SessionFactory


def create_household(session: Session, name: str) -> HouseholdModel:
    household = HouseholdModel(name=name)
    session.add(household)
    session.flush()
    return household


def list_households(session: Session) -> list[HouseholdModel]:
    return session.query(HouseholdModel).all()


def get_household(session: Session, household_id: int) -> HouseholdModel | None:
    return session.query(HouseholdModel).filter(HouseholdModel.id == household_id).first()


def get_household_by_name(session: Session, name: str) -> HouseholdModel | None:
    return session.query(HouseholdModel).filter(HouseholdModel.name == name).first()


def create_element(session: Session, name: str, household_id: int) -> ElementModel:
    element = ElementModel(name=name, household_id=household_id)
    session.add(element)
    session.flush()
    return element


def list_elements(session: Session, household_id: int) -> list[ElementModel]:
    return session.query(ElementModel).filter(ElementModel.household_id == household_id).all()


def get_element(session: Session, element_id: int) -> ElementModel | None:
    return session.query(ElementModel).filter(ElementModel.id == element_id).first()


def add_chore(
    session: Session,
    name: str,
    frequency: str,
    element_id: int,
    description: str | None = None,
    due_time: time | None = None,
) -> ChoreModel:
    chore = ChoreModel(
        name=name,
        frequency=frequency,
        element_id=element_id,
        description=description,
        due_time=due_time,
    )
    session.add(chore)
    session.flush()
    return chore


def list_chores(session: Session, element_id: int) -> list[ChoreModel]:
    return session.query(ChoreModel).filter(ChoreModel.element_id == element_id).all()


def get_chore(session: Session, chore_id: int) -> ChoreModel | None:
    return session.query(ChoreModel).filter(ChoreModel.id == chore_id).first()


def mark_chore_done(session: Session, chore_id: int, done_by: str) -> ActionModel | None:
    chore = get_chore(session, chore_id)
    if chore is None:
        return None
    action = ActionModel(chore_id=chore_id, done_by=done_by, done_at=datetime.now())
    session.add(action)
    session.flush()
    return action


def get_pending_chores(session: Session, household_id: int) -> list[ChoreModel]:
    elements = list_elements(session, household_id)
    element_ids = [e.id for e in elements]
    chores = session.query(ChoreModel).filter(ChoreModel.element_id.in_(element_ids)).all()
    return [c for c in chores if not c.is_done]


def list_actions(session: Session, chore_id: int) -> list[ActionModel]:
    return session.query(ActionModel).filter(ActionModel.chore_id == chore_id).order_by(ActionModel.done_at.desc()).all()


def get_chore_history(session: Session, household_id: int) -> list[ActionModel]:
    elements = list_elements(session, household_id)
    element_ids = [e.id for e in elements]
    from sqlalchemy import select
    chore_ids = [c.id for e in element_ids for c in list_chores(session, e)]
    return session.query(ActionModel).filter(ActionModel.chore_id.in_(chore_ids)).order_by(ActionModel.done_at.desc()).all()


def create_person(session: Session, name: str, household_id: int, telegram_id: str | None = None) -> PersonModel:
    person = PersonModel(name=name, household_id=household_id, telegram_id=telegram_id)
    session.add(person)
    session.flush()
    return person


def list_people(session: Session, household_id: int) -> list[PersonModel]:
    return session.query(PersonModel).filter(PersonModel.household_id == household_id).all()


def get_person_by_name(session: Session, name: str, household_id: int) -> PersonModel | None:
    return session.query(PersonModel).filter(PersonModel.name == name, PersonModel.household_id == household_id).first()


def get_person_by_telegram_id(session: Session, telegram_id: str) -> PersonModel | None:
    return session.query(PersonModel).filter(PersonModel.telegram_id == telegram_id).first()


def delete_element(session: Session, element_id: int) -> bool:
    element = get_element(session, element_id)
    if element is None:
        return False
    session.delete(element)
    session.flush()
    return True


def delete_chore(session: Session, chore_id: int) -> bool:
    chore = get_chore(session, chore_id)
    if chore is None:
        return False
    session.delete(chore)
    session.flush()
    return True


def delete_person(session: Session, person_id: int) -> bool:
    person = session.query(PersonModel).filter(PersonModel.id == person_id).first()
    if person is None:
        return False
    session.delete(person)
    session.flush()
    return True
