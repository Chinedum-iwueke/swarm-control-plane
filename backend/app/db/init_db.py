from app.db.session import Base, engine
from app.models import Agent, Task, TaskEvent  # noqa: F401


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print("Database tables initialized successfully.")


if __name__ == "__main__":
    main()
