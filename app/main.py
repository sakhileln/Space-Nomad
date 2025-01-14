"""
FastAPI application for managing space missions and retrieving SpaceX launches.

This API allows users to:
- View and create space missions stored in a local database.
- Retrieve data on SpaceX launches from an external API.

Modules included:
- Models, CRUD operations, and database setup for local mission data.
- Integration with SpaceX API to fetch live launch data.

The app initializes the database tables on startup and provides an HTTP interface
for users to interact with the system.
"""

import random

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    BackgroundTasks,
    Request,
)
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi_utils.tasks import repeat_every
from sqlalchemy.orm import Session

from . import crud, schemas, database
from .api import spacex, make_api_request


app = FastAPI()
# Setup templates
templates = Jinja2Templates(directory="app/templates")


# Dependency to get database session
def get_db():
    """
    Dependency function to get a database session.
    This is used to interact with the database in FastAPI route handlers.

    Yields:
        Session: SQLAlchemy session object to interact with the database.
    """
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.on_event("startup")
async def load_initial_data():
    """
    FastAPI startup event handler.
    This function creates all tables in the database upon server startup.
    """
    db = next(get_db())
    try:
        update_spacex_data(db)
    except ConnectionError as ce:
        print(f"Connection error occured loading SpaceX data: {ce}")
    except ValueError as ve:
        print(f"Value Error loading initial SpaceX data: {ve}")


@app.on_event("startup")
@repeat_every(seconds=3600)  # Runs every hour
def periodic_mission_update() -> None:
    """
    Periodically updates SpaceX mission data every hour.

    This function is triggered on the application startup and runs at specified intervals
    to fetch and update mission data from the SpaceX API.
    """
    db = next(get_db())
    update_spacex_data(db)


def update_spacex_data(db: Session):
    """
    Updates SpaceX mission data in the database.

    Args:
        db (Session): The database session to use for updating mission data.

    This function retrieves mission data from the SpaceX API, parses it,
    and creates or updates mission records in the database. Invalid missions
    are skipped and logged.
    """
    spacex_response = spacex.spacex_data
    if not spacex_response:
        print("No response from SpaceX API.")
        return

    spacex_missions = make_api_request.parse_mission_data(spacex_response)
    for mission in spacex_missions:
        if not mission.get("name") or not mission.get("status"):
            print(f"Invalid mission data: {mission}")
            continue  # Skip invalid missions

        crud.create_or_update_mission(db, mission)


@app.get("/")
def read_root():
    """
    Root endpoint for the API.
    Returns a welcome message for the Space Nomad app.

    Returns:
        dict: A dictionary with a welcome message.
    """
    return {"message": "Welcome to Space Nomad!"}


# Fun space facts to display
FUN_FACTS = [
    "The sun is 330,000 times more massive than Earth!",
    "One day on Venus is longer than a year on Venus.",
    "The Milky Way has over 200 billion stars.",
    "Space is completely silent because there's no air.",
    "Jupiter's Great Red Spot is a massive storm that has raged for hundreds of years.",
]


@app.get("/index", response_class=HTMLResponse)
def read_home(request: Request):
    """
    Fetch the home page with fun facts and latest space news
    """
    db = next(get_db())
    # Fetch mission stats
    missions = crud.get_missions(db, limit=100)
    total_missions = len(missions)
    completed_missions = len([m for m in missions if m.status.lower() == "completed"])
    ongoing_missions = len([m for m in missions if m.status.lower() == "ongoing"])

    # Random fact
    fun_fact = random.choice(FUN_FACTS)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "total_missions": total_missions,
            "completed_missions": completed_missions,
            "ongoing_missions": ongoing_missions,
            "fun_fact": fun_fact,
        },
    )


@app.get("/news/", response_class=HTMLResponse)
def fetch_space_news(request: Request):
    """
    Fetch the latest space news with pagination.
    """
    return templates.TemplateResponse("news.html", {"request": request})


@app.post("/update-missions/")
def trigger_spacex_update(
    background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """
    Trigger a manual update for SpaceX missions.
    Runs in the background to avoid blocking the request.
    """
    background_tasks.add_task(update_spacex_data, db)
    return {"message": "SpaceX missions update initiated."}


@app.get("/missions/")
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
def get_missions(
    db: Session = Depends(get_db),
    page: int = 1,
    size: int = 10,
    start_date: str = None,
    end_date: str = None,
    keyword: str = None,
):
    """
    Fetch missions with pagination and optional filtering.
    """
    missions = crud.get_filtered_missions(db, page, size, start_date, end_date, keyword)
    return {"missions": missions, "page": page, "size": size}


@app.post("/missions/")
def create_mission(mission: schemas.MissionCreate, db: Session = Depends(get_db)):
    """
    Create a new space mission in the database.
    Checks if the mission already exists before creating a new one.

    Args:
        mission (schemas.MissionCreate): The mission data to be added.
        db (Session): The database session, provided by dependency injection.

    Raises:
        HTTPException: If the mission already exists in the database.

    Returns:
        dict: The newly created mission object.
    """
    # Check if mission already exists
    existing_mission = crud.get_mission_by_name(db, mission.name)
    if existing_mission:
        raise HTTPException(status_code=400, detail="Mission already exists")

    # New mission
    new_mission = crud.create_mission(db=db, mission=mission)
    return new_mission


@app.get("/spacex-launches/")
def spacex_launches():
    """
    Get a list of SpaceX launches by querying an external API.

    Returns:
        list: A list of SpaceX launches.

    Raises:
        HTTPException: If no SpaceX launches are found.
    """
    launches = spacex.spacex_data
    if launches:
        return launches

    raise HTTPException(status_code=404, detail="SpaceX launches not found!")
