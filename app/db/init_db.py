from app.db.database import Base, engine


def init_db():
    """
    Initialize database tables.

    Currently there are no application models.
    As we add models in later phases, SQLAlchemy will create
    their corresponding tables here.
    """

    Base.metadata.create_all(bind=engine)