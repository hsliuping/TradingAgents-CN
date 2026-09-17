"""Run the image's configuration importer against its runtime database."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path('/app/scripts')))
import import_config_and_create_user as importer

database = os.environ['MONGODB_DATABASE']
importer.DB_NAME = database
original_load = importer.load_env_config


def runtime_config(script_dir):
    config = original_load(script_dir)
    config.update(
        mongodb_host=os.environ['MONGODB_HOST'],
        mongodb_port=int(os.environ['MONGODB_PORT']),
        mongodb_username=os.environ['MONGODB_USERNAME'],
        mongodb_password=os.environ['MONGODB_PASSWORD'],
        mongodb_database=database,
    )
    return config


importer.load_env_config = runtime_config
if __name__ == '__main__':
    importer.main()
