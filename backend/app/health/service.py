from sqlalchemy import text
from sqlalchemy.orm import Session


def check_database_connection(db: Session) -> dict[str, str]:
    result = db.execute(
        text(
            """
            SELECT
                current_database() AS database_name,
                current_user AS username
            """
        )
    )

    row = result.one()

    return {
        "status": "connected",
        "database": row.database_name,
        "username": row.username,
    }
