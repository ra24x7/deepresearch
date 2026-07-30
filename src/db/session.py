from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from config import PostgresSettings


def get_engine(settings: PostgresSettings) -> Engine:
    return create_engine(settings.dsn)


def get_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine)
