# Infrastructure Peewee

This directory contains the Peewee ORM implementation for the infrastructure layer.

## Structure
- `session/`: Handles database connection using `peewee` and `playhouse.db_url`.
- `model/`: Defines database models using `peewee.Model`.
- `repository/`: Implements the `TareaRepository` interface using Peewee.

## Configuration
It uses the `DATABASE_URL` environment variable to connect to the database.
- Default: `sqlite:///test.db`
- Example Postgres: `postgresql://user:password@host:port/dbname`
- Example SQLite: `sqlite:///path/to/db.sqlite`

## Notes
- Tables are created automatically on repository initialization if they don't exist.
