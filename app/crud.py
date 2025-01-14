"""
Module for handling mission-related database operations.

This module includes functions to create, retrieve, and search for missions
in the database using SQLAlchemy ORM. It provides basic CRUD operations
for interacting with mission data.

Functions:
    - create_mission: Creates a new mission in the database.
    - get_missions: Retrieves a list of missions with pagination support.
    - get_mission_by_name: Retrieves a mission by its name.
"""

from sqlalchemy.orm import Session
from . import models, schemas


# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
def get_filtered_missions(
    db, page, size, start_date, end_date, keyword, sort_by=None, sort_order="asc"
):
    """
    Retrieves a filtered list of missions from the database.

    Args:
        db: The database session.
        page (int): The page number for pagination.
        size (int): The number of missions to return per page.
        start_date (datetime): The earliest launch date to filter missions.
        end_date (datetime): The latest launch date to filter missions.
        keyword (str): A keyword to filter mission names.
        sort_by (str, optional): The column name to sort by.
        sort_order (str, optional): The order of sorting ('asc' or 'desc'). Defaults to 'asc'.

    Returns:
        List[models.Mission]: A list of missions matching the specified filters and pagination.
    """
    query = db.query(models.Mission)
    if start_date:
        query = query.filter(models.Mission.launch_date >= start_date)
    if end_date:
        query = query.filter(models.Mission.launch_date <= end_date)
    if keyword:
        query = query.filter(models.Mission.name.contains(keyword))
    if sort_by:
        sort_column = getattr(models.Mission, sort_by, None)
        if sort_column:
            query = query.order_by(
                sort_column.asc() if sort_order == "asc" else sort_column.desc()
            )
    return query.offset((page - 1) * size).limit(size).all()


def create_or_update_mission(db: Session, mission_data: dict):
    """
    Creates a new mission or updates an existing one in the database.

    Args:
        db (Session): The database session to use for the operation.
        mission_data (dict): A dictionary containing mission data.

    Returns:
        models.Mission: The created or updated mission object.
    """
    existing_mission = (
        db.query(models.Mission)
        .filter(models.Mission.name == mission_data["name"])
        .first()
    )
    if existing_mission:
        # Update existing mission
        for key, value in mission_data.items():
            setattr(existing_mission, key, value)
        db.commit()
        db.refresh(existing_mission)
        return existing_mission

    # Create new mission
    return create_mission(db, schemas.MissionCreate(**mission_data))


def create_mission(db: Session, mission: schemas.MissionCreate):
    """
    Creates a new mission and adds it to the database.

    Args:
        db (Session): The database session.
        mission (schemas.MissionCreate): The mission data to be created.

    Returns:
        models.Mission: The created mission object.
    """
    db_mission = models.Mission(**mission.dict())
    db.add(db_mission)
    db.commit()
    db.refresh(db_mission)
    return db_mission


def get_missions(db: Session, skip: int = 0, limit: int = 10):
    """
    Retrieves a list of missions from the database with pagination.

    Args:
        db (Session): The database session.
        skip (int, optional): The number of records to skip. Defaults to 0.
        limit (int, optional): The maximum number of records to return. Defaults to 10.

    Returns:
        list: A list of mission objects.
    """
    return db.query(models.Mission).offset(skip).limit(limit).all()


def get_mission_by_name(db: Session, name: str):
    """
    Retrieves a mission from the database by its name.

    Args:
        db (Session): The database session.
        name (str): The name of the mission.

    Returns:
        models.Mission or None: The mission object if found, otherwise None.
    """
    return db.query(models.Mission).filter(models.Mission.name == name).first()
