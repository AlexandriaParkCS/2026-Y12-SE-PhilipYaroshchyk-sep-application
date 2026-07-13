import os
import logging

from flask import Flask

log = logging.getLogger(__name__)

logging.basicConfig(
    filename="app.log",
    encoding="utf-8",
    level=logging.DEBUG,
    format=" %(asctime)s %(message)s",
)


def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=os.path.join(app.instance_path, 'database.db'),
        UPLOAD_FOLDER=os.path.join(app.static_folder, 'uploads'),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024
    )

    app.logger.info("Creating CatsAndDogs app")

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # initialise the database
    from . import db
    db.init_app(app)

    # register the blueprints
    from . import auth
    app.register_blueprint(auth.bp)
    
    from . import home
    app.register_blueprint(home.bp)

    from . import search
    app.register_blueprint(search.bp)

    # ensure the instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    # ensure the upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # a simple page that can be used to test that the application is working
    @app.route('/ping')
    def ping():
        return 'ok'

    return app