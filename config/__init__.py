import os

import yaml
from yaml.loader import SafeLoader

basedir = os.path.abspath(os.path.dirname(__file__))
ENV = os.getenv("FLASK_ENV") or "dev"

with open(os.path.join(basedir, ENV + ".yaml")) as config_file:
    config = yaml.load(config_file, Loader=SafeLoader)


class Config(object):
    DEBUG = config.get("DEBUG")
    SECRET_KEY = config.get("SECRET_KEY")
    PROPAGATE_EXCEPTIONS = config.get("PROPAGATE_EXCEPTIONS")

    # Database Config
    SQLALCHEMY_TRACK_MODIFICATIONS = config.get(
        "SQLALCHEMY_TRACK_MODIFICATIONS"
    )

    databases = config.get("DATABASE")

    inventory_optimizer_db = databases.get("inventory_optimizer")

    type = inventory_optimizer_db.get("type", "mysql")
    username = inventory_optimizer_db.get("username", "root")
    password = inventory_optimizer_db.get("password", "")
    host = inventory_optimizer_db.get("host", "localhost")
    port = inventory_optimizer_db.get("port", 3306)
    database = inventory_optimizer_db.get("database", "")

    SQLALCHEMY_DATABASE_URI = (
        f"{type}://{username}:{password}@{host}:{port}/{database}"
    )

    binds_database = databases.get("binds")
    if binds_database:
        SQLALCHEMY_BINDS = {}

        for key, value in binds_database.items():
            type = value.get("type", "mysql")
            username = value.get("username", "root")
            password = value.get("password", "")
            host = value.get("host", "localhost")
            port = value.get("port", 3306)
            database = value.get("database", "")
            SQLALCHEMY_BINDS[
                key
            ] = f"{type}://{username}:{password}@{host}:{port}/{database}"


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config_by_name = dict(
    dev=DevelopmentConfig, test=TestingConfig, prod=ProductionConfig
)
