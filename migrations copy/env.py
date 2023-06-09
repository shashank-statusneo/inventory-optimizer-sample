import logging
from logging.config import fileConfig

from sqlalchemy import MetaData
from flask import current_app

from alembic import context

USE_TWOPHASE = False

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")


# def include_name(name, type, _parent_names):
#     logger.info("==================")
#     logger.info(f"{type=}")
#     logger.info(f"{name=}")
#     logger.info(f"{_parent_names=}")


# def include_object_func(object, name, type_, reflected, compared_to):
#     logger.info(f"{object=}")
#     logger.info(f"{type_=}")
#     logger.info(f"{name=}")
#     logger.info(f"{reflected=}")
#     logger.info(f"{compared_to=}")

#     if type_ == "table":
#         if name == "users":
#             logger.info("true")
#             return True
#         else:
#             logger.info("false")
#             return False
#     return True


def get_engine(bind_key=None):
    try:
        # this works with Flask-SQLAlchemy<3 and Alchemical
        return current_app.extensions["migrate"].db.get_engine(bind=bind_key)
    except TypeError:
        # this works with Flask-SQLAlchemy>=3
        return current_app.extensions["migrate"].db.engines.get(bind_key)


def get_engine_url(bind_key=None):
    try:
        return (
            get_engine(bind_key)
            .url.render_as_string(hide_password=False)
            .replace("%", "%%")
        )
    except AttributeError:
        return str(get_engine(bind_key).url).replace("%", "%%")


# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
config.set_main_option("sqlalchemy.url", get_engine_url())
bind_names = []
if current_app.config.get("SQLALCHEMY_BINDS") is not None:
    bind_names = list(current_app.config["SQLALCHEMY_BINDS"].keys())
else:
    get_bind_names = getattr(
        current_app.extensions["migrate"].db, "bind_names", None
    )
    if get_bind_names:
        bind_names = get_bind_names()
for bind in bind_names:
    context.config.set_section_option(
        bind, "sqlalchemy.url", get_engine_url(bind_key=bind)
    )
target_db = current_app.extensions["migrate"].db

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_metadata(bind):
    """Return the metadata for a bind."""
    if bind == "":
        bind = None
    if hasattr(target_db, "metadatas"):
        return target_db.metadatas[bind]

    # legacy, less flexible implementation
    m = MetaData()
    for t in target_db.metadata.tables.values():
        if t.info.get("bind_key") == bind:
            t.tometadata(m)
    return m


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # for the --sql use case, run migrations for each URL into
    # individual files.

    engines = {"": {"url": context.config.get_main_option("sqlalchemy.url")}}
    for name in bind_names:
        engines[name] = rec = {}
        rec["url"] = context.config.get_section_option(name, "sqlalchemy.url")

    for name, rec in engines.items():
        logger.info("Migrating database %s" % (name or "<default>"))
        file_ = "%s.sql" % name
        logger.info("Writing output to %s" % file_)
        with open(file_, "w") as buffer:
            context.configure(
                url=rec["url"],
                output_buffer=buffer,
                target_metadata=get_metadata(name),
                literal_binds=True,
            )
            with context.begin_transaction():
                context.run_migrations(engine_name=name)


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # reference: http://alembic.zzzcomputing.com/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, "autogenerate", False):
            script = directives[0]
            if len(script.upgrade_ops_list) >= len(bind_names) + 1:
                empty = True
                for upgrade_ops in script.upgrade_ops_list:
                    if not upgrade_ops.is_empty():
                        empty = False
                if empty:
                    directives[:] = []
                    logger.info("No changes in schema detected.")

    # for the direct-to-DB use case, start a transaction on all
    # engines, then run all migrations, then commit all transactions.

    engines = {"": {"engine": get_engine()}}
    for name in bind_names:
        engines[name] = rec = {}
        rec["engine"] = get_engine(bind_key=name)

    # check for which database migration has to be done
    # x_args: to perform migrations on a single database
    # in case of stamp, migrated db is passed as a tag

    # x_args = context.get_x_argument()

    # if not x_args:
    #     # database stamp operation
    #     tag_args = context.get_tag_argument()
    #     migrate_db = tag_args
    # else:
    #     # database migration operation
    #     migrate_db = x_args[0]
    #     # if len(x_args) > 1:
    #     #     migrate_table = x_args[1]

    # clear all other database connections except migrate_db

    migrate_db = current_app.config("migrating_db")

    engine_conn = engines.get(migrate_db)
    engines.clear()
    engines[migrate_db] = engine_conn

    logger.info(f"{engines=}")

    for name, rec in engines.items():
        engine = rec["engine"]
        rec["connection"] = conn = engine.connect()

        if USE_TWOPHASE:
            rec["transaction"] = conn.begin_twophase()
        else:
            rec["transaction"] = conn.begin()

    try:
        for name, rec in engines.items():
            logger.info("Migrating database %s" % (name or "<default>"))
            context.configure(
                connection=rec["connection"],
                upgrade_token="%s_upgrades" % name,
                downgrade_token="%s_downgrades" % name,
                target_metadata=get_metadata(name),
                process_revision_directives=process_revision_directives,
                **current_app.extensions["migrate"].configure_args,
                # include_object=include_object_func,
            )
            # context.run_migrations(engine_name=name)
            context.run_migrations()

        if USE_TWOPHASE:
            for rec in engines.values():
                rec["transaction"].prepare()

        for rec in engines.values():
            rec["transaction"].commit()
    except:  # noqa: E722
        for rec in engines.values():
            rec["transaction"].rollback()
        raise
    finally:
        for rec in engines.values():
            rec["connection"].close()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
